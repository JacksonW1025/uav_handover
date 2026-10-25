#!/usr/bin/env python3
"""A4 exact fixed-point covariance/storage audit, independent of constructor.

All PSD enclosures use integer arithmetic and diagonal-dominance rounding.
All scalar radii use rational arithmetic and integer outward square roots.
Does not import theory.py or prepare_proofs.py.
"""
import argparse
from fractions import Fraction as F
import json
from math import factorial,isqrt,lcm
from pathlib import Path
import time
import numpy as np

from bench import load,N
from data import ROOT,sha,write

SCALE=10**24;YSCALE=10**12;H=F(1,250)
SPECIAL=[0,1,2,3,4,47,48]
SHIFT=[0,1,2,0,1,*range(3,45),47,48]

def ff(x):return F.from_float(float(x))
def ceilf(x):return -((-x.numerator)//x.denominator)
def sqrt_up(x):
    assert x>=0
    z=ceilf(x*YSCALE**2);s=isqrt(z)
    if s*s<z:s+=1
    return F(s,YSCALE)


def inverse3(p):
    a=[[ff(p[i,j]) for j in range(3)]+[F(int(i==j)) for j in range(3)] for i in range(3)]
    for i in range(3):
        pivot=a[i][i];assert pivot>0;a[i]=[x/pivot for x in a[i]]
        for j in range(3):
            if j!=i:
                v=a[j][i];a[j]=[x-v*y for x,y in zip(a[j],a[i])]
    inv=[r[3:] for r in a]
    for i in range(3):
        for j in range(3):assert sum(ff(p[i,k])*inv[k][j] for k in range(3))==int(i==j)
    return inv


def coefficients_exact(us,stale,cap_us,resume_us,c):
    T=F(str(c['brake_s']));alpha=F(str(c['alpha']));t=max(F(0),F(us-cap_us,10**6));z=min(t,T)
    cp=[F(1),alpha*(z-z*z/(2*T))];cv=[F(0),alpha*max(F(0),1-t/T)]
    if stale:return cp,cv,F(0)
    if cap_us<0 or not c['resume_s'] or us-resume_us>=F(str(c['resume_s']))*10**6:return [F(0),F(0)],[F(0),F(0)],F(1)
    u=max(F(0),F(us-resume_us,10**6)/F(str(c['resume_s'])));beta=3*u*u-2*u*u*u
    return [(1-beta)*x for x in cp],[(1-beta)*x for x in cv],beta


def rows_A(kp,kv,rho,cp,cv,sigma):
    q={2:rho,45:-(1-rho)*kp,46:-(1-rho)*kv}
    rows=[{} for _ in range(N)]
    rows[0]={0:F(1),1:H};rows[1]={1:F(1)};rows[2]=q.copy()
    for j,z in q.items():
        rows[0][j]=rows[0].get(j,F(0))+H*H/4*(z+int(j==2))
        rows[1][j]=rows[1].get(j,F(0))+H/2*(z+int(j==2))
    for i,pos,coeff in [(3,0,cp),(4,1,cv)]:
        ss=F(sigma[i-3]);rows[i]={pos:ss,47:-ss*coeff[0],48:-ss*coeff[1]}
    for i in range(5,47):rows[i]={i-2:F(1)}
    rows[47]={47:F(1)};rows[48]={48:F(1)}
    return [{j:v for j,v in row.items() if v} for row in rows]


def exact_map_numerator(rows,S,D):
    nums=[{j:int(v*D) for j,v in row.items()} for row in rows]
    x=S[SHIFT,:]*D
    for i in SPECIAL:
        x[i]=sum((S[j,:]*v for j,v in nums[i].items()),np.zeros(N,dtype=object))
    y=x[:,SHIFT]*D
    for i in SPECIAL:
        y[:,i]=sum((x[:,j]*v for j,v in nums[i].items()),np.zeros(N,dtype=object))
    assert np.array_equal(y,y.T)
    return y


def covariance_step(S,rows_lo,rows_hi,Q):
    D=lcm(*(v.denominator for rows in [rows_lo,rows_hi] for row in rows for v in row.values()))
    lo=exact_map_numerator(rows_lo,S,D);hi=exact_map_numerator(rows_hi,S,D);den=D*D
    result=(lo+den//2)//den+Q
    # Entry rounding <=.5 units; N units of diagonal dominate that symmetric
    # error. Row-sum domination additionally covers the other rho endpoint.
    difference=hi-lo
    pad=[int((sum(abs(x) for x in difference[i,:])+den-1)//den)+N for i in range(N)]
    for i,v in enumerate(pad):result[i,i]+=v
    return result,max(pad)


def variance(C,S):
    active=[(i,v) for i,v in enumerate(C) if v]
    value=sum(x*F(int(S[i,j]),SCALE)*y for i,x in active for j,y in active)
    assert value>=0
    return value


def width(C,G,S,m):
    affine=sum(abs(sum(C[i]*G[i][j] for i in range(N))) for j in range(2))
    return affine+sqrt_up(m*variance(C,S))


def audit(directory):
    started=time.perf_counter();b=load();decl=json.loads((directory/'candidate.json').read_text());manifest=json.loads((directory/'manifest.json').read_text())
    assert sha(directory/'trace.npz')==manifest['trace_sha256'];assert sha(directory/'candidate.json')==manifest['candidate_sha256']
    assert sha(ROOT/'config/p10_a4.json')==manifest['config_sha256']
    case=decl['case'];assert case in b['config']['theory']['repair_candidates']
    eps=F(str(decl['epsilon_P']));assert float(eps) in b['config']['theory']['epsilon_checked_grid']
    tr=dict(np.load(directory/'trace.npz',allow_pickle=False));assert len(tr['center'])==len(b['rows'])
    rlo=sum((-F(1,20))**j/factorial(j) for j in range(20));rhi=sum((-F(1,20))**j/factorial(j) for j in range(21))
    rho=[F((rlo*YSCALE).numerator//(rlo*YSCALE).denominator,YSCALE),F(ceilf(rhi*YSCALE),YSCALE)]
    assert rho[0]<=rlo<rhi<=rho[1]
    # The input metric is exactly the physical principal blocks of the fixed
    # A2-forward/A3-lateral P, NOT a rescaling or a single q residual bound.
    p_raw=[]
    for path in [ROOT/'data/p10-20261024-a2/construction-reviewed/certificate.json',ROOT/'data/p10-20261025-a3/source-08/matrix-candidate.json']:
        p=json.loads(path.read_text())['P_integer'];p_raw.append([[F(p[i][j],10**10) for j in range(3)] for i in range(3)])
    # Exact 3x3 inversion using rational decimal P rather than binary conversion.
    qi=[]
    for p in p_raw:
        aa=[[p[i][j] for j in range(3)]+[F(int(i==j)) for j in range(3)] for i in range(3)]
        for i in range(3):
            pivot=aa[i][i];assert pivot>0;aa[i]=[x/pivot for x in aa[i]]
            for j in range(3):
                if j!=i:
                    z=aa[j][i];aa[j]=[x-z*y for x,y in zip(aa[j],aa[i])]
        inv=[r[3:] for r in aa]
        Q=np.zeros((N,N),dtype=object)
        if eps:
            for i in range(3):
                for j in range(3):Q[i,j]=round(eps*eps*inv[i][j]*SCALE)
            for i in range(3):Q[i,i]+=3
            for i in range(3):
                margin=F(int(Q[i,i]),SCALE)-eps*eps*inv[i][i]
                assert margin>=sum(abs(F(int(Q[i,j]),SCALE)-eps*eps*inv[i][j]) for j in range(3) if j!=i)
        for i in range(N):Q[i,i]+=10**8 # (1e-8)^2 numerical-vector budget
        qi.append(Q)
    S=[np.eye(N,dtype=object)*2000000 for _ in range(2)];m=[1,1]
    cap_us=-5000000;resume_us=-10000000;old_stale=True;max_q2=F(0);max_lag=F(-1000);min_lag=F(1000)
    count_cross=0;count_sat=0;max_num=F(0);max_pad=0;failure=None;events=[];first_capture_constraint=None
    Cunits=[]
    for j in range(3):x=[F(0)]*N;x[j]=F(1);Cunits.append(x)
    for k,row in enumerate(b['rows']):
        us=row['profile_us'];stale=bool(row['oracle'][0]);cap=bool(row['oracle'][1]);resume=old_stale and not stale and cap_us>=0
        center=[[ff(x) for x in tr['center'][k,ax]] for ax in range(2)]
        G=[[[ff(x) for x in rr] for rr in tr['generators'][k,ax]] for ax in range(2)]
        if k==0:
            bound=7*(max(abs(ff(b['center'][ax,i])-center[ax][i]) for ax in range(2) for i in range(N))+
                sum(max(abs(ff(b['G'][ax,i,j])-G[ax][i][j]) for ax in range(2) for i in range(N)) for j in range(2)))
            assert bound<F(1,10**9)
        if cap:
            cap_us=us;events.append([us,'CAPTURE'])
            for ax in range(2):
                assert G[ax][47:49]==G[ax][0:2]
                assert abs(center[ax][47]-center[ax][0])<=F(1,10**6)
                assert abs(center[ax][48]-center[ax][1])<=F(1,4*10**6)
                ix=list(range(N));ix[47:49]=[0,1];S[ax]=S[ax][np.ix_(ix,ix)].copy()
                S[ax][47,47]+=4*10**12;S[ax][48,48]+=25*10**10;m[ax]+=2
        if resume:resume_us=us;events.append([us,'RESUME'])
        cp,cv,beta=coefficients_exact(us,stale,cap_us,resume_us,case)
        qbounds=[];pw=[];vw=[];step=[]
        for ax in range(2):
            pwidth=width(Cunits[0],G[ax],S[ax],m[ax]);vwidth=width(Cunits[1],G[ax],S[ax],m[ax])
            pw.append(pwidth);vw.append(vwidth);qbounds.append(abs(center[ax][2])+width(Cunits[2],G[ax],S[ax],m[ax]))
            scalar=[];sig=[];remainders=[]
            for pos,co,lim,ext in [(0,cp,F(1,2),ff(b['r'][k,ax])),(1,cv,F(1),ff(b['s'][k,ax]))]:
                C=Cunits[pos][:];C[47:49]=[-co[0],-co[1]]
                value=sum(C[i]*center[ax][i] for i in range(N))-beta*ext
                delta=width(C,G[ax],S[ax],m[ax]);sigma=int(abs(value)<lim)
                rem=max(F(0),abs(value)+delta-lim) if sigma else min(2*lim,max(F(0),delta-(abs(value)-lim)))
                scalar.append(value);sig.append(sigma);remainders.append(rem)
            step.append((scalar,sig,remainders))
        # Analytic native cast premises for every allowed set member at resets.
        if cap:
            for axis in range(2):
                import math
                cs=[abs(ff(math.cos(b['yaw']))),abs(ff(math.sin(b['yaw'])))]
                assert sum(cs[(axis+j)%2]*(abs(center[j][0])+pw[j]) for j in range(2))+abs(ff(b['origin'][axis]))<16
                assert sum(cs[(axis+j)%2]*(abs(center[j][1])+vw[j]) for j in range(2))<4
            if first_capture_constraint is None:
                component=[abs(center[ax][1])+vw[ax] for ax in range(2)]
                L=sqrt_up(sum(x*x for x in component));E=F(1,10**6) # >sqrt(2)*5e-7
                alpha=max(F(0),(L-1)/(L-E))
                first_capture_constraint={'profile_us':us,'velocity_component_upper':[str(x) for x in component],
                    'velocity_norm_upper':str(L),'capture_velocity_vector_error_upper':str(E),
                    'alpha_sufficient_lower':str(alpha),
                    'formula':'(1-alpha)*L+alpha*E<=1, alpha in[0,1]; prevents first instantaneous velocity clipping in any orthonormal yaw frame',
                    'scope':'first reset only. Before this reset all seven cases share the same dynamics; not a full continuous-alpha repair family guarantee'}
        q2=sum(x*x for x in qbounds);max_q2=max(max_q2,q2)
        lag=sum(ff(b['axis'][ax])*(ff(b['intent'][k,ax])-center[ax][0]) for ax in range(2));lr=sum(abs(ff(b['axis'][ax]))*pw[ax] for ax in range(2))
        max_lag=max(max_lag,lag+lr);min_lag=min(min_lag,lag-lr)
        import math
        norm_R2=ff(math.cos(b['yaw']))**2+ff(math.sin(b['yaw']))**2
        if q2>=F('9.80665')**2*min(F(1),norm_R2) or max_lag>F('4.5'):
            failure={'row':k,'profile_us':us,'reason':'OUTER_BOUND_NOT_CLOSED','q2_upper':str(q2)};break
        if k==len(b['rows'])-1:
            pe=sum((abs(center[ax][0]-ff(b['intent'][k,ax]))+pw[ax])**2 for ax in range(2))
            ve=sum((abs(center[ax][1]-ff(b['s'][k,ax]))+vw[ax])**2 for ax in range(2))
            if pe>F(1,5)**2 or ve>F(1,10)**2:failure={'row':k,'reason':'TERMINAL_BOUND_NOT_CLOSED'}
            break
        for ax in range(2):
            scalar,sig,rem=step[ax];lo=rows_A(ff(b['kp'][ax]),ff(b['kv'][ax]),rho[0],cp,cv,sig);hi=rows_A(ff(b['kp'][ax]),ff(b['kv'][ax]),rho[1],cp,cv,sig)
            Q=qi[ax].copy()
            if eps:m[ax]+=1
            for z,r in enumerate(rem):
                if r:Q[3+z,3+z]+=ceilf(r*r*SCALE);m[ax]+=1;count_cross+=1
            m[ax]+=1;count_sat+=sig.count(0)
            # Independently verify all center/generator recurrences, including
            # nominal nonlinear clip and non-free capture auxiliary states.
            residuals=[F(0),F(0),F(0)]
            for rows in [lo,hi]:
                for ch in range(3):
                    src=center[ax] if ch==0 else [r[ch-1] for r in G[ax]]
                    dest=[ff(x) for x in tr['center'][k+1,ax]] if ch==0 else [ff(x) for x in tr['generators'][k+1,ax,:,ch-1]]
                    expected=[sum(v*src[j] for j,v in rowa.items()) for rowa in rows]
                    if ch==0:
                        expected[3]=min(F(1,2),max(-F(1,2),scalar[0]));expected[4]=min(F(1),max(F(-1),scalar[1]))
                    # A next-row capture is an exact constrained copy plus the
                    # separately budgeted native float reset; compare pre-jump.
                    if b['rows'][k+1]['oracle'][1]:
                        for i in [47,48]:expected[i]=dest[i]
                    residuals[ch]=max(residuals[ch],*(abs(x-y) for x,y in zip(expected,dest)))
            rb=7*sum(residuals);assert rb<=F(1,10**8),'NUMERICAL_RECURRENCE_NOT_ENCLOSED';max_num=max(max_num,rb)
            S[ax],padding=covariance_step(S[ax],lo,hi,Q);max_pad=max(max_pad,padding)
        old_stale=stale
        if k%2000==0:print(json.dumps({'audit_case':case['id'],'verified_prefix':k,'epsilon_P':str(eps)}),flush=True)
    return {'schema':'p10-a4-exact-storage-audit-1','case':case,'epsilon_P':str(eps),'status':'VERIFIED_CONDITIONAL_PROXY_SEQUENCE' if failure is None else 'UNKNOWN',
        'full_rows':k+1,'failure':failure,'max_q_squared_upper':str(max_q2),'max_q_upper_display':float(sqrt_up(max_q2)),
        'max_lag_upper':str(max_lag),'max_lead_upper':str(-min_lag),'cross_boundary_remainder_groups':count_cross,'saturated_axis_samples':count_sat,
        'terminal_position_squared_upper':str(pe) if failure is None else None,'terminal_velocity_squared_upper':str(ve) if failure is None else None,
        'max_center_generator_L2_rounding':str(max_num),'rho_enclosure':[str(x) for x in rho],
        'proof':'Snext PSD-dominates both rho endpoint A S A^T plus full-metric input covariance and nonlinear clip remainders, by exact integer row-sum enclosure; V=eta^T S^-1 eta gives energy budget recursion. No scan is used as region proof',
        'input_metric':'fixed blockdiag(A2 forward P47,A3 lateral P47,I4 capture); current p/v/q support with all physical cross terms; deterministic queue and capture residual assumptions explicit',
        'output_scope':'stipulated q interpolation and pure geometric tilt proxy only; no actual SITL skip, height or whole-task safety',
        'events':events,'initial_set':'unchanged A3 actual startup center + lateral p +/- .01m and q +/- .1; same captured variables and old queues retained',
        'first_capture_parameter_constraint':first_capture_constraint,
        'max_fixedpoint_padding_units':max_pad,'elapsed_s':time.perf_counter()-started,'candidate_sha256':sha(directory/'manifest.json'),
        'verifier_sha256':sha(Path(__file__)),'new_flights':0,'B_C_D_started':False}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    result=audit(a.input);write(a.output/'audit.json',result);print(json.dumps({k:result[k] for k in ['case','epsilon_P','status','full_rows','max_q_upper_display','elapsed_s']}))

#!/usr/bin/env python3
"""Finite A4 reachability/storage candidate construction. Exact audit is separate."""
import argparse,json,math,time
from pathlib import Path
import numpy as np
from data import write,save,sha,ROOT
from bench import load,coefficients,transition,cov_map,N


def candidate(b,case,epsilon,keep=False,point_only=False):
    c=b['center'].copy();G=b['G'].copy();S=np.array([np.eye(N)*2e-18 for _ in range(2)])
    counts=np.ones(2,int);cap_us=-5000000;resume_us=-10000000;old_stale=True
    rho=math.exp(-.05);maxq=0.;maxlag=-1e9;minlag=1e9;absolute=0.;first_unknown=None;modecross=0;saturated=0
    states=[];gens=[];bounds=[];events=[];start=time.perf_counter()
    qw=[np.linalg.inv(p) for p in b['P']]
    if point_only:G[:]=0;S[:]=0;counts[:]=0
    for k,row in enumerate(b['rows']):
        us=row['profile_us'];stale=bool(row['oracle'][0]);cap=bool(row['oracle'][1]);resume=old_stale and not stale and cap_us>=0
        if cap:
            cap_us=us;events.append((us,'CAPTURE'))
            # Source-native NED float capture, then fixed-frame mapping.
            from models import rot
            from struct import pack,unpack
            cast=lambda a:np.array([unpack('!f',pack('!f',float(x)))[0] for x in a])
            c[:,47]=rot(cast(b['origin']+rot(c[:,0],b['yaw']))-b['origin'],b['yaw'])
            c[:,48]=rot(cast(rot(c[:,1],b['yaw'])),b['yaw'])
            for ax in range(2):
                G[ax,47:49]=G[ax,:2]
                ix=np.arange(N);ix[47:49]=[0,1];S[ax]=S[ax][np.ix_(ix,ix)]
                if not point_only:S[ax,47,47]+=(2e-6)**2;S[ax,48,48]+=(5e-7)**2;counts[ax]+=2
        if resume:resume_us=us;events.append((us,'RESUME'))
        cp,cv,beta=coefficients(us,stale,cap_us,resume_us,case)
        r=c[:,47:49]@cp+beta*b['r'][k];s=c[:,47:49]@cv+beta*b['s'][k]
        qbound=[];pbound=[];vbound=[];ce=[];sig=[];rem=[]
        for ax in range(2):
            qbound.append(abs(c[ax,2])+np.abs(G[ax,2]).sum()+math.sqrt(max(0,counts[ax]*S[ax,2,2])))
            pbound.append(np.abs(G[ax,0]).sum()+math.sqrt(max(0,counts[ax]*S[ax,0,0])))
            vbound.append(np.abs(G[ax,1]).sum()+math.sqrt(max(0,counts[ax]*S[ax,1,1])))
            ev=[];ss=[];re=[]
            for pos,coef,lim,value in [(0,cp,.5,c[ax,0]-r[ax]),(1,cv,1.,c[ax,1]-s[ax])]:
                C=np.zeros(N);C[pos]=1;C[47:49]=-coef
                delta=np.abs(C@G[ax]).sum()+math.sqrt(max(0,counts[ax]*(C@S[ax]@C)))
                sigma=float(abs(value)<lim)
                rr=max(0.,abs(value)+delta-lim) if sigma else min(2*lim,max(0.,delta-(abs(value)-lim)))
                ev.append(value);ss.append(sigma);re.append(rr)
            ce.append(ev);sig.append(ss);rem.append(re)
        qnorm=float(np.linalg.norm(qbound));lag=float((b['intent'][k]-c[:,0])@b['axis'])
        lagrad=float(np.abs(b['axis'])@np.array(pbound));maxlag=max(maxlag,lag+lagrad);minlag=min(minlag,lag-lagrad);absolute+=abs(lag)*.004
        maxq=max(maxq,qnorm);bounds.append([qnorm,lag+lagrad,lag-lagrad,*pbound,*vbound])
        states.append(c.copy());gens.append(G.copy())
        # A region proof, if obtained, must cover every prefix including warmup.
        if qnorm>=9.80665 or maxlag>4.5 or not np.isfinite(qnorm) or max(pbound)>10:
            if first_unknown is None:first_unknown={'row':k,'profile_us':us,'q_upper':qnorm,'lag_upper':maxlag,'reason':'BOUND_OR_DOMAIN_NOT_CLOSED'}
            if not point_only:break
        if k==len(b['rows'])-1:break
        nxt=c.copy();ng=G.copy()
        for ax in range(2):
            A=transition(b['kp'][ax],b['kv'][ax],rho,cp,cv,np.array(sig[ax]))
            if not point_only:
                Snew=cov_map(A,S[ax]);Q=np.eye(N)*1e-16
                if epsilon:Q[:3,:3]+=epsilon**2*qw[ax];counts[ax]+=1
                for z in range(2):
                    if rem[ax][z]>0:Q[3+z,3+z]+=rem[ax][z]**2;counts[ax]+=1;modecross+=1
                counts[ax]+=1;S[ax]=Snew+Q+np.eye(N)*N*1e-24
            saturated+=sum(x==0 for x in sig[ax])
            qn=rho*c[ax,2]-(1-rho)*(b['kp'][ax]*c[ax,45]+b['kv'][ax]*c[ax,46])
            vn=c[ax,1]+.002*(c[ax,2]+qn);pn=c[ax,0]+.002*(c[ax,1]+vn)
            nxt[ax,:3]=[pn,vn,qn];nxt[ax,3:5]=[np.clip(ce[ax][0],-.5,.5),np.clip(ce[ax][1],-1,1)]
            nxt[ax,5:47]=c[ax,3:45];ng[ax]=A@G[ax]
        c=np.rint(nxt*1e12)/1e12;G=np.rint(ng*1e12)/1e12;old_stale=stale
    terminal_p=float(np.linalg.norm(c[:,0]-b['intent'][min(k,len(b['rows'])-1)]))+float(np.linalg.norm(pbound))
    terminal_v=float(np.linalg.norm(c[:,1]-b['s'][min(k,len(b['rows'])-1)]))+float(np.linalg.norm(vbound))
    admitted=first_unknown is None and terminal_p<=.2 and terminal_v<=.1
    result={'case':case,'epsilon_P':epsilon,'candidate_only_NOT_proof':True,'candidate_admit':admitted,'first_unknown':first_unknown,
        'max_q_upper':maxq,'max_lag_upper':maxlag,'max_lead_upper':-minlag,'terminal_position_upper':terminal_p,'terminal_velocity_upper':terminal_v,
        'nominal_integrated_absolute_lag_m_s':absolute,'cross_boundary_remainders':modecross,'saturated_axis_samples':saturated,'point_only':point_only,
        'rows':k+1,'elapsed_s':time.perf_counter()-start,'events':events,
        'direct_replay_scope':'same model, initial center, source schedule/full horizon and seven repair candidates; output point only when zero uncertainty/no residual assumed'}
    if keep:return result,{'center':np.array(states),'generators':np.array(gens),'bounds_candidate':np.array(bounds)}
    return result


def main(output):
    output.mkdir(parents=True,exist_ok=False);b=load();results=[]
    for case in b['config']['theory']['repair_candidates']:
        for eps in b['config']['theory']['epsilon_checked_grid']:
            value=candidate(b,case,eps);results.append(value)
            print(json.dumps({k:value[k] for k in ['epsilon_P','candidate_admit','rows','max_q_upper','elapsed_s']}|{'case':case['id']}),flush=True)
    write(output/'tolerance-candidates.json',{'results':results,'scan':'finite checked grid only, not a maximum or monotonicity theorem','height':'unknown','new_flights':0})
    direct=[candidate(b,case,0,point_only=True) for case in b['config']['theory']['repair_candidates']]
    write(output/'direct-replay.json',{'cases':direct,'evaluations':len(direct),'same_initial_source_events_and_horizon':True,
        'comparison':'7 point evaluations vs same7 storage/covariance candidate evaluations per epsilon; tolerance exploration and certificate/audit costs additional, no evaluation saving claimed'})
    choices=[x for x in results if x['candidate_admit']]
    chosen=max(choices,key=lambda x:(x['epsilon_P'],-x['max_q_upper'])) if choices else results[0]
    selected,arrays=candidate(b,chosen['case'],chosen['epsilon_P'],keep=True)
    save(output/'selected-trace.npz',arrays);write(output/'selected.json',selected)
    write(output/'manifest.json',{'files':{p.name:sha(p) for p in output.iterdir() if p.is_file()},'frozen_config_sha256':sha(ROOT/'config/p10_a4.json')})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)

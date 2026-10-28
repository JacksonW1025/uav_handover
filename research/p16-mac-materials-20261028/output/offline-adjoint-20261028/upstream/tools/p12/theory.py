#!/usr/bin/env python3
"""Exact dyadic weight bounds and useful source-subsystem constraints, no fitting."""
import argparse,json,sys,math
from fractions import Fraction as F
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p3_memory import load_policy
from p9_model import write,sha


def matrix(x):return [[F(float(v)) for v in row] for row in np.asarray(x)]
def mm(a,b):return [[sum(x*y for x,y in zip(row,col)) for col in zip(*b)] for row in a]
def inf(a):return max(sum(abs(v) for v in row) for row in a)
def serial(a):return [[str(v) for v in row] for row in a]


def construct(out):
    out.mkdir(parents=True,exist_ok=False);P=load_policy()
    W0=matrix(abs(P['W0']));Wi=matrix(abs(P['Wi']));Wh=matrix(abs(P['Wh']));A=matrix(abs(P['W2']))
    B=[sum(Wh[32+i])+F(float(abs(P['bh'][32+i]))) for i in range(16)]
    H=[[F(i==j)+Wh[32+i][j]+B[i]*Wh[i][j]/4+Wh[16+i][j]/2 for j in range(16)] for i in range(16)]
    X=mm([[Wi[32+i][j]+B[i]*Wi[i][j]/4+Wi[16+i][j]/2 for j in range(16)] for i in range(16)],W0)
    AH=mm(A,H);AX=mm(A,X)
    write(out/'rational-matrices.json',{'schema':'p12-dyadic-weight-bound-1','policy_sha256':P['sha256'],
        'H':serial(H),'X':serial(X),'A_abs':serial(A),'action_H':serial(AH),'action_X':serial(AX),
        'semantics':'exact rational arithmetic on stored binary32 weights; analytic real sigmoid/tanh/ReLU/clip bounds; not hardware rounding proof'})
    E=[F(1,1000)]*16;obs=[F(1,1000)]*22;prefix=[]
    for k in range(8):
        eh=[sum(a*b for a,b in zip(row,E))+sum(a*b for a,b in zip(xrow,obs)) for row,xrow in zip(H,X)]
        ea=[min(F(2),sum(a*b for a,b in zip(row,eh))) for row in A]
        prefix.append({'call':k+1,'commits':k%2==0,'h_bound_max':float(min(F(2),max(eh))),
            'action_bound_max':float(max(ea)),'clipped_box_bound_reached':max(ea)==2})
        if k%2==0:E=[min(F(2),v) for v in eh]
    result={'schema':'p12-theory-attempt-1','policy_sha256':P['sha256'],
        'matrix_sha256':sha(out/'rational-matrices.json'),
        'network':{'h_gain_exact':str(inf(H)),'h_gain':float(inf(H)),'x_gain':float(inf(X)),
            'h_to_output_gain':float(inf(AH)),'x_to_output_gain':float(inf(AX)),
            'prefix_example':prefix,'first_box_trivial_call':next((r['call'] for r in prefix if r['clipped_box_bound_reached']),None),
            'domain':'h in [-1,1]^16; componentwise absolute errors; real arithmetic; arbitrary x; no sampled Jacobian claim',
            'full_feedback_storage':'NOT_ESTABLISHED; observation/plant/caches/clock and joint residual need coupled domain bounds'},
        'capture':{'relation':'same-phase capture: dp_target=dp_held; dv_target=alpha*dv_held,H; d(position input)=0; d(velocity input,H)=(1-alpha)*dv_held,H; memory unchanged',
            'speed_reference':'b_a(v,t)=prox_(a*t*L2)(v); globally 1-Lipschitz; integral D is t-Lipschitz',
            'finite_horizon':'||dr(t)||<=||dp_capture||+T||dv_capture||; ||ds(t)||<=||dv_capture|| for all 0<=t<=T; add documented casts',
            'repair_parameter':'if every allowed held |v_i|<=L, (1-alpha)*L+epsilon<=1 implies alpha>=1-(1-epsilon)/L; P12 actual alpha=1',
            'scope':'whole target hold profile and capture jump; not body closed-loop safety or resume guarantee'},
        'filter':{'global_branch_crossing_bound':'E_next <= max(rho_up*E+(1-rho_up)*U,rho_down*E+(1-rho_down)*U)',
            'same_command_initial_memory':'E(T)<=exp(-T/.025)*E0 for any same command sequence and branch crossings',
            'example_initial_error_1000_after_200ms_rad_s':1000*math.exp(-.2/.025),
            'thrust_interface':'|dT|<=2*k*Omega*|d(actual_scaled_joint)|; filter error alone does not bound actual joint error',
            'source_application':'configured Gazebo FirstOrderFilter update; applies every physical dt, not controller/native ticks'},
        'A4_counterexample':{'status':'NOT_PROVEN_EXCLUDED','reason':'filter constraints restrict an execution subsystem, but A4 innovation lives in p/v/q; no certified causal plant/estimator residual relation excludes its 22-step sequence while covering all records',
            'missing_first_interface':'first physical/estimator transition after command selection: bounded causal joint, torque, cache and estimation residual, coupled to complete feedback'},
        'actual_record_coverage':'P11#70 dual-clock legal word accepted; no future scheduler or whole plant coverage certificate',
        'method_not_score':'analytic componentwise hybrid incremental relations and repair constraints retained; empirical predictions are separate'}
    write(out/'theory.json',result);return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=construct(a.output);print(json.dumps({'network':r['network'],'A4_counterexample':r['A4_counterexample']}))

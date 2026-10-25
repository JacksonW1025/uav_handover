#!/usr/bin/env python3
"""Exact lower-gap counterexample to a uniform unstructured error-ball contract.

This is not a counterexample to all Lyapunov methods or to real vehicle safety.
"""
import argparse,json
from fractions import Fraction as F
from math import factorial
from pathlib import Path
from data import ROOT,write,sha
from bench import load

def ff(x):return F.from_float(float(x))
def inverse(p):
    a=[p[i][:]+[F(int(i==j)) for j in range(3)] for i in range(3)]
    for i in range(3):
        pivot=a[i][i];assert pivot>0;a[i]=[x/pivot for x in a[i]]
        for j in range(3):
            if j!=i:
                z=a[j][i];a[j]=[x-z*y for x,y in zip(a[j],a[i])]
    return [r[3:] for r in a]

def calculate():
    b=load();raw=json.loads((ROOT/'data/p10-20261024-a2/construction-reviewed/certificate.json').read_text())['P_integer']
    p=[[F(raw[i][j],10**10) for j in range(3)] for i in range(3)];inv=inverse(p)
    lam=F(119,10);w=[lam*inv[i][2] for i in range(3)]
    norm2=sum(w[i]*p[i][j]*w[j] for i in range(3) for j in range(3));assert norm2<9
    lo=sum((-F(1,20))**j/factorial(j) for j in range(20));hi=sum((-F(1,20))**j/factorial(j) for j in range(21))
    q0=ff(b['center'][0,2]);u0=-ff(b['kp'][0])*ff(b['center'][0,45])-ff(b['kv'][0])*ff(b['center'][0,46]);K=22
    assert q0>=0 and u0>=0 and w[2]>0
    # Bounds do not assume a global monotonicity property: each positive term
    # is bounded separately on the proven exponential interval.
    q_lower=q0*lo**K+u0*(1-hi**K)+w[2]*sum(lo**j for j in range(K))
    assert q_lower>F('9.80665')
    assert all(not r['oracle'][1] for r in b['rows'][:K])
    return {'schema':'p10-a4-unstructured-contract-counterexample-1','status':'EXACT_COUNTEREXAMPLE',
        'common_P_metric':'same full two-axis P47+cap auxiliary metric; all queue/capture and second-axis innovations zero; first-axis p/v/q vector below includes physical cross terms',
        'disturbance_support':'arbitrary model innovations supported only in current p/v/q, not arbitrary98 coordinates. Deterministic queue/reset structure retained. The counterexample is inside this physical-support unstructured ball',
        'epsilon_ball_containing_this_input':'3','per_step_w_p_v_q':[str(x) for x in w],'exact_P_norm_squared':str(norm2),
        'steps':K,'duration_s':'11/125','q_forward_lower':str(q_lower),'q_forward_lower_display':float(q_lower),
        'first_capture_profile_s':13.096,'queue_argument':'q at transitions0..21 reads the unchanged initialized oldest delay sample; newly clipped errors cannot reach it until transition22. Thus saturation of new queue samples does not invalidate this counterexample',
        'all_seven_repairs':'only change capture/resume starting after13s, so the unchanged first88ms counterexample applies to all of them',
        'scope':'no sound 45deg proxy guarantee over the COMPLETE uniform per-step epsilon>=3 physical-support ball for this M0/startup/horizon; not impossibility for that ball intersected with actual observation-hold/colored-error constraints, other interfaces/dynamics, or all Lyapunov methods',
        'actual_system_claim':'none: this adversarial sequence need not be a realizable real controller residual; the point is that an unstructured ball falsely includes it',
        'initial_state':'nominal member of the unchanged nonzero initial set',
        'input_P_sha256':sha(ROOT/'data/p10-20261024-a2/construction-reviewed/certificate.json'),'new_flights':0}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);r=calculate();write(a.output/'counterexample.json',r);print(r['q_forward_lower_display'])

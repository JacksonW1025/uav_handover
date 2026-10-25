#!/usr/bin/env python3
"""Exact complete common-interface residual norm checks on portable samples."""
import argparse,json
from fractions import Fraction as F
from math import factorial
from pathlib import Path
from data import ROOT,write,sha

def ff(x):return F.from_float(float(x))
def rotate(v,c,s):return [c*v[0]+s*v[1],s*v[0]-c*v[1]]

def check(path):
    data=json.loads(path.read_text());P=[]
    for p in [ROOT/'data/p10-20261024-a2/construction-reviewed/certificate.json',ROOT/'data/p10-20261025-a3/source-08/matrix-candidate.json']:
        raw=json.loads(p.read_text())['P_integer'];P.append([[F(raw[i][j],10**10) for j in range(3)] for i in range(3)])
    gains=json.loads((ROOT/'data/p9-20261024-freeze/model.json').read_text());kp=list(map(ff,gains['kp']));kv=list(map(ff,gains['kv']))
    rho=[sum((-F(1,20))**j/factorial(j) for j in range(n)) for n in [20,21]];out=[]
    for row in data['portable_complete_metric_samples']:
        c,s=ff(row['cos_fixed_yaw']),ff(row['sin_fixed_yaw'])
        p,v,q=[[[ff(x) for x in vec] for vec in row[name]] for name in ['p','v','q']]
        ep=rotate([ff(x)-ff(y) for x,y in zip(row['delayed_p'],row['delayed_r'])],c,s)
        dv=rotate([ff(x)-ff(y) for x,y in zip(row['delayed_v'],row['delayed_s'])],c,s)
        u=rotate([-kp[i]*min(F(1,2),max(-F(1,2),ep[i]))-kv[i]*min(F(1),max(F(-1),dv[i])) for i in range(2)],c,s)
        def innovation(r):
            qn=[r*q[0][i]+(1-r)*u[i] for i in range(2)]
            vn=[v[0][i]+F(1,500)*(q[0][i]+qn[i]) for i in range(2)]
            pn=[p[0][i]+F(1,500)*(v[0][i]+vn[i]) for i in range(2)]
            return [rotate([actual[i]-pred[i] for i in range(2)],c,s) for actual,pred in [(p[1],pn),(v[1],vn),(q[1],qn)]]
        w0=innovation(F(0));w1=innovation(F(1));slope=[[w1[i][a]-w0[i][a] for a in range(2)] for i in range(3)]
        def inner(x,y):return sum(x[i][ax]*P[ax][i][j]*y[j][ax] for ax in range(2) for i in range(3) for j in range(3))
        A=inner(slope,slope);B=2*inner(w0,slope);C=inner(w0,w0)+sum(ff(x)**2 for x in row['aux_innovation'])
        candidates=rho[:]
        if A and rho[0]<=-B/(2*A)<=rho[1]:candidates.append(-B/(2*A))
        lower=min(A*r*r+B*r+C for r in candidates)
        assert lower>0
        out.append({'run':row['run'],'sample_us':row['sample_us'],'phase':row['phase'],'P_norm_squared_lower':str(lower),
            'P_norm_lower_display':float(lower)**.5,'requires_epsilon_above_3':lower>9})
    assert any(r['requires_epsilon_above_3'] for r in out)
    return {'schema':'p10-a4-complete-metric-audit-1','status':'EXACT_DATA_LOWER_CONSTRAINTS',
        'state_order':'[p,v,q,22 clipped e/d pairs] per fixed-origin axis plus4 captured p/v auxiliaries',
        'metric':'same blockdiag(P_A2_forward47,P_A3_lateral47,I4) as storage input norm; all physical p/v/q cross terms retained',
        'queue_and_aux_support':'derived queue shifts verified by definition of the observation-history map; captured-state reset residuals recorded, not silently zero-filled',
        'checks':out,'input_sha256':sha(path),'not_an_empirical_hard_upper_bound':True,'new_flights':0}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);write(a.output/'audit.json',check(a.input))

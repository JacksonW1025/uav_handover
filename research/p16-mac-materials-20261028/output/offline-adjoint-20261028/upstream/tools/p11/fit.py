#!/usr/bin/env python3
"""Fixed bounded least squares on whole P11 MODEL-DEVELOPMENT conditions only."""
import argparse
import json
from pathlib import Path
import sys
import time
import numpy as np
from scipy.optimize import lsq_linear
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from p11.models import R,speeds,motor_step,features,G

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from p9_model import sha,write
from p3_memory import load_policy


def fit(datasets,kind):
    X=[];Y=[];OX=[[],[],[]];OY=[[],[],[]];rows=0
    for d in datasets:
        command=np.array([speeds(a) for a in d['action']]);rot=command.copy()
        if kind=='M1':rot[1:]=command[:-1]
        else:
            for k in range(1,len(rot)):rot[k]=motor_step(rot[k-1],command[max(0,k-2)])
        total=np.sum(rot**2,axis=1)/1e6
        dif=np.array([features(a)[1] for a in rot])
        st=d['sample_us'].astype(np.int64);lp=d['lp_sample'].astype(np.int64)
        for k in np.flatnonzero(np.diff(lp)>0)+1:
            old=k-1;start=int(np.searchsorted(st,lp[old],side='left'));end=int(np.searchsorted(st,lp[k],side='right'))
            if start<1 or end>len(st) or end<=start:continue
            dt=(lp[k]-lp[old])/1e6
            acc=(d['velocity'][k]-d['velocity'][old])/dt
            bz=R(d['attitude'][old])[:,2];u=float(np.mean(total[start:end]))
            for axis in range(3):
                x=np.zeros(4);x[0]=-bz[axis]*u;x[axis+1]=-d['velocity'][old,axis]
                X.append(x);Y.append(acc[axis]-(G if axis==2 else 0.))
        for k in range(1,len(st)):
            dt=(st[k]-st[k-1])/1e6
            if dt!=.004:continue
            wd=(d['omega'][k]-d['omega'][k-1])/dt
            for axis in range(3):OX[axis].append([dif[k-1,axis],-d['omega'][k-1,axis]]);OY[axis].append(wd[axis])
        rows+=len(st)
    X=np.array(X);Y=np.array(Y)
    sol=lsq_linear(X,Y,bounds=([0,0,0,0],[20,5,5,5]),tol=1e-12,max_iter=1000)
    torque=[];drag=[];angular=[]
    for x,y in zip(OX,OY):
        x=np.array(x);y=np.array(y);s=lsq_linear(x,y,bounds=([-1000,0],[1000,20]),tol=1e-12,max_iter=1000)
        torque.append(float(s.x[0]));drag.append(float(s.x[1]));angular.append({'rmse':float(np.sqrt(np.mean((x@s.x-y)**2))),
            'condition_number':float(np.linalg.cond(x)),'success':bool(s.success)})
    return {'kind':kind,'thrust':float(sol.x[0]),'drag':sol.x[1:].tolist(),'torque':torque,'angular_drag':drag,
        'execution_state':'4 asymmetric rotor states tau_up.0125/down.025' if kind=='M2' else 'one pending command; no rotor dynamics',
        'fit':{'active_rows':rows,'acceleration_scalar_rows':len(Y),'acceleration_rmse':float(np.sqrt(np.mean((X@sol.x-Y)**2))),
            'condition_number':float(np.linalg.cond(X)),'angular':angular,'success':bool(sol.success),
            'interpretation':'effective empirical coefficients, not identified exact physical mass/inertia or causal omission attribution'}}


def create(paths,out,scope):
    out.mkdir(parents=True,exist_ok=False);started=time.perf_counter();ds=[];sources=[]
    for p in paths:
        ds.append(dict(np.load(p)));sources.append({'path':str(p),'sha256':sha(p)})
    old=ROOT/'data/p9-20261024-freeze/model.json';m0=json.loads(old.read_text())
    models={'M0':{'kind':'M0','kp':m0['kp'],'kv':m0['kv'],'tau':m0['tau_s'],'delay_steps':22,
        'source_sha256':sha(old),'height':'UNMODELLED','assumption':'P9 gains reused at4ms as retained A4 baseline; not exact resampling'}}
    models.update({k:fit(ds,k) for k in ['M1','M2']})
    P=load_policy();np.savez_compressed(out/'policy.npz',**{k:P[k] for k in ['W0','b0','Wi','bi','Wh','bh','W2','b2']})
    write(out/'models.json',models)
    result={'schema':'p11-model-fit-1','scope':scope,'inputs':sources,'policy_tar_sha256':P['sha256'],
        'model_sha256':sha(out/'models.json'),'policy_arrays_sha256':sha(out/'policy.npz'),
        'compute_s':time.perf_counter()-started,'selection':'all3 retained; no post-heldout refit; admission decided separately from grouped predictions'}
    write(out/'fit.json',result);print(json.dumps(result));return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--formal',type=Path);p.add_argument('--smoke-input',type=Path)
    a=p.parse_args()
    if a.formal:
        plan=json.loads((ROOT/'config/p11.json').read_text());rows=[r for r in plan['rows'] if r['split']=='development']
        assert all(r['group'] in ['G15','G20'] for r in rows)
        paths=[a.formal/r['id']/'packed/measurement.npz' for r in rows]
        if not all(p.exists() for p in paths):raise RuntimeError('all fixed training cases must finish before model fit')
        create(paths,a.output,'formal whole condition development groups G15/G20 only')
    elif a.smoke_input:create([a.smoke_input],a.output,'development implementation smoke, not formal fitted model')
    else:p.error('formal or smoke-input required')

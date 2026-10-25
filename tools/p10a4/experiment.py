#!/usr/bin/env python3
"""Finite offline A4 diagnosis/fit/check, whole already-seen condition groups."""
import argparse
import json
from pathlib import Path
import time
import numpy as np
from scipy.optimize import lsq_linear
from data import write,sha,ROOT
from models import H,rot,baseline,valid_steps,predict_rows,residuals,rollout,q_features,q_at


def stats(x):
    x=np.asarray(x);return {'n':len(x),'mean':np.mean(x,axis=0).tolist(),'rmse':np.sqrt(np.mean(x*x,axis=0)).tolist(),
        'abs_p50':np.quantile(abs(x),.5,axis=0).tolist(),'abs_p95':np.quantile(abs(x),.95,axis=0).tolist(),
        'abs_p99':np.quantile(abs(x),.99,axis=0).tolist(),'max_abs':np.max(abs(x),axis=0).tolist()}


def load_inputs(inp):
    meta=json.loads((inp/'manifest.json').read_text());runs=[]
    for row in meta['runs']:
        assert sha(inp/row['file'])==row['sha256'];runs.append((row,dict(np.load(inp/row['file'],allow_pickle=False))))
    return runs


def diagnose(inp,out):
    out.mkdir(parents=True,exist_ok=False);records=[]
    for row,a in load_inputs(inp):
        m=baseline();k=valid_steps(a,22,row['profile_start_bound_us']);w,norm,aux,_=residuals(a,m,k)
        phases={}
        for phase in np.unique(a['phase'][k]):
            mask=a['phase'][k]==phase;phases[str(phase)]={'residual_NED_p_v_q':stats(w[mask]),'complete_P49x2_innovation':stats(norm[mask]),'aux_reset_residual':stats(aux[mask])}
        ages={name:{'min':int(a[name].min()),'median':float(np.median(a[name])),'max':int(a[name].max())} for name in ['lp_age_us','att_age_us']}
        correlation={}
        for lag in [1,5,25,125]:
            pair=(np.diff(a['t'][k],prepend=-1)==4000);ix=np.arange(lag,len(k));good=(k[ix]-k[ix-lag]==lag)&(a['phase'][k[ix]]==a['phase'][k[ix-lag]])
            x=norm[ix[good]];y=norm[ix[good]-lag]
            correlation[str(lag*H)]=None if len(x)<3 or np.std(x)==0 or np.std(y)==0 else float(np.corrcoef(x,y)[0,1])
        records.append({'run':row['run'],'role':row['role'],'valid_steps':len(k),'excluded_step_candidates':len(a['t'])-1-len(k),
            'state_sample_ages_us':ages,'phases':phases,'repeat_event_P_norm':None if not a['repeat'][k].any() else stats(norm[a['repeat'][k]]),
            'P_norm_time_correlation_descriptive':correlation,
            'acceleration_vs_q_rmse':np.sqrt(np.mean((a['a'][k]-a['q'][k])**2,axis=0)).tolist(),
            'queue_residual':'zero by deterministic reconstructed queue interface, not a native hidden-state claim',
            'statistical_unit':'flight/condition group; time rows correlated, no IID confidence claim'})
    write(out/'baseline-diagnostics.json',{'model':baseline(),'runs':records,'complete_metric':'blockdiag(Pf47,Pl47,I4 capture auxiliary); current-state cross terms retained, reconstructed queue differences0; common NED outputs rotated to fixed initial target-yaw frame for this metric','new_flights':0})


def fit_models(runs):
    train=[(r,a) for r,a in runs if r['role']=='fit'];trials=[]
    for tau in [.04,.08,.16]:
        for delay in [0,11,22,33]:
            xx=[];yy=[]
            for row,a in train:
                k=valid_steps(a,delay+2,row['profile_start_bound_us']);power,features=q_features(a,k,tau,delay)
                xx.append(features.reshape(-1,4)/np.sqrt(len(k)));yy.append((a['q'][k+1]-power[:,None]*a['q'][k]).reshape(-1)/np.sqrt(len(k)))
            x=np.concatenate(xx);y=np.concatenate(yy);coef=lsq_linear(x,y,bounds=(0,50),tol=1e-12).x
            trials.append({'tau':tau,'delay_steps':delay,'coef':coef.tolist(),'equal_run_q_objective':float(np.sum((x@coef-y)**2))})
    best=min(trials,key=lambda x:x['equal_run_q_objective'])
    m1={'name':'M1-native-clock-refit','kp':best['coef'][:2],'kv':best['coef'][2:],
        'tau':best['tau'],'delay_steps':best['delay_steps'],'plant':'q_trapezoid','yaw_transport':'delayed_frame','parameters':6,'state_dim':10,'sensor_clocks':True,
        'clock_scope':'conditioned observed future sensor timestamps; q past interpolation and forward q dynamics, p/v held until LP update; not a universal native schedule'}
    xx=[];yy=[]
    for row,a in train:
        k=valid_steps(a,m1['delay_steps']+2,row['profile_start_bound_us']);lp=a['t']-a['lp_age_us'];k=k[lp[k+1]-lp[k]==8000]
        q0=q_at(a,m1,k,lp[k]);x=np.stack([a['a'][k],q0,a['v'][k]],axis=-1).reshape(-1,3)
        xx.append(x/np.sqrt(len(k)));yy.append(a['a'][k+1].reshape(-1)/np.sqrt(len(k)))
    abc=lsq_linear(np.concatenate(xx),np.concatenate(yy),bounds=([0,0,-100],[.999,100,0]),tol=1e-12).x
    m2={**m1,'name':'M2-acceleration-state','plant':'acceleration_ar','acc_ar':abc.tolist(),'parameters':9,'state_dim':12,'acc_update_s':.008}
    return [baseline(),m1,m2],trials


def evaluate(inp,out):
    out.mkdir(parents=True,exist_ok=False);runs=load_inputs(inp);models,trials=fit_models(runs)
    write(out/'models.json',{'models':models,'finite_q_trials':trials,'fit_runs':[r['run'] for r,a in runs if r['role']=='fit'],
        'check_runs':[r['run'] for r,a in runs if r['role']!='fit'],'prospective':False,'height_model':False})
    results=[]
    for m in models:
        for row,a in runs:
            k=valid_steps(a,max(22,m['delay_steps']),row['profile_start_bound_us'])
            t0=time.perf_counter();w,norm,aux,wa=residuals(a,m,k);cost=(time.perf_counter()-t0)/len(k)
            phase={str(p):{'common_6D_residual':stats(w[a['phase'][k]==p]),'complete_baseline_metric':stats(norm[a['phase'][k]==p])} for p in np.unique(a['phase'][k])}
            # Fixed starts per whole flight: first profile point and each stage edge.
            edges=np.r_[0,np.flatnonzero(a['phase'][1:]!=a['phase'][:-1])+1]
            starts=sorted(set([int(k[0])]+[int(i) for i in edges if i>=k[0]]))
            rolls=[]
            for start in starts:
                for horizon in [.5,2.]:
                    length=int(round(horizon/H));end=start+length
                    if end>=len(a['t']) or not a['valid'][start:end+1].all() or not np.all(np.diff(a['t'][start:end+1])==4000):continue
                    pred=rollout(a,m,start,length);truth=np.c_[a['p'][start:end+1],a['v'][start:end+1],a['q'][start:end+1]]
                    err=pred-truth;predtilt=np.degrees(np.arctan(np.linalg.norm(pred[:,4:6],axis=1)/9.80665));truetilt=np.degrees(np.arctan(np.linalg.norm(truth[:,4:6],axis=1)/9.80665))
                    rolls.append({'start_sample_us':int(a['t'][start]),'stage':str(a['phase'][start]),'horizon_s':horizon,
                        'rmse_NED_p_v_q':np.sqrt(np.mean(err.reshape(-1,3,2)**2,axis=0)).tolist(),
                        'pred_peak_proxy_tilt_deg':float(predtilt.max()),'observed_peak_proxy_tilt_deg':float(truetilt.max()),
                        'peak_tilt_error_deg':float(predtilt.max()-truetilt.max()),
                        'misses_observed_45deg':bool(truetilt.max()>45 and predtilt.max()<=45)})
            start=int(k[0]);full=rollout(a,m,start,len(a['t'])-start-1);truth=np.c_[a['p'][start:],a['v'][start:],a['q'][start:]]
            results.append({'model':m['name'],'run':row['run'],'role':row['role'],'group':row['group'],'one_step_phases':phase,
                'one_step_seconds_per_row':cost,'M2_additional_acceleration_residual':None if wa is None else stats(wa),
                'metric_scope':'P49x2 is common complete baseline-interface metric; M2 acceleration residual separately retained, projection metric is NOT an 8-state certificate',
                'rolling':rolls,'full_logged_target_rollout_rmse':np.sqrt(np.mean((full-truth).reshape(-1,3,2)**2,axis=0)).tolist(),
                'prediction_scope':'hindsight actual future target/yaw conditioned replay, no future measured body states after each start; not prospective source-coupled prediction'})
    write(out/'comparison.json',{'results':results,'selection_bias':'all logs previously seen, complete condition groups retained; no random time split; descriptive within-flight rows not independent replicates'})
    print(json.dumps({'models':models,'rows':len(results)}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['diagnose','evaluate']);p.add_argument('--input',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    (diagnose if a.mode=='diagnose' else evaluate)(a.input,a.output)

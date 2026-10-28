#!/usr/bin/env python3
"""P12 scoring v2: failure witnesses and incomplete predictions are distinct.

Scoring may read future measurements. Forecast never imports this module.
Original P11 and P12 v1 score files are never changed by this tool.
"""
import argparse,json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p9_model import write,sha
from p11.models import tilt
from p11.score import so3,summary

TOL=.0041
WINDOW_TOL=.004  # Keep the original observed-window tolerance, not a relaxed cutoff.


def state(peak,threshold,complete,known=True):
    if known and peak is not None and peak>threshold:return 'FAILURE'
    if known and complete and peak is not None:return 'SUCCESS'
    return 'UNKNOWN'


def union(a,b):
    if 'FAILURE' in (a,b):return 'FAILURE'
    return 'SUCCESS' if a==b=='SUCCESS' else 'UNKNOWN'


def compare(predicted,observed,unmodelled=False):
    if predicted=='UNKNOWN':return 'UNKNOWN_UNMODELLED_HEIGHT' if unmodelled else 'UNKNOWN_PREDICTION_TRUNCATED'
    if observed=='UNKNOWN':return 'UNKNOWN_CENSORED'
    if predicted==observed:return 'AGREEMENT'
    return 'FALSE_ALARM' if predicted=='FAILURE' else 'DANGER_MISS'


def bundle(pt,ph,pc,ot,oh,oc,height=True):
    predicted={'tilt':state(pt,45.,pc),'height':state(ph,1.,pc,height)}
    observed={'tilt':state(ot,45.,oc),'height':state(oh,1.,oc)}
    predicted['task']=union(*predicted.values());observed['task']=union(*observed.values())
    comparisons={key:compare(predicted[key],observed[key],not height and key in ['height','task'] and predicted[key]=='UNKNOWN') for key in predicted}
    return {'predicted':predicted,'observed':observed,'comparisons':comparisons,
        'classification_eligible':{key:predicted[key]!='UNKNOWN' and observed[key]!='UNKNOWN' for key in predicted},
        'full_trajectory_eligible':{key:bool(pc and oc and (height or key=='tilt')) for key in predicted},
        'prediction_complete':bool(pc),'observation_complete':bool(oc),
        'semantics':'FAILURE may be witnessed in a valid prefix; SUCCESS requires complete coverage; UNKNOWN is never agreement'}


def maximum(values):return float(np.max(values)) if len(values) else None


def loss(z,baseline):
    return float(max(0.,np.max(z)-baseline)) if len(z) and baseline is not None else None


def score(predictions,packed,measurement,out):
    out.mkdir(parents=True,exist_ok=False)
    d=dict(np.load(packed/'measurement.npz'));doc=json.loads((packed/'prediction-input.json').read_text())
    observed=json.loads(measurement.read_text());meta=json.loads((predictions/'prediction.json').read_text())
    tt=d['profile_s'];start=float(doc['plan']['common_first_gap_profile_s']);end=float(doc['plan']['horizon_profile_s'])
    eligible=(tt>=start)&(tt<=end);angles=np.array([tilt(q) for q in d['attitude']])
    observed_end=min(end,float(tt[-1]));obs_complete=not observed['censored']
    actual_peak=maximum(angles[eligible]);obs_z0=float(np.interp(start,tt,d['position'][:,2])) if tt[0]<=start<=tt[-1] else None
    models={}
    for name,info in meta['models'].items():
        trace=np.load(predictions/(name+'.npz'))['trace'];t=trace[:,0]
        if len(t)==0 or np.any(np.diff(t)<=0):raise ValueError('empty or unordered prediction '+name)
        # A numerical stopping row is not a valid witness, even if one of its
        # output coordinates happens to remain finite. Keep earlier witnesses.
        good=np.all(np.isfinite(trace),axis=1) if name!='M0' else np.all(np.isfinite(trace[:,:8]),axis=1)
        stop=info.get('stop')
        if stop and stop.get('reason')=='NUMERICAL_UNCERTAIN':good &= t<float(stop.get('profile_s',t[-1]))
        bad=np.flatnonzero(~good);n=int(bad[0]) if len(bad) else len(t)
        known=trace[:n];kt=t[:n]
        full=bool(n==len(t) and stop is None and t[0]<=start and t[-1]>=end-TOL)
        valid=eligible&(tt>=kt[0])&(tt<=kt[-1]) if n else np.zeros(len(tt),bool)
        rows=np.flatnonzero(valid);target_t=tt[rows]
        pred=np.column_stack([np.interp(target_t,kt,known[:,j]) for j in range(1,trace.shape[1])]) if len(rows) else np.empty((0,trace.shape[1]-1))
        axes=2 if name=='M0' else 3;height=bool(info.get('height_modelled',name!='M0'))
        pe=pred[:,41:41+axes]-d['position'][rows,:axes]
        ve=pred[:,44:44+axes]-d['velocity'][rows,:axes]
        ae=pred[:,6]-angles[rows]
        scope=(kt>=start)&(kt<=observed_end) if n else np.zeros(0,bool)
        forecast=(kt>=start)&(kt<=end) if n else np.zeros(0,bool)
        peak=maximum(known[scope,7]);forward=maximum(known[forecast,7])
        z0=float(np.interp(start,kt,known[:,3])) if n and kt[0]<=start<=kt[-1] and height else None
        altitude=loss(known[scope,3],z0) if height else None
        risk=bundle(peak,altitude,full,observed['whole']['max_tilt_deg'],observed['whole']['max_altitude_loss_m'],obs_complete,height)
        common_error=abs(float(pred[:,6].max())-float(angles[rows].max())) if len(rows) else None
        whole_error=abs(peak-actual_peak) if full and obs_complete and peak is not None and actual_peak is not None else None
        r={'window_rows':int(eligible.sum()),'scored_rows':len(rows),
            'prediction_window_coverage':float(len(rows)/eligible.sum()) if eligible.any() else 0.,
            'observed_censored':observed['censored'],'prediction_stop':stop,'full_prediction':full,
            'valid_prediction_prefix_rows':n,'invalid_or_uncertain_tail_rows':len(t)-n,
            'position_norm_m':summary(np.linalg.norm(pe,axis=1)), 'velocity_norm_m_s':summary(np.linalg.norm(ve,axis=1)),
            'position_axis_m':[summary(pe[:,k]) for k in range(axes)],'velocity_axis_m_s':[summary(ve[:,k]) for k in range(axes)],
            'tilt_error_deg':summary(ae),'tilt_peak_deg':peak,'forward_horizon_tilt_peak_deg':forward,
            'observed_tilt_peak_deg':actual_peak,'peak_abs_error_deg':whole_error,'common_prefix_peak_abs_error_deg':common_error,
            'observed_peak_is_lower_bound':not obs_complete,'predicted_peak_is_lower_bound':not full,
            'risk_comparison':risk['comparisons']['tilt'],'height_risk_comparison':risk['comparisons']['height'],
            'task_risk_comparison':risk['comparisons']['task'],'risk':risk,
            'height_modelled':height,'altitude_loss_m':altitude,'compute_s':info.get('compute_s'),
            'attitude_SO3_deg':summary(so3(pred[:,47:51],d['attitude'][rows])) if name!='M0' and len(rows) else None,
            'action_error':summary(np.linalg.norm(pred[:,7:11]-d['action'][rows],axis=1)) if name!='M0' else None,
            'hidden_error':summary(np.linalg.norm(pred[:,11:27]-d['h_after'][rows],axis=1)) if name!='M0' else None,
            'event_windows':[]}
        for i,(a,b) in enumerate(doc['plan']['windows_profile_s']):
            for duration in [.5,2.]:
                finish=a+duration;aw=(tt>=a)&(tt<finish);pw=(kt>=a)&(kt<finish);cm=(target_t>=a)&(target_t<finish)
                reached=bool(aw.any());oc=bool(reached and tt[-1]>=finish-WINDOW_TOL)
                pc=bool(n and kt[0]<=a and kt[-1]>=finish-WINDOW_TOL)
                op=maximum(angles[aw]);pp=maximum(known[pw,7]);ol=loss(d['position'][aw,2],obs_z0);pl=loss(known[pw,3],z0) if height else None
                event=bundle(pp,pl,pc,op,ol,oc,height)
                if not reached:
                    event['comparisons']={key:'NOT_REACHED' for key in event['comparisons']}
                    event['classification_eligible']={key:False for key in event['classification_eligible']}
                r['event_windows'].append({'index':i,'planned_gap':[a,b],'window_s':duration,'rows':int(cm.sum()),
                    'overlaps_other_planned_event':any(j!=i and a<=c<finish for j,(c,_) in enumerate(doc['plan']['windows_profile_s'])),
                    'position_norm_m':summary(np.linalg.norm(pe[cm],axis=1)),'velocity_norm_m_s':summary(np.linalg.norm(ve[cm],axis=1)),
                    'tilt_error_deg':summary(ae[cm]),'censored':not(pc and oc),'observation_complete':oc,'prediction_complete':pc,
                    'observed_peak_deg':op,'observed_peak_is_lower_bound':not oc,'predicted_peak_deg':pp,'predicted_peak_is_lower_bound':not pc,
                    'observed_altitude_loss_m':ol,'predicted_altitude_loss_m':pl,'height_baseline_profile_s':start,
                    'risk_comparison':event['comparisons']['tilt'],'height_risk_comparison':event['comparisons']['height'],
                    'task_risk_comparison':event['comparisons']['task'],'risk':event})
        models[name]=r
    result={'schema':'p12-scoring-2','models':models,
        'inputs':{str(predictions/'prediction.json'):sha(predictions/'prediction.json'),str(packed/'measurement.npz'):sha(packed/'measurement.npz'),str(measurement):sha(measurement)},
        'alignment':'same absolute task time; no peak/capture/stop alignment; global height baseline retained for event windows',
        'thresholds':{'tilt_deg':45.,'altitude_loss_m':1.,'operator':'>'},
        'denominator_rule':'known failure witnesses may classify a truncated prefix; unknown tails never establish success; full-trajectory errors require both complete',
        'training_selection':'not recomputed or used; no model fit, selection, new predictions or flights'}
    write(out/'score.json',result);return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['predictions','packed','measurement','output']:p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();r=score(a.predictions,a.packed,a.measurement,a.output)
    print(json.dumps({k:{x:v[x] for x in ['risk_comparison','height_risk_comparison','task_risk_comparison','full_prediction']} for k,v in r['models'].items()}))

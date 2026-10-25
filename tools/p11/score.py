#!/usr/bin/env python3
"""Scoring side only: future measurements may be read here, never in forecast."""
import argparse
import json
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from p9_model import write,sha
from p11.models import tilt


def so3(a,b):
    a=a/np.linalg.norm(a,axis=1)[:,None];b=b/np.linalg.norm(b,axis=1)[:,None]
    return np.degrees(2*np.arccos(np.clip(np.abs(np.sum(a*b,axis=1)),0,1)))


def summary(x):
    x=np.asarray(x)
    return {'rmse':float(np.sqrt(np.mean(x*x))),'p95_abs':float(np.quantile(np.abs(x),.95)),'max_abs':float(np.max(np.abs(x)))} if x.size else None


def score(predictions,packed,measurement,out):
    out.mkdir(parents=True,exist_ok=False);d=dict(np.load(packed/'measurement.npz'));doc=json.loads((packed/'prediction-input.json').read_text())
    observed=json.loads(measurement.read_text());meta=json.loads((predictions/'prediction.json').read_text());report={}
    tt=d['profile_s'];start=doc['plan']['common_first_gap_profile_s'];end=doc['plan']['horizon_profile_s']
    eligible=(tt>=start)&(tt<=end);angles=np.array([tilt(q) for q in d['attitude']])
    for name,info in meta['models'].items():
        trace=np.load(predictions/(name+'.npz'))['trace'];t=trace[:,0];valid=eligible&(tt>=t[0])&(tt<=t[-1])
        if not valid.any():raise RuntimeError('no overlap with fixed scoring window')
        rows=np.flatnonzero(valid);target_t=tt[rows]
        predicted=np.column_stack([np.interp(target_t,t,trace[:,j]) for j in range(1,trace.shape[1])])
        # predicted excludes time: p0:3/v3:6/tilt6/action7:11/h11:27/r27:30/sv30:33/stale33/q34:38/omega38:41/lp41:44/lv44:47/att47:51
        axes=2 if name=='M0' else 3
        pos_error=predicted[:,41:41+axes]-d['position'][rows,:axes]
        vel_error=predicted[:,44:44+axes]-d['velocity'][rows,:axes]
        angle_error=predicted[:,6]-angles[rows]
        full_predicted=bool(info['stop'] is None and t[-1]>=end-.0041)
        tilt_fail=bool(observed['whole']['max_tilt_deg']>45.)
        # Envelope stops for radius/rate are not a predicted tilt exceedance.
        predicted_fail=bool(info['stop'] and info['stop'].get('angle_deg',0)>45.)
        actual_tilt_peak=float(angles[eligible].max()) if eligible.any() else None
        observed_end=min(end,float(tt[-1]));forecast_mask=(t>=start)&(t<=end)
        peak=float(trace[(t>=start)&(t<=observed_end),7].max()) if (t>=start).any() else float(trace[:,7].max())
        forward_peak=float(trace[forecast_mask,7].max()) if forecast_mask.any() else float(trace[:,7].max())
        common_peak_error=abs(float(predicted[:,6].max())-float(angles[rows].max()))
        whole_peak_error=abs(peak-actual_tilt_peak) if not observed['censored'] and full_predicted else None
        # A censored safe prefix cannot establish a safe whole task.
        outcome='DANGER_MISS' if tilt_fail and not predicted_fail else ('FALSE_ALARM' if not tilt_fail and not observed['censored'] and predicted_fail else ('UNKNOWN_CENSORED' if observed['censored'] and not tilt_fail else 'AGREEMENT'))
        if (info['stop'] is not None and not predicted_fail) or tt[-1]>end+.008:outcome='UNKNOWN_PREDICTION_TRUNCATED'
        r={'window_rows':int(eligible.sum()),'scored_rows':len(rows),'prediction_window_coverage':float(len(rows)/eligible.sum()),
            'observed_censored':observed['censored'],'prediction_stop':info['stop'],'full_prediction':full_predicted,
            'position_norm_m':summary(np.linalg.norm(pos_error,axis=1)),
            'velocity_norm_m_s':summary(np.linalg.norm(vel_error,axis=1)),
            'position_axis_m':[summary(pos_error[:,k]) for k in range(axes)],'velocity_axis_m_s':[summary(vel_error[:,k]) for k in range(axes)],
            'tilt_error_deg':summary(angle_error),'tilt_peak_deg':peak,'forward_horizon_tilt_peak_deg':forward_peak,'observed_tilt_peak_deg':actual_tilt_peak,
            'peak_abs_error_deg':whole_peak_error,'common_prefix_peak_abs_error_deg':common_peak_error,
            'observed_peak_is_lower_bound':observed['censored'],'risk_comparison':outcome,'compute_s':info['compute_s'],
            'height_modelled':name!='M0','attitude_SO3_deg':None,'action_error':None,'hidden_error':None,
            'event_windows':[],'task_risk_comparison':'UNKNOWN_UNMODELLED_HEIGHT' if name=='M0' else None}
        if name!='M0':
            r['attitude_SO3_deg']=summary(so3(predicted[:,47:51],d['attitude'][rows]))
            r['action_error']=summary(np.linalg.norm(predicted[:,7:11]-d['action'][rows],axis=1))
            r['hidden_error']=summary(np.linalg.norm(predicted[:,11:27]-d['h_after'][rows],axis=1))
            r['altitude_loss_m']=float(max(0.,np.max(trace[:,3])-np.interp(start,t,trace[:,3])))
            task_predicted_fail=predicted_fail or r['altitude_loss_m']>1.
            task_observed_fail=observed['task_outcome']=='FAILURE'
            r['task_risk_comparison']=('DANGER_MISS' if task_observed_fail and not task_predicted_fail else
                ('FALSE_ALARM' if observed['task_outcome']=='SUCCESS' and task_predicted_fail else
                ('UNKNOWN_CENSORED' if observed['task_outcome']=='UNKNOWN_CENSORED' else 'AGREEMENT')))
            if info['stop'] is not None and info['stop']['reason']=='NUMERICAL_UNCERTAIN':r['task_risk_comparison']='UNKNOWN_PREDICTION_TRUNCATED'
        for i,(a,b) in enumerate(doc['plan']['windows_profile_s']):
            for length in [.5,2.]:
                mask=(target_t>=a)&(target_t<a+length)
                aw=(tt>=a)&(tt<a+length);pw=(t>=a)&(t<a+length)
                observed_event_peak=float(angles[aw].max()) if aw.any() else None
                predicted_event_peak=float(trace[pw,7].max()) if pw.any() else None
                event_complete=bool(tt[-1]>=a+length-.004)
                if observed_event_peak is None:event_risk='NOT_REACHED'
                elif observed_event_peak>45 and predicted_event_peak is not None and predicted_event_peak<=45:event_risk='DANGER_MISS'
                elif not event_complete and observed_event_peak<=45:event_risk='UNKNOWN_CENSORED'
                elif predicted_event_peak is None:event_risk='UNKNOWN_PREDICTION_TRUNCATED'
                elif event_complete and observed_event_peak<=45 and predicted_event_peak>45:event_risk='FALSE_ALARM'
                else:event_risk='AGREEMENT'
                r['event_windows'].append({'index':i,'planned_gap':[a,b],'window_s':length,'rows':int(mask.sum()),
                    'overlaps_other_planned_event':any(j!=i and a<=c<a+length for j,(c,_) in enumerate(doc['plan']['windows_profile_s'])),
                    'position_norm_m':summary(np.linalg.norm(pos_error[mask],axis=1)),
                    'velocity_norm_m_s':summary(np.linalg.norm(vel_error[mask],axis=1)),
                    'tilt_error_deg':summary(angle_error[mask]),'censored':bool(not full_predicted or target_t[-1]<a+length-.008),
                    'observed_peak_deg':observed_event_peak,'observed_peak_is_lower_bound':not event_complete,
                    'predicted_peak_deg':predicted_event_peak,'risk_comparison':event_risk})
        r['training_selection_score']=(r['position_norm_m']['rmse']/.5+r['velocity_norm_m_s']['rmse']/.3+
            (r['peak_abs_error_deg'] if r['peak_abs_error_deg'] is not None else common_peak_error)/5.+10*(1-r['prediction_window_coverage'])+25*(outcome=='DANGER_MISS')+
            10*(outcome=='FALSE_ALARM')+(5 if name=='M0' else r['action_error']['rmse']/.1))
        report[name]=r
    result={'schema':'p11-scoring-1','models':report,'inputs':{str(predictions/'prediction.json'):sha(predictions/'prediction.json'),
        str(packed/'measurement.npz'):sha(packed/'measurement.npz'),str(measurement):sha(measurement)},
        'alignment':'absolute source profile time, no alignment by actual capture/peak/termination; fixed planned event windows',
        'interpretation':'empirical prediction comparison only; risk UNKNOWN when censored, no deterministic admission'}
    write(out/'score.json',result);return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--predictions',type=Path,required=True);p.add_argument('--packed',type=Path,required=True)
    p.add_argument('--measurement',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=score(a.predictions,a.packed,a.measurement,a.output);print(json.dumps({k:{x:v[x] for x in ['risk_comparison','position_norm_m','peak_abs_error_deg']} for k,v in r['models'].items()}))

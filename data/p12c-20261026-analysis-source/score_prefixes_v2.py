#!/usr/bin/env python3
"""Score stored frozen predictions; prefix arrays and denominators, never fits or flies."""
import json,sys
from pathlib import Path
from collections import Counter
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p11.models import tilt

def crossing(t,x,limit,complete):
 hit=np.flatnonzero(x>limit)
 if len(hit):
  k=int(hit[0]);return {'state':'FAILURE','sampled_bracket_profile_s':[None if k==0 else float(t[k-1]),float(t[k])]}
 return {'state':'SUCCESS' if complete else 'UNKNOWN','sampled_bracket_profile_s':None}

def main(out):
 out=out.resolve()
 if out.exists():raise FileExistsError(out)
 out.mkdir(parents=True);allrows=json.load(open(R/'data/p12c-20261026-preparation/protocol.json'))['rows'];records=[]
 for row in allrows:
  parent=R/'data/p12c-20261026-development'/row['id'];a=parent/'analysis'
  if not (parent/'result.json').exists():continue
  obs=dict(np.load(a/'packed/measurement.npz'));plan=json.load(open(a/'packed/prediction-input.json'))['plan'];m=json.load(open(a/'measured/measurement.json'));scores=json.load(open(a/'score/score.json'))['models'];meta=json.load(open(a/'prediction/prediction.json'))['models'];tt=obs['profile_s'];theta=np.array([tilt(q) for q in obs['attitude']]);start=plan['common_first_gap_profile_s'];end=plan['horizon_profile_s'];eligible=(tt>=start)&(tt<=end);obase=float(np.interp(start,tt,obs['position'][:,2]))
  for name,s in scores.items():
   trace=np.load(a/'prediction'/f'{name}.npz')['trace'];good=np.isfinite(trace).all(axis=1);stop=meta[name].get('stop')
   if stop and stop.get('reason')=='NUMERICAL_UNCERTAIN':good &= trace[:,0]<stop['profile_s']
   bad=np.flatnonzero(~good);n=int(bad[0]) if len(bad) else len(trace);tr=trace[:n];kt=tr[:,0];common=eligible&(tt>=kt[0])&(tt<=kt[-1]);t=tt[common];pred=np.column_stack([np.interp(t,kt,tr[:,j]) for j in range(1,tr.shape[1])]);hbase=float(np.interp(start,kt,tr[:,3]));pe=np.linalg.norm(pred[:,41:44]-obs['position'][common],axis=1);ve=np.linalg.norm(pred[:,44:47]-obs['velocity'][common],axis=1);te=abs(pred[:,6]-theta[common]);le=abs((pred[:,2]-hbase)-(obs['position'][common,2]-obase));arrays={'profile_s':t,'prefix_position_error_m':np.maximum.accumulate(pe),'prefix_velocity_error_m_s':np.maximum.accumulate(ve),'prefix_tilt_error_deg':np.maximum.accumulate(te),'prefix_LP_loss_error_m':np.maximum.accumulate(le)};path=out/f"{row['id']}-{name}.npz";np.savez_compressed(path,**arrays)
   ps=(kt>=start)&(kt<=end);B=plan['full_source_windows_profile_s'][1 if row['family']=='F4' else 2][0]-.004;j=int(np.argmin(abs(tt-B)));pj=int(np.argmin(abs(kt-B)));records.append({'id':row['id'],'class':row['class'],'on':row['observe'],'model':name,'split':'preparation_no_formal_holdout','risk':s['risk'],'tilt_peak_abs_error_deg':s['peak_abs_error_deg'],'tilt_point_error':s['tilt_error_deg'],'first_observed_controller_cache_crossing':{'tilt':crossing(tt[eligible],theta[eligible],45,not m['censored']),'height':crossing(tt[eligible],obs['position'][eligible,2]-obase,1,not m['censored'])},'first_predicted_crossing':{'tilt':crossing(kt[ps],tr[ps,7],45,s['full_prediction']),'height':crossing(kt[ps],tr[ps,3]-hbase,1,s['full_prediction'])},'B_before_prediction_diagnostic':{'reached':bool(tt[-1]>=B and not (m.get('failure') and B>float(tt[-1]))),'observed_profile_s':float(tt[j]),'predicted_profile_s':float(kt[pj]),'observed_LP_loss_m':float(obs['position'][j,2]-obase),'predicted_LP_loss_m':float(tr[pj,3]-hbase),'observed_LP_W_m_s':float(obs['velocity'][j,2]),'predicted_W_m_s':float(tr[pj,6]),'history_after_l2_error':float(np.linalg.norm(tr[pj,12:28]-obs['h_after'][j])),'action_after_l2_error':float(np.linalg.norm(tr[pj,8:12]-obs['action'][j])),'history_scope':'h/action after-update at nearest common absolute task time; mode/time mismatch retained, not strict paired hidden-before','warning':'if not reached B fields are not accepted as B state; source B index2 F2/index1 F4, minus4ms fixed pre-event point'},'prefix_arrays':str(path.relative_to(R)),'prefix_final_max':{k:float(v[-1]) for k,v in arrays.items() if k!='profile_s'},'event_windows':s['event_windows']})
 aggregate={}
 for name in sorted({r['model'] for r in records}):
  rs=[r for r in records if r['model']==name];axes={}
  for axis in ['tilt','height','task']:
   axes[axis]={'flight_records':len(rs),'classification_eligible':sum(r['risk']['classification_eligible'][axis] for r in rs),'full_trajectory_eligible':sum(r['risk']['full_trajectory_eligible'][axis] for r in rs),'comparisons':dict(Counter(r['risk']['comparisons'][axis] for r in rs))}
  aggregate[name]=axes
 (out/'summary.json').write_text(json.dumps({'schema':'p12c-frozen-model-prefix-scores-1','independent_flight_records':len({r['id'] for r in records}),'formal_holdout_records':0,'models_per_record':7,'models_or_overlapping_event_windows_are_not_independent_flights':True,'aggregate':aggregate,'records':records},indent=2)+'\n');print('SCORED',len(records),'model outputs for',len({r['id'] for r in records}),'preparation flights; no formal')
if __name__=='__main__':main(Path(sys.argv[1]))

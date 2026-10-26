from analysis_paths_v1 import analysis_dir
"""Full-prefix physical/controller prediction diagnostics; never changes scores."""
import sys,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'));sys.path.insert(0,str(Path(__file__).parent))
from p12c.features import load
from p11.models import tilt
from p9_model import write,sha
from record_review_v3 import json_plain,crossing

def stats(x):
 x=np.asarray(x)
 return {'rows':len(x),'rmse':float(np.sqrt(np.mean(x*x))),'max_abs':float(max(abs(x))),'p95_abs':float(np.quantile(abs(x),.95))} if len(x) else None

def process(target,ar,out):
 out.mkdir(parents=True,exist_ok=False);a=analysis_dir(target);d=load(target/'run',a);doc=json.load(open(a/'packed-physical/prediction-input.json'));m=json.load(open(a/'measured/measurement.json'));e=json.load(open(ar/'events/event-states.json'));phy=dict(np.load(ar/'physics.npz'));t=d['t'];stop=e['valid_end_s'];use=(t>=0)&(t<=stop);ix=np.flatnonzero(use);targetp=d['target_p'];targetv=d['target_v'];domain={}
 tests={'target_horizontal_norm26':np.linalg.norm(targetp[:,:2],axis=1)<=26,'target_velocity_norm8':np.linalg.norm(targetv,axis=1)<=8,'hidden_before_bound1':np.max(abs(d['h_before']),axis=1)<=1,'hidden_after_bound1':np.max(abs(d['h_after']),axis=1)<=1,'previous_bound1':np.max(abs(d['previous']),axis=1)<=1,'action_bound1':np.max(abs(d['action']),axis=1)<=1,'history_mean_bound1':np.max(abs(d['mean']),axis=1)<=1,'LP_sample_age24ms':(t==t)&((d['sample_us'].astype(np.int64)-d['lp_sample'].astype(np.int64))<=24000),'att_sample_age24ms':(d['sample_us'].astype(np.int64)-d['att_sample'].astype(np.int64))<=24000}
 for k,v in tests.items():
  bad=ix[~v[ix]];domain[k]={'recorded_projection':'PASS' if not len(bad) else 'OUTSIDE','first_exit_profile_s':None if not len(bad) else float(t[bad[0]])}
 age={}
 for clock in ['sample_us','native_us']:
  for src in ['lp_sample','att_sample']:
   v=d[clock].astype(np.int64)-d[src].astype(np.int64);age[clock+'-'+src+'_us']=[int(v[ix].min()),int(v[ix].max())]
 pred={};truth_angle=np.array([tilt(q) for q in d['attitude']]);B=doc['plan']['full_source_windows_profile_s'][1][0];bi=max(0,int(np.searchsorted(t,B,side='right')-1));bt=float(t[bi]);plannedA=doc['plan']['full_source_windows_profile_s'][0][0];baseidx=max(0,int(np.searchsorted(t,0,side='right')-1));H0=-d['position'][baseidx,2]
 for name in ['M3','M4','M5']:
  tr=np.load(a/f'prediction/{name}.npz')['trace'];tr=tr[np.isfinite(tr).all(axis=1)];pt=tr[:,0];sel=ix[(t[ix]>=pt[0])&(t[ix]<=pt[-1])];tt=t[sel];interp=lambda j,ts=tt:np.interp(ts,pt,tr[:,j]);errors={'tilt_deg':stats(interp(7)-truth_angle[sel]),'LP_cache_H_m':stats(-interp(44)+d['position'][sel,2]),'LP_cache_W_m_s':stats(interp(47)-d['velocity'][sel,2]),'predicted_plant_H_vs_LP_H_m':stats(-interp(3)+d['position'][sel,2]),'predicted_plant_W_vs_LP_W_m_s':stats(interp(6)-d['velocity'][sel,2]),'hidden_l2':stats(np.linalg.norm(np.column_stack([interp(j) for j in range(12,28)])-d['h_after'][sel],axis=1))}
  initial_pred_H=-float(np.interp(0,pt,tr[:,3]));pred_loss=initial_pred_H+tr[:,3];obs_loss=H0+d['position'][use,2]
  z={'common_prefix_s':[float(tt[0]),float(tt[-1])],'errors':errors,'first_predicted_task0_LPplant_D1_witness':crossing(pt,pred_loss,1),'first_observed_task0_LP_D1_witness':crossing(t[use],obs_loss,1),'height_witness_scope':'extra task0 cumulative diagnostic; canonical frozen scoring retains A-window LP baseline separately','compute_s':json.load(open(a/'prediction/prediction.json'))['models'][name]['compute_s'],'B_before':{'status':'NOT_REACHED' if B>stop else ('UNKNOWN_PREDICTION_PREFIX_ENDED' if not(pt[0]<=bt<=pt[-1]) else 'COVERED')}}
  if z['B_before']['status']=='COVERED':
   z['B_before'].update(planned_B_profile_s=B,evaluated_profile_s=bt,LP_cache_H_error_m=float(-interp(44,bt)+d['position'][bi,2]),LP_cache_W_error_m_s=float(interp(47,bt)-d['velocity'][bi,2]),hidden_l2=float(np.linalg.norm(np.array([interp(j,bt) for j in range(12,28)])-d['h_after'][bi])),action_l2=float(np.linalg.norm(np.array([interp(j,bt) for j in range(8,12)])-d['action'][bi])))
  if name=='M5':
   tp=phy['t'];selp=(tp>=max(0,pt[0]))&(tp<=min(stop,pt[-1]));ts=tp[selp];z['errors'].update(COM_H_m=stats(-interp(52,ts)-phy['HC'][selp]),COM_W_m_s=stats(interp(53,ts)-phy['W'][selp]));j=max(0,int(np.searchsorted(tp,bt,side='right')-1))
   if z['B_before']['status']=='COVERED':z['B_before'].update(COM_H_error_m=float(-interp(52,bt)-phy['HC'][j]),COM_W_error_m_s=float(interp(53,bt)-phy['W'][j]),COM_L_error_m=float(interp(52,bt)-np.interp(0,pt,tr[:,52])-phy['LC'][j]),filter_error_l2_rad_s=float(np.linalg.norm(np.array([interp(k,bt) for k in range(54,58)])-d['exec_filter_after'][bi])))
  pred[name]=z
 # Descriptive recovery-band process: no new classification/exclusion or dwell.
 rec=[]
 for ev in e['events']:
  if ev.get('resume_status')!='READ_AND_FRESH_CONFIRMED':rec.append({'event':ev['label'],'status':ev.get('resume_status','NOT_REACHED')});continue
  begin=ev['resume_profile_s'];end=B if ev['label']=='A' and B>begin else stop;sel=(phy['t']>=begin)&(phy['t']<=end);rr=np.flatnonzero(sel);inside=abs(phy['W'][rr])<=.1;first=np.flatnonzero(inside);outside=np.flatnonzero(~inside);stable=None
  if len(rr) and inside[-1]:stable=float(phy['t'][rr[0 if not len(outside) else outside[-1]+1]]-begin)
  rec.append({'event':ev['label'],'interval_profile_s':[begin,end],'direct_COM_W_at_resume_m_s':None if not len(rr) else float(phy['W'][rr[0]]),'first_entry_abs_W_le_0.1_s':None if not len(first) else float(phy['t'][rr[first[0]]]-begin),'after_last_exit_abs_W_le_0.1_until_window_end_s':stable,'meaning':'descriptive frozen meaningful0.1m/s band, no fitted dwell, not joint-settling or full safety certificate'})
 payload={'schema':'p13-time-process-1','id':target.name,'component_scores_unchanged':True,'full_prefix':pred,'sampled_history_target_domain':domain,'cache_ages_two_clocks':age,'physical_recovery_bands':rec,'original_joint_recovery_final_capture':m['joint_recovery_after_final_capture'],'physical_initial_known_not_exact_snapshot':True,'source_sha256':sha(Path(__file__))}
 write(out/'time-process.json',json_plain(payload));return payload
if __name__=='__main__':process(Path(sys.argv[1]),Path(sys.argv[2]),Path(sys.argv[3]))

#!/usr/bin/env python3
"""Old heldout miss is NOW SEEN diagnostic only; actual future inputs never scored as prediction."""
from pathlib import Path
import json,sys,numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p12c.features import load
from p11.models import plant,tilt
from p11.score import so3
from p9_model import write,sha
P=R/'data/p12-cont-20261026-formal/b2-ph1-AB';A=P/'analysis';O=R/'data/p12b-20261026-delivery/old-miss-diagnostic'
if O.exists():raise FileExistsError(O)
O.mkdir();d=load(P/'run',A);doc=json.load(open(A/'packed/prediction-input.json'));init=doc['initial'];plan=doc['plan'];models=json.load(open(R/'data/p12-cont-20261026-freeze/models/models.json'));m=models['M2'];trace=np.load(A/'prediction/M4.npz')['trace'];meta=json.load(open(A/'prediction/prediction.json'))['models']['M4'];score=json.load(open(A/'score/score.json'))['models']['M4'];start=plan['common_first_gap_profile_s'];end=plan['nominal_horizon_profile_s'];window=(d['t']>=start)&(d['t']<=end);angles=np.array([tilt(q) for q in d['attitude']]);i0=int(np.flatnonzero(d['sample_us']==init['sample_us'])[0]);roll={};summaries={}
for name in ['actual_filter','actual_joint']:
 p=np.array(init['position']);v=np.array(init['velocity']);q=np.array(init['attitude']);w=np.array(init['omega']);rows=[]
 for k in range(i0,len(d['t'])):
  if k>i0:
   inputs=d['exec_filter_after'][k-1] if name=='actual_filter' else abs(d['exec_scaled_joint'][k-1]);p,v,q,w,_=plant(p,v,q,w,inputs,m)
  rows.append(np.r_[d['t'][k],p,v,q,w,tilt(q)])
 a=np.asarray(rows);roll[name]=a;valid=(a[:,0]>=start)&(a[:,0]<=end);jj=np.arange(i0,len(d['t']))[valid]
 summaries[name]={'known_future_actuator_input':True,'point_peak_deg':float(a[valid,-1].max()),'tilt_RMSE_to_controller_cached_att_deg':float(np.sqrt(np.mean((a[valid,-1]-angles[jj])**2))),'position_RMSE_to_estimator_cache_m':float(np.sqrt(np.mean((a[valid,1:4]-d['position'][jj])**2))),'diagnosis_scope':'single initial reset then free empirical body model with actual future execution inputs; not autonomous forecast or a causal flight intervention'}
# Reset only for one-step conditional model residual diagnostics. Cache ages remain observed.
one=[]
for k in range(i0,len(d['t'])-1):
 p,v,q,w,acc=plant(d['position'][k],d['velocity'][k],d['attitude'][k],d['omega'][k],d['exec_filter_after'][k],m);one.append(np.r_[d['t'][k+1],p-d['position'][k+1],v-d['velocity'][k+1],tilt(q)-angles[k+1],so3(q[None],d['attitude'][k+1,None])[0],d['sample_us'][k+1]-d['lp_sample'][k+1]])
one=np.asarray(one);native=json.load(open(A/'native/native-audit.json'));captures=[c for c in native['captures'] if not c['activation']];pred_events=meta['target_events'];timing=[]
for c,e in zip(captures,pred_events):timing.append({'actual_sample_us':c['sample_us'],'predicted_sample_us':e['sample_us'],'actual_minus_predicted_us':c['sample_us']-e['sample_us'],'actual_phase':c['phase'],'source_guard_age_us':c['guard_age_us']})
first=np.flatnonzero(window&(angles>45));cross=None
if len(first):
 k=int(first[0]);cross={'last_observed_nonfailed_profile_s':float(d['t'][max(0,k-1)]),'first_observed_failed_profile_s':float(d['t'][k]),'controller_cache_angle_deg':float(angles[k]),'scope':'sampled controller attitude crossing bracket; frozen full-topic outcome retained separately'}
seq=[]
for label,a,b in [('pre_A',start-.5,start),('A_and_resume_to_B',start,plan['full_source_windows_profile_s'][1][0]),('after_B',plan['full_source_windows_profile_s'][1][0],end)]:
 sel=(d['t']>=a)&(d['t']<b);pred=np.interp(d['t'][sel],trace[:,0],trace[:,7]);err=pred-angles[sel];seq.append({'segment':label,'rows':int(sel.sum()),'tilt_abs_error_max_deg':float(abs(err).max()),'signed_tilt_error_mean_deg':float(err.mean())})
np.savez_compressed(O/'controlled-replays.npz',**roll,one_step=one)
obs=json.load(open(A/'observation/observation.json'));execution=json.load(open(A/'execution/execution.json'));initial_index=i0
result={'schema':'p12b-old-miss-diagnostic-1','old_case':'b2-ph1-AB','now_seen_material':True,'original_frozen_score_unchanged':{'tilt':score['risk_comparison'],'height':score['height_risk_comparison'],'task_OR':score['task_risk_comparison'],'M4_peak_deg':score['tilt_peak_deg'],'observed_controller_peak_deg':score['observed_tilt_peak_deg'],'frozen_full_topic_peak_deg':json.load(open(A/'measured/measurement.json'))['whole']['max_tilt_deg']},'first_sampled_tilt_crossing':cross,'initial_interfaces':{'sample_us':init['sample_us'],'LP_position_vs_world_pose_m':(d['position'][i0]-d['truth_pv'][i0,:3]).tolist(),'held_truth_age_us':int(d['sample_us'][i0]-d['truth_pv_sample'][i0]),'filter_initial':'actual last completed before initial cutoff; not steady command','unobserved_initial':'full solver/transport/EKF state not snapshotted'},'mode_timing_comparison':timing,'error_growth':seq,'known_input_neural_replay':{'status':obs['status'],'single_step':obs['single_step'],'continuous':obs.get('continuous_replay')},'known_command_execution_replay':{'status':execution['status'],'maximum_filter_error_rad_s':max(r['continuous_max_rad_s'] for r in execution['motors'].values())},'controlled_body_replays':summaries,'filter_vs_actual_joint_input_plant_replay_max_tilt_difference_deg':float(abs(roll['actual_filter'][:,-1]-roll['actual_joint'][:,-1]).max()),'physical_gravity':9.8,'unchanged_predictor_gravity':9.80665,'attribution':'known-input network/target/filter calculations are accurate; future actual actuator-input body replays and one-step cache residuals are diagnostics only. Remaining plant/estimator/cache/delivery feedback cannot be uniquely causally separated; task OR agreement does not remove tilt miss. No re-fit, new candidate, or claimed improvement.','inputs_sha256':{'packed':sha(A/'packed/prediction-input.json'),'prediction_M4':sha(A/'prediction/M4.npz'),'score':sha(A/'score/score.json')}}
write(O/'diagnostic.json',result);print(json.dumps({'original':result['original_frozen_score_unchanged'],'mode_timing':timing,'growth':seq,'body':summaries,'filter_joint_delta_deg':result['filter_vs_actual_joint_input_plant_replay_max_tilt_difference_deg']},indent=2))

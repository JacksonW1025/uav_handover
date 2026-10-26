#!/usr/bin/env python3
"""All-record, all-prefix candidate-domain audit; unobserved physical fields stay UNKNOWN."""
import json,sys,importlib.util
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p12c.features import load
from p12c_platform.accept import task_features
from p12.execution import DTYPE
from p11.models import tilt

def check(parent,out,cohort,solver_npz=None):
 out.mkdir(exist_ok=False);d,plan,m,end=task_features(parent);idx=np.flatnonzero((d['t']>=0)&(d['t']<=end));t=d['t'][idx];H=-d['truth_pv'][idx,2];theta=np.array([tilt(q) for q in d['truth_q'][idx]]);v=np.linalg.norm(d['truth_pv'][idx,3:6],axis=1);omega=abs(d['omega'][idx]).max(axis=1);lp_age=d['sample_us'][idx]-d['lp_sample'][idx];att_age=d['sample_us'][idx]-d['att_sample'][idx];obs={'H_pose_point':(H>=.7)&(H<=8),'theta_pose_point':theta<=50,'callback_velocity_proxy':v<=8,'controller_gyro_proxy':omega<=8,'controller_cache_age':(lp_age>=0)&(lp_age<=24000)&(att_age>=0)&(att_age<=24000),'hidden_previous_mean_boxes':(abs(d['h_before'][idx]).max(axis=1)<=1)&(abs(d['previous'][idx]).max(axis=1)<=1)&(abs(d['mean'][idx]).max(axis=1)<=1)};ok=np.logical_and.reduce(list(obs.values()));bad=np.flatnonzero(~ok);epoch=float(d['run_wall_ns'][0]-d['t'][0]*1e9);motor=[]
 for i in range(4):
  e=np.fromfile(parent/f'run/gz-motor/execution-p12-{i}.bin',DTYPE);pt=(e['end_ns'].astype(float)-epoch)/1e9;e=e[(pt>=0)&(pt<=end)];good=(e['command']>=0)&(e['command']<=1000)&(e['filter_before']>=0)&(e['filter_before']<=1000)&(e['filter_after']>=0)&(e['filter_after']<=1000)&(abs(e['scaled_joint'])<=1100)&(abs(e['dt']-.004)<1e-12);motor.append({'motor':i,'physics_steps':len(e),'all_recorded_domain_bounds':bool(good.all()),'command_range_rad_s':[float(e['command'].min()),float(e['command'].max())],'filter_range_rad_s':[float(e['filter_before'].min()),float(e['filter_after'].max())],'joint_scaled_abs_max_rad_s':float(abs(e['scaled_joint']).max()),'first_violation_step':None if good.all() else int(np.flatnonzero(~good)[0])})
 solver=None
 if solver_npz is not None:
  z=dict(np.load(solver_npz));sel=(z['sim_us']+4000>=d['sample_us'][idx[0]])&(z['sim_us']+4000<=d['sample_us'][idx[-1]]);solver={'source':'old FULL solver rows, not just servo-only subset; sim_us+4000 matches motor/IMU destination physical step','rows_in_task':int(sel.sum()),'free_joint_abs_max_rad_s':float(abs(z['free'][sel]).max()),'position_abs_max_rad':float(abs(z['position'][sel]).max()),'system_dimensions':sorted(set(z['n'][sel].tolist())),'all_joint_modes':sorted(set(z['mode'][sel].tolist())),'all_forces_unbounded_in_task':bool(np.all(~z['finite_impulse_limits'][sel])),'free_domain_at_observed_solver_calls':bool(np.all(abs(z['free'][sel])<=110)),'scope':'posthoc old physical-step values; no future invariant or new-record free-velocity observation'}
 unknown=[{'field':'instantaneous physical COM/body velocity','why':'only callback finite difference and LP delayed estimate; original pose physical time not retained'},{'field':'physical angular velocity / full rigid state between pose callbacks','why':'controller gyro is filtered/cached; truth angular topic is Euler finite difference, not physical body twist'},{'field':'continuous H/theta membership between callbacks','why':'sampled poses satisfy candidate bounds but future acceleration/integration and measurement-delay error bounds absent'},{'field':'new-record pre-solve free velocity and unwrapped joint angle/constraint mode','why':'heavy solver intentionally OFF; old source/step audit cannot fill new fields'},{'field':'future solver DeltaA/eta and body/cache invariant set','why':'posthoc matrix accuracy cannot establish all future rounding/feedback bounds'}]
 np.savez_compressed(out/'all-prefix-domain.npz',profile_s=t,observed_projection_ok=ok,**obs)
 doc={'schema':'p12c-domain-membership-1','case':parent.name,'cohort':cohort,'full_task_recorded':not m['censored'],'valid_task_interval_s':[float(t[0]),float(t[-1])],'observed_projection':'PASS' if ok.all() and all(r['all_recorded_domain_bounds'] for r in motor) else 'EXIT_OBSERVED','first_observed_projection_exit_profile_s':None if not len(bad) else float(t[bad[0]]),'first_actual_domain_status_unknown_profile_s':float(t[0]),'actual_finite_domain':'UNKNOWN_FROM_INITIAL_PHYSICAL_STATE_AND_CONTINUOUS_MEMBERSHIP','observable_ranges':{'H_pose_m':[float(H.min()),float(H.max())],'theta_pose_deg_max':float(theta.max()),'callback_velocity_norm_m_s_max':float(v.max()),'controller_gyro_component_max':float(omega.max()),'cache_ages_max_us':[int(lp_age.max()),int(att_age.max())]},'physics_motor':motor,'old_solver_full_task':solver,'unobservable_or_unproved':unknown,'case_excluded':False,'A4':'NOT_PROVEN_EXCLUDED'};(out/'membership.json').write_text(json.dumps(doc,indent=2)+'\n');return doc

def main(out):
 if out.exists():raise FileExistsError(out)
 out.mkdir(parents=True);rows=[]
 for r in json.load(open(R/'data/p12c-20261026-preparation/protocol.json'))['rows']:
  p=R/'data/p12c-20261026-development'/r['id']
  if (p/'result.json').exists():rows.append(check(p,out/r['id'],'new preparation'))
  else:rows.append({'case':r['id'],'actual_finite_domain':'NO_RECORD_NOT_STARTED','case_excluded':False})
 for s in sorted((R/'data/p12b-20261026-preparation-v2/solver-recheck').glob('*/solver-rows.npz')):
  p=R/'data/p12b-20261026-development-v2'/s.parent.name;rows.append(check(p,out/('old-'+p.name),'old source solver evidence whole task',s))
 p=R/'data/p12-cont-20261026-formal/b2-ph1-AB';rows.append(check(p,out/'old-heldout-tilt-miss','old frozen tilt miss whole task'))
 original=json.load(open(R/'data/p12b-20261026-delivery/old-miss-diagnostic-v2/scope-review.json'));free=np.load(R/'data/p12b-20261026-delivery/old-miss-diagnostic-v2/controlled-replays.npz');oldexits={}
 for key in ['actual_filter','actual_joint']:
  x=free[key];bad=(x[:,-1]>45)|(abs(x[:,11:14]).max(axis=1)>8)|(np.linalg.norm(x[:,1:3],axis=1)>10)|(-x[:,3]>8);hit=np.flatnonzero(bad);j=int(hit[0]) if len(hit) else None;oldexits[key]={'first_stopping_envelope_exit_profile_s':None if j is None else float(x[j,0]),'at_exit_tilt_deg':None if j is None else float(x[j,-1]),'at_exit_max_omega':None if j is None else float(abs(x[j,11:14]).max()),'at_exit_horizontal_radius_m':None if j is None else float(np.linalg.norm(x[j,1:3])),'scope':'same source forecast stopping envelope45deg/8rad/s/radius10m/height8m, NOT a proven empirical accuracy domain'}
 forecasts=[]
 for r in json.load(open(R/'data/p12c-20261026-preparation/protocol.json'))['rows']:
  p=R/'data/p12c-20261026-development'/r['id']/'analysis'
  if not (p/'prediction/M4.npz').exists():continue
  tr=np.load(p/'prediction/M4.npz')['trace'];bad=(tr[:,7]>45)|(abs(tr[:,39:42]).max(axis=1)>8)|(np.linalg.norm(tr[:,1:3],axis=1)>10)|(-tr[:,3]>8);meta=json.load(open(p/'prediction/prediction.json'))['models']['M4'];sc=json.load(open(p/'score/score.json'))['models']['M4'];forecasts.append({'id':r['id'],'reported_stop':meta['stop'],'numerical_all_finite':bool(np.isfinite(tr).all()),'source_stopping_envelope_hit_any':bool(bad.any()),'classification':sc['risk']['comparisons'],'max_timewise_tilt_error_deg':sc['tilt_error_deg']['max_abs'],'full_peak_error_deg':sc['peak_abs_error_deg'],'actual_coverage_certificate':False})
 doc={'schema':'p12c-all-target-domain-review-1','actual_records':rows,'formal24':[{'id':r['id'],'actual_finite_domain':'NO_RECORD_NOT_STARTED'} for r in json.load(open(R/'config/p12c-platform.json'))['rows']],'old_controlled_replay_original_scope':original,'old_recomputed_stopping_envelope':oldexits,'new_M4_prefix_connection':forecasts,'conclusion':'No claim that servo subset matrix agreement covers a full failing trajectory. All recorded prefixes inspected; actual physical/domain invariance UNKNOWN from initial state. New numerically complete point forecasts can have14deg timing error while remaining inside a stopping envelope. Old future-input free plant exits before A; this is not a flight causal intervention or autonomous score.','new_SITL':0};(out/'all-records.json').write_text(json.dumps(doc,indent=2)+'\n');print('DOMAIN_REVIEW',len(rows),'rows, physical membership UNKNOWN; oldexits',oldexits)
if __name__=='__main__':main(Path(sys.argv[1]))

#!/usr/bin/env python3
"""Post-stop descriptive supplement; frozen treatments, validity and scores unchanged."""
import json,sys,hashlib
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p9_model import write,sha
from p12c.features import load
from p12.execution import DTYPE
D=R/'data/p12-cont-20261026-delivery-v2';F=R/'data/p12-cont-20261026-formal'
assert not (D/'final-supplement.json').exists()
cases=json.load(open(D/'cases.json'));costs={};execution={};total=0
for ident,c in cases.items():
 p=F/ident;d=load(p/'run',p/'analysis');doc=json.load(open(p/'analysis/packed/prediction-input.json'));end=doc['plan']['nominal_horizon_profile_s'];grid=np.arange(0,end,.004)
 assert d['t'][0]<=0 and d['t'][-1]>=end
 table=np.asarray(doc['plan']['profile']['table']);jt=np.clip(np.floor((grid-doc['plan']['profile']['table_t0_s'])/.004+1e-8).astype(int),0,len(table)-1);j=np.searchsorted(d['t'],grid,side='right')-1;e=np.linalg.norm(d['position'][j]-table[jt,:3],axis=1)
 costs[ident]={'full_task_window_profile_s':[0,end],'coverage':'COMPLETE','tracking_squared_integral_m2s':float(.004*np.sum(e*e)),'tracking_peak_m':float(e.max()),'task_outcome':c['task_outcome']}
 ms={}
 for i,sign in enumerate([1,1,-1,-1]):
  a=np.fromfile(p/f'run/gz-motor/execution-p12-{i}.bin',DTYPE);total+=len(a)
  residual=a['scaled_joint']-sign*a['filter_before'];rep=json.load(open(p/'analysis/execution/execution.json'))['motors'][str(i)]
  ms[str(i)]={'rows':len(a),'turning_direction':sign,'signed_residual_max_abs_rad_s':float(abs(residual).max()),'signed_residual_formula':'scaled_joint - turning_direction * filter_before','initial_filter_rad_s':float(a['filter_before'][0]),'initial_joint_rad_s':float(a['joint'][0]),'continuous_filter_replay_max_rad_s':rep['continuous_max_rad_s'],'thrust_formula_max_N':rep['thrust_magnitude_formula_max_N'],'future_hard_bound':'NOT_PROVEN; empirical finite records only'}
 execution[ident]=ms
phase=json.load(open(D/'extra/event-phase-recovery.json'));captures=[]
for ident,row in phase.items():
 for e in row['events']:
  for c in e.get('capture_details',[]):captures.append({'id':ident,'branch':row['branch'],'mode':c['mode'],'phase':c['phase'],'activation':c['activation'],'guard_age_us':c['guard_age_us'],'horizontal_velocity_input_error_m_s':c['horizontal_velocity_input_error_m_s']})
pre=json.load(open(D/'prestate-diagnostics.json'))
summary={'comparisons':len(pre),'strict_pairs':0,'diagnostic_limit_failures':{k:sum(not r['continuous_diagnostic_pass'][k] for r in pre) for k in pre[0]['continuous_diagnostic_pass']},'discrete_difference_counts':{k:sum(r['discrete'][k]>0 for r in pre) for k in pre[0]['discrete']},'scope':'descriptive fixed-window diagnostics; no assigned outcome excluded or relabeled'}
write(D/'final-supplement.json',{'schema':'p12-cont-final-supplement-1','SITL_starts':0,'full_task_tracking_costs':costs,'execution':execution,'execution_motor_steps':total,'planned_event_captures':captures,'prestate_summary':summary,'repair_sample_window':'all formal engineering logs retained; planned repair capture mode separately verified','posthoc_scope':'source-connection residual diagnostic, fixed full-task metric and completeness bookkeeping; not new primary thresholds/fit/group/validity'})
base=D/'all-raw-derived-history-manifest.json';known={r['path'] for r in json.load(open(base))['files']};added=[]
for folder in (R/'data').glob('p12-cont-*'):
 for p in folder.rglob('*.npz'):
  name=str(p.relative_to(R))
  if name not in known:added.append({'path':name,'bytes':p.stat().st_size,'sha256':sha(p)})
write(D/'raw-manifest-supplement.json',{'base_sha256':sha(base),'added_full_npz':added,'no_deletion_or_decimation':True})
assert sum(c['branch']=='REPAIR' for c in captures)==10
assert all(c['mode']==2 and c['horizontal_velocity_input_error_m_s']==0 for c in captures if c['branch']=='REPAIR')
print('SUPPLEMENT_PASS',total,'motorsteps',len(captures),'planned captures',len(added),'new NPZ paths')

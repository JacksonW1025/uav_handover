#!/usr/bin/env python3
"""Supplemental scoring only: actual prefixes/costs, no fitting or launch."""
import sys,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'));sys.path.insert(0,str(Path(__file__).parent))
from preparation_acceptance import feat
from p12c.features import compare
from p11.models import tilt
from p12.execution import DTYPE
O=R/'data/p12b-20261026-delivery/prefix-and-costs';O.mkdir(exist_ok=False)
valid=[3,5,6,7,8];features={};parents={};tables={};allrows=json.load(open(R/'data/p12b-20261026-preparation-v2/protocol.json'))['rows'];costs={};forecasts=[]
for row in allrows:
 i=row['ordinal'];parent=R/'data/p12b-20261026-development-v2'/row['id'];parents[i]=parent;features[i]=feat(parent);tables[i]=json.load(open(R/'data/p12b-20261026-delivery/event-tables'/row['id']/'event-states.json'))

def crossing(t,v,threshold,complete):
 idx=np.flatnonzero(v>threshold)
 if not len(idx):return {'state':'SUCCESS' if complete else 'UNKNOWN','bracket_s':None,'coverage_end_s':float(t[-1])}
 k=int(idx[0]);return {'state':'FAILURE','bracket_s':[None if k==0 else float(t[k-1]),float(t[k])],'scope':'sampled first-crossing bracket; no claim of continuous-time exact hit'}
for i in valid:
 parent=parents[i];a=parent/'analysis';d=dict(np.load(a/'packed/measurement.npz'));plan=json.load(open(a/'packed/prediction-input.json'))['plan'];start=plan['common_first_gap_profile_s'];end=plan['horizon_profile_s'];meta=json.load(open(a/'prediction/prediction.json'));scores=json.load(open(a/'score/score.json'))['models'];tt=d['profile_s'];angle=np.array([tilt(q) for q in d['attitude']]);obsbase=float(np.interp(start,tt,d['position'][:,2]));observed=(tt>=start)&(tt<=end)
 for model,info in meta['models'].items():
  tr=np.load(a/'prediction'/f'{model}.npz')['trace'];good=np.all(np.isfinite(tr),axis=1);stop=info.get('stop')
  if stop and stop.get('reason')=='NUMERICAL_UNCERTAIN':good &= tr[:,0]<stop['profile_s']
  bad=np.flatnonzero(~good);n=int(bad[0]) if len(bad) else len(tr);tr=tr[:n];kt=tr[:,0];predscope=(kt>=start)&(kt<=end);sel=observed&(tt>=kt[0])&(tt<=kt[-1]);t=tt[sel];pred=np.column_stack([np.interp(t,kt,tr[:,j]) for j in range(1,tr.shape[1])]);height=bool(info.get('height_modelled',True));pbase=float(np.interp(start,kt,tr[:,3]));pe=np.linalg.norm(pred[:,41:44]-d['position'][sel],axis=1);ve=np.linalg.norm(pred[:,44:47]-d['velocity'][sel],axis=1);ae=abs(pred[:,6]-angle[sel]);he=abs((pred[:,2]-pbase)-(d['position'][sel,2]-obsbase));prefix={'profile_s':t,'max_position_error_m':np.maximum.accumulate(pe),'max_velocity_error_m_s':np.maximum.accumulate(ve),'max_tilt_error_deg':np.maximum.accumulate(ae),'max_LP_loss_error_m':np.maximum.accumulate(he)};np.savez_compressed(O/f'{i}-{model}-prefix.npz',**prefix)
  s=scores[model];forecasts.append({'ordinal':i,'id':allrows[i-3]['id'] if False else parent.name,'model':model,'split':'preparation_not_formal','classification':s['risk'],'observed_crossings':{'tilt':crossing(tt[observed],angle[observed],45,True),'height':crossing(tt[observed],d['position'][observed,2]-obsbase,1,True)},'prediction_crossings':{'tilt':crossing(kt[predscope],tr[predscope,7],45,s['full_prediction']),'height':crossing(kt[predscope],tr[predscope,3]-pbase,1,s['full_prediction']) if height else {'state':'UNKNOWN_UNMODELLED'}},'full_prefix_maxima':{k:float(v[-1]) for k,v in prefix.items() if k!='profile_s'},'event_windows':s['event_windows'],'arrays':str((O/f'{i}-{model}-prefix.npz').relative_to(R))})
# Physical cost integrals on separate full valid-task and common AB/repair windows.
for i,parent in parents.items():
 cfg=json.load(open(parent/'run/config.json'));d=features[i];epoch=float(d['run_wall_ns'][0]-d['t'][0]*1e9);end=tables[i]['valid_experiment_end_profile_s'];common_end=min(tables[j]['valid_experiment_end_profile_s'] for j in ([5,7] if i in [5,7] else [6,8] if i in [6,8] else [i]));first=tables[i]['events'][0]['planned_window_profile_s'][0];result={}
 for name,lo,hi in [('valid_task_prefix',0,end),('common_AB_repair',first,common_end)]:
  total={'actual_scaled_joint_square_rad2_s':0.,'consumed_command_total_variation_rad_s':0.,'absolute_thrust_impulse_N_s':0.}
  for motor in range(4):
   e=np.fromfile(parent/f'run/gz-motor/execution-p12-{motor}.bin',DTYPE);tm=(e['end_ns'].astype(np.float64)-epoch)/1e9;sel=(tm>=lo)&(tm<=hi);v=e[sel];t=tm[sel];dt=np.diff(t)
   total['actual_scaled_joint_square_rad2_s']+=float(np.sum((v['scaled_joint'][1:]**2+v['scaled_joint'][:-1]**2)*dt/2));total['consumed_command_total_variation_rad_s']+=float(np.sum(abs(np.diff(v['command']))));total['absolute_thrust_impulse_N_s']+=float(np.sum((abs(v['thrust'][1:])+abs(v['thrust'][:-1]))*dt/2))
  result[name]={'window_s':[lo,hi],'full_task_complete':not tables[i]['censored'],**total,'units_scope':'mechanical proxies, not electrical energy; host/physical step association retained, actual dt integrated'}
 costs[str(i)]={'id':parent.name,**result}
pre={}
for a,b in [(5,7),(6,8)]:
 lo=tables[a]['events'][0]['planned_window_profile_s'][0];pre[f'{a}_vs_{b}']=compare(features[a],features[b],[lo-.5,lo])
(O/'prefixes.json').write_text(json.dumps({'independent_flights':5,'models_per_flight':7,'formal_holdout_flights':0,'scores':forecasts},indent=2)+'\n');(O/'costs-and-covariates.json').write_text(json.dumps({'costs':costs,'pre_A_covariates':pre,'causal_scope':'no strict pairs, no new independent blocks; achieved phase is not a selection variable'},indent=2)+'\n');print('PREFIX_COSTS_COMPLETE no new flight')

#!/usr/bin/env python3
"""Predeclared phase contrasts, repeatability, clocks and prefix diagnostics; no fitting/SITL."""
import argparse,json,sys,itertools
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p9_model import write,sha
from p12c.features import load
F=ROOT/'data/p12-cont-20261026-formal'
def stat(v):
 v=np.asarray(v,dtype=float)
 return {'n':len(v),'mean':float(v.mean()) if len(v) else None,'min':float(v.min()) if len(v) else None,'max':float(v.max()) if len(v) else None}
def witness(t,condition):
 j=np.flatnonzero(condition)
 return {'status':'WITNESSED','first_sample_profile_s':float(t[j[0]]),'previous_sample_profile_s':float(t[max(0,j[0]-1)]),'scope':'first sampled witness; no certified first physical crossing'} if len(j) else {'status':'NO_SAMPLED_WITNESS; success requires full coverage'}
def main(base):
 base=base.resolve();out=base/'extra';out.mkdir(exist_ok=False);(out/'prefix').mkdir();cases=json.load(open(base/'cases.json'));plan=json.load(open(ROOT/'config/p12-cont.json'));clocks={};events={};prefix={};eq=[];phase=[];noise=[]
 for row in plan['rows']:
  name=row['id']
  if name not in cases:continue
  c=cases[name];a=F/name/'analysis';run=F/name/'run';scores=json.load(open(a/'score/score.json'))['models'];d=load(run,a);doc=json.load(open(a/'packed/prediction-input.json'));first=doc['plan']['common_first_gap_profile_s'];end=doc['plan']['nominal_horizon_profile_s'];epoch=d['run_wall_ns'][0]-d['t'][0]*1e9
  clocks[name]=json.load(open(a/'observation/observation.json'))['clock'];event_rows=[]
  for event in c['event_reach']:
   w=event['planned_profile_s'];caps=event['actual_captures'];item={'planned_profile_s':w,'status':event['status'],'resume_read_confirmed':event['resume_read_confirmed'],'capture_details':[]}
   for cap in caps:
    j=np.flatnonzero(d['sample_us']==cap['sample_us']);res=np.flatnonzero(d['read_valid']&(d['t']>=w[1]))
    k=int(j[0]) if len(j) else None;r=int(res[0]) if len(res) else None
    item['capture_details'].append({**cap,'profile_interval_s':[(v-epoch)/1e9 for v in cap['capture_host_interval_ns']],
      'capture_to_resume_sample_s':float((int(d['sample_us'][r])-cap['sample_us'])/1e6) if r is not None else None,
      'capture_to_resume_native_s':float((int(d['native_us'][r])-cap['native_us'])/1e6) if r is not None else None,
      'capture_to_resume_host_s':float(d['t'][r]-(np.mean(cap['capture_host_interval_ns'])-epoch)/1e9) if r is not None else None,
      'restored_after_event':'complete task recovery separately reported; reference reset is not body recovery'})
   event_rows.append(item)
  events[name]={'assigned_phase':row['phase'],'branch':row['branch'],'events':event_rows,'all_captures_including_startup_terminal':c['captures'],'final_recovery':c['measurement']['joint_recovery_after_final_capture']}
  ti=d['t'];tilt=np.degrees(np.arccos(np.clip(1-2*(d['attitude'][:,1]**2+d['attitude'][:,2]**2),-1,1)));sel=(ti>=first)&(ti<=end);t=ti[sel];H=-d['position'][sel,2];Hw=-d['truth_pv'][sel,2];i0=max(0,int(np.searchsorted(ti,0,side='right')-1));hw0=-d['truth_pv'][i0,2];hc0=float(np.interp(first,ti,-d['position'][:,2]))
  prefix[name]={'observed_cached_tilt':witness(t,tilt[sel]>45),'observed_cached_height_loss':witness(t,hc0-H>1),'world_height_loss_from_common_task_start':witness(t,hw0-Hw>1),'observed_complete':not c['censored'],'risk_labels':'scorev2 remains authoritative; sampled cached/GT diagnostics do not relabel frozen raw LP/att task criteria','models':{}}
  if prefix[name]['world_height_loss_from_common_task_start']['status']=='WITNESSED':
   hit=np.flatnonzero(hw0-Hw>1)[0];allj=np.flatnonzero(sel)[hit];previous=np.flatnonzero(d['truth_pv_sample'][:allj]<d['truth_pv_sample'][allj]);prefix[name]['world_height_loss_from_common_task_start']['callback_sample_interval_us']=[int(d['truth_pv_sample'][previous[-1]]) if len(previous) else None,int(d['truth_pv_sample'][allj])]
  for f in (a/'prediction').glob('*.npz'):
   model=f.stem;tr=np.load(f)['trace'][:scores[model]['valid_prediction_prefix_rows']]
   if not len(tr):continue
   mask=(t>=tr[0,0])&(t<=tr[-1,0]);tt=t[mask]
   if not len(tt):continue
   pa=np.interp(tt,tr[:,0],tr[:,7]);ph=np.interp(tt,tr[:,0],-tr[:,3]);ae=abs(pa-tilt[sel][mask]);he=abs(ph-H[mask]);we=abs(ph-Hw[mask]);cachehe=abs(np.interp(tt,tr[:,0],-tr[:,44])-H[mask]);ph0=float(np.interp(first,tr[:,0],-tr[:,3]))
   np.savez_compressed(out/'prefix'/f'{name}-{model}.npz',profile_s=tt,tilt_abs_error_deg=ae,height_proxy_abs_error_m=he,world_height_unaligned_error_m=we,height_cached_prediction_error_m=cachehe,tilt_prefix_max_error_deg=np.maximum.accumulate(ae),height_prefix_max_error_m=np.maximum.accumulate(he))
   prefix[name]['models'][model]={'predicted_tilt':witness(tt,pa>45),'predicted_height_proxy_loss':witness(tt,ph0-ph>1),'common_prefix_tilt_error_deg':stat(ae),'common_prefix_height_proxy_error_m':stat(he),'height_cached_prediction_error_m':stat(cachehe),'independent_world_height_error_m':stat(we),'world_scope':'unadjusted estimator-NED proxy vs world; origin/bias not certified, no post-hoc alignment; no absolute-world safety certificate','prefix_rows':len(tt)}
  m3=np.load(a/'prediction/M3.npz');m4=np.load(a/'prediction/M4.npz');eq.append({'id':name,'numerically_identical_M3_M4':m3.files==m4.files and all(np.array_equal(m3[k],m4[k],equal_nan=True) for k in m3.files),'meaning':'new native window changes common actual initialization; M4 future gate may not alter prediction when all planned captures already after gate'})
 for block in range(1,5):
  family='F4' if block==2 else 'F2'
  for branch in ['A','B','AB','REPAIR','NORMAL']:
   ids={ph:([f'b{block}-ph{ph}-NORMAL0',f'b{block}-ph{ph}-NORMAL1'] if branch=='NORMAL' else [f'b{block}-ph{ph}-{branch}']) for ph in [1,2]};row={'block':block,'family':family,'branch':branch,'ids':ids}
   if not all(n in cases for names in ids.values() for n in names):row['status']='INCOMPLETE_NO_REPLACEMENT'
   else:
    complete=all(not cases[n]['censored'] for names in ids.values() for n in names);row['status']='COMPLETE' if complete else 'CENSORED_FULL_PEAK_NOT_ESTIMABLE'
    row['full_peak_gate2_minus_gate1']={k:float(np.mean([cases[n]['measurement']['whole'][k] for n in ids[2]])-np.mean([cases[n]['measurement']['whole'][k] for n in ids[1]])) if complete else None for k in ['max_tilt_deg','max_altitude_loss_m']}
    row['task_outcomes']={ph:[cases[n]['task_outcome'] for n in names] for ph,names in ids.items()}
   phase.append(row)
  for ph in [1,2]:
   names=[f'b{block}-ph{ph}-NORMAL{k}' for k in [0,1]];row={'block':block,'family':family,'phase':ph,'ids':names}
   if all(n in cases for n in names):row.update(status='COMPLETE',absolute_whole_difference={k:abs(cases[names[0]]['measurement']['whole'][k]-cases[names[1]]['measurement']['whole'][k]) for k in ['max_tilt_deg','max_altitude_loss_m']})
   else:row['status']='INCOMPLETE_NO_SUBSTITUTION'
   noise.append(row)
 aggregate={}
 for family,branch,metric in itertools.product(['F2','F4'],['A','B','AB','REPAIR','NORMAL'],['max_tilt_deg','max_altitude_loss_m']):
  values=[p['full_peak_gate2_minus_gate1'][metric] for p in phase if p['family']==family and p['branch']==branch and p['status']=='COMPLETE'];q=stat(values)
  if len(values)==3:
   se=np.std(values,ddof=1)/np.sqrt(3);q['t2_95_exploratory_interval']=[float(q['mean']-4.302653*se),float(q['mean']+4.302653*se)]
  q['scope']='assigned read-policy total effect including pre-event delivery/cache effects; no achieved-phase filtering; F4 n1 descriptive, no population inference';aggregate[f'{family}/{branch}/{metric}']=q
 for name,value in [('clock-words',clocks),('event-phase-recovery',events),('prefix-errors-witnesses',prefix),('M3-M4-equality',eq),('assigned-phase-contrasts',phase),('assigned-phase-estimates',aggregate),('formal-normal-repeatability',noise)]:write(out/(name+'.json'),value)
 write(out/'prefix-array-manifest.json',{'files':{str(f.relative_to(ROOT)):sha(f) for f in sorted((out/'prefix').glob('*.npz'))},'all_full_arrays_local':True,'no_SITL':True,'no_new_fit':True,'sampling':'all common observed controller reads, no decimation'})
 print('EXTRA_ANALYSIS',len(cases),'valid flights; no new starts/fits')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--analysis',type=Path,required=True);a=p.parse_args();main(a.analysis)

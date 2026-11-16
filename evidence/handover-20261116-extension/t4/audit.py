from pathlib import Path
import sys,json,time,hashlib
import numpy as np
from pyulog import ULog
R=Path('/home/car/uav_handover');P=Path(__file__).parent
sys.path.insert(0,str(R/'tools'))
from output_chain import read_trace
start=time.monotonic();out={'execution_host':'Thor','source':'original ULog and per-motor binaries','gate':[],'delivery':[]}
for run in sorted((R/'data/handover-t4-active-release-20261116').glob('*/flight')):
 p=run/'flight.ulg';u=ULog(str(p),message_name_filter_list=['research_actuator','actuator_motors','research_output','vehicle_attitude','vehicle_local_position','vehicle_land_detected','vehicle_status','raptor_input','raptor_status','research_memory'])
 d={x.name:x.data for x in u.data_list if x.multi_id==0};o=d['research_actuator'];a=d['actuator_motors'];b=d['research_output']
 ev=[json.loads(x) for x in (run/'events.jsonl').read_text().splitlines()]
 bound=next(x['end_bound_px4_us'] for x in ev if x['event']=='handover_requested' and x.get('subject'))
 oi=int(np.flatnonzero((o['owner']==1)&(o['timestamp']>=bound))[0]);pub=int(o['actuator_timestamp'][oi])
 owned={}
 for i in range(len(o['timestamp'])):owned.setdefault(int(o['actuator_timestamp'][i]),[]).append(i)
 smap={}
 for j,t in enumerate(a['timestamp']):
  for i in owned.get(int(t),[]):
   if all(abs(float(o[f'control[{k}]'][i])-float(a[f'control[{k}]'][j]))<1e-6 for k in range(4)):
    smap.setdefault(int(a['timestamp_sample'][j]),set()).add(int(o['owner'][i]))
 ai=np.flatnonzero(a['timestamp']==pub);assert len(ai)==1;first_sample=int(a['timestamp_sample'][ai[0]])
 br={}
 for j,s in enumerate(b['timestamp_sample']):br.setdefault(int(s),[]).append(j)
 case={'run':str(run),'first_publication_us':pub,'first_sample_us':first_sample,'dropouts':len(u.dropouts),'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'motors':[]}
 for file in sorted((run/'gz-motor').glob('*.bin')):
  mid,t,tail=read_trace(file)
  ids=np.flatnonzero((t['sim_us']>=pub)&(t['sim_us']<=pub+100000));rows=[]
  for j in ids:
   sample=int(t['applied_sample_us'][j]);tm=int(t['sim_us'][j]);val=float(t['ref_motor_input'][j])
   matches=[k for k in br.get(sample,[]) if int(b['timestamp'][k])<=tm]
   err=min([abs(val-float(b[f'motor_speed[{mid}]'][k])) for k in matches],default=None)
   assert err==0
   rows.append({'sim_us':tm,'sample_us':sample,'owner':sorted(smap.get(sample,set())),'value':val,'bridge_error':err,'received':int(t['received'][j])})
  first=next(x for x in rows if x['owner']==[1]);expected=next(x for x in rows if x['sim_us']==pub+4000)
  case['motors'].append({'motor':mid,'tail_bytes':tail,'first_N_delay_us':first['sim_us']-pub,'first_N_sample_us':first['sample_us'],'expected_step_owner':expected['owner'],'first_sample_ever_applied':bool(np.any(t['applied_sample_us']==first_sample)),'window':rows,'bin_sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
 end=next(x['end_bound_px4_us'] for x in ev if x['event']=='explore_subject_finished')
 q=d['vehicle_attitude'];mask=(q['timestamp']>=pub)&(q['timestamp']<=end)
 tilt=np.degrees(np.arccos(np.clip(1-2*(q['q[1]'][mask]**2+q['q[2]'][mask]**2),-1,1)))
 lp=d['vehicle_local_position'];lm=(lp['timestamp']>=pub)&(lp['timestamp']<=end)
 land=d['vehicle_land_detected'];vs=d['vehicle_status']
 case['physical']={'max_tilt_deg':float(tilt.max()),'max_loss_m':float(lp['z'][lm].max()-lp['z'][lm][0]),'landed':bool(np.any((land['timestamp']>end)&land['landed'])),'disarmed':bool(np.any((vs['timestamp']>end)&(vs['arming_state']!=2)))}
 case['events']=[x for x in ev if x['event'].startswith('t4_') or x['event'] in ['explore_pre_switch','process_stopped','handover_requested','explore_switch_confirmed']]
 import csv
 case['relay_events']=[x for x in csv.DictReader((run/'relay.csv').open()) if x['event'] not in ['source','forward','held']]
 case['result']=json.loads((run.parent/'result.json').read_text())
 out['delivery'].append(case)
out['wall_s']=time.monotonic()-start
(P/'raw-audit.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'gate_counts':[len(x['transitions']) for x in out['gate']],'delivery':[(x['first_publication_us'],[(m['motor'],m['first_N_delay_us'],m['first_sample_ever_applied']) for m in x['motors']]) for x in out['delivery']],'wall_s':out['wall_s']},indent=2))

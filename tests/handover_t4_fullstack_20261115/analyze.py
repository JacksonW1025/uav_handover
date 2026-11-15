from pathlib import Path
import json,sys,csv,hashlib
import numpy as np
from pyulog import ULog
R=Path(__import__('os').environ['HANDOVER_RESEARCH_ROOT']);A=Path(__file__).parent;B=R/'data/handover-t4-fullstack-20261115';sys.path.insert(0,str(R/'tools'));from output_chain import read_trace
out=[]
for run in sorted(B.glob('*/flight')):
 if not (run.parent/'result.json').exists():continue
 ev=[json.loads(x) for x in (run/'events.jsonl').read_text().splitlines()];result=json.loads((run.parent/'result.json').read_text());u=ULog(str(run/'flight.ulg'));d={x.name:x.data for x in u.data_list if x.multi_id==0};o=d['research_actuator'];a=d['actuator_motors'];b=d['research_output'];req=next(e for e in ev if e['event']=='handover_requested' and e.get('subject'));bound=req['end_bound_px4_us'];ii=np.flatnonzero((o['owner']==1)&(o['timestamp']>=bound));i=int(ii[0]);pub=int(o['actuator_timestamp'][i]);old=int(o['actuator_timestamp'][i-1]);mp={}
 for j in range(len(a['timestamp'])):
  k=np.flatnonzero(o['actuator_timestamp']==a['timestamp'][j]);matches=[int(o['owner'][h]) for h in k if np.max(np.abs(np.array([o[f'control[{n}]'][h] for n in range(4)])-np.array([a[f'control[{n}]'][j] for n in range(4)])))<1e-6]
  if matches:mp.setdefault(int(a['timestamp_sample'][j]),set()).update(matches)
 marker=int(a['timestamp_sample'][np.flatnonzero(a['timestamp']==pub)[0]]);relay=list(csv.DictReader((run/'relay.csv').open()));window=[x for x in relay if x['event'] in ['window_begin','deadline_callback','deadline_monitor','release_latest']];row={'case':run.parent.name,'result':result,'request_native_lower':bound,'first_N_publication':pub,'first_N_sample':marker,'last_C_publication':old,'relay_window':window,'motors':[],'dropouts':len(u.dropouts),'early_owner_records':[{k:float(v[j]) for k,v in o.items()} for j in np.flatnonzero((o['timestamp']>=pub-16000)&(o['timestamp']<=pub+60000))]}
 for file in sorted((run/'gz-motor').glob('*.bin')):
  mid,t,tail=read_trace(file);sel=np.flatnonzero((t['sim_us']>=pub-12000)&(t['sim_us']<=pub+100000));rows=[]
  for j in sel:
   sid=int(t['applied_sample_us'][j]);owners=sorted(mp.get(sid,set()));bk=np.flatnonzero((b['timestamp_sample']==sid)&(b['timestamp']<=int(t['sim_us'][j])));val=float(t['ref_motor_input'][j]);err=min([abs(val-float(b[f'motor_speed[{mid}]'][h])) for h in bk],default=None);rows.append({'sim_us':int(t['sim_us'][j]),'sample_us':sid,'owners':owners,'input':val,'bridge_value_error':err,'received':int(t['received'][j]),'step_wall_ns':int(t['step_wall_ns'][j])})
  first=next((x for x in rows if x['sim_us']>=pub and x['owners']==[1]),None);expected=next(x for x in rows if x['sim_us']>=pub+4000);row['motors'].append({'motor':mid,'tail_bytes':tail,'first_N':first,'first_expected_step':expected,'rows':rows})
 end=next(e['end_bound_px4_us'] for e in ev if e['event']=='explore_subject_finished');land=d['vehicle_land_detected'];status=d['vehicle_status'];q=d['vehicle_attitude'];mask=(q['timestamp']>=pub)&(q['timestamp']<=end);qx=q['q[1]'][mask];qy=q['q[2]'][mask];tilt=np.degrees(np.arccos(np.clip(1-2*(qx*qx+qy*qy),-1,1)));lp=d['vehicle_local_position'];lm=(lp['timestamp']>=pub)&(lp['timestamp']<=end);z=lp['z'][lm];row['physical']={'max_tilt_deg':float(tilt.max()),'loss_m':float(z.max()-z[0]),'landed_after_subject':bool(np.any((land['timestamp']>end)&(land['landed']==1))),'disarmed_after_subject':bool(np.any((status['timestamp']>end)&(status['arming_state']!=2)))};row['process_stops']=[e for e in ev if e['event']=='process_stopped'];row['source_ulog_sha256']=hashlib.sha256((run/'flight.ulg').read_bytes()).hexdigest();out.append(row);print(row['case'],pub,marker,[x['first_N']['sim_us']-pub for x in row['motors']],row['physical'])
(A/'evidence.json').write_text(json.dumps(out,indent=2)+'\n')

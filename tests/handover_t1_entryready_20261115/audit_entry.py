import os
import sys,json,pathlib,numpy as np
from pyulog import ULog
ROOT=pathlib.Path(os.environ['HANDOVER_RESEARCH_ROOT']);sys.path.insert(0,str(ROOT/'tools'))
from output_chain import read_trace
from analyze import clean
base=pathlib.Path(__file__).resolve().parent;f=base/'N/flight';u=ULog(str(f/'flight.ulg'));d={x.name:x.data for x in u.data_list if x.multi_id==0};p=d['research_p11'];o=d['research_actuator'];m=d['research_memory'];sends=[json.loads(s) for s in (f/'explore-setpoints.jsonl').read_text().splitlines()]
a=int(np.flatnonzero(p['activation']==1)[-1]);t=int(p['timestamp'][a]);native=int(np.flatnonzero((p['timestamp']>=t)&(p['native_step']==1))[0]);mi=int(np.flatnonzero((m['timestamp']==t)&(m['kind']==2))[0]);oi=int(np.flatnonzero((o['actuator_timestamp']>=t)&(o['owner']==1))[0]);pub=int(o['actuator_timestamp'][oi]);out=dict(activation_us=t,first_native_inference_us=int(p['timestamp'][native]),first_publication_us=pub,first_inference_stale=int(p['stale'][native]),first_inference_last_valid_read_us=int(p['last_valid_read_us'][native]),first_inference_reference_age_us=int(p['timestamp'][native]-p['last_valid_read_us'][native]),entry_mode=int(m['entry_mode'][mi]),entry_gru_max_abs_difference=float(max(abs(m[f'gru[{i}]'][mi]-m[f'gru_before_entry[{i}]'][mi]) for i in range(16))),entry_previous_action=[float(m[f'previous_action[{i}]'][mi]) for i in range(4)],entry_classic_action=[float(m[f'classic_action[{i}]'][mi]) for i in range(4)],matching_sends=[],motors={})
payload=np.array([p[f'network_target_position[{j}]'][native] for j in range(3)]+[p[f'network_target_velocity[{j}]'][native] for j in range(3)],dtype=np.float32);out['first_inference_payload_pv']=payload.tolist()
for s in sends:
 if np.array_equal(np.array(s['position']+s['velocity'],dtype=np.float32),payload):out['matching_sends'].append(s)
pre=a-1;out['prior_p11']={k:clean(p[k][pre]) for k in ['timestamp','last_valid_read_us','stale','active','subscription_updated','external_valid'] if k in p}
meas=json.loads((base/'analysis-v1/measurements.json').read_text())['N'];hi=meas['attitude_budget']['35.0']['first_crossing_native_us']
if hi is None:hi=meas['end_native_us']
lo=hi-2000000;wm=(p['timestamp']>=lo)&(p['timestamp']<=hi);out['late_window']=dict(start_us=lo,end_us=hi,stale=int(p['stale'][wm].sum()),native_steps=int(p['native_step'][wm].sum()),activation=int(p['activation'][wm].sum()),max_ref_age_us=int((p['timestamp'][wm]-p['last_valid_read_us'][wm]).max()))
for j in range(4):
 mid,z,tail=read_trace(f/'gz-motor'/f'motor-{j}.bin');zz=z[(z['sim_us']>=lo)&(z['sim_us']<=hi)];ii=np.searchsorted(o['actuator_timestamp'],zz['applied_sample_us'],side='right')-1;first=int(np.flatnonzero(z['applied_sample_us']>=pub)[0]);out['motors'][str(j)]=dict(first_applied_us=int(z['sim_us'][first]),first_sample_us=int(z['applied_sample_us'][first]),late_max_age_us=int((zz['sim_us']-zz['applied_sample_us']).max()),late_max_gap_us=int(np.diff(zz['sim_us']).max()),late_owner_values=np.unique(o['owner'][ii]).tolist(),late_identity_match=bool(np.all(o['actuator_timestamp'][ii]==zz['applied_sample_us'])),tail_bytes=tail)
tr=d['trajectory_setpoint'];tt=int(p['external_timestamp'][native]);ti=int(np.flatnonzero(tr['timestamp']==tt)[0]);out['first_inference_external_timestamp_us']=tt;out['source_sample_age_us']=int(p['timestamp'][native]-tt);out['source_8fields']=[float(tr[f'position[{j}]'][ti]) for j in range(3)]+[float(tr[f'velocity[{j}]'][ti]) for j in range(3)]+[float(tr['yaw'][ti]),float(tr['yawspeed'][ti])];out['matching_8fields']=bool(len(out['matching_sends'])==1 and np.array_equal(np.array(out['source_8fields'],dtype=np.float32),np.array(out['matching_sends'][0]['position']+out['matching_sends'][0]['velocity']+[out['matching_sends'][0]['yaw'],out['matching_sends'][0]['yawspeed']],dtype=np.float32)));out['target_yaw_matches']=bool(p['target_yaw'][native]==tr['yaw'][ti]);out['initial_native_rows']=[]
for i in np.flatnonzero((p['timestamp']>=t)&(p['timestamp']<=pub)&(p['native_step']==1)):
 out['initial_native_rows'].append({k:clean(p[k][i]) for k in ['timestamp','external_timestamp','last_valid_read_us','stale','target_yaw','subscription_updated']})
from handover_explore.analyze import enhanced_window
out['first_windows']={str(sec):enhanced_window(d,t,t+int(sec*1e6)) for sec in [1,2]}
(base/'analysis-v1/entry-and-late-audit.json').write_text(json.dumps(clean(out),indent=2)+'\n');print(json.dumps(clean(out),indent=2))

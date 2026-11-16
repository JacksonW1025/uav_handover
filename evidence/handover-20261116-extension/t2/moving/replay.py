#!/usr/bin/env python3
"""Exact one-step history interventions at authenticated recorded flight states; no simulator."""
import sys,json,hashlib,platform,datetime
from pathlib import Path
import numpy as np
from pyulog import ULog
R=Path('/home/car/uav_handover');O=Path(__file__).resolve().parent;sys.path.insert(0,str(R/'tools'));import p3_memory as rp
P=rp.load_policy();ex=rp.example_check(P);assert ex<1e-5
spec=[('tight_turn_moving',Path('/home/car/handover-experiments-20261116/t1-triplet/N/flight')),('tight_turn_early',Path('/home/car/handover-experiments-20261116/t1-triplet/PRE/flight')),('cruise_1mps',R/'data/p4-20261016-b-M1-N2-1'),('decelerating',R/'data/p4-20261016-b-M2-N2-1'),('cruise_reentry',R/'data/p4-20261016-b-M3-N2-1'),('hover_reentry',R/'data/p4-20261016-a-D2-N2-1')]
def step(h,x):
 e=np.maximum(0,x@P['W0'].T+P['b0']);gi=e@P['Wi'].T+P['bi'];gh=h@P['Wh'].T+P['bh'];sig=lambda z:1/(1+np.exp(-z));rg=sig(gi[:16]+gh[:16]);zg=sig(gi[16:32]+gh[16:32]);ng=np.tanh(gi[32:]+rg*gh[32:]);hn=(1-zg)*ng+zg*h;raw=hn@P['W2'].T+P['b2'];return hn,raw,{'encoded':e.tolist(),'reset_gate':rg.tolist(),'update_gate':zg.tolist(),'candidate':ng.tolist()}
def motor(a):return (np.clip(a,-1,1)[[0,2,3,1]]+1)/2
results=[]
for name,path in spec:
 meta=json.loads((path/'metadata.json').read_text());assert meta['policy_sha256']==P['sha256']
 u=ULog(str(path/'flight.ulg'),['research_memory','raptor_input','vehicle_status','vehicle_local_position','vehicle_attitude','vehicle_angular_velocity']);topics={d.name:d.data for d in u.data_list if d.multi_id==0};vs=topics['vehicle_status'];armed=vs['timestamp'][vs['arming_state']==2];seq=[s for s in rp.native_sequence(topics['research_memory'],topics['raptor_input']) if armed[0]<=s['t']<=armed[-1]];v=rp.validate(P,seq)
 record={'name':name,'path':str(path),'ulog_sha256':hashlib.sha256((path/'flight.ulg').read_bytes()).hexdigest(),'source_metadata_ulog_sha256':meta.get('ulog_sha256'),'validation':v,'frames':[]}
 if v['steps_over_1e-5'] or v['checked']<10:
  record['status']='BASELINE_FAILED';results.append(record);continue
 entries=[i for i,s in enumerate(seq) if s['active'] and s['entry'] is not None];first=entries[-1];t0=seq[first]['t'];record['entry_us']=t0
 for offset in [0,.08,.25,.5,1,2.7]:
  i=next((i for i in range(first,len(seq)) if seq[i]['t']>=t0+offset*1e6 and seq[i]['active']),None)
  if i is None:continue
  s=seq[i];x=s['x'];h=s['entry'] if s['entry'] is not None else seq[i-1]['gru'];assert s['source'].startswith('research_memory.policy_input');prev=motor(x[18:]);fr={'time_us':s['t'],'offset_s':(s['t']-t0)/1e6,'physical_reference_input':x[:18].tolist(),'previous_action_input':x[18:].tolist(),'gru_input':h.tolist(),'observed_gru':s['gru'].tolist(),'variants':{}}
  for tn,kh,ka in [('reset',0,0),('action_only',0,1),('gru_only',1,0),('both',1,1)]:
   xx=x.copy();xx[18:]*=ka;hn,raw,gates=step(h*kh,xx);m=motor(raw);delta=m-prev;fr['variants'][tn]={'output_motor':m.tolist(),'raw_action':raw.tolist(),'max_motor_delta':float(np.max(np.abs(delta))),'motor_delta_l2':float(np.linalg.norm(delta)),'motor_collective_delta':float(np.mean(delta)),'gru_next':hn.tolist(),'clip_components':int(np.sum(np.abs(raw)>1)),**gates}
  actual=fr['variants']['both'];err=float(np.max(np.abs(np.array(actual['gru_next'])-s['gru'])));assert err<1e-5;fr['baseline_error']=err
  for tn,q in fr['variants'].items():
   q['output_delta_from_observed_l2']=float(np.linalg.norm(np.array(q['output_motor'])-actual['output_motor']));q['gru_delta_from_observed_l2']=float(np.linalg.norm(np.array(q['gru_next'])-s['gru']))
  # native backward-asof physical state, actual values rather than inferred from policy observation
  state={}
  for topic,cols in [('vehicle_local_position',['x','y','z','vx','vy','vz']),('vehicle_attitude',['q[0]','q[1]','q[2]','q[3]']),('vehicle_angular_velocity',['xyz[0]','xyz[1]','xyz[2]'])]:
   t=topics[topic];j=np.searchsorted(t['timestamp'],s['t'],side='right')-1;state[topic]={'age_us':int(s['t']-t['timestamp'][j]),**{k:float(t[k][j]) for k in cols}}
  fr['physical_state']=state;record['frames'].append(fr)
 record['status']='VERIFIED';results.append(record)
 (O/'results.json').write_text(json.dumps({'host':platform.node(),'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'policy_sha256':P['sha256'],'example_error':ex,'cases':results},indent=2)+'\n')
 print(name,v['checked'],v['max_abs_error'],len(record['frames']),flush=True)

from core import *
from pyulog import ULog
def vec(d,name,n):return np.column_stack([d[f'{name}[{k}]'] for k in range(n)]).astype(float)
def extract(name):
 path=ROOT/'upstream/data'/f'p2-20261015-s1a-S1-c_to_n-{name}-1'
 m=json.loads((path/'p2-metrics.json').read_text());entry=m['entry']['px4_us'];change=m['change_px4_us']
 u=ULog(str(path/'flight.ulg'),['research_memory','raptor_input','vehicle_attitude','vehicle_local_position','vehicle_angular_velocity','actuator_motors'])
 D={x.name:x.data for x in u.data_list if x.multi_id==0};d=D['research_memory'];ri=D['raptor_input'];where={int(v):j for j,v in enumerate(ri['timestamp_sample'])}
 steps=np.flatnonzero((d['kind']==1)&(d['timestamp']>=entry)&(d['timestamp']<entry+600000))
 h=vec(d,'gru',16);prev=vec(d,'previous_action',4);q=vec(ri,'orientation',4)
 x=np.column_stack([vec(ri,'position',3),np.array([R(T(v)).numpy().flatten() for v in q]),vec(ri,'linear_velocity',3),vec(ri,'angular_velocity',3)])
 # First activation sample is missing from raptor_input in both original logs.
 # Start at first complete input row, 4 ms after entry, with its logged prestate.
 first=next(k for k in steps if int(d['timestamp_sample'][k]) in where)
 steps=steps[steps>=first];out=[];errs=[];hg=h[first-1].copy()
 for k in steps:
  if int(d['timestamp_sample'][k]) not in where:break
  j=where[int(d['timestamp_sample'][k])]
  if k==first:hist=prev[k]
  elif d['native_step'][k]:hist=(prev[k-1]+prev[k])/2
  else:hist=prev[k]
  hh,a=net(T(hg),T(np.r_[x[j],hist]));expected=prev[k+1]
  errs.append(np.max(np.abs(a.numpy()-expected)))
  out.append((int(d['timestamp_sample'][k]),x[j],bool(d['native_step'][k]),expected))
  if d['native_step'][k]:hg=h[k]
 def asof(topic,fields,t):
  a=D[topic];k=np.searchsorted(a.get('timestamp_sample',a['timestamp']),t,side='right')-1
  return np.array([a[f][k] for f in fields],float)
 t=out[0][0]
 state=dict(position=asof('vehicle_local_position',['x','y','z'],t),velocity=asof('vehicle_local_position',['vx','vy','vz'],t),attitude=asof('vehicle_attitude',[f'q[{k}]' for k in range(4)],t),omega=asof('vehicle_angular_velocity',[f'xyz[{k}]' for k in range(3)],t))
 dest=ROOT/f'switch-{name}.npz'
 np.savez_compressed(dest,time=[v[0] for v in out],x=[v[1] for v in out],native=[v[2] for v in out],action=[v[3] for v in out],h=h[first-1],previous=prev[first],**state)
 am=D['actuator_motors'];before=np.flatnonzero(am['timestamp']<change)[-1];after=np.flatnonzero(am['timestamp']>=change)[0]
 info={'case':name,'start_from_entry_ms':(t-entry)/1000,'first_sample_missing':entry not in where,'rows':len(out),'single_step_action_max_error':max(errs),'single_step_action_mean_error':float(np.mean(errs)),'change_us':change,'entry_us':entry,'measured_motor_step':m['auxiliary']['motor']['step_at_change'],'classic_motor':m['auxiliary']['motor']['mean_command_before_change'],'classic_last':vec(am,'control',4)[before].tolist(),'first_neural_motor':vec(am,'control',4)[after].tolist(),'target':m['reference_at_takeover']['position_ned_m'],'target_velocity':m['reference_at_takeover']['velocity_ned_m_s'],'physical_speed':m['state_at_change']['horizontal_speed_m_s'],'tilt_peak_deg':m['primary']['window_constraints']['tilt_safety_deg']['max'],'altitude_loss_m':m['primary']['max_altitude_loss_m']}
 (ROOT/f'switch-{name}.json').write_text(json.dumps(info,indent=2));print(info)
if __name__=='__main__':
 for n in ['N0','N2']:extract(n)

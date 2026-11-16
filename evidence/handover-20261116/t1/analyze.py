"""Independent read-only analysis of completed T1 triplet. Run only after flight ends."""
import json,sys,hashlib,csv
from pathlib import Path
import numpy as np
from pyulog import ULog
ROOT=Path('/home/car/uav_handover');sys.path.insert(0,str(ROOT/'tools'))
from output_chain import read_trace
BASE=Path('/tmp/handover3h-thor-20261116');OUT=Path(__file__).resolve().parent
def last(d,t):return max(0,int(np.searchsorted(d['timestamp'],t,side='right')-1))
def vec(d,n,i,count):return np.array([d[f'{n}[{j}]'][i] for j in range(count)],float)
def state(d,t):
 l=d['vehicle_local_position'];a=d['vehicle_attitude'];w=d['vehicle_angular_velocity'];i=last(l,t);j=last(a,t);k=last(w,t)
 return dict(position=[float(l[x][i]) for x in ['x','y','z']],velocity=[float(l[x][i]) for x in ['vx','vy','vz']],q=vec(a,'q',j,4).tolist(),omega=vec(w,'xyz',k,3).tolist(),ages_us=[int(t-l['timestamp'][i]),int(t-a['timestamp'][j]),int(t-w['timestamp'][k])])
def peak(v,t,mask):
 ix=np.flatnonzero(mask)[np.argmax(v[mask])]
 return dict(value=float(v[ix]),timestamp_us=int(t[ix]))
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.ndarray):return x.tolist()
 if isinstance(x,np.generic):return x.item()
 return x
rows={}
for arm in ['C2','N','PRE']:
 f=BASE/arm/'flight'
 if not (BASE/arm/'result.json').exists():raise RuntimeError(arm+' has not completed')
 u=ULog(str(f/'flight.ulg'));d={z.name:z.data for z in u.data_list if z.multi_id==0};events=[json.loads(z) for z in (f/'events.jsonl').read_text().splitlines()]
 ps=next(x for x in events if x['event']=='explore_profile_started')
 start=int(ps['native_start_lower_us']);marker=int(next(x for x in events if x['event']=='t1_margin_trigger')['end_bound_px4_us'])
 end=int(next(x for x in events if x['event']=='explore_subject_finished')['end_bound_px4_us'])
 l=d['vehicle_local_position'];a=d['vehicle_attitude'];p=d['research_p11'];o=d['research_actuator']
 tilt=np.degrees(np.arccos(np.clip(1-2*(a['q[1]']**2+a['q[2]']**2),-1,1)))
 lm=(l['timestamp']>=start)&(l['timestamp']<=end);am=(a['timestamp']>=start)&(a['timestamp']<=end)
 r=dict(arm=arm,profile_lower_us=start,marker_us=marker,end_us=end,marker_profile_s=(marker-start)/1e6,profile_state=state(d,start),marker_state=state(d,marker),profile_peak_tilt=peak(tilt,a['timestamp'],am),ulog_dropouts=len(u.dropouts),ulog_sha256=hashlib.sha256((f/'flight.ulg').read_bytes()).hexdigest())
 r['marker_peak_tilt']=peak(tilt,a['timestamp'],am&(a['timestamp']>=marker))
 r['profile_descent_peak']=peak(l['z']-l['z'][last(l,start)],l['timestamp'],lm)
 r['marker_descent_peak']=peak(l['z']-l['z'][last(l,marker)],l['timestamp'],lm&(l['timestamp']>=marker))
 crossings=np.flatnonzero(am&(tilt>35))
 r['first_35_us']=int(a['timestamp'][crossings[0]]) if len(crossings) else None
 pm=(p['timestamp']>=start)&(p['timestamp']<=end)&(p['native_step']==1)&(p['active']==1)
 ts=p['timestamp'][pm];nn=int(pm.sum())
 if nn:
  pi=np.array([p[f'policy_input[{j}]'][pm] for j in range(22)]).T
  yaw=p['target_yaw'][pm];cs=np.cos(yaw);sn=np.sin(yaw)
  errors={}
  for group,actual,target,idx,bound in [('position','position','network_target_position',0,.5),('velocity','velocity','network_target_velocity',12,1.)]:
   dv=np.array([p[f'{actual}[{j}]'][pm]-p[f'{target}[{j}]'][pm] for j in range(3)]).T
   raw=np.column_stack([cs*dv[:,0]+sn*dv[:,1],sn*dv[:,0]-cs*dv[:,1],-dv[:,2]])
   reconstructed=np.clip(raw,-bound,bound)
   errors[group]=dict(max_policy_match_error=float(np.max(np.abs(reconstructed-pi[:,idx:idx+3]))),raw_max_abs=np.max(abs(raw),axis=0).tolist(),clipped_rows_by_axis=(abs(raw)>bound+1e-5).sum(axis=0).tolist())
  acts=np.array([p[f'executor_action[{j}]'][pm] for j in range(4)]).T
  r['profile_native']=dict(rows=nn,stale=int(p['stale'][pm].sum()),max_reference_age_us=int(np.max(ts-p['last_valid_read_us'][pm])),errors=errors,action_boundary_rows_by_motor=(abs(acts)>=.99999).sum(axis=0).tolist())
  with (OUT/(arm+'-native.csv')).open('w') as h:
   w=csv.writer(h);w.writerow(['native_us','profile_s','tilt_deg','position_clip_axes','velocity_clip_axes','action_boundary_count','reference_age_us','stale'])
   for ti,i in enumerate(np.flatnonzero(pm)):
    ai=last(a,int(p['timestamp'][i]))
    w.writerow([int(p['timestamp'][i]),(int(p['timestamp'][i])-start)/1e6,float(tilt[ai]),int(np.sum(abs(pi[ti,:3])>=.49999)),int(np.sum(abs(pi[ti,12:15])>=.99999)),int(np.sum(abs(acts[ti])>=.99999)),int(p['timestamp'][i]-p['last_valid_read_us'][i]),int(p['stale'][i])])
  endwin=r['first_35_us'] or r['profile_peak_tilt']['timestamp_us'];beginwin=max(start,endwin-2000000)
  mm=(p['timestamp']>=beginwin)&(p['timestamp']<=endwin)
  r['late_window']=dict(start_us=beginwin,end_us=endwin,native_rows=int(p['native_step'][mm].sum()),stale=int(p['stale'][mm].sum()),max_reference_age_us=int(np.max(p['timestamp'][mm]-p['last_valid_read_us'][mm])),motors={})
  for j in range(4):
   mid,z,tail=read_trace(f/'gz-motor'/f'motor-{j}.bin');zz=z[(z['sim_us']>=beginwin)&(z['sim_us']<=endwin)]
   ii=np.searchsorted(o['actuator_timestamp'],zz['applied_sample_us'],side='right')-1
   r['late_window']['motors'][j]=dict(samples=len(zz),max_age_us=int(np.max(zz['sim_us']-zz['applied_sample_us'])),owners=np.unique(o['owner'][ii]).tolist(),identity_match=bool(np.all(o['actuator_timestamp'][ii]==zz['applied_sample_us'])),tail_bytes=tail)
 with (OUT/(arm+'-trajectory.csv')).open('w') as h:
  w=csv.writer(h);w.writerow(['native_us','profile_s','marker_s','descent_from_profile_m','descent_from_marker_m','vz','tilt_deg'])
  for i in np.flatnonzero(lm):
   t=int(l['timestamp'][i]);w.writerow([t,(t-start)/1e6,(t-marker)/1e6,float(l['z'][i]-l['z'][last(l,start)]),float(l['z'][i]-l['z'][last(l,marker)]),float(l['vz'][i]),float(tilt[last(a,t)])])
 rows[arm]=r
def diff(a,b):
 return {**{k:float(np.linalg.norm(np.array(a[k])-b[k])) for k in ['position','velocity','omega']},'attitude_deg':float(np.degrees(2*np.arccos(np.clip(abs(np.dot(a['q'],b['q'])),-1,1))))}
matching={a+'-'+b:{s:diff(rows[a][s],rows[b][s]) for s in ['profile_state','marker_state']} for a,b in [('C2','N'),('C2','PRE'),('N','PRE')]}
(OUT/'results.json').write_text(json.dumps(clean(dict(arms=rows,matching=matching)),indent=2))
print(json.dumps(clean(dict(arms={k:{x:v[x] for x in ['profile_peak_tilt','marker_descent_peak','first_35_us','profile_native'] if x in v} for k,v in rows.items()},matching=matching)),indent=2))

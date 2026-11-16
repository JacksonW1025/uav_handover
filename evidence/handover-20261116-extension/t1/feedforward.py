"""Completed-flight classic FF/NOFF consumption audit. No simulation control."""
from pathlib import Path
import json,csv,hashlib
import numpy as np
from pyulog import ULog
P=Path(__file__).resolve().parent;B=Path('/tmp/handover3h-t1-feedforward-20261116');out={}
for arm in ['FF','NOFF']:
 result=json.loads((B/arm/'result.json').read_text());assert result['status']=='PASS' and result['cleanup_error'] is None
 f=B/arm/'flight';u=ULog(str(f/'flight.ulg'));d={z.name:z.data for z in u.data_list if z.multi_id==0};ev=[json.loads(s) for s in (f/'events.jsonl').read_text().splitlines()];start=next(z['native_start_lower_us'] for z in ev if z['event']=='explore_profile_started');end=next(z['end_bound_px4_us'] for z in ev if z['event']=='explore_subject_finished');q=1.25;stop=start+5e6*q
 a=d['vehicle_attitude'];l=d['vehicle_local_position'];sp=d['trajectory_setpoint'];co=d['vehicle_local_position_setpoint'];cm=d['vehicle_control_mode'];p=d['research_p11'];o=d['research_actuator'];vs=d['vehicle_status']
 def last(z,t):return max(0,int(np.searchsorted(z['timestamp'],t,side='right')-1))
 tilt=np.degrees(np.arccos(np.clip(1-2*(a['q[1]']**2+a['q[2]']**2),-1,1)));phase=(a['timestamp']-start)/1e6/q;mask=(phase>=4)&(phase<=7);is_=np.flatnonzero(mask);pk=is_[np.argmax(tilt[mask])];lm=(l['timestamp']>=stop)&(l['timestamp']<=start+7e6*q);li=np.flatnonzero(lm);low=li[np.argmax(l['z'][lm])];zstop=l['z'][last(l,stop)];p0=last(l,start);a0=last(a,start)
 r={'result':result,'profile_lower_us':start,'initial_position':[float(l[k][p0]) for k in ['x','y','z']],'initial_velocity':[float(l[k][p0]) for k in ['vx','vy','vz']],'initial_q':[float(a[f'q[{j}]'][a0]) for j in range(4)],'late_peak_tilt':float(tilt[pk]),'peak_normalized_phase':float(phase[pk]),'poststop_descent_m':float(l['z'][low]-zstop),'ulog_dropouts':len(u.dropouts),'ulog_sha256':hashlib.sha256((f/'flight.ulg').read_bytes()).hexdigest()}
 lo=start+4e6*q;hi=start+7e6*q
 for name,z in [('received',sp),('controller_output',co)]:
  m=(z['timestamp']>=lo)&(z['timestamp']<=hi);v=np.array([z[f'acceleration[{j}]'][m] for j in range(3)]).T;r[name]={'samples':int(m.sum()),'finite_values':int(np.isfinite(v).sum()),'nan_values':int(np.isnan(v).sum()),'acc_norm_max':float(np.nanmax(np.linalg.norm(v,axis=1))) if np.isfinite(v).any() else None}
 r['runtime']={}
 for name,z,field in [('classic_enabled',cm,'flag_multicopter_position_control_enabled'),('offboard',cm,'flag_control_offboard_enabled'),('nav_state',vs,'nav_state'),('raptor_active',p,'active'),('output_owner',o,'owner')]:
  m=(z['timestamp']>=lo)&(z['timestamp']<=hi);r['runtime'][name]=np.unique(z[field][m]).tolist()
 with (P/f'{arm}-feedforward.csv').open('w') as h:
  w=csv.writer(h);w.writerow(['normalized_phase','tilt_deg','descent_from_stop_m','vx','vy','vz','received_ax','received_ay','output_ax','output_ay','output_az','attitude_setpoint_tilt_deg'])
  for i in is_:
   t=a['timestamp'][i];j=last(l,t);k=last(sp,t);c=last(co,t);ats=d.get('vehicle_attitude_setpoint');asp=float('nan')
   if ats is not None:
    z=last(ats,t);asp=float(np.degrees(np.arccos(np.clip(1-2*(ats['q_d[1]'][z]**2+ats['q_d[2]'][z]**2),-1,1))))
   w.writerow([phase[i],tilt[i],l['z'][j]-zstop,l['vx'][j],l['vy'][j],l['vz'][j],sp['acceleration[0]'][k],sp['acceleration[1]'][k],co['acceleration[0]'][c],co['acceleration[1]'][c],co['acceleration[2]'][c],asp])
 out[arm]=r
(P/'feedforward-summary.json').write_text(json.dumps(out,indent=2,allow_nan=False));print(json.dumps(out,indent=2))

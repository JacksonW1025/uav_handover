"""Thor-only T1 read-only signal reconstruction. Native controller samples; derivative estimates explicitly labelled."""
import json,hashlib,csv
from pathlib import Path
import numpy as np
from pyulog import ULog
P=Path(__file__).resolve().parent; B=P.parent/'t1-triplet'; R=json.loads((P.parent/'t1-analysis/results.json').read_text());summ={}
source=Path('/home/car/uav_handover/data/handover-t1-entryready-20261115-v1/private-build/mc_raptor.cpp');src=source.read_bytes()
for arm in ['N','PRE']:
 f=B/arm/'flight/flight.ulg';u=ULog(str(f));d={x.name:x.data for x in u.data_list if x.multi_id==0};p=d['research_p11']; start=R['arms'][arm]['profile_lower_us'];end=R['arms'][arm]['end_us'];m=(p['native_step']==1)&(p['active']==1)&(p['timestamp']>=start)&(p['timestamp']<=end)
 t=p['timestamp'][m].astype(float);phase=(t-start)/1e6
 def v(k,n):return np.array([p[f'{k}[{i}]'][m] for i in range(n)],float).T
 pos=v('position',3);vel=v('velocity',3);tp=v('network_target_position',3);tv=v('network_target_velocity',3);q=v('attitude',4);pi=v('policy_input',22);act=v('executor_action',4);yaw=p['target_yaw'][m];c=np.cos(yaw);s=np.sin(yaw)
 def rotate(z):return np.column_stack((c*z[:,0]+s*z[:,1],s*z[:,0]-c*z[:,1],-z[:,2]))
 e=rotate(vel-tv);ep=rotate(pos-tp);tilt=np.degrees(np.arccos(np.clip(1-2*(q[:,1]**2+q[:,2]**2),-1,1)))
 # 80 ms centered secants; end effects use shorter available interval.
 idx=np.arange(len(t));lo=np.maximum(idx-5,0);hi=np.minimum(idx+5,len(t)-1);dt=(t[hi]-t[lo])/1e6
 acc=(vel[hi]-vel[lo])/dt[:,None];tacc=(tv[hi]-tv[lo])/dt[:,None]
 raw=rotate(vel);target=rotate(tv);o=d['research_actuator'];oi=np.searchsorted(o['timestamp'],t,side='right')-1;valid=oi>=0;oi=np.maximum(oi,0);ctrl=np.array([o[f'control[{i}]'][oi] for i in range(4)]).T
 col={'native_us':t,'phase_s':phase,'tilt_deg':tilt,'yaw_rad':yaw,'altitude_m':-pos[:,2],'vz_down_mps':vel[:,2],'az_down_est80ms':acc[:,2],'horizontal_accel_est80ms':np.linalg.norm(acc[:,:2],axis=1),'target_horizontal_accel_est80ms':np.linalg.norm(tacc[:,:2],axis=1),'action_mean':act.mean(axis=1),'action_spread':np.ptp(act,axis=1),'control_mean':ctrl.mean(axis=1),'control_spread':np.ptp(ctrl,axis=1),'control_age_us':t-o['timestamp'][oi]}
 for i in range(3):
  for name,ar in [('vel_targetframe',raw),('reference_vel_targetframe',target),('error_velocity',e),('input_velocity',pi[:,12:15]),('error_position',ep)]:col[f'{name}_{i}']=ar[:,i]
 for i in range(4):col[f'action_{i}']=act[:,i];col[f'control_{i}']=ctrl[:,i]
 with (P/f'{arm}-dynamics.csv').open('w') as h:
  w=csv.writer(h);w.writerow(col);w.writerows(zip(*col.values()))
 win=(phase>=4.6)&(phase<=6.7);ix=np.flatnonzero(win);clip=ix[abs(e[ix,0])>1.00001];pk=ix[np.argmax(tilt[ix])]
 def row(i):return {k:float(z[i]) for k,z in col.items()}
 summ[arm]={'ulog_sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'max_reconstruction_error':float(np.max(abs(np.clip(e,-1,1)-pi[:,12:15]))),'all_active_profile_yaw_range': [float(yaw.min()),float(yaw.max())],'clipping_start':row(clip[0]),'clipping_end':row(clip[-1]),'maximum_tilt':row(pk),'max_velocity_error':row(ix[np.argmax(abs(e[ix,0]))]),'min_altitude':row(ix[np.argmin(-pos[ix,2])]),'control_alignment_owner_values':np.unique(o['owner'][oi[win]]).tolist(),'max_control_age_us_window':float(np.max(t[win]-o['timestamp'][oi[win]]))}
(P/'summary.json').write_text(json.dumps({'source_path':str(source),'source_sha256':hashlib.sha256(src).hexdigest(),'arms':summ},indent=2));print(json.dumps(summ,indent=2))

"""Run only once both isolated PRE runs have completed; no simulator control."""
import json,hashlib,sys,csv
from pathlib import Path
import numpy as np
from pyulog import ULog
sys.path.insert(0,'/home/car/uav_handover/tools')
from output_chain import read_trace
P=Path(__file__).resolve().parent;out={}
for key,scale,B in [('q115',1.15,P.parent/'t1-triplet/PRE'),('q125',1.25,Path('/tmp/handover3h-t1-retime-20261116/PRE'))]:
 end=json.loads((B/'result.json').read_text());assert end['status']=='PASS' and end['cleanup_error'] is None
 f=B/'flight';u=ULog(str(f/'flight.ulg'));d={x.name:x.data for x in u.data_list if x.multi_id==0};ev=[json.loads(x) for x in (f/'events.jsonl').read_text().splitlines()]
 start=next(x['native_start_lower_us'] for x in ev if x['event']=='explore_profile_started');finish=next(x['end_bound_px4_us'] for x in ev if x['event']=='explore_subject_finished');l=d['vehicle_local_position'];a=d['vehicle_attitude'];p=d['research_p11'];o=d['research_actuator']
 def ix(t,T):return max(0,int(np.searchsorted(t,T,side='right')-1))
 at=a['timestamp'];lt=l['timestamp'];tilt=np.degrees(np.arccos(np.clip(1-2*(a['q[1]']**2+a['q[2]']**2),-1,1)));phase=(at-start)/1e6/scale;lp=(lt-start)/1e6/scale
 pm=(p['native_step']==1)&(p['active']==1)&(p['timestamp']>=start)&(p['timestamp']<=finish);pt=p['timestamp'][pm];np_= (pt-start)/1e6/scale
 dv=np.array([p[f'velocity[{i}]'][pm]-p[f'network_target_velocity[{i}]'][pm] for i in range(3)]).T;y=p['target_yaw'][pm];raw=np.cos(y)*dv[:,0]+np.sin(y)*dv[:,1];clip=abs(raw)>1.00001
 am=(phase>=4)&(phase<=7);inds=np.flatnonzero(am);peak=inds[np.argmax(tilt[am])];post=(phase>=5)&(phase<=7);pp=np.flatnonzero(post)[np.argmax(tilt[post])];lm=(lp>=5)&(lp<=7);li=np.flatnonzero(lm);low=li[np.argmax(l['z'][lm])];zstop=float(l['z'][ix(lt,start+5e6*scale)]);zstart=float(l['z'][ix(lt,start)])
 nc=np.flatnonzero(clip&(np_>=4)&(np_<=7));cross=np.flatnonzero(am&(tilt>35));endwin=int(at[cross[0] if len(cross) else peak]);begin=endwin-2000000
 posi=ix(lt,start);ai=ix(at,start)
 r={'q':scale,'result':end,'profile_lower_us':start,'native_active_first_us':int(p['timestamp'][np.flatnonzero((p['native_step']==1)&(p['active']==1))[0]]),'initial':{'position':[float(l[k][posi]) for k in ['x','y','z']],'velocity':[float(l[k][posi]) for k in ['vx','vy','vz']],'q':[float(a[f'q[{k}]'][ai]) for k in range(4)]},'late_peak_tilt':float(tilt[peak]),'late_peak_normalized_s':float(phase[peak]),'poststop_peak_tilt':float(tilt[pp]),'poststop_descent_from_stop_m':float(l['z'][low]-zstop),'poststop_descent_from_profile_m':float(l['z'][low]-zstart),'minimum_altitude_normalized_s':float(lp[low]),'clip_rows_late':len(nc),'clip_span_s':float((pt[nc[-1]]-pt[nc[0]])/1e6) if len(nc) else 0,'clip_start_normalized_s':float(np_[nc[0]]) if len(nc) else None,'velocity_error_abs_peak':float(np.max(abs(raw[(np_>=4)&(np_<=7)]))),'stale_active_profile':int(p['stale'][pm].sum()),'reference_age_max_us':int(np.max(pt-p['last_valid_read_us'][pm])),'first35_normalized_s':float(phase[cross[0]]) if len(cross) else None,'ulog_dropouts':len(u.dropouts),'ulog_sha256':hashlib.sha256((f/'flight.ulg').read_bytes()).hexdigest(),'motor_window_us':[begin,endwin],'motors':{}}
 for j in range(4):
  _,z,tail=read_trace(f/'gz-motor'/f'motor-{j}.bin');z=z[(z['sim_us']>=begin)&(z['sim_us']<=endwin)];ii=np.searchsorted(o['actuator_timestamp'],z['applied_sample_us'],side='right')-1;assert np.all(ii>=0)
  r['motors'][j]={'count':len(z),'owners':np.unique(o['owner'][ii]).tolist(),'exact_identity':bool(np.all(o['actuator_timestamp'][ii]==z['applied_sample_us'])),'age_max_us':int(np.max(z['sim_us']-z['applied_sample_us'])),'tail_bytes':tail}
 with (P/(key+'-retime.csv')).open('w') as h:
  w=csv.writer(h);w.writerow(['normalized_phase_s','tilt_deg','descent_from_stop_m','vz_down','velocity_error_axis1','input_velocity_axis1'])
  for k,T in enumerate(pt):
   j=ix(lt,T);i=ix(at,T);w.writerow([np_[k],float(tilt[i]),float(l['z'][j]-zstop),float(l['vz'][j]),float(raw[k]),float(p['policy_input[12]'][pm][k])])
 out[key]=r
(P/'retime-summary.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))

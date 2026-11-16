#!/usr/bin/env python3
"""Thor-only after both flights exit; original ULogs and four motors, new output only."""
import json,sys,hashlib,csv,platform,time
from pathlib import Path
import numpy as np
from pyulog import ULog
sys.path.insert(0,'/home/car/uav_handover/tools')
from output_chain import read_trace
ROOT=Path('/home/car/uav_handover');BATCH=ROOT/'data/handover-t3-semantics-20261116-v1';OUT=Path('/tmp/handover-t3-semantics-20261116/flight-analysis');OUT.mkdir(exist_ok=False)
def vec(d,k,n=3):return np.stack([d[f'{k}[{i}]'] for i in range(n)],axis=1)
def records(p):return [json.loads(s) for s in p.read_text().splitlines()]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
results=[]
for case in ['001_zero_capture','002_continuous_capture']:
 f=BATCH/(case+'-a1');run=f/'flight';execution=json.loads((f/'result.json').read_text());cfg=json.loads((f/'config.json').read_text());spec=cfg['explore'];events=records(run/'events.jsonl');sends=records(run/'explore-setpoints.jsonl');req=next(e for e in events if e['event']=='handover_requested' and e.get('subject'));end=next(e for e in events if e['event']=='explore_subject_finished')['end_bound_px4_us'];start=req['end_bound_px4_us'];firstevent=next(e for e in events if e['event']=='f1_first_postrequest_publish');send=next(s for s in sends if s['id']==firstevent['send_count']);gate=next(e for e in events if e['event']=='f1_reference_release_gate')
 u=ULog(str(run/'flight.ulg'),message_name_filter_list=['research_p11','research_actuator','vehicle_attitude','vehicle_local_position','vehicle_command_ack','vehicle_status','vehicle_land_detected']);ds={d.name:d.data for d in u.data_list if d.multi_id==0}
 p=ds['research_p11'];pt=p['timestamp'].astype(np.int64);ai=np.flatnonzero((pt>=start)&p['activation'].astype(bool)&p['active'].astype(bool))[0];active=int(pt[ai]);ri=np.flatnonzero((pt>=active)&p['subscription_updated'].astype(bool)&p['external_valid'].astype(bool))[0];read=int(pt[ri]);o=ds['research_actuator'];ot=o['actuator_timestamp'].astype(np.int64);ni=np.flatnonzero((ot>=active)&(o['owner']==1))[0];pub=int(ot[ni]);ci=np.flatnonzero((ot<pub)&(o['owner']==2))[-1]
 targp=vec(p,'network_target_position');targv=vec(p,'network_target_velocity');vel=vec(p,'velocity');pos=vec(p,'position');action=vec(p,'executor_action',4);inp=vec(p,'policy_input',22);mot=vec(o,'control',4);native=p['native_step'].astype(bool)
 freeze=(pt>=active)&(pt<read)&p['active'].astype(bool)&native
 dt=np.maximum(0,np.minimum(np.r_[pt[1:],pt[-1]],read)-np.maximum(pt,active))/1e6
 impulse=float(np.sum(dt[freeze]*np.sum((vel[freeze]-targv[freeze])**2,axis=1)))
 prior=np.flatnonzero((pt<read)&native)[-1]
 physical=[]
 for path in sorted((run/'gz-motor').glob('motor-*.bin')):
  mid,m,tail=read_trace(path);pidx=np.flatnonzero(m['applied_sample_us']>=pub)[0];exact=np.flatnonzero(m['applied_sample_us']==read);ridx=int(exact[0]) if len(exact) else None
  physical.append({'motor':mid,'first_publication_applied_us':int(m['sim_us'][pidx]),'first_publication_applied_sample_us':int(m['applied_sample_us'][pidx]),'restored_reference_sample_applied_us':int(m['sim_us'][ridx]) if ridx is not None else None,'first_step_wall_ns':int(m['step_wall_ns'][pidx]),'tail_bytes':tail,'sha256':sha(path)})
 assert len(physical)==4 and all(x['tail_bytes']==0 for x in physical)
 firstfour=max(x['first_publication_applied_us'] for x in physical)
 att=ds['vehicle_attitude'];at=att['timestamp'].astype(np.int64);q=vec(att,'q',4);tilt=np.degrees(np.arccos(np.clip(1-2*(q[:,1]**2+q[:,2]**2),-1,1)))
 lp=ds['vehicle_local_position'];lt=lp['timestamp'].astype(np.int64);entry=lp['z'][np.searchsorted(lt,pub,side='right')-1]
 peaks={}
 for secs in [1,2]:
  mask=(at>=pub)&(at<min(pub+secs*1000000,end));zmask=(lt>=pub)&(lt<min(pub+secs*1000000,end));peaks[str(secs)]={'max_tilt_deg':float(tilt[mask].max()),'max_altitude_loss_m':float(max(0,lp['z'][zmask].max()-entry)),'observed_s':min(secs,(end-pub)/1e6)}
 mm=(at>=pub)&(at<=end);zz=(lt>=pub)&(lt<=end)
 a200=(pt>=active)&(pt<active+200000)&p['active'].astype(bool)&native
 status=ds['vehicle_status'];land=ds['vehicle_land_detected'];landed=np.flatnonzero((land['timestamp']>end)&(land['landed']==1));disarmed=np.flatnonzero((status['timestamp']>end)&(status['arming_state']!=2))
 firstsend=np.array(send['position']+send['velocity']+[send['yaw'],send['yawspeed']],dtype=np.float32)
 expected=np.array([.8,0,-4,.4,0,0,spec['fixed_reference_yaw_rad'],0],dtype=np.float32)
 adopted=np.r_[targp[ri],targv[ri],p['target_yaw'][ri]].astype(np.float32)
 row={'case':case,'hostname':platform.node(),'execution':execution,'input_ulog_sha256':sha(run/'flight.ulg'),'ulog_dropouts':len(u.dropouts),'request_lower_us':start,'activation_us':active,'first_neural_publication_us':pub,'first_four_application_us':firstfour,'first_valid_reference_read_us':read,'read_after_four_ms':(read-firstfour)/1000,'activation_to_reference_ms':(read-active)/1000,'gate':gate,'first_send':send,'first_payload_exactly_matches_plan_float32':bool(np.array_equal(firstsend,expected)),'first_adopted_position_velocity_yaw_matches_plan_float32':bool(np.array_equal(adopted,expected[:7])),'first_send_strictly_after_all_four_application':send['before_ns']>max(x['first_step_wall_ns'] for x in physical),'four_motors':physical,'pre_reference_native_count':int(freeze.sum()),'all_pre_reference_targets_zero':bool(np.all(targv[freeze]==0)),'pre_reference_squared_velocity_error_integral_m2_s':impulse,'first_neural_target_velocity':targv[np.flatnonzero(pt==pub)[0]].tolist(),'first_motor_jump_L2':float(np.linalg.norm(mot[ni]-mot[ci])),'reference_target_position_jump_m':float(np.linalg.norm(targp[ri]-targp[prior])),'reference_target_velocity_jump_m_s':float(np.linalg.norm(targv[ri]-targv[prior])),'reference_action_equivalent_motor_step_L2':float(np.linalg.norm((action[ri]-action[prior])/2)),'input_at_bound_axes_200ms':int(np.sum(np.abs(inp[a200,12:15])>=.999999)),'action_at_bound_axes_200ms':int(np.sum(np.abs(action[a200])>=.999999)),'native_rows_200ms':int(a200.sum()),'request_state':{'position':req.get('position'),'pre_switch':next(e for e in events if e['event']=='explore_pre_switch')},'entry_state':{'position':pos[ai].tolist(),'velocity':vel[ai].tolist(),'attitude':vec(p,'attitude',4)[ai].tolist(),'angular_velocity':vec(p,'angular_velocity')[ai].tolist()},'physical':{'peak_tilt_deg':float(tilt[mm].max()),'max_altitude_loss_m':float(max(0,lp['z'][zz].max()-entry)),'first_35deg_us':int(at[mm&(tilt>35)][0]) if np.any(mm&(tilt>35)) else None,'first_45deg_us':int(at[mm&(tilt>45)][0]) if np.any(mm&(tilt>45)) else None,'windows':peaks},'first_landed_after_subject_us':int(land['timestamp'][landed[0]]) if len(landed) else None,'first_disarmed_after_subject_us':int(status['timestamp'][disarmed[0]]) if len(disarmed) else None,'stop_events':[e for e in events if e['event']=='process_stopped']}
 with (OUT/(case+'-reference.csv')).open('w') as f:
  w=csv.writer(f);w.writerow(['native_us','time_from_first_neural_s','active','target_vx','target_vy','target_vz','vx','vy','vz','position_error_m','motor_action_0','motor_action_1','motor_action_2','motor_action_3'])
  for i in np.flatnonzero((pt>=active-50000)&(pt<=active+2000000)&native):w.writerow([int(pt[i]),(pt[i]-pub)/1e6,int(p['active'][i]),*targv[i],*vel[i],float(np.linalg.norm(pos[i]-targp[i])),*action[i]])
 with (OUT/(case+'-physical.csv')).open('w') as f:
  w=csv.writer(f);w.writerow(['native_us','time_from_first_neural_s','tilt_deg'])
  for i in np.flatnonzero((at>=pub-50000)&(at<=min(pub+2000000,end))):w.writerow([int(at[i]),(at[i]-pub)/1e6,float(tilt[i])])
 (OUT/(case+'.json')).write_text(json.dumps(row,indent=2)+'\n');results.append(row)
a,b=results;delta={}
for k in ['position','velocity','angular_velocity']:delta[k]=float(np.linalg.norm(np.array(a['entry_state'][k])-b['entry_state'][k]))
x,y=np.array(a['entry_state']['attitude']),np.array(b['entry_state']['attitude']);delta['attitude_deg']=float(np.degrees(2*np.arccos(np.clip(abs(x@y)/np.linalg.norm(x)/np.linalg.norm(y),0,1))))
(OUT/'summary.json').write_text(json.dumps({'machine':platform.node(),'analysis_time_ns':time.time_ns(),'entry_deltas':delta,'cases':results},indent=2)+'\n')
print(json.dumps({'entry_deltas':delta,'cases':[{k:r[k] for k in ['case','read_after_four_ms','pre_reference_native_count','pre_reference_squared_velocity_error_integral_m2_s','first_motor_jump_L2','reference_action_equivalent_motor_step_L2','physical','first_payload_exactly_matches_plan_float32','first_adopted_position_velocity_yaw_matches_plan_float32','first_landed_after_subject_us','first_disarmed_after_subject_us']} for r in results]},indent=2))

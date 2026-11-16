import json,sys,hashlib
from pathlib import Path
import numpy as np
from pyulog import ULog
O=Path(__file__).resolve().parent;sys.path.insert(0,'/home/car/uav_handover/tools');import p3_memory as rp
from output_chain import read_trace
P=rp.load_policy()
def vec(d,k,i,n):return np.array([d[f'{k}[{j}]'][i] for j in range(n)],float)
def last(d,t):return max(0,int(np.searchsorted(d['timestamp'],t,side='right')-1))
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.ndarray):return x.tolist()
 if isinstance(x,np.generic):return x.item()
 return x
rows={}
for arm in (sys.argv[1:] or ['N4','N2']):
 f=O/arm/'flight';res=json.loads((O/arm/'result.json').read_text());u=ULog(str(f/'flight.ulg'));d={z.name:z.data for z in u.data_list if z.multi_id==0};m=d['research_memory'];p=d['research_p11'];o=d['research_actuator'];l=d['vehicle_local_position'];a=d['vehicle_attitude'];w=d['vehicle_angular_velocity'];vs=d['vehicle_status']
 mi=np.flatnonzero((m['kind']==2)&m['active'])[-1];t=int(m['timestamp'][mi]);ni=np.flatnonzero((p['timestamp']>=t)&p['native_step']&p['active'])[0];nt=int(p['timestamp'][ni]);oi=np.flatnonzero((o['actuator_timestamp']>=nt)&(o['owner']==1))[0];ci=np.flatnonzero(o['actuator_timestamp']==m['classic_actuator_timestamp'][mi]);assert len(ci)==1
 h=vec(m,'gru',mi,16);action=vec(m,'previous_action',mi,4);classic=vec(o,'control',ci[0],4);mapped=(classic*2-1)[[0,3,1,2]]
 idx=last(l,t);ai=last(a,t);wi=last(w,t);q=vec(a,'q',ai,4);tilt=np.degrees(np.arccos(np.clip(1-2*(a['q[1]']**2+a['q[2]']**2),-1,1)))
 valid=vs['timestamp'][vs['arming_state']==2];seq=[s for s in rp.native_sequence(m,d['raptor_input']) if valid[0]<=s['t']<=valid[-1]];validation=rp.validate(P,seq)
 refmask=(p['timestamp']>=nt)&(p['timestamp']<nt+2000000)&p['native_step']&p['active'];windows={}
 events=[json.loads(x) for x in (f/'events.jsonl').read_text().splitlines()];subject_end=int(next(x['end_bound_px4_us'] for x in events if x['event']=='explore_subject_finished'));
 for seconds in [.08,.25,1,2,(subject_end-t)/1e6]:
  am=(a['timestamp']>=t)&(a['timestamp']<=t+seconds*1e6);lm=(l['timestamp']>=t)&(l['timestamp']<=t+seconds*1e6)
  windows[str(seconds)]={'max_tilt_deg':float(max(tilt[am])),'max_descent_m':float(max(l['z'][lm]-l['z'][idx])),'max_velocity_norm':float(max(np.sqrt(l['vx'][lm]**2+l['vy'][lm]**2+l['vz'][lm]**2)))}
 row=dict(result=res,ulog_sha256=hashlib.sha256((f/'flight.ulg').read_bytes()).hexdigest(),dropouts=len(u.dropouts),entry_us=t,native_us=nt,entry_mode=int(m['entry_mode'][mi]),entry_result=int(m['entry_result'][mi]),gru=h,gru_l2=float(np.linalg.norm(h)),gru_before=vec(m,'gru_before_entry',mi,16),previous_action=action,classic_action_error=float(max(abs(mapped-action))),classic_owner=int(o['owner'][ci[0]]),classic_age_us=t-int(m['classic_actuator_timestamp'][mi]),first_ref={k:float(p[k][ni]) for k in ['stale','last_valid_read_us','native_step','active']},first_reference={k:vec(p,k,ni,3) for k in ['network_target_position','network_target_velocity','position','velocity']},first_native_policy_input=vec(p,'policy_input',ni,22),first_output=vec(o,'control',oi,4),last_classic_output=classic,first_motor_step_max=float(max(abs(vec(o,'control',oi,4)-classic))),first_motor_collective_delta=float(np.mean(vec(o,'control',oi,4)-classic)),first_two_seconds_stale=int(sum(p['stale'][refmask])),first_two_seconds_max_reference_age_us=int(max(p['timestamp'][refmask]-p['last_valid_read_us'][refmask])),state={'position':[float(l[k][idx]) for k in ['x','y','z']],'velocity':[float(l[k][idx]) for k in ['vx','vy','vz']],'q':q,'omega':vec(w,'xyz',wi,3),'tilt_deg':float(tilt[ai])},windows=windows,validation=validation)
 row['pure_history_comparison_checks']=bool(row['classic_action_error']<1e-5 and row['classic_owner']==2 and row['entry_mode']==int(arm[1:]) and row['entry_result']==1 and not row['first_ref']['stale'] and row['first_ref']['last_valid_read_us']>0 and nt-row['first_ref']['last_valid_read_us']<=12000 and (np.max(abs(h))==0 if arm=='N2' else np.max(abs(h-vec(m,'gru_before_entry',mi,16)))<1e-5))
 native=next(z for z in seq if z['t']==nt and z['active']);hn=rp.gru_step(P,h,native['x']);raw=hn@P['W2'].T+P['b2'];pred=np.clip(raw,-1,1);td=d['research_timing'];ti=np.flatnonzero(td['timestamp']==nt);row['first_native_action_match_error']=float(min(max(abs(pred-vec(td,'action',i,4))) for i in ti));row['first_native_raw_action']=raw;row['first_native_clipped_action']=pred;row['first_native_mapped_motor']=(pred[[0,2,3,1]]+1)/2;row['first_native_to_first_published_motor_difference']=float(max(abs(row['first_native_mapped_motor']-row['first_output'])))
 om=(o['actuator_timestamp']>=t)&(o['actuator_timestamp']<=t+500000)&(o['owner']==1);collective=np.mean([o[f'control[{j}]'][om] for j in range(4)],axis=0);ots=o['actuator_timestamp'][om];row['first_half_second_collective']={'min':float(min(collective)),'min_offset_s':float((ots[np.argmin(collective)]-t)/1e6),'max':float(max(collective)),'max_offset_s':float((ots[np.argmax(collective)]-t)/1e6),'classic_before':float(np.mean(classic))}
 row['subject_end_us']=subject_end;row['final_arming_state']=int(vs['arming_state'][-1]);row['final_landed']=bool(d['vehicle_land_detected']['landed'][-1]);row['gazebo_first_neural_application']={}
 for motor in range(4):
  mid,z,tail=read_trace(f/'gz-motor'/f'motor-{motor}.bin');zi=np.searchsorted(o['actuator_timestamp'],z['applied_sample_us'],side='right')-1;valid=(zi>=0);owner=np.zeros(len(z),int);owner[valid]=o['owner'][zi[valid]];sel=np.flatnonzero((z['sim_us']>=t)&(owner==1))[0];j=zi[sel]
  row['gazebo_first_neural_application'][str(motor)]={'sim_us':int(z['sim_us'][sel]),'applied_sample_us':int(z['applied_sample_us'][sel]),'identity_match':bool(o['actuator_timestamp'][j]==z['applied_sample_us'][sel]),'matches_first_published_neural':bool(j==oi),'tail_bytes':tail,'ref_motor_input':float(z['ref_motor_input'][sel])}
 rows[arm]=row
x,y=[rows[k]['state'] for k in (['N4','N2'] if len(rows)==2 else [next(iter(rows))]*2)];match={k:float(np.linalg.norm(np.array(x[k])-y[k])) for k in ['position','velocity','omega']};match['attitude_deg']=float(np.degrees(2*np.arccos(np.clip(abs(np.dot(x['q'],y['q'])),-1,1))))
(O/'summary.json').write_text(json.dumps(clean({'arms':rows,'matching':match}),indent=2));print(json.dumps(clean({'matching':match,'arms':{k:{s:v[s] for s in ['pure_history_comparison_checks','first_motor_step_max','first_motor_collective_delta','windows','first_ref','first_two_seconds_stale','gru_l2']} for k,v in rows.items()}}),indent=2))

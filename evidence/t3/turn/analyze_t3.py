#!/usr/bin/env python3
"""Run on Thor only. Read frozen F1 export; never launches flight or alters source."""
import argparse,json,hashlib,csv,gzip,math,pathlib
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--archive',type=pathlib.Path,required=True);p.add_argument('--out',type=pathlib.Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
raw=(a.archive/'f1-comparison.json').read_bytes(); sha=hashlib.sha256(raw).hexdigest()
assert sha=='81f6dcb59541dc4e6667745194df25f54d2debb2888fc748194eac799e8843f8',sha
j=json.loads(raw);records=[]
for r in j['rows']:
 if r['arm']=='E1':continue
 c=r['chain'];t=r['trace'];origin=r['anchor_request_lower_us'];ts=np.rint(np.array(t['t_state'])*1e6).astype('int64')+origin
 target=np.array(t['target_velocity']);vel=np.array(t['velocity']);action=np.array(t['action']);act=np.array(t['active'])
 assert all(x['applied_sample_us']==c['first_neural_publish_us'] for x in c['four_motor_records'])
 assert all(x['sim_us']==c['first_four_application_us'] for x in c['four_motor_records'])
 assert np.all(np.array(c['first_publication_inference']['target_velocity'])==0)
 firstread=c['first_read_us'];active=c['activation_us'];firstpub=c['first_neural_publish_us'];mask=(ts>=active)&(ts<firstread)&(act==1)
 indices=np.flatnonzero(mask);assert len(indices)>0
 assert np.all(target[mask]==0),r['case']
 pre=ts<firstread;last=np.flatnonzero(pre)[-1];post=np.flatnonzero(ts>=firstread)[0]
 # Explicit left-hold integration over clipped [activation, firstread) native intervals.
 impulse=0.;covered=0
 for ix in indices:
  end=min(firstread,int(ts[ix+1]) if ix+1<len(ts) else firstread);dt=max(0,end-max(active,int(ts[ix])))/1e6
  impulse+=dt*float(np.sum((vel[ix]-target[ix])**2));covered+=dt
 actual=c['first_reference_consumption'];before=c['before_activation_native'];fp=c['first_publication_inference']
 assert actual['timestamp_us']==firstread
 pub_motor=(np.array(fp['action'])[[0,2,3,1]]+1)/2
 assert np.max(np.abs(pub_motor-np.array(c['first_neural_motor'])))<1e-6
 rec={'case':r['case'],'arm':r['arm'],'request_native_lower_us':origin,'ACK_native_us':[x['timestamp_us'] for x in c['ack']],
      'activation_us':active,'first_neural_publish_us':firstpub,'first_all_four_applied_us':c['first_four_application_us'],'first_valid_reference_read_us':firstread,
      'motor_to_reference_ms':(firstread-c['first_four_application_us'])/1000,'activation_to_reference_ms':(firstread-active)/1000,
      'zero_target_native_rows':int(mask.sum()),'zero_target_velocity_error_squared_integral_m2_s':impulse,'integral_coverage_s':covered,
      'before_activation_target_velocity':before['target_velocity'],'first_applied_command_target_velocity':fp['target_velocity'],
      'first_applied_normalized_motor':c['first_neural_motor'],'previous_classic_normalized_motor':c['last_classic_motor'],'first_motor_step_L2':c['motor_jump_l2'],
      'resume_target_position':actual['target_position'],'resume_target_velocity':actual['target_velocity'],'resume_action':actual['action'],
      'target_position_jump_from_previous_native_m':float(np.linalg.norm(np.array(actual['target_position'])-np.array(t['target_position'])[last])),
      'target_velocity_jump_from_previous_native_m_s':float(np.linalg.norm(np.array(actual['target_velocity'])-target[last])),
      'previous_native_before_read_us':int(ts[last]),'first_trace_native_at_or_after_read_us':int(ts[post]),
      'normalized_motor_equivalent_step_at_reference_L2':float(np.linalg.norm((np.array(actual['action'])-action[last])/2)),
      'peak_tilt_deg':r['physical']['peak_tilt_deg'],'first_1s_peak_tilt_deg':r['physical']['peak_tilt_first_1s'],
      'velocity_atbound_axes_200ms':c['velocity_atbound_axes_200ms'],'action_atbound_axes_200ms':c['action_atbound_axes_200ms'],'native_steps_200ms':c['native_steps_200ms'],
      'first_send_profile_phase_s':c['first_send']['profile_s']}
 # Optional independent physical CSV peak check, wholly on original sample grid.
 candidates=[a.archive/(r['case']+'-a1')/'physical-attitude.csv.gz',a.archive/'native'/(r['case']+'-a1')/'physical-attitude.csv.gz']
 physical=next((q for q in candidates if q.exists()),None)
 if physical:
  with gzip.open(physical,'rt') as f: rows=list(csv.DictReader(f))
  v=np.array([float(x['tilt_deg']) for x in rows]);assert abs(v.max()-rec['peak_tilt_deg'])<1e-6
  rec['native_attitude_peak_recomputed']=float(v.max());rec['attitude_csv_sha256']=hashlib.sha256(physical.read_bytes()).hexdigest()
 records.append(rec)
output={'source_sha256':sha,'analysis':'Frozen F1 offline recomputation; new numerical analysis, zero new flights','records':records}
(a.out/'t3-recomputed.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
keys=['case','motor_to_reference_ms','zero_target_native_rows','zero_target_velocity_error_squared_integral_m2_s','first_motor_step_L2','normalized_motor_equivalent_step_at_reference_L2','target_position_jump_from_previous_native_m','target_velocity_jump_from_previous_native_m_s','peak_tilt_deg']
with (a.out/'t3-mechanism.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows([{k:r[k] for k in keys} for r in records])
print(json.dumps(output,ensure_ascii=False,indent=2))


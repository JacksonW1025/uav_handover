#!/usr/bin/env python3
"""Supplement frozen score with strict observed-pass checks and actual activation timing."""
import argparse,json,sys
from pathlib import Path
import numpy as np
from pyulog import ULog
sys.path.insert(0,str(Path(__file__).parent));import score as s
m=s.m

def main(out):
 rows=[]
 for path in sorted(Path(__file__).parent.glob('[0-9][0-9][0-9]*/score.json')):
  r=m.load(path);a=m.load(path.parent/'audit.json');run=Path(r['run']);start=r['start_native_us'];req=r['request_lower_us'];end=r['end_native_us'];w=r['native_windows']['subject'];ph=r['physical'];u=ULog(str(run/'flight.ulg'),message_name_filter_list=['research_memory','research_p11','research_target','vehicle_attitude','vehicle_local_position','research_angular_velocity'])
  d={z.name:z.data for z in u.data_list if z.multi_id==0};finite={}
  for topic,fields in [('vehicle_attitude',[f'q[{i}]' for i in range(4)]),('vehicle_local_position',['x','y','z','vx','vy','vz']),('research_angular_velocity',[f'xyz[{i}]' for i in range(3)])]:
   z=d.get(topic,{});t=np.asarray(z.get('timestamp',[]));ix=(t>=start)&(t<=end);finite[topic]=bool(ix.any() and np.isfinite(np.column_stack([z[k][ix] for k in fields])).all())
  gaps={k:ph[k]['max_gap_s'] for k in ['attitude_coverage','position_coverage','rate_coverage']};coverage_ok=bool(w.get('complete') and w.get('observations_finite') and all(finite.values()) and all(v is not None and v<=.020001 for v in gaps.values()) and not u.dropouts)
  failure=ph['first_tilt_gt45_s'] is not None or ph['first_loss_gt1_s'] is not None
  status='FAILURE' if failure else ('OBSERVED_PASS' if coverage_ok else 'UNKNOWN')
  item=dict(case=r['case'],physical_task_final=status,raw_score_physical_task=r['physical_task'],coverage_and_finite_ok=coverage_ok,native_window_complete=w.get('complete'),native_window_finite=w.get('observations_finite'),direct_finite=finite,max_gap_s=gaps,dropout_count=len(u.dropouts),boundary_kind='neural_motor_owner' if r['controller']=='neural' else 'classic_AUTO_LOITER_nav_state',start_us=start,pre_request_state=a['request_state'],pre_boundary_state=a['start_state'])
  p=d['research_p11'];pt=p['timestamp'];ix=np.flatnonzero((pt>=req)&(pt<=start+100000)&(p['active']==1)&(p['native_step']==1))
  if r['controller']=='neural' and len(ix):
   i=int(ix[0]);z=m.row(p,i);item['first_active_native_consumption']=z;item['active_to_owner_us']=start-int(pt[i]);item['active_to_score_start_us']=r['first_score_sample_s']*1e6+start-int(pt[i]);item['activation_velocity_error_m_s']=float(np.linalg.norm(s.vector(p,'velocity')[i]-s.vector(p,'network_target_velocity')[i]));item['initial_gru_before_norm']=float(np.linalg.norm(s.vector(p,'gru_before',16)[i]));item['initial_previous_action']=s.vector(p,'previous_action_before',4)[i].tolist()
   mem=d['research_memory'];mt=mem['timestamp'];mi=np.flatnonzero((mt>=req)&(mt<=start+100000)&(mem['kind']==2));item['entry_memory_events']=[m.row(mem,int(j)) for j in mi]
  capture=a['activation_capture_rows'];rtgt=a['spec']['state_parameters']['MC_RAPTOR_RTGT'];item['capture_expected_mode']=rtgt;item['capture_verified']=None
  if r['controller']=='neural' and len(capture)==1:
   z=capture[0];v=np.array([z[f'velocity[{j}]'] for j in range(3)]);vv=np.array([z[f'vehicle_velocity[{j}]'] for j in range(3)]);expect=np.zeros(3) if rtgt==0 else np.array([vv[0],vv[1],0]);item['capture_verified']=bool(z['mode']==rtgt and np.max(abs(v-expect))<=1e-6);item['captured_velocity']=vv.tolist();item['captured_target_velocity']=v.tolist()
  original=m.load(path.parent/'original-analysis.json')
  if r['controller']=='neural':
   rec=original['boundaries'][0]['frozen_joint_recovery']
  else:
   fu=ULog(str(run/'flight.ulg'));fd={z.name:z.data for z in fu.data_list if z.multi_id==0};rec=m.joint_recovery(fd,start,end,2)
  safety=any(e['event']=='failure' and 'safety' in str(e.get('reason','')).lower() for e in m.lines(run/'events.jsonl'))
  item['frozen_joint_recovery']=rec
  item['frozen_numeric_and_recovery_recomputed']=m.frozen(w,rec,safety)
  item['frozen_original']=r.get('original_frozen')
  item['frozen_note']='Same frozen numeric limits and recovery algorithm, independently recomputed. Original evidence-limited aggregate retained. Expected native reference semantics require the separate capture audit, never silent removal of other missing evidence.'
  rows.append(item)
 if out.exists():raise RuntimeError('refuse existing output')
 s.write(out,dict(rows=rows,note='Final physical pass requires native coverage, finite samples, <=20ms gaps and no ULog dropouts. Physical finite violations remain failures even when other evidence is missing. Score values and old outputs are unchanged. V starts after actual motor ownership, not necessarily the first activation inference.'))
 print(json.dumps([{k:x.get(k) for k in ['case','physical_task_final','coverage_and_finite_ok','capture_verified','initial_gru_before_norm','active_to_owner_us']} for x in rows]))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();main(a.out)

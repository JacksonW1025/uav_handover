#!/usr/bin/env python3
"""Actual event witnesses and irreversible height margin on common absolute task time."""
import json,sys
from pathlib import Path
import numpy as np
from pyulog import ULog
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p12c.features import load
from p12b.read_trace import load as direct_read
from p11.models import tilt
from p9_model import write,sha

def create(run,analysis,out):
 if out.exists():raise FileExistsError(out)
 run=run.resolve();analysis=analysis.resolve();cfg=json.load(open(run/'config.json'))
 if (analysis/'native/history.npz').exists():d=load(run,analysis)
 else:
  from preparation_acceptance import feat
  d=feat(run.parent)
 if (analysis/'packed/prediction-input.json').exists():plan=json.load(open(analysis/'packed/prediction-input.json'))['plan']
 else:
  from p11.pack import source_plan
  events=[json.loads(x) for x in (run/'events.jsonl').read_text().splitlines()];origin=next(x for x in events if x['event']=='p1_reference_origin');plan=source_plan(cfg,origin['origin_ned_m'],origin['yaw_rad'])
 first=plan['common_first_gap_profile_s'];end=plan['nominal_horizon_profile_s'];n=len(d['t']);i0=max(0,int(np.searchsorted(d['t'],0,side='right')-1));H=-d['truth_pv'][:,2];H0=H[i0];L=H0-H;lp0=-d['position'][i0,2];lploss=lp0+d['position'][:,2]
 hist=np.maximum.accumulate(np.where(d['t']>=0,np.maximum(L,0),0));lphist=np.maximum.accumulate(np.where(d['t']>=0,np.maximum(lploss,0),0));table=np.asarray(plan['profile']['table']);jt=np.clip(np.floor((d['t']-plan['profile']['table_t0_s'])/.004+1e-8).astype(int),0,len(table)-1);task=table[jt,:3];tracking=np.linalg.norm(d['position'][:,:2]-task[:,:2],axis=1)
 if (analysis/'native/native-audit.json').exists():native=json.load(open(analysis/'native/native-audit.json'))
 else:
  from p12.audit import audit as legacy_native
  native=legacy_native(run,out.parent/(out.name+'-legacy-native'))
 measured=json.load(open(analysis/'measured/measurement.json')) if (analysis/'measured/measurement.json').exists() else json.load(open(out.parent/(out.name+'-measurement')/'measurement.json'))
 valid_end=min(end,float(d['t'][-1]));epoch=d['run_wall_ns'][0]-d['t'][0]*1e9
 if measured.get('failure'):valid_end=min(valid_end,(measured['failure']['monotonic_ns']-epoch)/1e9)
 has_direct=(run/'gz-motor/read-p12b.bin').exists();direct=direct_read(run/'gz-motor/read-p12b.bin') if has_direct else None
 pre=[]
 for k in range(n):
  if not has_direct:pre.append(None);continue
  candidates=np.flatnonzero((direct['timestamp_sample']==d['sample_us'][k])&(direct['pre_read_wall_ns']>=d['run_wall_ns'][k])&(direct['pre_read_wall_ns']<=d['read_wall_ns'][k]))
  if len(candidates)!=1:raise RuntimeError('event table same-call direct record not unique')
  pre.append(int(candidates[0]))
 output=next(x.data for x in ULog(str(run/'flight.ulg'),['research_output']).data_list if x.name=='research_output');bridge_time=output['wall_monotonic_ns'];bridge_idx=np.searchsorted(bridge_time,d['run_wall_ns'],side='right')-1
 rows=[];event_info=[]
 def state(label,t,witness=None):
  if t<d['t'][0] or t>valid_end:return {'label':label,'status':'NOT_REACHED','planned_profile_s':float(t),'record_end_profile_s':float(d['t'][-1]),'valid_experiment_end_profile_s':float(valid_end),'state':None}
  k=max(0,int(np.searchsorted(d['t'],t,side='right')-1));p=pre[k];j=bridge_idx[k]
  return {'label':label,'status':'OBSERVED','requested_profile_s':float(t),'observed_profile_s':float(d['t'][k]),'sample_us':int(d['sample_us'][k]),'native_us':int(d['native_us'][k]),'witness':witness,'state':{'world_height_m':float(H[k]),'task_start_world_height_m':float(H0),'world_current_loss_m':float(L[k]),'world_current_height_margin_m':float(1-L[k]),'world_historical_max_loss_m':float(hist[k]),'world_history_margin_m':float(1-hist[k]),'world_height_failed_ever':bool(hist[k]>1),'world_callback_age_us':int(d['sample_us'][k]-d['truth_pv_sample'][k]),'world_down_velocity_callback_difference_m_s':float(d['truth_pv'][k,5]),'LP_z_ned_m':float(d['position'][k,2]),'LP_down_velocity_m_s':float(d['velocity'][k,2]),'LP_current_loss_m':float(lploss[k]),'LP_historical_loss_m':float(lphist[k]),'LP_height_failed_ever':bool(lphist[k]>1),'attitude_quaternion':d['attitude'][k].tolist(),'tilt_deg':tilt(d['attitude'][k]),'world_truth_tilt_deg':tilt(d['truth_q'][k]),'angular_velocity_body_rad_s':d['omega'][k].tolist(),'horizontal_task_tracking_error_m':float(tracking[k]),'horizontal_active_reference_error_m':float(np.linalg.norm(d['position'][k,:2]-d['target_p'][k,:2])),'position_ned_m':d['position'][k].tolist(),'velocity_ned_m_s':d['velocity'][k].tolist(),'target_p_ned_m':d['target_p'][k].tolist(),'target_v_ned_m_s':d['target_v'][k].tolist(),'h_before':d['h_before'][k].tolist(),'previous_action_before':d['previous'][k].tolist(),'action_after':d['action'][k].tolist(),'history_mean_before':d['mean'][k].tolist(),'history_count_before':int(d['count'][k]),'last_completed_filter_after_rad_s':d['exec_filter_after'][k].tolist(),'last_completed_scaled_joint_rad_s':d['exec_scaled_joint'][k].tolist(),'last_consumed_command_rad_s':d['exec_command'][k].tolist(),'latest_bridge_published_command_rad_s':None if j<0 else [float(output[f'motor_speed[{a}]'][j]) for a in range(4)],'bridge_selected_sample_us':None if j<0 else int(output['timestamp_sample'][j]),'pending_transport_queue':'NOT_FULLY_OBSERVED; latest bridge and last consumed are distinct','execution_state_age_us':((d['run_wall_ns'][k].astype(np.int64)-d['exec_end_ns'][k].astype(np.int64))/1000).tolist(),'lp_age_us':int(d['sample_us'][k]-d['lp_sample'][k]),'attitude_age_us':int(d['sample_us'][k]-d['att_sample'][k]),'actual_GRU_commit':bool(d['committed'][k]),'pre_read_initialized':None if p is None else bool(direct['timing_initialized_pre'][p]),'force_sync_initialized':None if p is None else bool(direct['force_sync_initialized_pre'][p]),'force_sync_pre':None if p is None else int(direct['force_sync_pre'][p]),'index_pre':None if p is None else int(direct['call_index_pre'][p]),'gate_applicable':None if p is None else bool(direct['gate_applicable'][p]),'gate_permit':None if p is None else bool(direct['gate_permit'][p]),'actual_valid_read':None if p is None else bool(direct['read_valid'][p]),'repair_not_before_ms':None if p is None else int(direct['repair_not_before_ms'][p])}}
 sources=plan['full_source_windows_profile_s'];ab=[0,1] if cfg['p11']['source']['condition'].endswith('h45-g0.55') else [0,2]
 # Family is also determined from source gap: preserve original source index.
 if len(sources)>2 and abs(sources[1][0]-sources[0][1]-.55)<1e-5:ab=[0,1]
 mask=cfg['p11']['event_mask']
 for name,index in zip(['A','B'],ab):
  a,b=sources[index];rows.append(state(name+'_before',a-.004));e={'label':name,'source_index':index,'planned_window_profile_s':[a,b]}
  if index not in mask:
   e['status']='NOT_PLANNED';rows += [{'label':name+'_capture','status':'NOT_PLANNED','state':None},{'label':name+'_resume','status':'NOT_PLANNED','state':None}];event_info.append(e);continue
  caps=[c for c in native['captures'] if not c['activation'] and a<=(np.mean(c['capture_host_interval_ns'])-epoch)/1e9<b+.1]
  if len(caps)>1:raise RuntimeError('multiple planned captures')
  if caps:
   c=caps[0];t=(np.mean(c['capture_host_interval_ns'])-epoch)/1e9;row=state(name+'_capture',t,c);rows.append(row);e['capture_profile_s']=t;e['status']='CAPTURE_REACHED'
   res=np.flatnonzero((d['t']>=b)&(d['read_valid'])&(~d['stale']))
   if len(res):
    jr=int(res[0]);rows.append(state(name+'_resume',float(d['t'][jr]),{'actual_external_read_sample_us':int(d['sample_us'][jr])}));e['resume_profile_s']=float(d['t'][jr]);e['resume_status']='READ_AND_FRESH_CONFIRMED'
    sel=(d['t']>=t)&(d['t']<d['t'][jr]);ep=d['position'][sel]-d['target_p'][sel];ev=d['velocity'][sel]-d['target_v'][sel];yaw=d['target_yaw'][sel];c0=np.cos(yaw);s0=np.sin(yaw);px=c0*ep[:,0]+s0*ep[:,1];py=s0*ep[:,0]-c0*ep[:,1];vx=c0*ev[:,0]+s0*ev[:,1];vy=s0*ev[:,0]-c0*ev[:,1]
    e['entire_capture_hold']={'rows':int(sel.sum()),'horizontal_position_max_axis_m':float(np.max(abs(np.c_[px,py]))),'horizontal_velocity_max_axis_m_s':float(np.max(abs(np.c_[vx,vy]))),'position_clipped_rows':int(np.sum(np.max(abs(np.c_[px,py]),axis=1)>.5)),'velocity_clipped_rows':int(np.sum(np.max(abs(np.c_[vx,vy]),axis=1)>1)),'capture_to_resume_s':float(d['t'][jr]-t)}
   else:rows.append({'label':name+'_resume','status':'NOT_REACHED','state':None});e['resume_status']='NOT_REACHED'
  else:
   e['status']='NOT_REACHED' if d['t'][-1]<b+.1 else 'MISSING_CAPTURE';rows += [{'label':name+'_capture','status':e['status'],'state':None},{'label':name+'_resume','status':'NOT_REACHED','state':None}]
  event_info.append(e)
 recover=measured['joint_recovery_after_final_capture']
 if recover['status']=='SETTLED' and measured['final_capture_us'] is not None and recover['from_final_capture_s'] is not None:
  entry=measured['final_capture_us']+recover['from_final_capture_s']*1e6;matches=np.flatnonzero(d['native_us']>=entry)
  if len(matches):rows.append(state('poststream_recovery_interval_entry',float(d['t'][matches[0]]),{'entry_native_us':entry,'confirmation_native_us':entry+cfg['joint_recovery']['dwell_s']*1e6,'final_capture_recovery':recover,'meaning':'interval start after frozen dwell verification; sampled state aligned at first controller row on/after entry, not exact continuous first recovery'}))
  else:rows.append({'label':'poststream_recovery_interval_entry','status':'INSUFFICIENT_CONTROLLER_ALIGNMENT','state':None})
 else:rows.append({'label':'poststream_recovery_interval_entry','status':recover['status'],'state':None})
 rows.append(state('nominal_task_end',end))
 out.mkdir(parents=True,exist_ok=False);write(out/'event-states.json',{'schema':'p12b-event-states-1','run':str(run),'raw_ulog_sha256':sha(run/'flight.ulg'),'direct_read_sha256':sha(run/'gz-motor/read-p12b.bin') if has_direct else None,'pre_read_readiness_scope':'direct-v2 canonical' if has_direct else 'NOT_AVAILABLE_OR_NOT_PASSED; no backfilled readiness flags','valid_experiment_end_profile_s':float(valid_end),'LP_table_loss_origin':'task0 diagnostic; frozen LP primary criterion retains first common A sample reference','H_convention':'H=-truth_NED_z, baseline common task start, never reset; truth velocity is callback finite difference not direct physical twist','event_state_semantics':'p/v/q/cache and h/previous/history-before at accepted call, active target after source target update, action-after distinguished; asynchronous execution age retained','events':event_info,'rows':rows,'full_task_measurement':measured['whole'],'frozen_outcome':measured['frozen_flight_outcome'],'task_outcome':measured['task_outcome'],'censored':measured['censored']})
 print('EVENT_TABLE',len(rows),[(e['label'],e['status']) for e in event_info])
if __name__=='__main__':create(Path(sys.argv[1]),Path(sys.argv[2]),Path(sys.argv[3]))

#!/usr/bin/env python3
"""P1 per-run measurement of the subject event (handover or same-controller baseline) from raw run evidence.

Reads flight.ulg, events.jsonl, config.json and the analyzer's metrics.json; writes only p1-metrics.json.
Times are native PX4 microseconds. The trigger is the native pre-request bound taken while the reference
stream still ran; the actual change is the actuator owner change (handovers), the AUTO_LOITER nav_state change
(classic baseline) or RAPTOR's logged target capture after its setpoint timeout (RAPTOR baseline).
"""
import argparse,hashlib,json,math
from pathlib import Path
import numpy as np
from pyulog import ULog
from recovery import recovery,_recovery
from p0_metrics import raptor_captures,raptor_target_profile,controller_target,neural_intervals

TOPICS=['vehicle_local_position','vehicle_angular_velocity','research_angular_velocity','vehicle_attitude','actuator_motors',
        'research_actuator','vehicle_status','trajectory_setpoint','research_state_response','research_target']
SUBJECTS={'p1_c_to_n':'C_to_N','p1_n_to_c':'N_to_C','p1_baseline_classic':'classic_brake','p1_baseline_raptor':'raptor_hold'}
LOITER=4

def clean(v):
    if isinstance(v,dict):return {k:clean(x) for k,x in v.items()}
    if isinstance(v,np.ndarray):return clean(v.tolist())
    if isinstance(v,(list,tuple)):return [clean(x) for x in v]
    if isinstance(v,(float,np.floating)):return float(v) if math.isfinite(v) else None
    if isinstance(v,(np.integer,)):return int(v)
    if isinstance(v,np.bool_):return bool(v)
    return v

def asof(stamps,t):
    i=int(np.searchsorted(stamps,t,side='right'))-1
    return i if i>=0 else None

def hold_durations(t,mask,start,end):
    """Total time [s] the as-of held sample satisfies mask inside [start,end)."""
    t=np.asarray(t,np.int64);nxt=np.r_[t[1:],end]
    a=np.clip(t,start,end);b=np.clip(nxt,start,end)
    return float(np.sum((b-a)[mask])/1e6)

def speed_matched_capture(target,t_c):
    """P4-01c: research_target activation capture with mode 1 (T1) near the owner change, else None."""
    if target is None or 'kind' not in target:return None
    t=np.asarray(target['timestamp'],np.int64)
    rows=np.flatnonzero((target['kind']==1)&(target['activation']==1)&(target['mode']==1)&(np.abs(t-t_c)<=50000))
    if not len(rows):return None
    i=rows[0];return {'px4_us':int(t[i]),'velocity_ned_m_s':[float(target[f'velocity[{k}]'][i]) for k in range(3)]}

def profile_row_at(target,stamp):
    t=np.asarray(target['timestamp'],np.int64);rows=np.flatnonzero((target['kind']==2)&(t<=stamp))
    if not len(rows):return None
    i=rows[-1];return {'px4_us':int(t[i]),'position_ned_m':[float(target[f'position[{k}]'][i]) for k in range(3)],
        'velocity_ned_m_s':[float(target[f'velocity[{k}]'][i]) for k in range(3)]}

def tilt_deg(q):return np.degrees(np.arccos(np.clip(1-2*(q[:,1]**2+q[:,2]**2),-1,1)))

def analyze(run,allow_abort=False):
    run=Path(run).resolve();cfg=json.loads((run/'config.json').read_text());meta=json.loads((run/'metadata.json').read_text())
    events=[json.loads(s) for s in (run/'events.jsonl').read_text().splitlines()]
    metrics=json.loads((run/'metrics.json').read_text())
    # P2 kinds reuse the P1 flight sequence and measurement; their profile is the recorded merged p2_profile.
    kind=meta['experiment_type'];flow=kind.replace('p2_','p1_');p1=cfg.get('p2_profile') or cfg['p1'];problems=[]
    ulog=ULog(str(run/'flight.ulg'),TOPICS)
    topics={d.name:d.data for d in ulog.data_list if d.multi_id==0}
    messages=[(int(m.timestamp),m.message) for m in ulog.logged_messages]
    trig=next((e for e in events if e['event']=='p1_trigger'),None)
    post=[e for e in events if e['event']=='p1_phase_ended' and e['label']=='post_event']
    stopped=next((e for e in events if e['event']=='p1_reference_stopped'),None)
    out={'run':str(run),'kind':kind,'subject':SUBJECTS.get(flow),'condition':cfg.get('p1_condition'),'speed_m_s':cfg.get('p1_speed_m_s'),
         'ulog_sha256':hashlib.sha256((run/'flight.ulg').read_bytes()).hexdigest(),'time_base':'native PX4 us (simulation time)'}
    if trig is None or not (post or allow_abort):return {**out,'status':'INCOMPLETE','problems':['p1_trigger or post_event phase missing']}
    t_r=int(trig['end_bound_px4_us'])
    if post:t_e=int(post[0]['px4_end_us'])
    else:
        # Exploration only: an aborted flight is measured up to the planned window end, disarm or log end.
        vs=next(d.data for d in ulog.data_list if d.name=='vehicle_status' and d.multi_id==0)
        disarm=vs['timestamp'][(vs['timestamp']>t_r)&(vs['arming_state']!=2)]
        t_e=int(min([t_r+p1['post_handover_s']*1e6,ulog.last_timestamp]+([int(disarm[0])] if len(disarm) else [])))
        out['window_truncated']={'reason':'post_event phase missing (flight aborted)','window_end_px4_us':t_e}
    out['trigger_px4_us']=t_r;out['window_end_px4_us']=t_e
    transitions=metrics.get('actuator_owner_transitions',[])
    intervals=neural_intervals(transitions,metrics['ulog_end_us'])
    captures=raptor_captures(messages,intervals)
    # P4-01c T1: the speed-matched target moves after the capture; its logged per-cycle target is the controller target.
    profile=raptor_target_profile(topics.get('research_target'),intervals)
    target=controller_target(topics['trajectory_setpoint'],captures+profile)
    status=topics['vehicle_status']
    # Actual change and the incoming controller's reference capture.
    reference={};t_c=None;mode_us=None
    if flow in ['p1_c_to_n','p1_n_to_c']:
        want=(2,1) if flow=='p1_c_to_n' else (1,2)
        tr=next((x for x in transitions if x['px4_us']>=t_r and (x['from'],x['to'])==want),None)
        if tr is None:problems.append('owner change after trigger missing')
        else:t_c=int(tr['px4_us']);mode_us=tr.get('mode_change_us');out['owner_transition']=tr
    elif flow=='p1_baseline_classic':
        rows=np.flatnonzero((status['timestamp']>=t_r)&(status['nav_state']==LOITER))
        if len(rows):mode_us=t_c=int(status['nav_state_timestamp'][rows[0]])
        else:problems.append('AUTO_LOITER after trigger missing')
    else:
        cap=next((c for c in captures if c[0]>=t_r),None)
        if cap is None:problems.append('RAPTOR capture after trigger missing')
        else:t_c=int(cap[0])
    if t_c is None or not t_r<=t_c<t_e:
        return clean({**out,'status':'INCOMPLETE','problems':problems or ['change outside window']})
    out['change_px4_us']=t_c
    out['delays_ms']={'trigger_to_change':(t_c-t_r)/1e3,'trigger_to_nav_state':(mode_us-t_r)/1e3 if mode_us else None,
        'nav_state_to_change':(t_c-mode_us)/1e3 if mode_us else None,
        'note':'trigger is a native lower bound read before the request, so trigger-based delays are upper bounds of the true request delay'}
    sp=topics['trajectory_setpoint'];st=sp['timestamp'].astype(np.int64)
    if flow in ['p1_c_to_n','p1_baseline_raptor']:
        cap=next((c for c in captures if c[0]>=t_c-20000),None)
        on_change=cap is not None and abs(cap[0]-t_c)<=50000
        reference={'mechanism':'RAPTOR internal capture (current position and yaw, zero velocity)',
                   'capture_px4_us':cap[0] if cap else None,'position_ned_m':cap[1] if cap else None,'velocity_ned_m_s':[0.,0.,0.]}
        if flow=='p1_c_to_n':
            reference['classification']='activation_reset_hold' if on_change else 'not_at_activation'
            r=topics['research_state_response'];rows=np.flatnonzero((r['timestamp']>=t_c)&(r['target']==1)&(r['operation']==1)&(r['result']==0)&(r['active']==1))
            speed_matched=speed_matched_capture(topics.get('research_target'),t_c)
            if speed_matched is not None:
                reference.update({'mechanism':'RAPTOR internal capture (current position and yaw, current horizontal velocity, then fixed deceleration; P4-01c T1)',
                    'classification':'activation_speed_matched' if on_change else 'not_at_activation','velocity_ned_m_s':speed_matched['velocity_ned_m_s']})
            if len(rows):
                i=rows[0];values=[float(r[f'values[{k}]'][i]) for k in range(20,26)]
                reference['state_read_after_entry']={'px4_us':int(r['timestamp'][i]),'position_ned_m':values[:3],'velocity_ned_m_s':values[3:]}
                if speed_matched is None:reference['state_read_matches_capture']=bool(cap) and max(abs(a-b) for a,b in zip(values[:3],cap[1]))<1e-4 and max(map(abs,values[3:]))<1e-6
                else:
                    # T1: the state read returns the target of that cycle, i.e. the logged profile row at the read time.
                    row=profile_row_at(topics['research_target'],int(r['timestamp'][i]))
                    reference['state_read_profile_row_px4_us']=row['px4_us'] if row else None
                    reference['state_read_matches_capture']=bool(cap and row) and max(abs(a-b) for a,b in zip(values,row['position_ned_m']+row['velocity_ned_m_s']))<1e-4
            else:reference['state_read_matches_capture']=False
            want='activation_reset_hold' if speed_matched is None else 'activation_speed_matched'
            if reference['classification']!=want or not reference['state_read_matches_capture']:problems.append('RAPTOR activation capture not confirmed')
        else:
            last=st[st<t_c];reference['classification']='setpoint_timeout_hold'
            reference['last_external_setpoint_to_capture_ms']=(t_c-int(last[-1]))/1e3 if len(last) else None
    else:
        rows=np.flatnonzero(st>=t_c)
        if not len(rows) or st[rows[0]]-t_c>100000:problems.append('AUTO_LOITER trajectory_setpoint after change missing')
        else:
            i=rows[0];fin=asof(st,t_e)
            reference={'mechanism':'AUTO_LOITER (navigator loiter point, FlightTaskAuto braking trajectory)','classification':'auto_loiter',
                'first_setpoint_px4_us':int(st[i]),'position_ned_m':[float(sp[f'position[{k}]'][i]) for k in range(3)],
                'velocity_ned_m_s':[float(sp[f'velocity[{k}]'][i]) for k in range(3)],
                'final_position_ned_m':[float(sp[f'position[{k}]'][fin]) for k in range(3)]}
    out['reference_at_takeover']=reference
    # Observations (acquisition clocks as in P0 recovery).
    local=dict(topics['vehicle_local_position']);local['timestamp']=local.get('timestamp_sample',local['timestamp'])
    ang_name='research_angular_velocity' if 'research_angular_velocity' in topics else 'vehicle_angular_velocity'
    angular=dict(topics[ang_name]);angular['timestamp']=angular.get('timestamp_sample',angular['timestamp'])
    lt=local['timestamp'].astype(np.int64);pos=np.stack([local[k] for k in 'xyz'],1).astype(float);vel=np.stack([local['v'+k] for k in 'xyz'],1).astype(float)
    ic=asof(lt,t_c);ir=asof(lt,t_r)
    axis=np.asarray(p1['motion_axis_ned'],float)
    out['state_at_change']={'position_ned_m':pos[ic],'velocity_ned_m_s':vel[ic],'horizontal_speed_m_s':float(np.hypot(*vel[ic,:2])),
        'speed_along_axis_m_s':float(vel[ic]@axis),'altitude_m':float(-pos[ic,2])}
    out['state_at_trigger']={'position_ned_m':pos[ir],'horizontal_speed_m_s':float(np.hypot(*vel[ir,:2])),'altitude_m':float(-pos[ir,2])}
    w=(lt>=t_r)&(lt<t_e);wc=(lt>=t_c)&(lt<t_e)
    tg=np.searchsorted(target['timestamp'],lt,side='right')-1
    tpos=np.stack([target[f'position[{k}]'][np.maximum(tg,0)] for k in range(3)],1);tpos[tg<0]=np.nan
    err=np.linalg.norm(pos-tpos,axis=1)
    final=tpos[asof(lt,t_e-1)]
    out['primary']={
        'max_altitude_loss_m':max(0.,float(np.max(pos[w,2])-pos[ir,2])),
        'max_altitude_loss_definition':'max over [trigger, window end] of descent below the altitude at the trigger',
        'max_below_active_target_altitude_m':max(0.,float(np.nanmax(pos[w,2]-tpos[w,2])))}
    rec=recovery(local,angular,cfg['joint_recovery'],t_c,t_e,target)
    jr=rec['joint_recovery']
    out['primary']['joint_recovery']={'status':jr['status'],'from_change_s':jr['time_s'],
        'from_trigger_s':(jr['entry_us']-t_r)/1e6 if jr['entry_us'] else None,'confirmed_px4_us':jr['confirmed_us'],
        'true_first_recovery_uncertain':jr['true_first_recovery_uncertain'],'position_reference':rec['position_reference'],
        'fixed_reference_comparison':rec['fixed_reference_comparison']['joint_recovery'],
        'trajectory_setpoint_only_comparison':_recovery(local,angular,cfg['joint_recovery'],t_c,t_e,topics['trajectory_setpoint'])['joint_recovery'],
        'observation_quality':rec['observation_quality']}
    # Constraints in the handover window [trigger, window end], frozen P0 thresholds.
    att=topics['vehicle_attitude'];at=att['timestamp'].astype(np.int64);aw=(at>=t_r)&(at<t_e)
    tilt=tilt_deg(np.stack([att[f'q[{i}]'] for i in range(4)],1)[aw])
    av=topics['vehicle_angular_velocity'];avt=av['timestamp'].astype(np.int64);avw=(avt>=t_r)&(avt<t_e)
    rate=np.max(np.abs(np.stack([av[f'xyz[{i}]'] for i in range(3)],1)[avw]),axis=1)
    limits={'horizontal_radius_m':(float(np.max(np.hypot(pos[w,0],pos[w,1]))),cfg['safety_radius_m']),
        'altitude_m':(float(np.max(-pos[w,2])),cfg['safety_altitude_m']),'below_ground_z_m':(float(np.max(pos[w,2])),1.0),
        'tilt_safety_deg':(float(np.max(tilt)),cfg['safety_tilt_deg']),'angular_rate_component_rad_s':(float(np.max(rate)),cfg['safety_angular_rate_rad_s']),
        'error_to_active_target_m':(float(np.nanmax(err[w])),cfg['hover_max_error_m']),'tilt_hover_deg':(float(np.max(tilt)),cfg['hover_max_tilt_deg'])}
    out['primary']['window_constraints']={k:{'max':a,'limit':b,'satisfied':a<=b} for k,(a,b) in limits.items()}
    out['primary']['window_constraints_all_satisfied']=all(a<=b for a,b in limits.values())
    out['primary']['window_constraints_note']='Window = [trigger, end of post_event phase]. Safety envelope plus P0 hover error/tilt limits applied to the active controller target; unchanged p0.json thresholds.'
    # Auxiliary.
    overshoot=float(np.max((pos[wc]-final)@axis)) if np.all(np.isfinite(final)) else None
    out['auxiliary']={'max_position_error_to_active_target_m':float(np.nanmax(err[wc])),
        'max_position_error_to_active_target_window_m':float(np.nanmax(err[w])),
        'max_deviation_from_final_target_m':float(np.max(np.linalg.norm(pos[wc]-final,axis=1))) if np.all(np.isfinite(final)) else None,
        'overshoot_past_final_target_along_axis_m':overshoot,'final_target_ned_m':final,
        'travel_from_change_to_final_target_m':float(np.linalg.norm(final[:2]-pos[ic,:2])) if np.all(np.isfinite(final)) else None}
    m=topics['actuator_motors'];mt=m['timestamp'].astype(np.int64);mv=np.stack([m[f'control[{i}]'] for i in range(4)],1).astype(float)
    lo,hi=p1['motor_step_window_s'];sw=(mt>=t_c+lo*1e6)&(mt<=t_c+hi*1e6)
    idx=np.flatnonzero(sw);steps=np.max(np.abs(np.diff(mv[idx],axis=0)),axis=1) if len(idx)>1 else np.array([])
    j=int(np.searchsorted(mt,t_c))
    sat=p1['motor_saturation'];mw=(mt>=t_r)&(mt<t_e)
    upper=np.any(mv>=sat['upper'],axis=1);lower=np.any(mv<=sat['lower'],axis=1)
    out['auxiliary']['motor']={'step_at_change':float(np.max(np.abs(mv[j]-mv[j-1]))) if 0<j<len(mt) else None,
        'max_step_in_window':float(np.max(steps)) if len(steps) else None,'step_window_s':[lo,hi],
        'saturation_upper_s':hold_durations(mt[mw],upper[mw],t_r,t_e),'saturation_lower_s':hold_durations(mt[mw],lower[mw],t_r,t_e),
        'saturation_any_s':hold_durations(mt[mw],(upper|lower)[mw],t_r,t_e),'saturation_definition':sat,
        'mean_command_before_change':mv[(mt>=t_c-500000)&(mt<t_c)].mean(0)}
    out['auxiliary']['reference_stream_stop']=stopped
    # Repeatability fingerprint: 5 s of position samples after the change.
    k=np.flatnonzero(lt>=t_c)[:500]
    out['fingerprint_sha256']=hashlib.sha256(pos[k].astype(np.float32).tobytes()).hexdigest()
    out['curves']={'note':'every 5th local-position sample for figures; time relative to the actual change',
        't_s':((lt[w]-t_c)/1e6)[::5],'position_ned_m':pos[w][::5],'velocity_ned_m_s':vel[w][::5],'target_ned_m':tpos[w][::5]}
    sel=(mt>=t_c-1000000)&(mt<t_c+2000000)
    out['curves']['motor_t_s']=(mt[sel]-t_c)/1e6;out['curves']['motor']=mv[sel]
    out['problems']=problems;out['status']='MEASURED' if not problems else 'INCOMPLETE'
    return clean(out)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);a=p.parse_args()
    result=analyze(a.run);(a.run/'p1-metrics.json').write_text(json.dumps(result,indent=1,ensure_ascii=False,allow_nan=False)+'\n')
    print(result['status'],result.get('problems'));raise SystemExit(0 if result['status']=='MEASURED' else 1)

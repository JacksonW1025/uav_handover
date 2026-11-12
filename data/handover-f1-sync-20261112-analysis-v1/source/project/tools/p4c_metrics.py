#!/usr/bin/env python3
"""P4-01c per-run takeover-target evidence and metrics on top of p2_metrics; writes only p4c-metrics.json.

Target evidence (research_target, RAPTOR's own log of every capture and every T1 target): exactly one activation
capture at the C->N owner change with the planned MC_RAPTOR_RTGT and MC_RAPTOR_RTDEC; the captured vehicle state equals
the vehicle_local_position sample RAPTOR used; T0: zero target velocity and no profile rows; T1: initial target velocity
= that sample's horizontal velocity (vertical 0), every profile row equal to the closed-form profile recomputed here
(speed0 - a t along the captured direction, position its integral, end point speed0^2/(2a)), profile not interrupted
before the window end. Metrics: max tilt, max altitude loss, motor step and saturation, flight outcome (p2-metrics.json),
settle time (3D speed below the threshold from then on until the window end), distance from the takeover point to the
settle point, maximum travel past the takeover point along the motion axis, observation clipping (research_memory.policy_input, exact executor input), curves for figures.
"""
import argparse,json,math
from pathlib import Path
import numpy as np
from pyulog import ULog
from p1_metrics import clean,asof,hold_durations,tilt_deg
from p2_metrics import longest_run
KIND_CAPTURE,KIND_PROFILE,KIND_END=1,2,3
KIND_STEP=1

def profile(p0,v0,decel,t_s):
    """Closed-form T1 target at times t_s [s] after the capture (independent of research/state/TargetProfile.hpp)."""
    t=np.maximum(np.asarray(t_s,float),0.);s0=math.hypot(v0[0],v0[1]);u=np.array([v0[0]/s0,v0[1]/s0]) if s0>0 else np.zeros(2)
    ts=s0/decel;tau=np.minimum(t,ts);speed=np.where(t<ts,s0-decel*t,0.);d=s0*tau-.5*decel*tau*tau
    pos=np.stack([p0[0]+u[0]*d,p0[1]+u[1]*d,np.full_like(d,p0[2])],1);vel=np.stack([u[0]*speed,u[1]*speed,np.zeros_like(speed)],1)
    return pos,vel,np.where(t<ts,2,3)

def vec(topic,name,i,n=3):return [float(topic[f'{name}[{k}]'][i]) for k in range(n)]

def target_check(cfg,target,local,t_r,t_c,t_e):
    tol=cfg['p4c']['target_check'];tp=cfg['p2_treatment_parameters'];mode,decel=int(tp['rtgt']),float(tp['rtdec']);problems=[]
    if target is None:return {'status':'MISSING','problems':['research_target missing']}
    tt=np.asarray(target['timestamp'],np.int64);kind=np.asarray(target['kind'])
    caps=np.flatnonzero((kind==KIND_CAPTURE)&(target['activation']==1))
    near=[int(i) for i in caps if abs(int(tt[i])-t_c)<=50000]
    out={'planned_mode':mode,'planned_decel_m_s2':decel,'activation_captures_in_run':int(len(caps)),'activation_captures_at_change':len(near)}
    if len(near)!=1:return {**out,'status':'FAILED','problems':[f'{len(near)} activation captures at the owner change (expected 1)']}
    i=near[0];c={'px4_us':int(tt[i]),'mode':int(target['mode'][i]),'decel_m_s2':float(target['decel'][i]),'phase':int(target['phase'][i]),
        'capture_sample':int(target['capture_sample'][i]),'local_position_sample':int(target['local_position_sample'][i]),
        'vehicle_position_ned_m':vec(target,'vehicle_position',i),'vehicle_velocity_ned_m_s':vec(target,'vehicle_velocity',i),
        'target_position_ned_m':vec(target,'position',i),'target_velocity_ned_m_s':vec(target,'velocity',i),'target_yaw_rad':float(target['yaw'][i])}
    out['capture']=c
    if c['mode']!=mode:problems.append(f"capture mode {c['mode']} != planned {mode}")
    if abs(c['decel_m_s2']-decel)>tol['decel_tolerance_m_s2']:problems.append('capture deceleration != planned MC_RAPTOR_RTDEC')
    # The vehicle state RAPTOR captured is the logged vehicle_local_position sample it used (independent check).
    ls=np.asarray(local['timestamp_sample'],np.int64);k=np.flatnonzero(ls==c['local_position_sample'])
    if not len(k):problems.append('captured vehicle_local_position sample not in the log')
    else:
        k=int(k[-1]);lp=[float(local[x][k]) for x in 'xyz'];lv=[float(local['v'+x][k]) for x in 'xyz']
        out['local_position_row']={'position_ned_m':lp,'velocity_ned_m_s':lv}
        if max(abs(a-b) for a,b in zip(lp+lv,c['vehicle_position_ned_m']+c['vehicle_velocity_ned_m_s']))>1e-6:problems.append('captured vehicle state differs from the logged local-position sample')
        if max(abs(a-b) for a,b in zip(lp,c['target_position_ned_m']))>tol['position_tolerance_m']:problems.append('capture target position is not the vehicle position')
    prof=np.flatnonzero((kind==KIND_PROFILE)&(tt>=c['px4_us']))
    ends=np.flatnonzero((kind==KIND_END)&(tt>=c['px4_us']))
    out['profile_rows']=int(len(prof))
    if mode==0:
        out['initial_target_velocity_ned_m_s']=c['target_velocity_ned_m_s']
        if c['phase']!=1 or max(map(abs,c['target_velocity_ned_m_s']))>0.:problems.append('T0 capture is not a zero-velocity hold')
        if np.any((kind==KIND_PROFILE)):problems.append('T0 run has profile rows')
    else:
        v=c['vehicle_velocity_ned_m_s'];want=[v[0],v[1],0.]
        out['initial_target_velocity_ned_m_s']=c['target_velocity_ned_m_s'];out['initial_target_speed_m_s']=math.hypot(*c['target_velocity_ned_m_s'][:2])
        if max(abs(a-b) for a,b in zip(c['target_velocity_ned_m_s'],want))>tol['initial_velocity_tolerance_m_s']:problems.append('T1 initial target velocity != captured horizontal vehicle velocity')
        p0=c['target_position_ned_m'];s0=math.hypot(want[0],want[1])
        out['stop_time_s']=s0/decel;out['stop_distance_m']=s0*s0/(2*decel)
        if not len(prof):problems.append('T1 profile rows missing')
        else:
            t_s=(np.asarray(target['timestamp_sample'],np.int64)[prof]-c['capture_sample'])/1e6
            pos,vel,phase=profile(p0,want,decel,t_s)
            lpos=np.stack([target[f'position[{k}]'][prof] for k in range(3)],1).astype(float);lvel=np.stack([target[f'velocity[{k}]'][prof] for k in range(3)],1).astype(float)
            out['profile_max_abs_error']={'position_m':float(np.max(np.abs(lpos-pos))),'velocity_m_s':float(np.max(np.abs(lvel-vel))),
                'phase_mismatches':int(np.sum(np.asarray(target['phase'])[prof]!=phase))}
            in_window=tt[prof]<t_e
            out['profile_rows_in_window']=int(in_window.sum());out['profile_span_s']=float(t_s[in_window].max()) if in_window.any() else 0.
            out['end_point_ned_m']=profile(p0,want,decel,[1e6])[0][0]
            if out['profile_max_abs_error']['position_m']>tol['position_tolerance_m'] or out['profile_max_abs_error']['velocity_m_s']>tol['velocity_tolerance_m_s']:problems.append('T1 profile rows differ from the closed-form profile')
            # Phase is a discrete label: a row within rounding of the stop time may carry either label.
            near_stop=np.abs(t_s-s0/decel)<=1e-5
            if np.any((np.asarray(target['phase'])[prof]!=phase)&~near_stop):problems.append('T1 profile phase differs from the closed-form profile')
            if out['profile_span_s']<out['stop_time_s']:problems.append('T1 profile ended before the target stopped')
            gaps=np.diff(tt[prof][in_window]);out['profile_max_gap_us']=int(gaps.max()) if len(gaps) else None
        early=[int(j) for j in ends if tt[j]<t_e]
        if early:problems.append(f'T1 profile ended inside the window (reason {int(target["end_reason"][early[0]])})')
        out['end_rows']=[{'px4_us':int(tt[j]),'reason':int(target['end_reason'][j])} for j in ends[:3]]
    out['problems']=problems;out['status']='VERIFIED' if not problems else 'FAILED'
    return out

def clipping(cfg,memory,t_c,t_e):
    c=cfg['p4c']['clipping'];mt=np.asarray(memory['timestamp'],np.int64)
    w=np.flatnonzero((memory['kind']==KIND_STEP)&(memory['active']==1)&(mt>=t_c)&(mt<t_e))
    out={'rows':int(len(w)),'definition':c['definition']}
    if not len(w):return out
    x=np.stack([memory[f'policy_input[{k}]'][w] for k in range(22)],1).astype(float);t=mt[w]
    for name,(lo,hi),lim in [('position',c['policy_input_position'],c['position_limit_m']),('velocity',c['policy_input_velocity'],c['velocity_limit_m_s'])]:
        axes=np.abs(x[:,lo:hi])>=lim*(1-c['relative_tolerance']);mask=axes.any(1);hit=np.flatnonzero(mask)
        out[name]={'limit':lim,'triggered':bool(len(hit)),'rows':int(len(hit)),'duration_s':hold_durations(t,mask,t_c,t_e),'longest_continuous_s':longest_run(t,mask,t_e),
            'first_after_change_s':float((t[hit[0]]-t_c)/1e6) if len(hit) else None,'last_after_change_s':float((t[hit[-1]]-t_c)/1e6) if len(hit) else None,
            'per_axis_rows':[int(a) for a in axes.sum(0)],'max_abs_component':float(np.max(np.abs(x[:,lo:hi])))}
    return out

def settle(cfg,local,t_c,t_e,axis,failed):
    thr=cfg['p4c']['settle']['speed_threshold_m_s'];lt=np.asarray(local['timestamp_sample'],np.int64);w=np.flatnonzero((lt>=t_c)&(lt<t_e))
    pos=np.stack([local[k] for k in 'xyz'],1).astype(float);vel=np.stack([local['v'+k] for k in 'xyz'],1).astype(float)
    ic=asof(lt,t_c);speed=np.linalg.norm(vel[w],axis=1);out={'speed_threshold_m_s':thr,'samples':int(len(w))}
    # T0 overshoots and returns to its capture point, so the settle distance alone hides the travel past the takeover.
    out['max_travel_along_axis_m']=float(np.max((pos[w]-pos[ic])@axis)) if len(w) else None
    above=np.flatnonzero(speed>=thr)
    if failed or not len(w) or (len(above) and above[-1]==len(w)-1):return {**out,'settled':False,'settle_time_s':None,'settle_distance_m':None}
    j=w[above[-1]+1] if len(above) else w[0];d=pos[j]-pos[ic]
    return {**out,'settled':True,'settle_time_s':float((lt[j]-t_c)/1e6),'settle_px4_us':int(lt[j]),'settle_position_ned_m':pos[j],
        'takeover_position_ned_m':pos[ic],'settle_distance_m':float(np.hypot(d[0],d[1])),'settle_distance_along_axis_m':float(d@axis),
        'settle_altitude_change_m':float(-d[2])}

def analyze(run):
    run=Path(run).resolve();cfg=json.loads((run/'config.json').read_text());out={'run':str(run),'condition':cfg.get('p1_condition'),'treatment':cfg.get('p2_treatment')}
    if not (run/'p2-metrics.json').exists():return clean({**out,'status':'INCOMPLETE','problems':['p2-metrics.json missing']})
    m=json.loads((run/'p2-metrics.json').read_text());problems=[]
    if 'change_px4_us' not in m:return clean({**out,'status':'INCOMPLETE','problems':['subject event not measured']})
    t_r,t_c,t_e=m['trigger_px4_us'],m['change_px4_us'],m['window_end_px4_us']
    u=ULog(str(run/'flight.ulg'),['research_target','research_memory','vehicle_local_position','vehicle_attitude'])
    t={d.name:d.data for d in u.data_list if d.multi_id==0};local=t['vehicle_local_position']
    axis=np.asarray(cfg['p2_profile']['motion_axis_ned'],float);fo=m.get('flight_outcome') or {}
    out.update({'speed_m_s':cfg.get('p1_speed_m_s'),'target_mode':int(cfg['p2_treatment_parameters']['rtgt']),'window_s':(t_e-t_c)/1e6,
        'speed_at_change_m_s':m['state_at_change']['speed_along_axis_m_s'],'flight_outcome':fo.get('outcome'),'flight_failure_reasons':fo.get('reasons'),
        'window_truncated':m.get('window_truncated')})
    out['target']=target_check(cfg,t.get('research_target'),local,t_r,t_c,t_e);problems+=out['target']['problems']
    pr=m['primary'];au=m['auxiliary']
    out['metrics']={'max_tilt_deg':pr['window_constraints']['tilt_safety_deg']['max'],'max_altitude_loss_m':pr['max_altitude_loss_m'],
        'motor_step_at_change':au['motor']['step_at_change'],'motor_max_step_window':au['motor']['max_step_in_window'],
        'motor_saturation_any_s':au['motor']['saturation_any_s'],'motor_longest_continuous_saturation_s':fo.get('longest_continuous_saturation_s'),
        'max_angular_rate_rad_s':pr['window_constraints']['angular_rate_component_rad_s']['max'],'max_horizontal_radius_m':pr['window_constraints']['horizontal_radius_m']['max'],
        'joint_recovery_status':pr['joint_recovery']['status'],'joint_recovery_from_change_s':pr['joint_recovery']['from_change_s'],
        'flight_failure':fo.get('outcome')=='FAILURE'}
    out['settle']=settle(cfg,local,t_c,t_e,axis,fo.get('outcome')=='FAILURE')
    if out['settle']['settled'] and out['target'].get('end_point_ned_m') is not None:
        e=np.asarray(out['settle']['settle_position_ned_m'])-np.asarray(out['target']['end_point_ned_m'])
        out['settle']['settle_minus_target_end_along_axis_m']=float(e@axis)
    memory=t.get('research_memory')
    if memory is None:problems.append('research_memory missing')
    else:out['clipping']=clipping(cfg,memory,t_c,t_e)
    # Curves for figures (time relative to the change; along-axis position relative to the takeover point).
    lt=np.asarray(local['timestamp_sample'],np.int64);ic=asof(lt,t_c);w=np.flatnonzero((lt>=t_c-1000000)&(lt<t_e))[::5]
    pos=np.stack([local[k] for k in 'xyz'],1).astype(float);vel=np.stack([local['v'+k] for k in 'xyz'],1).astype(float)
    att=t['vehicle_attitude'];at=np.asarray(att['timestamp'],np.int64);aw=np.flatnonzero((at>=t_c-1000000)&(at<t_e))[::5]
    out['curves']={'t_s':(lt[w]-t_c)/1e6,'along_axis_m':(pos[w]-pos[ic])@axis,'speed_along_axis_m_s':vel[w]@axis,'altitude_change_m':-(pos[w,2]-pos[ic,2]),
        'tilt_t_s':(at[aw]-t_c)/1e6,'tilt_deg':tilt_deg(np.stack([att[f'q[{i}]'][aw] for i in range(4)],1).astype(float))}
    tg=t.get('research_target')
    if tg is not None and out['target'].get('capture'):
        tt=np.asarray(tg['timestamp'],np.int64);k=np.flatnonzero((tg['kind']==KIND_PROFILE)&(tt>=t_c-20000)&(tt<t_e))[::5]
        p0=np.asarray(out['target']['capture']['target_position_ned_m'])
        out['curves']['target_t_s']=(tt[k]-t_c)/1e6;out['curves']['target_along_axis_m']=(np.stack([tg[f'position[{j}]'][k] for j in range(3)],1)-pos[ic])@axis
        out['curves']['target_speed_along_axis_m_s']=np.stack([tg[f'velocity[{j}]'][k] for j in range(3)],1)@axis
        out['curves']['capture_point_along_axis_m']=float((p0-pos[ic])@axis)
    out['problems']=problems;out['status']='MEASURED' if not problems else 'INCOMPLETE'
    return clean(out)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);a=p.parse_args()
    r=analyze(a.run);(a.run/'p4c-metrics.json').write_text(json.dumps(r,indent=1,ensure_ascii=False,allow_nan=False)+'\n')
    print(r['status'],r['problems'],r.get('flight_outcome'));raise SystemExit(0 if r['status']=='MEASURED' else 1)

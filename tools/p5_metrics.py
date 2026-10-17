#!/usr/bin/env python3
"""P5 per-run measurement; writes only p5-metrics.json.

p5_gap (E2/E3): RAPTOR tracks the runner's line through its external trajectory_setpoint input; the stream pauses
for D s and resumes. From RAPTOR's own logs: every setpoint reception (raptor_status), every target capture and T1
target (research_target) and the exact executor input (research_memory.policy_input). Per gap: setpoint-free interval
vs plan, the in-flight capture (time after the last reception, mode, deceleration, captured vehicle state, T1 profile
against the closed form, END row at the resume), RAPTOR's target before and after the resume (the jump) compared with
0.5*a*D^2 and with the exact prediction (offset at the capture + trajectory travel - target travel from the capture to
the resume), the observation at the resume, observation clipping, catch-up time, tilt and altitude per gap; E3 also the
altitude change and the along-track lag at every cycle end. Whole run: max tilt, altitude loss, motor saturation,
settle after the line comes to rest, joint recovery after the final capture, the pre-registered flight outcome, flight
direction, heading and seed realized, the setup entry with the planned memory treatment.

p2_c_to_n (E1) and p2_n_to_c (E4): summaries on top of p2-metrics.json / p4c-metrics.json: realized flight direction in
the world and relative to RAPTOR's target yaw, per-axis clipping in the target frame with the magnitude of the
unclipped error, and for E4 the N->C window metrics and the setup entry.
"""
import argparse,json,math
from pathlib import Path
import numpy as np
from pyulog import ULog
from p1_metrics import clean,asof,hold_durations,tilt_deg
from p2_metrics import longest_run
from p4c_metrics import profile as t1_profile
from p4_metrics import heading_before_arming
from recovery import recovery
KIND_STEP,KIND_ENTRY=1,2
T_CAPTURE,T_PROFILE,T_END=1,2,3
TOPICS=['raptor_status','trajectory_setpoint','research_target','research_memory','vehicle_local_position','vehicle_attitude',
        'vehicle_angular_velocity','research_angular_velocity','actuator_motors','vehicle_status','research_timing']

def vec(topic,name,i,n=3):return [float(topic[f'{name}[{k}]'][i]) for k in range(n)]
def ang(deg):return float((deg+180.)%360.-180.)

def entry_rows(memory,rini):
    """Every mode entry with its memory treatment (all entries of the run must use the planned RINI and apply it)."""
    rows=np.flatnonzero(memory['kind']==KIND_ENTRY)
    out=[{'px4_us':int(memory['timestamp'][i]),'entry_mode':int(memory['entry_mode'][i]),'entry_result':int(memory['entry_result'][i])} for i in rows]
    ok=bool(out) and all(e['entry_mode']==rini and (rini<2 or e['entry_result']==1) for e in out)
    return {'entries':out,'planned_rini':rini,'status':'VERIFIED' if ok else 'FAILED'}

def independence(cfg,meta,local,status):
    planned=cfg.get('p4_independence') or {};gz=next((p['command'] for p in meta['processes'] if p['name']=='gazebo'),[])
    seed=gz[gz.index('--seed')+1] if '--seed' in gz else None;heading=heading_before_arming(local,status)
    want=float(cfg['p4']['independence']['initial_yaw']['heading_at_zero_deg'])-(planned.get('initial_yaw_deg') or 0.)
    out={'planned':planned or None,'gazebo_seed_argument':seed,'heading_before_arming_deg':heading,'expected_heading_deg':want,
         'heading_error_deg':None if heading is None else ang(heading-want)};problems=[]
    if planned.get('sim_seed') is not None and seed!=str(planned['sim_seed']):problems.append('Gazebo command does not carry the planned seed')
    if heading is None or abs(out['heading_error_deg'])>3.0:problems.append('heading before arming differs from the planned initial heading')
    return out,problems

def clip_flags(x,lim,tol):return np.abs(x)>=lim*(1-tol)

def clipping_axes(cfg,memory,t0,t1,section='p5'):
    """Per-axis clipping of the exact executor input in [t0,t1): position [0:3], velocity [12:15] (target frame, FLU)."""
    c=cfg[section]['clipping'];mt=np.asarray(memory['timestamp'],np.int64)
    w=np.flatnonzero((memory['kind']==KIND_STEP)&(memory['active']==1)&(mt>=t0)&(mt<t1))
    out={'rows':int(len(w))}
    if not len(w):return out
    x=np.stack([memory[f'policy_input[{k}]'][w] for k in range(22)],1).astype(float);t=mt[w]
    for name,(lo,hi),lim in [('position',c['policy_input_position'],c['position_limit_m']),('velocity',c['policy_input_velocity'],c['velocity_limit_m_s'])]:
        f=clip_flags(x[:,lo:hi],lim,c['relative_tolerance']);mask=f.any(1);hit=np.flatnonzero(mask)
        out[name]={'limit':lim,'triggered':bool(len(hit)),'duration_s':hold_durations(t,mask,t0,t1),'longest_continuous_s':longest_run(t,mask,t1),
                   'per_axis_duration_s':[hold_durations(t,f[:,k],t0,t1) for k in range(3)],'both_horizontal_axes_s':hold_durations(t,f[:,0]&f[:,1],t0,t1),
                   'first_s':float((t[hit[0]]-t0)/1e6) if len(hit) else None,'last_s':float((t[hit[-1]]-t0)/1e6) if len(hit) else None,
                   'max_abs_component':[float(v) for v in np.max(np.abs(x[:,lo:hi]),0)]}
    return out

def unclipped_horizontal(memory,local,timing,targets,t0,t1):
    """Ratio |clipped| / |true| of RAPTOR's horizontal velocity and position error over [t0,t1). The true error is the
    vehicle_local_position sample RAPTOR used in that cycle (research_timing.local_position_sample) minus the target in
    force (targets(t) -> position, velocity); the horizontal norm is rotation invariant, so no frame is needed. The ratio
    is reported for rows whose true error reaches 80% of the limit (where clipping can act); the reconstruction is
    validated on the unclipped rows (residual reported)."""
    mt=np.asarray(memory['timestamp'],np.int64);w=np.flatnonzero((memory['kind']==KIND_STEP)&(memory['active']==1)&(mt>=t0)&(mt<t1))
    if not len(w) or timing is None:return None
    tt=np.asarray(timing['timestamp'],np.int64);called=np.asarray(timing['executor_called']).astype(bool);tt_c=tt[called];ls_c=np.asarray(timing['local_position_sample'],np.int64)[called]
    lts=np.asarray(local['timestamp_sample'],np.int64);out={}
    pos=np.stack([local[k] for k in 'xyz'],1).astype(float);vel=np.stack([local['v'+k] for k in 'xyz'],1).astype(float)
    it=np.searchsorted(tt_c,mt[w],side='right')-1;ok=it>=0;it=np.maximum(it,0)
    ok&=np.abs(tt_c[it]-mt[w])<=1000
    il=np.searchsorted(lts,ls_c[it],side='left');il=np.minimum(il,len(lts)-1);ok&=lts[il]==ls_c[it]
    tp,tv=targets(mt[w])
    for name,state,tgt,(lo,hi),lim in [('position',pos,tp,(0,2),0.5),('velocity',vel,tv,(12,14),1.0)]:
        true=np.linalg.norm((state[il]-tgt)[:,:2],axis=1);seen=np.linalg.norm(np.stack([memory[f'policy_input[{k}]'][w] for k in range(lo,hi)],1).astype(float),axis=1)
        good=ok&np.isfinite(true);unclipped=good&(seen<lim*0.999);near=good&(true>=0.8*lim)
        out[name]={'max_true_m_or_m_s':float(np.max(true[good])) if good.any() else None,'rows_at_or_above_80pct_limit':int(near.sum()),
                   'min_retained_ratio':float(np.min(seen[near]/true[near])) if near.any() else None,
                   'validation_max_abs_residual':float(np.max(np.abs(seen[unclipped]-true[unclipped]))) if unclipped.any() else None,'rows':int(good.sum()),'rows_unmatched':int((~ok).sum())}
    return out

def window_basics(cfg,topics,t0,t1,alt_ref_t):
    local=topics['vehicle_local_position'];lt=np.asarray(local.get('timestamp_sample',local['timestamp']),np.int64)
    w=(lt>=t0)&(lt<t1);z=np.asarray(local['z'],float);i0=asof(lt,alt_ref_t)
    att=topics['vehicle_attitude'];at=np.asarray(att['timestamp'],np.int64);aw=(at>=t0)&(at<t1)
    tilt=tilt_deg(np.stack([att[f'q[{i}]'] for i in range(4)],1).astype(float)[aw])
    av=topics['vehicle_angular_velocity'];avt=np.asarray(av['timestamp'],np.int64);avw=(avt>=t0)&(avt<t1)
    rate=np.max(np.abs(np.stack([av[f'xyz[{i}]'] for i in range(3)],1).astype(float)[avw]),1) if avw.any() else np.zeros(1)
    m=topics['actuator_motors'];mt=np.asarray(m['timestamp'],np.int64);mv=np.stack([m[f'control[{i}]'] for i in range(4)],1).astype(float);mw=(mt>=t0)&(mt<t1)
    sat=cfg['p2']['motor_saturation'];mask=np.any(mv>=sat['upper'],1)|np.any(mv<=sat['lower'],1)
    return {'max_tilt_deg':float(np.max(tilt)) if len(tilt) else None,'max_angular_rate_rad_s':float(np.max(rate)),
            'max_altitude_loss_m':max(0.,float(np.max(z[w])-z[i0])) if w.any() else None,'min_altitude_m':float(np.min(-z[w])) if w.any() else None,
            'max_horizontal_radius_m':float(np.max(np.hypot(local['x'][w],local['y'][w]))) if w.any() else None,
            'motor_saturation_any_s':hold_durations(mt[mw],mask[mw],t0,t1),'motor_longest_continuous_saturation_s':longest_run(mt[mw],mask[mw],t1)}

# ---- p5_gap ------------------------------------------------------------------------------------------------------
def receptions(status,sp):
    """PX4 times of the external setpoints: raptor_status cycles with a trajectory_setpoint update merged with the logged
    trajectory_setpoint rows (every publication is logged, stamped at its arrival in PX4; RAPTOR reads it in its next
    4 ms cycle). A raptor_status row can be missing from the log (RAPTOR skips the publication in a cycle with a
    duplicate gyro sample), so neither source alone is a complete reception record."""
    t=np.asarray(status['timestamp'],np.int64);a=t[np.asarray(status['subscription_update_trajectory_setpoint'])==1]
    return np.unique(np.r_[a,np.asarray(sp['timestamp'],np.int64)])

def setpoint_rows(sp,rec):
    """Logged trajectory_setpoint rows in publication order with RAPTOR's reception time attached. Every runner setpoint is
    logged (interval 0); the k-th logged row inside the stream belongs to the k-th reception when the counts agree."""
    t=np.asarray(sp['timestamp'],np.int64)
    pos=np.stack([sp[f'position[{k}]'] for k in range(3)],1).astype(float);vel=np.stack([sp[f'velocity[{k}]'] for k in range(3)],1).astype(float)
    return t,pos,vel

def analyze_gap(run,cfg,meta,events,topics,u,problems):
    out={};spec=cfg['p5_condition_spec'];prof=cfg['p2_profile'];tp=cfg['p2_treatment_parameters'];p5=cfg['p5']
    axis=np.asarray(prof['motion_axis_ned'],float);v_ref=float(cfg['p1_speed_m_s']);g=prof['gaps'];D=float(g['duration_s'])
    mode,decel=int(tp['rtgt']),float(tp['rtdec'])
    started=next((e for e in events if e['event']=='p1_profile_started'),None);ended=next((e for e in events if e['event']=='p5_stream_ended'),None)
    post=next((e for e in events if e['event']=='p1_phase_ended' and e['label']=='post_stream'),None)
    failure=next((e for e in events if e['event']=='failure'),None)
    status=topics['raptor_status'];local=topics['vehicle_local_position'];memory=topics.get('research_memory');target=topics.get('research_target')
    if started is None or memory is None or target is None:problems.append('profile start, research_memory or research_target missing');return out
    t_start=int(started['px4_bound_us']);vs=topics['vehicle_status']
    disarm=np.asarray(vs['timestamp'],np.int64)[(np.asarray(vs['timestamp'],np.int64)>t_start)&(np.asarray(vs['arming_state'])!=2)]
    t_log_end=int(min([u.last_timestamp]+([int(disarm[0])] if len(disarm) else [])))
    t_stream_end=int(ended['end_bound_px4_us']) if ended else t_log_end
    t_end=int(post['px4_end_us']) if post else t_log_end
    out['aborted']=failure is not None;out['failure_reason']=failure['reason'] if failure else None
    out['times_px4_us']={'profile_start':t_start,'stream_end':t_stream_end,'window_end':t_end}
    rec=receptions(status,topics['trajectory_setpoint']);rec=rec[(rec>=t_start)&(rec<=t_stream_end)]
    d=np.diff(rec);idx=np.flatnonzero(d>100000)
    gaps=[];tg=np.asarray(target['timestamp'],np.int64);kind=np.asarray(target['kind'])
    mt=np.asarray(memory['timestamp'],np.int64);step_active=(memory['kind']==KIND_STEP)&(memory['active']==1)
    lt=np.asarray(local['timestamp'],np.int64);lts=np.asarray(local['timestamp_sample'],np.int64)
    pos=np.stack([local[k] for k in 'xyz'],1).astype(float);vel=np.stack([local['v'+k] for k in 'xyz'],1).astype(float)
    sp=topics['trajectory_setpoint'];spt,spp,spv=setpoint_rows(sp,rec)
    out['planned_gaps']=int(g['count']);out['observed_gaps']=int(len(idx))
    if len(idx)!=int(g['count']) and not out['aborted']:problems.append(f"{len(idx)} setpoint gaps observed, {g['count']} planned")
    tim=p5['gap_timing']
    def traj_point(t):
        """Trajectory point in force at t: latest logged setpoint row at or before t, advanced by its velocity."""
        i=np.searchsorted(spt,t,side='right')-1
        return spp[i]+spv[i]*((t-spt[i])/1e6)[...,None] if np.ndim(t) else spp[i]+spv[i]*(t-spt[i])/1e6
    for k,i in enumerate(idx):
        t_last,t_first=int(rec[i]),int(rec[i+1]);gap={'index':k,'last_reception_px4_us':t_last,'first_reception_px4_us':t_first,
            'silence_s':(t_first-t_last)/1e6,'planned_D_s':D};gp=[]
        if not (D-tim['early_s']<=gap['silence_s']<=D+tim['late_s']):gp.append('setpoint-free interval differs from the planned D')
        caps=np.flatnonzero((kind==T_CAPTURE)&(np.asarray(target['activation'])==0)&(tg>t_last)&(tg<=t_first))
        gap['in_flight_captures']=int(len(caps))
        if len(caps)!=1:gp.append(f'{len(caps)} in-flight captures in the gap (expected 1)');gaps.append({**gap,'problems':gp});problems+=[f'gap {k}: '+x for x in gp];continue
        c=int(caps[0]);t_cap=int(tg[c]);csample=int(target['capture_sample'][c])
        cap={'px4_us':t_cap,'after_last_reception_s':(t_cap-t_last)/1e6,'mode':int(target['mode'][c]),'decel_m_s2':float(target['decel'][c]),
             'vehicle_position_ned_m':vec(target,'vehicle_position',c),'vehicle_velocity_ned_m_s':vec(target,'vehicle_velocity',c),
             'target_position_ned_m':vec(target,'position',c),'target_velocity_ned_m_s':vec(target,'velocity',c),'target_yaw_rad':float(target['yaw'][c]),
             'local_position_sample':int(target['local_position_sample'][c])}
        gap['capture']=cap;lo,hi=tim['capture_delay_s']
        if not lo<=cap['after_last_reception_s']<=hi:gp.append('capture not in the first cycle after the 200 ms timeout')
        if cap['mode']!=mode or abs(cap['decel_m_s2']-decel)>1e-5:gp.append('capture mode or deceleration differs from the plan')
        k_l=np.flatnonzero(lts==cap['local_position_sample'])
        if not len(k_l) or max(abs(a-b) for a,b in zip(list(pos[k_l[-1]])+list(vel[k_l[-1]]),cap['vehicle_position_ned_m']+cap['vehicle_velocity_ned_m_s']))>1e-6:gp.append('captured vehicle state differs from the logged local-position sample')
        if max(abs(a-b) for a,b in zip(cap['target_position_ned_m'],cap['vehicle_position_ned_m']))>1e-4:gp.append('capture target position is not the vehicle position')
        v0=cap['vehicle_velocity_ned_m_s'];p0=cap['target_position_ned_m']
        prof_rows=np.flatnonzero((kind==T_PROFILE)&(tg>=t_cap)&(tg<t_first+20000));ends=np.flatnonzero((kind==T_END)&(tg>=t_cap)&(tg<=t_first+20000))
        gap['profile_rows']=int(len(prof_rows))
        if mode==0:
            if max(map(abs,cap['target_velocity_ned_m_s']))>0 or len(prof_rows):gp.append('T0 in-flight capture is not a zero-velocity hold')
            before_p,before_v=np.asarray(p0),np.zeros(3)
        else:
            want=[v0[0],v0[1],0.];gap['initial_target_speed_m_s']=math.hypot(v0[0],v0[1])
            if max(abs(a-b) for a,b in zip(cap['target_velocity_ned_m_s'],want))>1e-5:gp.append('T1 initial target velocity != captured horizontal vehicle velocity')
            ts=(np.asarray(target['timestamp_sample'],np.int64)[prof_rows]-csample)/1e6;pp,pv,_=t1_profile(p0,want,decel,ts)
            lp=np.stack([target[f'position[{j}]'][prof_rows] for j in range(3)],1).astype(float);lv=np.stack([target[f'velocity[{j}]'][prof_rows] for j in range(3)],1).astype(float)
            gap['profile_max_abs_error']={'position_m':float(np.max(np.abs(lp-pp))) if len(prof_rows) else None,'velocity_m_s':float(np.max(np.abs(lv-pv))) if len(prof_rows) else None}
            if not len(prof_rows) or gap['profile_max_abs_error']['position_m']>1e-4 or gap['profile_max_abs_error']['velocity_m_s']>1e-4:gp.append('T1 profile rows missing or differ from the closed form')
            if len(ends)!=1 or int(target['end_reason'][ends[0]])!=1:gp.append('T1 profile not ended by the external setpoint at the resume')
            # Target in force in the last cycle before the resume = the closed form at that cycle's gyro sample.
            last=prof_rows[tg[prof_rows]<t_first]
            ls=int(np.asarray(target['timestamp_sample'],np.int64)[last[-1]]) if len(last) else csample
            bp,bv,_=t1_profile(p0,want,decel,[(ls-csample)/1e6]);before_p,before_v=bp[0],bv[0]
            gap['stop_time_s']=gap['initial_target_speed_m_s']/decel
        # Target after the resume: the first setpoint RAPTOR received (END row for T1; the logged setpoint row otherwise).
        if mode!=0 and len(ends):e=int(ends[0]);after_p,after_v=np.asarray(vec(target,'position',e)),np.asarray(vec(target,'velocity',e))
        else:
            j=int(np.searchsorted(spt,t_last+100000));after_p,after_v=spp[j],spv[j]
        D_cr=(t_first-t_cap)/1e6
        jump_p=after_p-before_p;jump_v=after_v-before_v
        s0=math.hypot(v0[0],v0[1]);tau=min(D_cr,s0/decel) if mode else 0.;travel_t=s0*tau-.5*decel*tau*tau if mode else 0.
        # Offset at the capture: captured vehicle position relative to the trajectory point at the capture time.
        offset=float((np.asarray(p0)-traj_point(t_cap))@axis)
        gap['resume']={'capture_to_resume_s':D_cr,'target_before_ned_m':before_p,'target_velocity_before_ned_m_s':before_v,'target_after_ned_m':after_p,'target_velocity_after_ned_m_s':after_v,
            'jump_along_axis_m':float(jump_p@axis),'jump_horizontal_m':float(np.hypot(*jump_p[:2])),'jump_vertical_m':float(jump_p[2]),
            'velocity_jump_along_axis_m_s':float(jump_v@axis),'velocity_jump_horizontal_m_s':float(np.hypot(*jump_v[:2])),
            'estimate_half_a_D2_m':.5*decel*D*D if mode else None,'estimate_half_a_Dcr2_m':.5*decel*D_cr*D_cr if mode else None,
            'offset_at_capture_along_axis_m':offset,'trajectory_travel_capture_to_resume_m':v_ref*D_cr,'target_travel_capture_to_resume_m':travel_t,
            'prediction_m':-offset+v_ref*D_cr-travel_t,'t1_stopped_before_resume':bool(mode and D_cr>=s0/decel)}
        # Observation RAPTOR used in the first inference after the resume and in the last before the capture.
        def obs(i):return {'px4_us':int(mt[i]),'position_error':[float(memory[f'policy_input[{q}]'][i]) for q in range(3)],'velocity_error':[float(memory[f'policy_input[{q}]'][i]) for q in range(12,15)]}
        a=np.flatnonzero(step_active&(mt>=t_first));b=np.flatnonzero(step_active&(mt<t_cap))
        gap['observation_first_after_resume']=obs(a[0]) if len(a) else None;gap['observation_last_before_capture']=obs(b[-1]) if len(b) else None
        nxt=int(rec[idx[k+1]]) if k+1<len(idx) else min(t_first+int(float(prof['post_gap_s'])*1e6),t_stream_end)
        gap['segment_end_px4_us']=nxt
        gap['clipping_in_gap']=clipping_axes(cfg,memory,t_last,t_first);gap['clipping_after_resume']=clipping_axes(cfg,memory,t_first,nxt)
        gap['window']=window_basics(cfg,topics,t_last,nxt,t_last)
        # Catch-up: RAPTOR's observed horizontal errors within thresholds for the dwell, searched until the segment end.
        cu=p5['catch_up'];w=np.flatnonzero(step_active&(mt>=t_first)&(mt<nxt))
        pe=np.hypot(memory['policy_input[0]'][w],memory['policy_input[1]'][w]);ve=np.hypot(memory['policy_input[12]'][w],memory['policy_input[13]'][w])
        good=(pe<=cu['position_m'])&(ve<=cu['velocity_m_s']);tw=mt[w];start=None;gap['catch_up_s']=None
        for q in range(len(w)):
            if not good[q]:start=None;continue
            if start is None:start=tw[q]
            if tw[q]-start>=cu['dwell_s']*1e6:gap['catch_up_s']=float((start-t_first)/1e6);break
        gap['catch_up_search_s']=(nxt-t_first)/1e6
        # Cycle end (E3): altitude change since the first gap and along-/cross-track lag behind the trajectory point.
        t_cycle=min(t_first+int(float(g['recover_s'])*1e6),t_stream_end) if float(g['recover_s'])>0 else nxt
        il=asof(lts,t_cycle);tpnt=traj_point(t_cycle);dv=tpnt-pos[il];perp=np.array([-axis[1],axis[0],0.])
        gap['cycle_end']={'px4_us':int(t_cycle),'along_track_lag_m':float(dv@axis),'cross_track_m':float(dv@perp),'speed_along_axis_m_s':float(vel[il]@axis)}
        gap['problems']=gp;problems+=[f'gap {k}: '+x for x in gp];gaps.append(gap)
    out['gaps']=gaps
    # Diagnostic: research_memory inference rows and raptor_status rows missing from the log while streaming.
    st_=mt[memory['kind']==KIND_STEP];st_=st_[(st_>=t_start)&(st_<=t_stream_end)];rs_=np.asarray(status['timestamp'],np.int64);rs_=rs_[(rs_>=t_start)&(rs_<=t_stream_end)]
    out['log_continuity']={'research_memory_step_rows':int(len(st_)),'research_memory_gaps_over_4ms':int((np.diff(st_)>4000).sum()),'research_memory_max_gap_us':int(np.diff(st_).max()) if len(st_)>1 else None,
        'raptor_status_gaps_over_4ms':int((np.diff(rs_)>4000).sum()),'raptor_status_max_gap_us':int(np.diff(rs_).max()) if len(rs_)>1 else None}
    if gaps:
        t_g0=gaps[0]['last_reception_px4_us'];i0=asof(lts,t_g0)
        for gp_ in gaps:
            if 'cycle_end' in gp_:
                il=asof(lts,gp_['cycle_end']['px4_us']);gp_['cycle_end']['altitude_change_since_first_gap_m']=float(-(pos[il,2]-pos[i0,2]))
        # Tracking before the first gap (reference for the lag and catch-up), from the exact executor input.
        w=np.flatnonzero(step_active&(mt>=t_g0-500000)&(mt<t_g0))
        out['tracking_before_first_gap']={'position_error_horizontal_mean_m':float(np.mean(np.hypot(memory['policy_input[0]'][w],memory['policy_input[1]'][w]))) if len(w) else None,
            'velocity_error_horizontal_mean_m_s':float(np.mean(np.hypot(memory['policy_input[12]'][w],memory['policy_input[13]'][w]))) if len(w) else None}
        ip=asof(lts,t_g0);out['direction']={'planned_axis_ned':list(axis),'planned_deg':ang(math.degrees(math.atan2(axis[1],axis[0]))),
            'velocity_at_first_gap_ned_m_s':list(vel[ip]),'realized_deg':ang(math.degrees(math.atan2(vel[ip,1],vel[ip,0]))),'speed_m_s':float(np.hypot(*vel[ip,:2]))}
        out['direction']['error_deg']=ang(out['direction']['realized_deg']-out['direction']['planned_deg'])
        if abs(out['direction']['error_deg'])>5.:problems.append('realized flight direction differs from the planned axis by more than 5 deg')
        yaw=gaps[0].get('capture',{}).get('target_yaw_rad')
        if yaw is not None:out['direction']['relative_to_target_yaw_deg']=ang(out['direction']['planned_deg']-math.degrees(yaw))
        whole_end=t_end
        out['whole']=window_basics(cfg,topics,t_g0,whole_end,t_g0)
        out['clipping_whole']=clipping_axes(cfg,memory,t_g0,t_stream_end)
        # Settle after the line comes to rest (deceleration end = stream end - end_hold_s, simulation time ~ wall time).
        t_rest=t_stream_end-int(float(prof['end_hold_s'])*1e6);w=(lts>=t_rest)&(lts<t_stream_end);sp_=np.linalg.norm(vel[w],axis=1);above=np.flatnonzero(sp_>=cfg['p5']['settle']['speed_threshold_m_s'])
        out['settle_after_rest']={'rest_px4_us':t_rest,'settled':bool(w.any() and (not len(above) or above[-1]<len(sp_)-1)) and not out['aborted'],
            'settle_time_s':float((lts[w][above[-1]+1]-t_rest)/1e6) if w.any() and len(above) and above[-1]<len(sp_)-1 else (0. if w.any() and not len(above) else None)}
    # Curves for figures, time from the first gap (last reception before it): vehicle lag behind the trajectory point,
    # RAPTOR's target relative to the trajectory point (latest setpoint or capture/T1 row, whichever is later), tilt.
    if gaps:
        t0c=gaps[0]['last_reception_px4_us'];t1c=min(t_stream_end,t_end);w=np.flatnonzero((lts>=t0c-1000000)&(lts<t1c))[::5]
        tw=lts[w];tp_=traj_point(tw)
        rows=[(int(a),0,spp[i]) for i,a in enumerate(spt)]+[(int(tg[q]),1,np.asarray(vec(target,'position',q))) for q in np.flatnonzero(((kind==T_CAPTURE)|(kind==T_PROFILE))&(tg>=t0c-1000000)&(tg<t1c))]
        rows.sort(key=lambda r:(r[0],r[1]));rt=np.array([r[0] for r in rows],np.int64);rp=np.stack([r[2] for r in rows]);ri=np.searchsorted(rt,tw,side='right')-1
        att=topics['vehicle_attitude'];at=np.asarray(att['timestamp'],np.int64);aw=np.flatnonzero((at>=t0c-1000000)&(at<t1c))[::5]
        out['curves']={'t_s':(tw-t0c)/1e6,'vehicle_lag_m':(tp_-pos[w])@axis,'target_minus_trajectory_m':(rp[ri]-tp_)@axis,'speed_along_axis_m_s':vel[w]@axis,
            'altitude_change_m':-(pos[w,2]-pos[asof(lts,t0c),2]),'tilt_t_s':(at[aw]-t0c)/1e6,'tilt_deg':tilt_deg(np.stack([att[f'q[{i}]'] for i in range(4)],1).astype(float)[aw]),
            'gap_intervals_s':[[(x['last_reception_px4_us']-t0c)/1e6,(x['first_reception_px4_us']-t0c)/1e6] for x in gaps]}
    # Final capture after the stream ended at rest, joint recovery to it (frozen P0 thresholds).
    caps=np.flatnonzero((kind==T_CAPTURE)&(tg>t_stream_end-300000)&(tg<=t_stream_end+400000))
    out['final_capture']=None;jr={'status':'NOT_MEASURED'}
    if len(caps) and not out['aborted']:
        c=int(caps[0]);out['final_capture']={'px4_us':int(tg[c]),'mode':int(target['mode'][c]),'target_velocity_ned_m_s':vec(target,'velocity',c)}
        rows=[(int(tg[c]),vec(target,'position',c))]+[(int(tg[q]),vec(target,'position',q)) for q in np.flatnonzero((kind==T_PROFILE)&(tg>tg[c])&(tg<t_end))]
        tgt={'timestamp':np.array([r[0] for r in rows],np.int64),**{f'position[{k}]':np.array([r[1][k] for r in rows]) for k in range(3)}}
        loc=dict(local);loc['timestamp']=lts;an_name='research_angular_velocity' if 'research_angular_velocity' in topics else 'vehicle_angular_velocity'
        angular=dict(topics[an_name]);angular['timestamp']=np.asarray(angular.get('timestamp_sample',angular['timestamp']),np.int64)
        r=recovery(loc,angular,cfg['joint_recovery'],int(tg[c]),t_end,tgt)['joint_recovery'];jr={'status':r['status'],'from_final_capture_s':r['time_s']}
    out['joint_recovery_after_final_capture']=jr
    # Pre-registered flight outcome.
    crit=p5['failure_criteria'];reasons=[];wh=out.get('whole') or {}
    if wh:
        if wh['max_tilt_deg'] is not None and wh['max_tilt_deg']>=cfg['safety_tilt_deg']:reasons.append('safety_envelope:tilt_safety_deg')
        if wh['max_angular_rate_rad_s']>=cfg['safety_angular_rate_rad_s']:reasons.append('safety_envelope:angular_rate_component_rad_s')
        if wh['max_horizontal_radius_m'] is not None and wh['max_horizontal_radius_m']>=cfg['safety_radius_m']:reasons.append('safety_envelope:horizontal_radius_m')
        if wh['motor_longest_continuous_saturation_s']>=crit['motor_saturation_continuous_s']:reasons.append('motor_saturation')
        if wh['min_altitude_m'] is not None and wh['min_altitude_m']<=crit['ground_altitude_m']:reasons.append('ground')
    if out['aborted'] and 'safety' in str(out['failure_reason']):reasons.append('runner_safety_abort')
    if not out['aborted'] and (jr.get('status')!='SETTLED' or jr.get('from_final_capture_s') is None or jr['from_final_capture_s']>crit['no_joint_recovery_s']):reasons.append('no_joint_recovery')
    if out['aborted'] and not reasons:problems.append('run aborted without a pre-registered flight-failure reason')
    out['flight_outcome']={'outcome':'FAILURE' if reasons else 'SUCCESS','reasons':reasons}
    if not out['aborted'] and len(gaps)!=int(g['count']):problems.append('gap analysis incomplete')
    return out

# ---- E1 / E4 -----------------------------------------------------------------------------------------------------
def analyze_p2(run,cfg,meta,events,topics,problems):
    out={};kind=meta['experiment_type'];m=json.loads((run/'p2-metrics.json').read_text())
    if 'change_px4_us' not in m:problems.append('subject event not measured');return out
    t_c,t_e=m['change_px4_us'],m['window_end_px4_us'];axis=np.asarray(cfg['p2_profile']['motion_axis_ned'],float)
    local=topics['vehicle_local_position'];lts=np.asarray(local['timestamp_sample'],np.int64);i=asof(lts,t_c)
    v=[float(local['v'+k][i]) for k in 'xyz'];fo=m.get('flight_outcome') or {}
    out['direction']={'planned_axis_ned':list(axis),'planned_deg':ang(math.degrees(math.atan2(axis[1],axis[0]))),'velocity_at_change_ned_m_s':v,
        'realized_deg':ang(math.degrees(math.atan2(v[1],v[0]))),'speed_m_s':math.hypot(v[0],v[1])}
    out['direction']['error_deg']=ang(out['direction']['realized_deg']-out['direction']['planned_deg'])
    if abs(out['direction']['error_deg'])>5.:problems.append('realized flight direction differs from the planned axis by more than 5 deg')
    pr=m['primary'];au=m['auxiliary']
    out['metrics']={'max_tilt_deg':pr['window_constraints']['tilt_safety_deg']['max'],'max_altitude_loss_m':pr['max_altitude_loss_m'],
        'motor_step_at_change':au['motor']['step_at_change'],'motor_saturation_any_s':au['motor']['saturation_any_s'],
        'max_angular_rate_rad_s':pr['window_constraints']['angular_rate_component_rad_s']['max'],'joint_recovery_from_change_s':pr['joint_recovery']['from_change_s'],
        'flight_outcome':fo.get('outcome'),'flight_failure_reasons':fo.get('reasons')}
    memory=topics.get('research_memory')
    if memory is None:problems.append('research_memory missing');return out
    out['setup_and_subject_entries']=entry_rows(memory,int(cfg['p2_treatment_parameters'].get('rini',0)))
    if out['setup_and_subject_entries']['status']!='VERIFIED':problems.append('a mode entry did not use the planned memory treatment')
    if kind=='p2_c_to_n':
        target=topics.get('research_target');tg=np.asarray(target['timestamp'],np.int64)
        caps=np.flatnonzero((target['kind']==T_CAPTURE)&(target['activation']==1)&(np.abs(tg-t_c)<=50000))
        if len(caps)!=1:problems.append('activation capture at the change not unique');return out
        c=int(caps[0]);yaw=float(target['yaw'][c]);p0=np.asarray(vec(target,'position',c));mode=int(target['mode'][c]);decel=float(target['decel'][c])
        out['direction']['target_yaw_deg']=math.degrees(yaw);out['direction']['relative_to_target_yaw_deg']=ang(out['direction']['planned_deg']-math.degrees(yaw))
        rel=out['direction']['relative_to_target_yaw_deg'];out['direction']['angle_to_nearest_target_axis_deg']=float(min(abs(ang(rel-a)) for a in (-180,-90,0,90,180)))
        out['clipping']=clipping_axes(cfg,memory,t_c,t_e,'p4c')
        v0=vec(target,'vehicle_velocity',c);csample=int(target['capture_sample'][c])
        def targets(t):
            if mode==0:return np.repeat(p0[None],len(t),0),np.zeros((len(t),3))
            # Profile time from the capture: memory rows are stamped in the same cycle as the gyro sample (lockstep).
            pp,pv,_=t1_profile(p0,[v0[0],v0[1],0.],decel,(np.asarray(t,np.int64)-int(tg[c]))/1e6);return pp,pv
        out['true_error']=unclipped_horizontal(memory,local,topics.get('research_timing'),targets,t_c,t_e)
    return out

def analyze(run):
    run=Path(run).resolve();cfg=json.loads((run/'config.json').read_text());meta=json.loads((run/'metadata.json').read_text())
    events=[json.loads(s) for s in (run/'events.jsonl').read_text().splitlines()];kind=meta['experiment_type']
    out={'run':str(run),'kind':kind,'condition':cfg.get('p1_condition'),'treatment':cfg.get('p2_treatment'),'treatment_parameters':cfg.get('p2_treatment_parameters')};problems=[]
    u=ULog(str(run/'flight.ulg'),TOPICS);topics={d.name:d.data for d in u.data_list if d.multi_id==0}
    out['independence'],pi=independence(cfg,meta,topics['vehicle_local_position'],topics['vehicle_status']);problems+=pi
    # Takeover-target parameters in force (log header and changes before the profile/subject).
    values=dict(u.initial_parameters)
    for stamp,name,value in sorted(u.changed_parameters,key=lambda x:x[0]):values[name]=value
    out['parameters_final']={k:values.get(k) for k in ['MC_RAPTOR_RINI','MC_RAPTOR_RTGT','MC_RAPTOR_RTDEC','MC_RAPTOR_RSH']}
    tp=cfg.get('p2_treatment_parameters') or {}
    want={'MC_RAPTOR_RINI':int(tp.get('rini',0)),'MC_RAPTOR_RSH':1}
    if 'rtgt' in tp:want.update({'MC_RAPTOR_RTGT':int(tp['rtgt']),'MC_RAPTOR_RTDEC':float(tp['rtdec'])})
    if any(out['parameters_final'].get(k) is None or abs(out['parameters_final'][k]-v)>1e-5 for k,v in want.items()):problems.append(f"parameters {out['parameters_final']} != planned {want}")
    if kind=='p5_gap':
        out.update(analyze_gap(run,cfg,meta,events,topics,u,problems))
        memory=topics.get('research_memory')
        if memory is not None:
            out['setup_entry']=entry_rows(memory,int(tp.get('rini',0)))
            if out['setup_entry']['status']!='VERIFIED':problems.append('a mode entry did not use the planned memory treatment')
    elif (run/'p2-metrics.json').exists():out.update(analyze_p2(run,cfg,meta,events,topics,problems))
    else:problems.append('p2-metrics.json missing')
    out['problems']=problems;out['status']='MEASURED' if not problems else 'INCOMPLETE'
    return clean(out)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);a=p.parse_args()
    r=analyze(a.run);(a.run/'p5-metrics.json').write_text(json.dumps(r,indent=1,ensure_ascii=False,allow_nan=False)+'\n')
    print(r['status'],r['problems'],(r.get('flight_outcome') or {}).get('outcome'));raise SystemExit(0 if r['status']=='MEASURED' else 1)

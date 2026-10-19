#!/usr/bin/env python3
"""P6 per-run measurement; writes only p6-metrics.json.

p5_gap with one interruption (B, C1, and the equivalence with config/p5.json): the frozen P5 analyzer
(p5_metrics.analyze) unchanged. p5_gap with explicit interruption windows (C2): the same analyzer with
analyze_gap_windows (a copy of p5_metrics.analyze_gap with the planned D and restored interval per gap). Both get a
'p6' block: time of the maximum tilt and of the first sample >= 45 deg (from the first interruption).

p6_ident (A): RAPTOR follows the runner's step / chase / brake / capture profile through its external setpoint input.
Checks: seed and heading realized, parameters, every mode entry with N2 applied, the family start found in the logged
setpoints, the stream executed (capture: the 2.0 s pause with exactly one zero-velocity in-flight capture 200-216 ms
after the last reception), chase switch recorded. Measures max tilt (time, first >= 45 deg), altitude loss, angular
rate, radius, motor saturation, per-axis clipping in the target frame over [family start - 1 s, end of post_stream].
Outcome classes (config p6.ident.outcome): IDENT_OK, IDENT_EXCEEDED_45 (labelled ident_exceeded_45, not a failure, not
test data), IDENT_ABORTED (runner safety abort; the recorded part is measured and exported).
"""
import argparse,json,math
from pathlib import Path
import numpy as np
from pyulog import ULog
import p5_metrics,p5_open_gap
from p5_metrics import (vec,ang,entry_rows,independence,clip_flags,clipping_axes,window_basics,receptions,setpoint_rows,
                        KIND_STEP,T_CAPTURE,T_PROFILE,T_END,TOPICS,t1_profile,asof,tilt_deg,recovery)
from p1_metrics import clean

def tilt_timing(topics,t0,t1,limit=45.):
    att=topics['vehicle_attitude'];at=np.asarray(att['timestamp'],np.int64);w=(at>=t0)&(at<t1)
    if not w.any():return {'max_tilt_deg':None}
    tilt=tilt_deg(np.stack([att[f'q[{i}]'] for i in range(4)],1).astype(float)[w]);tw=at[w];k=int(np.argmax(tilt));over=np.flatnonzero(tilt>=limit)
    return {'reference_px4_us':int(t0),'max_tilt_deg':float(tilt[k]),'max_tilt_at_s':float((tw[k]-t0)/1e6),
            'first_at_or_above_45_s':float((tw[over[0]]-t0)/1e6) if len(over) else None,'at_or_above_45_s':float(len(over)*np.median(np.diff(tw))/1e6) if len(over) and len(tw)>1 else 0.}

def analyze_gap_windows(run,cfg,meta,events,topics,u,problems):
    """Copy of the frozen p5_metrics.analyze_gap for explicit interruption windows (P6 C2): planned D and restored
    interval per gap instead of one duration_s/recover_s. Only the marked lines differ."""
    out={};spec=cfg['p5_condition_spec'];prof=cfg['p2_profile'];tp=cfg['p2_treatment_parameters'];p5=cfg['p5']
    axis=np.asarray(prof['motion_axis_ned'],float);v_ref=float(cfg['p1_speed_m_s']);g=prof['gaps']
    Ds=[round(b-a,9) for a,b in g['windows_s']];recs=[round(g['windows_s'][k+1][0]-g['windows_s'][k][1],9) for k in range(len(Ds)-1)]+[0.]  # P6: per gap
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
        D=Ds[min(k,len(Ds)-1)]  # P6: planned D of this gap
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
        t_cycle=min(t_first+int(recs[min(k,len(recs)-1)]*1e6),t_stream_end) if recs[min(k,len(recs)-1)]>0 else nxt  # P6: per gap
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

# ---- p6_ident ----------------------------------------------------------------------------------------------------
def family_start(cfg,events,sp):
    """PX4 time of the family start: the first logged setpoint after the reference hold that leaves the hold state
    (position or velocity), searched from 0.5 s before the start predicted from the native profile-start bound."""
    started=next(e for e in events if e['event']=='p1_profile_started');plan=next(e for e in events if e['event']=='p6_ident_plan')
    est=int(started['px4_bound_us'])+int(float(plan['family_start_profile_s'])*1e6)
    t=np.asarray(sp['timestamp'],np.int64);pos=np.stack([sp[f'position[{k}]'] for k in range(3)],1).astype(float);vel=np.stack([sp[f'velocity[{k}]'] for k in range(3)],1).astype(float)
    h=np.flatnonzero((t>=est-1500000)&(t<est-500000))
    if not len(h):return None,est
    hp=pos[h[-1]];c=np.flatnonzero((t>=est-500000)&((np.abs(pos-hp).max(1)>1e-4)|(np.abs(vel).max(1)>1e-6)))
    return (int(t[c[0]]) if len(c) else None),est

def analyze_ident(run,cfg,meta,events,topics,u,problems):
    out={};p=cfg['p2_profile'];spec=cfg['p6_condition_spec']
    started=next((e for e in events if e['event']=='p1_profile_started'),None);ended=next((e for e in events if e['event']=='p6_stream_ended'),None)
    post=next((e for e in events if e['event']=='p1_phase_ended' and e['label']=='post_stream'),None);failure=next((e for e in events if e['event']=='failure'),None)
    status=topics['raptor_status'];local=topics['vehicle_local_position'];memory=topics.get('research_memory');target=topics.get('research_target');sp=topics['trajectory_setpoint']
    if started is None or memory is None or target is None:problems.append('profile start, research_memory or research_target missing');return out
    vs=topics['vehicle_status'];vst=np.asarray(vs['timestamp'],np.int64);t_start=int(started['px4_bound_us'])
    disarm=vst[(vst>t_start)&(np.asarray(vs['arming_state'])!=2)];t_log_end=int(min([u.last_timestamp]+([int(disarm[0])] if len(disarm) else [])))
    t_stream_end=int(ended['end_bound_px4_us']) if ended else t_log_end;t_end=int(post['px4_end_us']) if post else t_log_end
    out['aborted']=failure is not None;out['failure_reason']=failure['reason'] if failure else None
    t_fam,est=family_start(cfg,events,sp)
    out['family']=p['family'];out['times_px4_us']={'profile_start':t_start,'family_start':t_fam,'family_start_predicted':est,'stream_end':t_stream_end,'window_end':t_end}
    if t_fam is None:problems.append('family start not found in the logged setpoints');return out
    out['family_start_offset_from_prediction_s']=(t_fam-est)/1e6
    if abs(out['family_start_offset_from_prediction_s'])>0.1:problems.append('family start more than 0.1 s from the native prediction')
    sw=next((e for e in events if e['event']=='p6_chase_switch'),None)
    if p['family']=='chase':
        if sw is None and not out['aborted']:problems.append('chase switch not recorded')
        out['chase_switch']={k:sw.get(k) for k in ['family_time_s','reason','along_axis_lag_m']} if sw else None
    lts=np.asarray(local['timestamp_sample'],np.int64);pos=np.stack([local[k] for k in 'xyz'],1).astype(float);vel=np.stack([local['v'+k] for k in 'xyz'],1).astype(float)
    axis=np.asarray(p['motion_axis_ned'],float);t0=t_fam-1000000
    out['whole']=window_basics(cfg,topics,t0,t_end,t_fam);out['tilt']=tilt_timing(topics,t_fam,t_end)
    out['clipping']=clipping_axes(cfg,memory,t0,t_stream_end)
    i=asof(lts,t_fam);out['state_at_family_start']={'velocity_ned_m_s':list(vel[i]),'speed_along_axis_m_s':float(vel[i]@axis)}
    out['max_speed_along_axis_m_s']=float(np.max(vel[(lts>=t_fam)&(lts<t_end)]@axis)) if ((lts>=t_fam)&(lts<t_end)).any() else None
    # capture family: the pause and its zero-velocity in-flight capture (P5 gap_timing rule).
    gap=None
    if p['family']=='capture':
        rec=receptions(status,sp);rec=rec[(rec>=t_start)&(rec<=t_stream_end)];d=np.diff(rec);idx=np.flatnonzero(d>100000)
        tg=np.asarray(target['timestamp'],np.int64);kind=np.asarray(target['kind']);tim=cfg['p5']['gap_timing'];D=float(p['gap_s'])
        if len(idx)!=1 and not out['aborted']:problems.append(f'{len(idx)} setpoint gaps observed, 1 planned')
        if len(idx):
            t_last,t_first=int(rec[idx[0]]),int(rec[idx[0]+1]);gap={'last_reception_px4_us':t_last,'first_reception_px4_us':t_first,'silence_s':(t_first-t_last)/1e6,'planned_D_s':D}
            if not (D-tim['early_s']<=gap['silence_s']<=D+tim['late_s']):problems.append('setpoint-free interval differs from the planned D')
            caps=np.flatnonzero((kind==T_CAPTURE)&(np.asarray(target['activation'])==0)&(tg>t_last)&(tg<=t_first))
            gap['in_flight_captures']=int(len(caps))
            if len(caps)!=1:problems.append(f'{len(caps)} in-flight captures in the gap (expected 1)')
            else:
                c=int(caps[0]);gap['capture']={'px4_us':int(tg[c]),'after_last_reception_s':(int(tg[c])-t_last)/1e6,'mode':int(target['mode'][c]),
                    'vehicle_velocity_ned_m_s':vec(target,'vehicle_velocity',c),'target_velocity_ned_m_s':vec(target,'velocity',c)}
                lo,hi=tim['capture_delay_s']
                if not lo<=gap['capture']['after_last_reception_s']<=hi:problems.append('capture not in the first cycle after the 200 ms timeout')
                if gap['capture']['mode']!=0 or max(map(abs,gap['capture']['target_velocity_ned_m_s']))>0 or ((kind==T_PROFILE)&(tg>=tg[c])&(tg<t_first)).any():problems.append('capture is not a zero-velocity hold')
    out['gap']=gap
    lim=float(cfg['p6']['ident']['safety_tilt_deg']);mt=out['tilt']['max_tilt_deg']
    if out['aborted']:
        if 'safety' not in str(out['failure_reason']):problems.append('run aborted without a safety reason')
        cls='IDENT_ABORTED'
    elif mt is not None and mt>=45.:cls='IDENT_EXCEEDED_45'
    else:cls='IDENT_OK'
    out['ident_outcome']={'class':cls,'ident_exceeded_45':bool(mt is not None and mt>=45.),'runner_tilt_abort_deg':lim,'altitude_loss_abort_m':cfg.get('p6_altitude_loss_abort_m')}
    return out

def analyze(run):
    run=Path(run).resolve();cfg=json.loads((run/'config.json').read_text());meta=json.loads((run/'metadata.json').read_text());kind=meta['experiment_type']
    if kind=='p5_gap':
        windows='windows_s' in cfg['p2_profile']['gaps']
        if windows:
            frozen=p5_metrics.analyze_gap;p5_metrics.analyze_gap=analyze_gap_windows
            try:out=p5_metrics.analyze(run)
            finally:p5_metrics.analyze_gap=frozen
        else:out=p5_metrics.analyze(run)
        out['p6']={'analyzer':'p5_metrics.analyze with analyze_gap_windows' if windows else 'p5_metrics.analyze (frozen P5)'}
        gaps=out.get('gaps') or [];t0=gaps[0]['last_reception_px4_us'] if gaps else None
        if out.get('aborted'):
            # A run aborted inside an interruption (closed gaps only in the frozen analyzer): the P5 open-gap measurement
            # (tools/p5_open_gap.py, unchanged) at batch time; single-interruption runs only.
            try:og=p5_open_gap.open_gap(run)
            except KeyError:og={'open_gap':None,'note':'not measured for explicit windows'}
            out['p6']['open_gap']=og
            if t0 is None and og and og.get('open_gap'):t0=og['last_arrival_px4_us']
        if t0 is not None:
            u=ULog(str(run/'flight.ulg'),['vehicle_attitude']);topics={d.name:d.data for d in u.data_list if d.multi_id==0}
            out['p6']['tilt']=tilt_timing(topics,t0,out['times_px4_us']['window_end'])
            out['p6']['time_origin_px4_us']=t0
        return clean(out)
    events=[json.loads(s) for s in (run/'events.jsonl').read_text().splitlines()]
    out={'run':str(run),'kind':kind,'condition':cfg.get('p1_condition'),'treatment':cfg.get('p2_treatment'),'treatment_parameters':cfg.get('p2_treatment_parameters')};problems=[]
    u=ULog(str(run/'flight.ulg'),TOPICS);topics={d.name:d.data for d in u.data_list if d.multi_id==0}
    out['independence'],pi=independence(cfg,meta,topics['vehicle_local_position'],topics['vehicle_status']);problems+=pi
    values=dict(u.initial_parameters)
    for stamp,name,value in sorted(u.changed_parameters,key=lambda x:x[0]):values[name]=value
    out['parameters_final']={k:values.get(k) for k in ['MC_RAPTOR_RINI','MC_RAPTOR_RTGT','MC_RAPTOR_RTDEC','MC_RAPTOR_RSH']}
    tp=cfg['p2_treatment_parameters'];want={'MC_RAPTOR_RINI':int(tp['rini']),'MC_RAPTOR_RSH':1,'MC_RAPTOR_RTGT':int(tp['rtgt']),'MC_RAPTOR_RTDEC':float(tp['rtdec'])}
    if any(out['parameters_final'].get(k) is None or abs(out['parameters_final'][k]-v)>1e-5 for k,v in want.items()):problems.append(f"parameters {out['parameters_final']} != planned {want}")
    if kind=='p6_ident':
        out.update(analyze_ident(run,cfg,meta,events,topics,u,problems))
        memory=topics.get('research_memory')
        if memory is not None:
            out['setup_entry']=entry_rows(memory,int(tp['rini']))
            if out['setup_entry']['status']!='VERIFIED':problems.append('a mode entry did not use the planned memory treatment')
    else:problems.append('not a P6 kind')
    out['problems']=problems;out['status']='MEASURED' if not problems else 'INCOMPLETE'
    return clean(out)

def outcome(m):
    """(class, flight_failure) of a run's p6-metrics: p5_gap -> P5 flight outcome; p6_ident -> ident class."""
    if m.get('kind')=='p6_ident':c=(m.get('ident_outcome') or {}).get('class');return c,False
    return (m.get('flight_outcome') or {}).get('outcome'),(m.get('flight_outcome') or {}).get('outcome')=='FAILURE'

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);a=p.parse_args()
    r=analyze(a.run);(a.run/'p6-metrics.json').write_text(json.dumps(r,indent=1,ensure_ascii=False,allow_nan=False)+'\n')
    print(r['status'],r['problems'],outcome(r)[0]);raise SystemExit(0 if r['status']=='MEASURED' else 1)

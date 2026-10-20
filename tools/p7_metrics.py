#!/usr/bin/env python3
"""P7 per-run measurement; writes only p7-metrics.json.

The frozen P6 analysis first (tools/p6_metrics.analyze: the frozen P5 analyzer for one interruption, the P6 windows copy
for explicit interruption windows; interruption timing, captures, resume jumps, flight outcome), then a 'p7' block:

  parameters   MC_RAPTOR_RREC in the log equals the treatment (0 for T0/T1a3, 2.0 for T1a3r2)
  recovery     research_recovery evidence (rate-limited recovery, config p7.recovery). RREC = 0: no row at all. RREC > 0:
               exactly one START per closed interruption, in RAPTOR's first cycle on the resumed setpoint (<= 12 ms after
               its arrival) and none elsewhere; the START state equals the vehicle_local_position sample RAPTOR used in
               that cycle; every STEP row and the CONVERGED END reproduced by an offline replay of the law from the START
               state with the logged setpoints and gyro-sample times (max residual reported, <= 1e-4 required); END reason
               and time; catch-up duration = END CONVERGED - START (None when the recovery ended otherwise); duration in
               which the acceleration was limited; the target jump the network saw at the resume (virtual target start =
               vehicle position minus the target in force before the resume) next to the setpoint jump of the P5 analyzer.
  lag          per resume over [resume, resume + 6 s] (config p7.lag): along-track lag behind the original trajectory and
               horizontal distance to it, maximum and value at the window end.
  tilt         time of the maximum tilt and first sample >= 45 deg from the first interruption (as P6).
No model fitting, prediction or classification.
"""
import argparse,json,math
from pathlib import Path
import numpy as np
from pyulog import ULog
import p6_metrics
from p5_metrics import receptions,setpoint_rows,asof
from p1_metrics import clean

TOPICS=['research_recovery','research_timing','vehicle_local_position','trajectory_setpoint','raptor_status']
R_START,R_STEP,R_END=1,2,3
END_NAMES={1:'CONVERGED',2:'STALE',3:'INACTIVE'}
REPLAY_TOLERANCE=1e-4

def params(run):
    u=ULog(str(run/'flight.ulg'),['vehicle_status']);values=dict(u.initial_parameters)
    for stamp,name,value in sorted(u.changed_parameters,key=lambda x:x[0]):values[name]=value
    return values

def replay(rec,seg,omega,max_dt,exit_p,exit_v):
    """Replay the rate-limited law over one recovery segment (row indices: START, STEP..., [END]) from the START state with the
    logged setpoints and sample times. Returns per-row residuals and whether the END CONVERGED row converges in the replay."""
    i0=seg[0];ts=np.asarray(rec['timestamp_sample'],np.int64)
    p=np.array([float(rec[f'target_position[{k}]'][i0]) for k in range(2)]);v=np.array([float(rec[f'target_velocity[{k}]'][i0]) for k in range(2)])
    rate=float(rec['rate'][i0]);last=int(ts[i0]);res_p=[];res_v=[];limited_dt=0.;converged_ok=None;limits_ok=True
    for i in seg[1:]:
        kind=int(rec['kind'][i])
        if kind==R_END and int(rec['end_reason'][i])!=1:break
        t=int(ts[i]);dt=0.
        if t>last:dt=min((t-last)*1e-6,max_dt);last=t
        sp=np.array([float(rec[f'setpoint_position[{k}]'][i]) for k in range(2)]);sv=np.array([float(rec[f'setpoint_velocity[{k}]'][i]) for k in range(2)])
        a=omega*omega*(sp-p)+2.*omega*(sv-v);n=math.hypot(a[0],a[1]);lim=n>rate
        if lim:a=a*(rate/n)
        v=v+a*dt;p=p+v*dt
        dp=math.hypot(*(sp-p));dv=math.hypot(*(sv-v));conv=dp<exit_p and dv<exit_v
        if kind==R_STEP:
            res_p.append(float(np.max(np.abs(p-np.array([float(rec[f'target_position[{k}]'][i]) for k in range(2)])))))
            res_v.append(float(np.max(np.abs(v-np.array([float(rec[f'target_velocity[{k}]'][i]) for k in range(2)])))))
            if conv or bool(rec['limited'][i])!=lim:limits_ok=False
            if lim:limited_dt+=dt
        else:converged_ok=conv
    return {'steps':len(res_p),'max_position_residual_m':max(res_p) if res_p else None,'max_velocity_residual_m_s':max(res_v) if res_v else None,
            'limited_s':limited_dt,'limit_flags_match':limits_ok,'converged_in_replay':converged_ok}

def recovery_block(run,cfg,base,T,problems):
    tp=cfg['p2_treatment_parameters'];rate=float(tp.get('rrec',0.));rc=cfg['p7']['recovery']
    rec=T.get('research_recovery');gaps=base.get('gaps') or []
    out={'rate_m_s2':rate,'rows':0 if rec is None else int(len(rec['timestamp']))}
    if rate<=0.:
        if out['rows']:problems.append('research_recovery rows with MC_RAPTOR_RREC = 0')
        out['status']='NO_RECOVERY_ROWS (RREC = 0)' if not out['rows'] else 'UNEXPECTED_ROWS';return out
    if rec is None:problems.append('no research_recovery rows with MC_RAPTOR_RREC > 0');out['status']='MISSING';return out
    kind=np.asarray(rec['kind']);ts=np.asarray(rec['timestamp_sample'],np.int64);tt=np.asarray(rec['timestamp'],np.int64)
    starts=np.flatnonzero(kind==R_START);out['starts']=int(len(starts))
    tm=T['research_timing'];tts=np.asarray(tm['timestamp_sample'],np.int64);tls=np.asarray(tm['local_position_sample'],np.int64)
    lp=T['vehicle_local_position'];lts=np.asarray(lp['timestamp_sample'],np.int64)
    axis=np.asarray(cfg['p2_profile']['motion_axis_ned'],float)
    segs=[];used=set()
    for k,s in enumerate(starts):
        nxt=starts[k+1] if k+1<len(starts) else len(kind)
        idx=list(range(s,nxt));end=next((i for i in idx if kind[i]==R_END),None)
        seg=[i for i in idx if i<=(end if end is not None else nxt-1)];segs.append((s,end,seg))
    out['recoveries']=[]
    for g in gaps:
        t_first=int(g['first_reception_px4_us']);cand=[x for x in segs if t_first<=int(tt[x[0]])<=t_first+12000]
        item={'gap':g['index'],'first_reception_px4_us':t_first}
        if len(cand)!=1:problems.append(f"gap {g['index']}: {len(cand)} recovery starts in the first cycle after the resume (expected 1)");out['recoveries'].append(item);continue
        s,end,seg=cand[0];used.add(int(s))
        item.update({'start_px4_us':int(tt[s]),'start_sample':int(ts[s]),'start_after_resume_s':(int(tt[s])-t_first)/1e6,
                     'vehicle_position_ned_m':[float(rec[f'vehicle_position[{k}]'][s]) for k in range(3)],'vehicle_velocity_ned_m_s':[float(rec[f'vehicle_velocity[{k}]'][s]) for k in range(3)],
                     'setpoint_position_ned_m':[float(rec[f'setpoint_position[{k}]'][s]) for k in range(3)],'setpoint_velocity_ned_m_s':[float(rec[f'setpoint_velocity[{k}]'][s]) for k in range(3)]})
        # START state = the local-position sample RAPTOR used in that cycle (research_timing of the same gyro sample).
        j=np.flatnonzero(tts==ts[s])
        if len(j):
            l=np.flatnonzero(lts==tls[j[0]])
            if len(l):
                ref=[float(lp[x][l[0]]) for x in ['x','y','vx','vy']];got=item['vehicle_position_ned_m'][:2]+item['vehicle_velocity_ned_m_s'][:2]
                item['start_state_max_abs_difference']=max(abs(a-b) for a,b in zip(ref,got))
                if item['start_state_max_abs_difference']>1e-6:problems.append(f"gap {g['index']}: recovery start state differs from the local-position sample")
            else:item['start_state_max_abs_difference']=None
        else:item['start_state_max_abs_difference']=None
        r=replay(rec,seg,float(rc['omega_rad_s']),float(rc['max_dt_s']),float(rc['exit_position_m']),float(rc['exit_velocity_m_s']));item['replay']=r
        if r['max_position_residual_m'] is not None and (r['max_position_residual_m']>REPLAY_TOLERANCE or r['max_velocity_residual_m_s']>REPLAY_TOLERANCE):problems.append(f"gap {g['index']}: virtual target differs from the replayed law")
        if not r['limit_flags_match']:problems.append(f"gap {g['index']}: limit flag or convergence differs from the replayed law")
        if abs(float(rec['rate'][s])-rate)>1e-6:problems.append(f"gap {g['index']}: recovery rate differs from the treatment")
        if end is None:item.update({'end':None,'catch_up_s':None,'duration_s':None})
        else:
            reason=END_NAMES.get(int(rec['end_reason'][end]),str(int(rec['end_reason'][end])))
            item.update({'end':reason,'end_px4_us':int(tt[end]),'duration_s':(int(ts[end])-int(ts[s]))/1e6,'catch_up_s':(int(ts[end])-int(ts[s]))/1e6 if reason=='CONVERGED' else None,
                         'end_position_difference_m':float(rec['position_difference'][end]),'end_velocity_difference_m_s':float(rec['velocity_difference'][end])})
            if reason=='CONVERGED' and r['converged_in_replay'] is False:problems.append(f"gap {g['index']}: CONVERGED end not reproduced by the replay")
        # Target jump the network saw at the resume: virtual target start (vehicle) minus the target in force before.
        before=((g.get('resume') or {}).get('target_before_ned_m'))
        if before is not None:
            vb=(g['resume'].get('target_velocity_before_ned_m_s'))
            item['observed_jump_along_axis_m']=float((np.asarray(item['vehicle_position_ned_m'])-np.asarray(before))@axis)
            item['observed_velocity_jump_along_axis_m_s']=float((np.asarray(item['vehicle_velocity_ned_m_s'][:2]+[0.])-np.asarray(vb[:2]+[0.]))@axis) if vb is not None else None
            item['setpoint_jump_along_axis_m']=g['resume'].get('jump_along_axis_m')
        out['recoveries'].append(item)
    # A start outside a planned resume is accepted only when the network never observed the virtual target: no STEP row
    # and an END CONVERGED in the start cycle (e.g. the stream start after a hover timeout capture in the setup, when the
    # activation followed a pre-stream setpoint within 200 ms; the virtual target = vehicle state was already within 0.02).
    extra=[(s,end,seg) for s,end,seg in segs if int(s) not in used]
    def silent(x):
        s,end,seg=x;return end is not None and int(rec['end_reason'][end])==1 and int(ts[end])==int(ts[s]) and not any(kind[i]==R_STEP for i in seg)
    loud=[x for x in extra if not silent(x)]
    if loud and not base.get('aborted'):problems.append(f'{len(loud)} recovery starts not at a resume with virtual-target cycles')
    out['starts_not_at_a_resume']=len(extra);out['starts_not_at_a_resume_without_virtual_target_cycles']=[{'start_px4_us':int(tt[x[0]]),'start_sample':int(ts[x[0]])} for x in extra if silent(x)]
    ends=[x['end'] for x in out['recoveries'] if 'end' in x]
    out['status']='VERIFIED' if not [p for p in problems if 'recover' in p or 'virtual target' in p or 'replay' in p] else 'PROBLEMS'
    out['catch_up_s']=[x.get('catch_up_s') for x in out['recoveries']];out['ends']=ends
    return out

def lag_block(cfg,base,T,window):
    gaps=base.get('gaps') or [];axis=np.asarray(cfg['p2_profile']['motion_axis_ned'],float)
    sp=T['trajectory_setpoint'];rec_t=receptions(T['raptor_status'],sp);spt,spp,spv=setpoint_rows(sp,rec_t)
    lp=T['vehicle_local_position'];lts=np.asarray(lp['timestamp_sample'],np.int64);pos=np.stack([np.asarray(lp[k],float) for k in 'xyz'],1)
    t_end=int((base.get('times_px4_us') or {}).get('window_end') or lts[-1]);t_end=min(t_end,int(lts[-1]))
    out=[]
    for k,g in enumerate(gaps):
        t0=int(g['first_reception_px4_us']);t1=t0+int(window*1e6);w=np.flatnonzero((lts>=t0)&(lts<=min(t1,t_end)))
        if not len(w):out.append({'gap':g['index'],'samples':0});continue
        i=np.searchsorted(spt,lts[w],side='right')-1;tp=spp[i]+spv[i]*((lts[w]-spt[i])/1e6)[:,None]
        d=tp-pos[w];along=d@axis;hor=np.hypot(d[:,0],d[:,1])
        nxt=gaps[k+1]['last_reception_px4_us'] if k+1<len(gaps) else None
        out.append({'gap':g['index'],'window_s':window,'samples':int(len(w)),'truncated':bool(t1>t_end),'observed_until_s':float((lts[w][-1]-t0)/1e6),
            'cut_by_next_interruption':bool(nxt is not None and nxt<t1),'next_interruption_after_s':(nxt-t0)/1e6 if nxt is not None else None,
            'max_along_track_lag_m':float(along.max()),'max_along_track_lag_at_s':float((lts[w][int(np.argmax(along))]-t0)/1e6),'min_along_track_lag_m':float(along.min()),
            'max_horizontal_distance_m':float(hor.max()),'along_track_lag_at_window_end_m':float(along[-1]),'horizontal_distance_at_window_end_m':float(hor[-1]),
            'at_resume':{'along_track_lag_m':float(along[0]),'horizontal_distance_m':float(hor[0])}})
    return out

def analyze(run):
    run=Path(run).resolve();cfg=json.loads((run/'config.json').read_text())
    base=p6_metrics.analyze(run);problems=list(base.get('problems') or [])
    u=ULog(str(run/'flight.ulg'),TOPICS);T={d.name:d.data for d in u.data_list if d.multi_id==0}
    values=dict(u.initial_parameters)
    for stamp,name,value in sorted(u.changed_parameters,key=lambda x:x[0]):values[name]=value
    tp=cfg['p2_treatment_parameters'];p7={'parameters':{'MC_RAPTOR_RREC':values.get('MC_RAPTOR_RREC'),'planned':float(tp.get('rrec',0.))}}
    if values.get('MC_RAPTOR_RREC') is None or abs(float(values['MC_RAPTOR_RREC'])-float(tp.get('rrec',0.)))>1e-5:problems.append(f"MC_RAPTOR_RREC {values.get('MC_RAPTOR_RREC')} != planned {tp.get('rrec',0.)}")
    p7['recovery']=recovery_block(run,cfg,base,T,problems)
    p7['lag']=lag_block(cfg,base,T,float(cfg['p7']['lag']['window_s']))
    # Task criterion (p7.task_failure_criterion), reported next to the frozen flight outcome (never replaces it).
    wh=base.get('whole') or {};tc=cfg['p7'].get('task_failure_criterion') or json.loads((Path(__file__).resolve().parents[1]/'config/p7.json').read_text())['p7']['task_failure_criterion'];og=((base.get('p6') or {}).get('open_gap') or {})
    tilt=wh.get('max_tilt_deg') if wh.get('max_tilt_deg') is not None else og.get('max_tilt_deg_until_raptor_end');alt=wh.get('max_altitude_loss_m')
    reasons=(['tilt'] if tilt is not None and tilt>=float(tc['tilt_deg']) else [])+(['altitude_loss'] if alt is not None and alt>float(tc['altitude_loss_m']) else [])
    if base.get('aborted') and 'safety' in str(base.get('failure_reason')) and 'tilt' not in reasons:reasons.append('runner_safety_abort')
    fo=(base.get('flight_outcome') or {}).get('outcome');p7['task_outcome']={'outcome':'FAILURE' if reasons else 'SUCCESS','reasons':reasons,'max_tilt_deg':tilt,'max_altitude_loss_m':alt,
        'differs_from_flight_outcome':bool(fo is not None and fo!=('FAILURE' if reasons else 'SUCCESS'))}
    out=dict(base);out['p7']=p7;out['problems']=problems;out['status']='MEASURED' if not problems else 'INCOMPLETE'
    return clean(out)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);a=p.parse_args()
    r=analyze(a.run);(a.run/'p7-metrics.json').write_text(json.dumps(r,indent=1,ensure_ascii=False,allow_nan=False)+'\n')
    print(r['status'],r['problems'],p6_metrics.outcome(r)[0]);raise SystemExit(0 if r['status']=='MEASURED' else 1)

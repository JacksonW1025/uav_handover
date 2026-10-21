#!/usr/bin/env python3
"""P8 per-run measurement; writes only p8-metrics.json.

A (kind p6_ident, config/p8.json): the frozen P6 analysis first (tools/p6_metrics.analyze: seed and heading, parameters,
mode entries with N2, family start, chase switch, max tilt and its time, altitude loss, clipping, ident outcome class),
then a 'p8' block:
  parameters   MC_RAPTOR_RREC in the log equals the treatment (0) and research_recovery has no row
  jump         jump family: exactly one setpoint step along the axis in the logged stream (step size = position increment
               minus the velocity feed-forward advance between the two rows; planned jump_m within 0.01 m); its arrival
               time and family time (planned accel_s + pre_jump_s within 0.03 s); RAPTOR's first cycle reading it; the
               realized cruise before and after it (setpoints at the cruise speed); the state just before / after
  lag          along-axis lag of the vehicle behind the time-parameterized target (latest logged setpoint advanced by its
               velocity) from the family start: initial value after the jump / target appearance, maximum, first time it
               is <= 0.2 m (catch-up), and the vehicle speed maximum
  vertical     altitude (above the local origin) at the family start, minimum, max altitude loss and its time (P6 window
               [family start - 1 s, end of post_stream], reference at the family start), max descent / climb speed,
               the motor command mean (actuator_motors) minimum / maximum and time at the upper or lower limit
  task_criterion   the P8 fixed second criterion (max tilt >= 45 deg or max altitude loss > 1.0 m), reported only (an
               identification flight is not a failure test)
No model fitting, prediction or classification.
"""
import argparse,json,math
from pathlib import Path
import numpy as np
from pyulog import ULog
import p6_metrics
from p5_metrics import receptions,setpoint_rows,asof
from p1_metrics import clean

TOPICS=['trajectory_setpoint','raptor_status','vehicle_local_position','actuator_motors','research_recovery','vehicle_attitude']
JUMP_SIZE_TOL_M=0.01;JUMP_TIME_TOL_S=0.03;CATCH_UP_M=0.2

def parameters(u):
    values=dict(u.initial_parameters)
    for stamp,name,value in sorted(u.changed_parameters,key=lambda x:x[0]):values[name]=value
    return values

def line(T,t_start,t_stream_end,origin):
    """Logged stream setpoints (t, along-axis s relative to the hover capture, v along axis) inside the profile."""
    sp=T['trajectory_setpoint'];t=np.asarray(sp['timestamp'],np.int64);w=(t>=t_start-20000)&(t<=t_stream_end)
    pos=np.stack([np.asarray(sp[f'position[{k}]'],float) for k in range(3)],1)[w];vel=np.stack([np.asarray(sp[f'velocity[{k}]'],float) for k in range(3)],1)[w]
    return t[w],pos,vel

def jump_block(cfg,base,T,axis,problems):
    p=cfg['p2_profile'];tm=base.get('times_px4_us') or {};t_fam=tm.get('family_start')
    if t_fam is None:return None
    t,pos,vel=line(T,int(tm['profile_start']),int(tm['stream_end']),None);s=pos@axis;v=vel@axis
    adv=v[:-1]*np.diff(t)/1e6;step=np.diff(s)-adv
    L=float(p['jump_m']);big=np.flatnonzero(np.abs(step)>L/2)
    out={'planned_jump_m':L,'steps_found':int(len(big))}
    if len(big)!=1:problems.append(f'{len(big)} setpoint jumps found, 1 planned');return out
    k=int(big[0]);tj=int(t[k+1]);out.update({'jump_m':float(step[k]),'jump_setpoint_px4_us':tj,'last_setpoint_before_px4_us':int(t[k]),
        'family_time_s':(tj-t_fam)/1e6,'planned_family_time_s':float(p['accel_s'])+float(p['pre_jump_s'])})
    if abs(out['jump_m']-L)>JUMP_SIZE_TOL_M:problems.append('setpoint jump differs from the planned jump_m')
    if not -0.005<=out['family_time_s']-out['planned_family_time_s']<=JUMP_TIME_TOL_S:problems.append('setpoint jump not at the planned family time')
    V=float(p['speed_m_s']);cruise=np.abs(v-V)<1e-4
    pre=np.flatnonzero(cruise[:k+1]);post=np.flatnonzero(cruise[k+1:])+k+1
    out['realized_pre_jump_cruise_s']=float((t[k]-t[pre[0]])/1e6+0.02) if len(pre) else None
    # post-jump cruise: from the jump setpoint to the first setpoint below the cruise speed (deceleration start)
    dec=np.flatnonzero((np.arange(len(t))>k)&(v<V-1e-4))
    out['realized_post_jump_cruise_s']=float((t[dec[0]]-tj)/1e6) if len(dec) else None;out['planned_post_jump_cruise_s']=float(p['post_jump_s'])
    st=T['raptor_status'];stt=np.asarray(st['timestamp'],np.int64);rd=np.flatnonzero((np.asarray(st['subscription_update_trajectory_setpoint'])==1)&(stt>=tj))
    out['raptor_first_read_px4_us']=int(stt[rd[0]]) if len(rd) else None;out['raptor_read_delay_s']=(int(stt[rd[0]])-tj)/1e6 if len(rd) else None
    return out

def lag_block(cfg,base,T,axis,t_ref):
    """Along-axis lag behind the time-parameterized target from t_ref (jump setpoint arrival / target appearance)."""
    tm=base.get('times_px4_us') or {};t_end=int(tm.get('window_end') or 0);t_stream=int(tm['stream_end'])
    sp=T['trajectory_setpoint'];spt,spp,spv=setpoint_rows(sp,receptions(T['raptor_status'],sp))
    lp=T['vehicle_local_position'];lts=np.asarray(lp['timestamp_sample'],np.int64);pos=np.stack([np.asarray(lp[k],float) for k in 'xyz'],1);vel=np.stack([np.asarray(lp['v'+k],float) for k in 'xyz'],1)
    w=np.flatnonzero((lts>=t_ref)&(lts<=min(t_end,t_stream)))
    if not len(w):return {'samples':0}
    i=np.searchsorted(spt,lts[w],side='right')-1;tp=spp[i]+spv[i]*((lts[w]-spt[i])/1e6)[:,None]
    lag=(tp-pos[w])@axis;tt=(lts[w]-t_ref)/1e6;cu=np.flatnonzero(lag<=CATCH_UP_M)
    sp_u=vel[w]@axis
    return {'reference_px4_us':int(t_ref),'samples':int(len(w)),'initial_lag_m':float(lag[0]),'max_lag_m':float(lag.max()),'max_lag_at_s':float(tt[int(np.argmax(lag))]),
            'catch_up_s':float(tt[cu[0]]) if len(cu) else None,'catch_up_rule':f'first sample with along-axis lag <= {CATCH_UP_M} m','min_lag_m':float(lag.min()),'min_lag_at_s':float(tt[int(np.argmin(lag))]),
            'max_speed_along_axis_m_s':float(sp_u.max()),'max_speed_along_axis_at_s':float(tt[int(np.argmax(sp_u))])}

def vertical_block(cfg,base,T):
    tm=base.get('times_px4_us') or {};t_fam=int(tm['family_start']);t0=t_fam-1000000;t1=int(tm['window_end'])
    lp=T['vehicle_local_position'];lts=np.asarray(lp['timestamp_sample'],np.int64);z=np.asarray(lp['z'],float);vz=np.asarray(lp['vz'],float)
    w=(lts>=t0)&(lts<t1);i0=asof(lts,t_fam);loss=z[w]-z[i0];k=int(np.argmax(loss))
    m=T['actuator_motors'];mt=np.asarray(m['timestamp'],np.int64);mv=np.stack([np.asarray(m[f'control[{i}]'],float) for i in range(4)],1);mw=(mt>=t0)&(mt<t1)
    mean=mv[mw].mean(1) if mw.any() else np.zeros(0);sat=cfg['p2']['motor_saturation']
    at=np.any(mv[mw]>=sat['upper'],1)|np.any(mv[mw]<=sat['lower'],1) if mw.any() else np.zeros(0,bool)
    dt=np.median(np.diff(mt[mw]))/1e6 if mw.sum()>1 else 0.
    return {'window':'[family start - 1 s, end of post_stream), altitude reference at the family start','altitude_at_family_start_m':float(-z[i0]),
            'min_altitude_m':float(-z[w].max()),'max_altitude_loss_m':max(0.,float(loss.max())),'max_altitude_loss_at_s':float((lts[w][k]-t_fam)/1e6),
            'max_descent_speed_m_s':float(vz[w].max()),'max_climb_speed_m_s':float(-vz[w].min()),
            'motor_command_mean_min':float(mean.min()) if len(mean) else None,'motor_command_mean_max':float(mean.max()) if len(mean) else None,
            'motor_any_at_limit_s':float(at.sum()*dt),'motor_limits':sat}

def analyze_ident(run,cfg,base,problems):
    u=ULog(str(run/'flight.ulg'),TOPICS);T={d.name:d.data for d in u.data_list if d.multi_id==0}
    values=parameters(u);tp=cfg['p2_treatment_parameters'];p8={}
    rr=T.get('research_recovery');rows=0 if rr is None else int(len(rr['timestamp']))
    p8['parameters']={'MC_RAPTOR_RREC':values.get('MC_RAPTOR_RREC'),'planned_rrec':float(tp.get('rrec',0.)),'research_recovery_rows':rows}
    if values.get('MC_RAPTOR_RREC') is None or abs(float(values['MC_RAPTOR_RREC'])-float(tp.get('rrec',0.)))>1e-5:problems.append(f"MC_RAPTOR_RREC {values.get('MC_RAPTOR_RREC')} != planned {tp.get('rrec',0.)}")
    if rows:problems.append(f'{rows} research_recovery rows with RREC 0')
    tm=base.get('times_px4_us') or {};p=cfg['p2_profile'];axis=np.asarray(p['motion_axis_ned'],float)
    if tm.get('family_start') is None:return p8
    if p['family']=='jump':
        p8['jump']=jump_block(cfg,base,T,axis,problems)
        tj=(p8['jump'] or {}).get('jump_setpoint_px4_us')
        p8['lag']=lag_block(cfg,base,T,axis,tj) if tj else None
    elif p['family']=='chase':
        sw=base.get('chase_switch') or {}
        p8['chase']={'switch_family_time_s':sw.get('family_time_s'),'reason':sw.get('reason'),'planned_max_chase_s':float(p['max_chase_s']),'x0_m':float(p['x0_m'])}
        p8['lag']=lag_block(cfg,base,T,axis,int(tm['family_start']))
    p8['vertical']=vertical_block(cfg,base,T)
    tc=cfg['p8']['criteria']['task'];tilt=(base.get('tilt') or {}).get('max_tilt_deg');alt=p8['vertical']['max_altitude_loss_m']
    reasons=(['tilt'] if tilt is not None and tilt>=float(tc['tilt_deg']) else [])+(['altitude_loss'] if alt>float(tc['altitude_loss_m']) else [])
    if base.get('aborted'):reasons.append('runner_safety_abort')
    p8['task_criterion']={'exceeded':bool(reasons),'reasons':reasons,'max_tilt_deg':tilt,'max_altitude_loss_m':alt,
        'note':'reported only; identification flights are not failure tests (ident class is the outcome)'}
    return p8

def analyze(run):
    run=Path(run).resolve();cfg=json.loads((run/'config.json').read_text());meta=json.loads((run/'metadata.json').read_text())
    base=p6_metrics.analyze(run);problems=list(base.get('problems') or [])
    if meta['experiment_type']=='p6_ident':p8=analyze_ident(run,cfg,base,problems)
    else:problems.append('not a P8 kind');p8=None
    out=dict(base);out['p8']=p8;out['problems']=problems;out['status']='MEASURED' if not problems else 'INCOMPLETE'
    return clean(out)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);a=p.parse_args()
    r=analyze(a.run);(a.run/'p8-metrics.json').write_text(json.dumps(r,indent=1,ensure_ascii=False,allow_nan=False)+'\n')
    print(r['status'],r['problems'],p6_metrics.outcome(r)[0]);raise SystemExit(0 if r['status']=='MEASURED' else 1)

"""Sample-based recovery with a complete, bounded observation interval."""
import numpy as np

def sustained(t, good, valid, start, end, dwell_s, max_gap_s, break_before=None):
    t=np.asarray(t,dtype=np.int64);good=np.asarray(good,bool);valid=np.asarray(valid,bool)
    best_good=best_observed=None;observed=False;gap_seen=False
    breaks=np.zeros(len(t),bool) if break_before is None else np.asarray(break_before,bool)
    for i,stamp in enumerate(t):
        if stamp<start or stamp>=end:continue
        continuous=i>0 and 0<stamp-t[i-1]<=max_gap_s*1e6 and not breaks[i]
        if breaks[i] or (i>0 and t[i-1]>=start and not continuous) or not valid[i]:gap_seen=True
        if not valid[i]:best_good=best_observed=None;continue
        if best_observed is None or not continuous:best_observed=stamp
        if stamp-best_observed>=dwell_s*1e6:observed=True
        if not good[i]:best_good=None;continue
        if best_good is None or not continuous:best_good=stamp
        if stamp-best_good>=dwell_s*1e6:
            return {'status':'SETTLED','time_s':float((best_good-start)/1e6),
                    'entry_us':int(best_good),'confirmed_us':int(stamp),'stage_end_us':int(end),
                    'true_first_recovery_uncertain':gap_seen}
    return {'status':'NOT_SETTLED' if observed else 'INSUFFICIENT_OBSERVATION',
            'time_s':None,'entry_us':None,'confirmed_us':None,'stage_end_us':int(end),
            'true_first_recovery_uncertain':gap_seen}

def setpoint_reference(setpoint, t):
    """Position target in effect at each time: last published trajectory_setpoint, held
    without a staleness limit (it is a command, not an observation). NaN before the first one."""
    st=setpoint['timestamp'].astype(np.int64);i=np.searchsorted(st,t,side='right')-1
    ref=np.stack([setpoint[f'position[{k}]'][np.maximum(i,0)] for k in range(3)],1).astype(np.float64)
    ref[i<0]=np.nan
    return ref

def recovery(local, angular, cfg, start, end, setpoint=None):
    """Joint recovery. With position_reference='active_trajectory_setpoint' the verdict uses the
    controller's own position target; the fixed NED reference is always reported for comparison."""
    use_setpoint=cfg.get('position_reference')=='active_trajectory_setpoint'
    if use_setpoint and setpoint is None:raise ValueError('setpoint reference requires trajectory_setpoint')
    result=_recovery(local,angular,cfg,start,end,setpoint if use_setpoint else None)
    result['position_reference']='active_trajectory_setpoint' if use_setpoint else 'fixed_ned'
    if use_setpoint:
        fixed=_recovery(local,angular,cfg,start,end,None)
        result['fixed_reference_comparison']={'joint_recovery':fixed['joint_recovery'],'position_band_entry':fixed['position_band_entry'],
            'note':'Comparison only; the fixed NED reference also measures setpoint drift accumulated across handovers.'}
    return result

def _recovery(local, angular, cfg, start, end, setpoint):
    lt=local['timestamp'].astype(np.int64);at=angular['timestamp'].astype(np.int64)
    # Union evaluates every angular sample, including spikes between position samples.
    grid=np.unique(np.r_[lt[(lt>=start)&(lt<end)],at[(at>=start)&(at<end)]])
    li=np.searchsorted(lt,grid,side='right')-1;ai=np.searchsorted(at,grid,side='right')-1
    valid=(li>=0)&(ai>=0);li=np.maximum(li,0);ai=np.maximum(ai,0)
    gap=cfg['max_observation_gap_s'];valid &= (grid>=lt[li])&(grid>=at[ai]);valid &= (grid-lt[li]<=gap*1e6)&(grid-at[ai]<=gap*1e6)
    pos=np.stack([local[k][li] for k in ['x','y','z']],1)
    vel=np.stack([local[k][li] for k in ['vx','vy','vz']],1)
    omega=np.stack([angular[f'xyz[{i}]'][ai] for i in range(3)],1)
    ref=setpoint_reference(setpoint,grid) if setpoint is not None else np.asarray(cfg['position_reference_ned_m'],float)
    ep=np.linalg.norm(pos-ref,axis=1)
    ev=np.linalg.norm(vel-cfg['velocity_reference_ned_m_s'],axis=1)
    ew=np.linalg.norm(omega-cfg['angular_velocity_reference_frd_rad_s'],axis=1)
    valid &= np.isfinite(ep)&np.isfinite(ev)&np.isfinite(ew)
    joint=(ep<=cfg['position_threshold_m'])&(ev<=cfg['velocity_threshold_m_s'])&(ew<=cfg['angular_velocity_threshold_rad_s'])
    # A fresh sample after a source gap must restart continuity even when the
    # other topic fills the union grid and its backward-aligned age stays <=20ms.
    breaks=np.zeros(len(grid),bool)
    for indices,source in [(li,lt),(ai,at)]:
        changed=np.r_[True,np.diff(indices)!=0]
        prior=np.maximum(indices-1,0)
        breaks |= changed & (indices>0) & (source[indices]-source[prior]>gap*1e6)
    joint_result=sustained(grid,joint,valid,start,end,cfg['dwell_s'],gap,breaks)
    # Preserve the old position-only concept, now with explicit scope and name.
    p=np.stack([local[k] for k in ['x','y','z']],1)
    pref=setpoint_reference(setpoint,lt) if setpoint is not None else np.asarray(cfg['position_reference_ned_m'],float)
    pe=np.linalg.norm(p-pref,axis=1)
    position=sustained(lt,pe<=cfg['position_threshold_m'],np.isfinite(pe),start,end,cfg['dwell_s'],gap)
    return {'start_us':int(start),'end_us':int(end),
            'position_band_entry':position,'joint_recovery':joint_result,
            'position_band_entry_time_s':position['time_s'],
            'joint_recovery_time_s':joint_result['time_s'],
            'reference_and_thresholds':cfg,
            'observation_quality':{'union_samples':len(grid),'invalid_aligned_samples':int(sum(~valid)),
                'source_gap_breaks':int(sum(breaks)),
                'position_velocity_max_alignment_age_us':int(max(grid-lt[li])) if len(grid) else None,
                'angular_velocity_max_alignment_age_us':int(max(grid-at[ai])) if len(grid) else None,
                'alignment':'backward as-of only; fresh sample after source gap restarts continuity'}}

#!/usr/bin/env python3
"""P4 per-run checks on top of p2_metrics / p3_metrics; writes only p4-metrics.json.

Independent run conditions actually realized (Gazebo command carried the planned seed, heading before arming equals
the planned initial heading), the state at each takeover (speed and acceleration along the motion axis, for the 01b
baseline matching), teacher-forcing coverage before an N2 takeover (consecutive teacher-forced native steps right
before the mode entry, at least p4.teacher_forcing_min_native_steps), the pre-motion planned-path check and the
largest horizontal radius actually flown. Reads the stored p2-metrics.json or p3-metrics.json for the event times.
"""
import argparse,json,math
from pathlib import Path
import numpy as np
from pyulog import ULog
from p1_metrics import clean,asof
KIND_STEP,KIND_ENTRY=1,2

def heading_before_arming(local,status):
    armed=status['timestamp'][status['arming_state']==2].astype(np.int64)
    if not len(armed):return None
    t=local['timestamp'].astype(np.int64);w=(t>=armed[0]-1000000)&(t<armed[0])
    if not w.any():return None
    h=local['heading'][w].astype(float);return float(np.degrees(math.atan2(np.mean(np.sin(h)),np.mean(np.cos(h)))))

def capture_state(local,t_c,axis,window_s):
    t=local['timestamp_sample'].astype(np.int64) if 'timestamp_sample' in local else local['timestamp'].astype(np.int64)
    i=asof(t,t_c);w=(t>=t_c-window_s*1e6)&(t<=t_c)
    v=np.array([local[k][i] for k in ['vx','vy','vz']],float);acc=np.stack([local[k][w] for k in ['ax','ay','az']],1).astype(float)
    return {'px4_us':int(t_c),'speed_along_axis_m_s':float(v@axis),'horizontal_speed_m_s':float(np.hypot(v[0],v[1])),
            'acceleration_along_axis_m_s2':float(acc.mean(0)@axis) if len(acc) else None,'acceleration_window_s':window_s,'samples':int(w.sum())}

def teacher_coverage(memory,t_c):
    """Consecutive inactive, teacher-forced native steps immediately before the mode entry that precedes t_c."""
    mt=memory['timestamp'].astype(np.int64);entry=np.flatnonzero((memory['kind']==KIND_ENTRY)&(mt<=t_c+20000)&(mt>=t_c-100000))
    t_entry=int(mt[entry[-1]]) if len(entry) else t_c
    idx=np.flatnonzero((memory['kind']==KIND_STEP)&(memory['native_step']==1)&(mt<t_entry))
    n=0
    for i in idx[::-1]:
        if memory['active'][i]==0 and memory['teacher_forced'][i]==1:n+=1
        else:break
    return {'entry_px4_us':t_entry,'consecutive_teacher_forced_native_steps':n,'span_s':float((t_entry-mt[idx[-n]])/1e6) if n else 0.}

def analyze(run):
    run=Path(run).resolve();cfg=json.loads((run/'config.json').read_text());meta=json.loads((run/'metadata.json').read_text())
    events=[json.loads(s) for s in (run/'events.jsonl').read_text().splitlines()];kind=meta['experiment_type'];p4=cfg['p4'];problems=[]
    p3kind=kind.startswith('p3_');mname='p3-metrics.json' if p3kind else 'p2-metrics.json'
    out={'run':str(run),'kind':kind,'condition':cfg.get('p3_condition') if p3kind else cfg.get('p1_condition'),
         'treatment':cfg.get('p3_treatment') if p3kind else cfg.get('p2_treatment')}
    if not (run/mname).exists():return clean({**out,'status':'INCOMPLETE','problems':[mname+' missing']})
    m=json.loads((run/mname).read_text())
    u=ULog(str(run/'flight.ulg'),['vehicle_local_position','vehicle_status','research_memory']);t={d.name:d.data for d in u.data_list if d.multi_id==0}
    local,status=t['vehicle_local_position'],t['vehicle_status']
    # Independent run conditions.
    planned=cfg.get('p4_independence') or {};gz=next((p['command'] for p in meta['processes'] if p['name']=='gazebo'),[])
    seed_cmd=gz[gz.index('--seed')+1] if '--seed' in gz else None;heading=heading_before_arming(local,status)
    # Gazebo spawn yaw is CCW from East (ENU); PX4 heading is CW from North incl. declination (config heading_at_zero_deg).
    want_yaw=float(p4['independence']['initial_yaw']['heading_at_zero_deg'])-(planned.get('initial_yaw_deg') or 0.)
    out['independence']={'planned':planned or None,'gazebo_seed_argument':seed_cmd,'heading_before_arming_deg':heading,'expected_heading_deg':want_yaw,
        'heading_error_deg':None if heading is None else float((heading-want_yaw+180)%360-180)}
    if planned.get('sim_seed') is not None and seed_cmd!=str(planned['sim_seed']):problems.append('Gazebo command does not carry the planned seed')
    if planned.get('sim_seed') is None and seed_cmd is not None:problems.append('unplanned Gazebo seed')
    if heading is None or abs(out['independence']['heading_error_deg'])>3.0:problems.append('heading before arming differs from the planned initial heading')
    # Takeover states and teacher-forcing coverage.
    if p3kind:
        spec=cfg['p3_condition_spec'];axis=np.asarray((spec.get('motion') or {}).get('axis_ned',[1.,0.,0.]),float)
        changes={n:e['change_px4_us'] for n,e in (m.get('events') or {}).items() if n in ['first_C_to_N','second_C_to_N','baseline_recapture']}
        rini=int(cfg['p3_treatment_parameters']['rini']);tf_event='second_C_to_N'
        if spec.get('motion'):
            chk=next((e for e in events if e['event']=='p3_motion_check'),None);out['planned_path']=chk
            if chk is None or not chk['max_planned_radius_m']<=chk['limit_m']:problems.append('M3 planned path check missing or outside the limit')
    else:
        axis=np.asarray(cfg['p2_profile']['motion_axis_ned'],float);changes={'subject':m.get('change_px4_us')} if m.get('change_px4_us') else {}
        rini=int(cfg['p2_treatment_parameters'].get('rini',0));tf_event='subject'
        chk=next((e for e in events if e['event']=='p4_planned_path_check'),None);out['planned_path']=chk
        if cfg.get('p1_speed_m_s') and (chk is None or not chk['inside']):problems.append('planned path check missing or outside the limit')
        fin=next((e for e in events if e['event']=='p4_final_setpoint'),None);out['final_setpoint']=fin
        if kind=='p2_baseline_raptor' and cfg['p2_profile'].get('raptor_baseline_stop_early_s') and fin is None:problems.append('baseline final setpoint missing')
    win=p4['baseline_matching']['acceleration_window_s']
    out['takeover_state']={n:capture_state(local,tc,axis,win) for n,tc in changes.items() if tc}
    out['motion_axis_ned']=axis
    if rini==4 and (p3kind or kind=='p2_c_to_n'):
        memory=t.get('research_memory')
        if memory is None or tf_event not in changes:problems.append('teacher-forcing coverage not measurable')
        else:
            out['teacher_forcing_coverage']=teacher_coverage(memory,changes[tf_event])
            if out['teacher_forcing_coverage']['consecutive_teacher_forced_native_steps']<p4['teacher_forcing_min_native_steps']:problems.append('fewer teacher-forced native steps before the takeover than required')
    # Diagnostic: research_memory inference rows missing from the log (one row per 4 ms control call while armed).
    memory=t.get('research_memory')
    if memory is not None:
        st=memory['timestamp'][memory['kind']==KIND_STEP].astype(np.int64);gaps=np.diff(st)
        out['log_continuity']={'research_memory_step_rows':int(len(st)),'gaps_over_4ms':int((gaps>4000).sum()),'max_gap_us':int(gaps.max()) if len(gaps) else None}
    vs=status['timestamp'][status['arming_state']==2].astype(np.int64);lt=local['timestamp'].astype(np.int64)
    w=(lt>=vs[0])&(lt<=vs[-1]) if len(vs) else np.zeros(len(lt),bool)
    out['max_horizontal_radius_m']=float(np.max(np.hypot(local['x'][w],local['y'][w]))) if w.any() else None;out['safety_radius_m']=cfg['safety_radius_m']
    out['problems']=problems;out['status']='MEASURED' if not problems else 'INCOMPLETE'
    return clean(out)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);a=p.parse_args()
    r=analyze(a.run);(a.run/'p4-metrics.json').write_text(json.dumps(r,indent=1,ensure_ascii=False,allow_nan=False)+'\n')
    print(r['status'],r['problems']);raise SystemExit(0 if r['status']=='MEASURED' else 1)

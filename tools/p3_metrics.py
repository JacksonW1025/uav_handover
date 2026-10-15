#!/usr/bin/env python3
"""P3 per-run measurement of the RAPTOR memory lifecycle sequence; writes only p3-metrics.json.

Events (native PX4 us): first C->N (always N0), N->C (classic OFFBOARD takeover, NCO=0), second C->N (memory
treatment), or for the RAPTOR continuous-hover baseline its re-capture after the stream stops. Each event is measured
like P1/P2 (trigger = native pre-request bound, actual change = actuator owner change or RAPTOR capture). Evidence
checked independently from the ULog: treatment parameters in force over time, the exit memory RAPTOR stored on its own
thread at the N->C, the mode-entry writes at both C->N, teacher forcing during the deactivation, RAPTOR's activation
capture with zero target velocity, ownership sequence, the pre-registered short-stage exemption, and flight outcome.
"""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from pyulog import ULog
from recovery import recovery
from p0_metrics import raptor_captures,controller_target,neural_intervals
from p1_metrics import clean,asof,hold_durations,tilt_deg
from p2_metrics import params_at,vec,longest_run,classic_commands,matching_command
from p2_action_map import header_map

TOPICS=['vehicle_local_position','vehicle_angular_velocity','research_angular_velocity','vehicle_attitude','actuator_motors',
        'research_actuator','vehicle_status','trajectory_setpoint','research_state_response','research_memory','research_timing']
KIND_STEP,KIND_ENTRY,KIND_EXIT=1,2,3
CLASSIC,NEURAL=2,1

def yaw_deg(q):return float(np.degrees(np.arctan2(2*(q[0]*q[3]+q[1]*q[2]),1-2*(q[2]**2+q[3]**2))))

def measure(cfg,topics,target,t_r,t_c,t_e,judge_recovery=True):
    """One event: [t_r, t_e) window, actual change t_c. Same quantities and frozen thresholds as p1_metrics."""
    p3=cfg['p3'];local=dict(topics['vehicle_local_position']);local['timestamp']=local.get('timestamp_sample',local['timestamp'])
    ang=dict(topics['research_angular_velocity'] if 'research_angular_velocity' in topics else topics['vehicle_angular_velocity'])
    ang['timestamp']=ang.get('timestamp_sample',ang['timestamp'])
    lt=local['timestamp'].astype(np.int64);pos=np.stack([local[k] for k in 'xyz'],1).astype(float);vel=np.stack([local['v'+k] for k in 'xyz'],1).astype(float)
    ic,ir=asof(lt,t_c),asof(lt,t_r);w=(lt>=t_r)&(lt<t_e);wc=(lt>=t_c)&(lt<t_e)
    att=topics['vehicle_attitude'];at=att['timestamp'].astype(np.int64);q=np.stack([att[f'q[{i}]'] for i in range(4)],1).astype(float)
    out={'trigger_px4_us':t_r,'change_px4_us':t_c,'window_end_px4_us':t_e,'window_s':(t_e-t_r)/1e6,'trigger_to_change_ms':(t_c-t_r)/1e3,
         'state_at_change':{'position_ned_m':pos[ic],'velocity_ned_m_s':vel[ic],'horizontal_speed_m_s':float(np.hypot(*vel[ic,:2])),
                            'altitude_m':float(-pos[ic,2]),'yaw_deg':yaw_deg(q[asof(at,t_c)])}}
    tg=np.searchsorted(target['timestamp'],lt,side='right')-1
    tpos=np.stack([target[f'position[{k}]'][np.maximum(tg,0)] for k in range(3)],1);tpos[tg<0]=np.nan
    err=np.linalg.norm(pos-tpos,axis=1)
    out['max_altitude_loss_m']=max(0.,float(np.max(pos[w,2])-pos[ir,2]))
    if judge_recovery:
        rec=recovery(local,ang,cfg['joint_recovery'],t_c,t_e,target);jr=rec['joint_recovery']
        out['joint_recovery']={'status':jr['status'],'from_change_s':jr['time_s'],'confirmed_px4_us':jr['confirmed_us'],
            'true_first_recovery_uncertain':jr['true_first_recovery_uncertain'],'position_reference':rec['position_reference'],
            'fixed_reference_comparison':rec['fixed_reference_comparison']['joint_recovery']}
    else:out['joint_recovery']={'status':'NOT_JUDGED','reason':'window shorter than the joint-recovery dwell (pre-registered short deactivation)'}
    aw=(at>=t_r)&(at<t_e);tilt=tilt_deg(q[aw])
    av=topics['vehicle_angular_velocity'];avt=av['timestamp'].astype(np.int64);avw=(avt>=t_r)&(avt<t_e)
    rate=np.max(np.abs(np.stack([av[f'xyz[{i}]'] for i in range(3)],1)[avw]),axis=1)
    limits={'horizontal_radius_m':(float(np.max(np.hypot(pos[w,0],pos[w,1]))),cfg['safety_radius_m']),
        'altitude_m':(float(np.max(-pos[w,2])),cfg['safety_altitude_m']),'below_ground_z_m':(float(np.max(pos[w,2])),1.0),
        'tilt_safety_deg':(float(np.max(tilt)),cfg['safety_tilt_deg']),'angular_rate_component_rad_s':(float(np.max(rate)),cfg['safety_angular_rate_rad_s']),
        'error_to_active_target_m':(float(np.nanmax(err[w])),cfg['hover_max_error_m']),'tilt_hover_deg':(float(np.max(tilt)),cfg['hover_max_tilt_deg'])}
    out['window_constraints']={k:{'max':a,'limit':b,'satisfied':a<=b} for k,(a,b) in limits.items()}
    out['max_tilt_deg']=float(np.max(tilt));out['max_error_to_active_target_m']=float(np.nanmax(err[wc])) if wc.any() else None
    m=topics['actuator_motors'];mt=m['timestamp'].astype(np.int64);mv=np.stack([m[f'control[{i}]'] for i in range(4)],1).astype(float)
    lo,hi=p3['motor_step_window_s'];idx=np.flatnonzero((mt>=t_c+lo*1e6)&(mt<=min(t_c+hi*1e6,t_e)))
    steps=np.max(np.abs(np.diff(mv[idx],axis=0)),axis=1) if len(idx)>1 else np.array([])
    j=int(np.searchsorted(mt,t_c));sat=p3['motor_saturation'];mw=(mt>=t_r)&(mt<t_e)
    mask=np.any(mv>=sat['upper'],1)|np.any(mv<=sat['lower'],1)
    out['motor']={'step_at_change':float(np.max(np.abs(mv[j]-mv[j-1]))) if 0<j<len(mt) else None,
        'max_step_in_window':float(np.max(steps)) if len(steps) else None,'saturation_any_s':hold_durations(mt[mw],mask[mw],t_r,t_e),
        'longest_continuous_saturation_s':longest_run(mt[mw],mask[mw],t_e),'mean_command_before_change':mv[(mt>=t_c-500000)&(mt<t_c)].mean(0)}
    sel=(mt>=t_c-1000000)&(mt<min(t_c+2000000,t_e))
    out['curves']={'motor_t_s':(mt[sel]-t_c)/1e6,'motor':mv[sel]}
    k=np.flatnonzero(w)[::5]
    out['curves'].update({'t_s':(lt[k]-t_c)/1e6,'position_ned_m':pos[k],'velocity_ned_m_s':vel[k],'target_ned_m':tpos[k]})
    out['min_altitude_m']=float(np.min(-pos[w,2]))
    return out

def capture_check(topics,captures,t_c,activation):
    cap=next((c for c in captures if c[0]>=t_c-20000),None)
    ref={'capture_px4_us':cap[0] if cap else None,'position_ned_m':cap[1] if cap else None,'velocity_ned_m_s':[0.,0.,0.]}
    if activation:
        ref['classification']='activation_reset_hold' if cap is not None and abs(cap[0]-t_c)<=50000 else 'not_at_activation'
        r=topics['research_state_response'];rows=np.flatnonzero((r['timestamp']>=t_c)&(r['target']==1)&(r['operation']==1)&(r['result']==0)&(r['active']==1))
        if len(rows):
            i=rows[0];values=[float(r[f'values[{k}]'][i]) for k in range(20,26)]
            ref['state_read_after_entry']={'px4_us':int(r['timestamp'][i]),'position_ned_m':values[:3],'velocity_ned_m_s':values[3:]}
            ref['state_read_matches_capture']=bool(cap) and max(abs(a-b) for a,b in zip(values[:3],cap[1]))<1e-4 and max(map(abs,values[3:]))<1e-6
        else:ref['state_read_matches_capture']=False
        ref['zero_velocity_capture']=ref['classification']=='activation_reset_hold' and ref['state_read_matches_capture']
    else:ref['classification']='setpoint_timeout_hold' if cap is not None else 'missing'
    return ref

def memory_rows(memory,kind,lo,hi):
    t=memory['timestamp'].astype(np.int64);return np.flatnonzero((memory['kind']==kind)&(t>=lo)&(t<=hi))

def memory_vector(memory,i):return np.r_[vec(memory,'gru',i,16),vec(memory,'previous_action',i,4)]

def entry_check(cfg,memory,actuator,t_r,t_c,rini,exit_memory,mapping):
    tol=cfg['p3']['entry_check']['value_tolerance'];problems=[]
    rows=memory_rows(memory,KIND_ENTRY,t_r,t_c+20000)
    if not len(rows):return {'status':'MISSING','problems':['mode-entry research_memory row missing']}
    i=int(rows[-1]);before=np.r_[vec(memory,'gru_before_entry',i,16),vec(memory,'previous_action_before_entry',i,4)]
    written=memory_vector(memory,i);classic=vec(memory,'classic_action',i,4)
    out={'px4_us':int(memory['timestamp'][i]),'entry_rows_in_window':len(rows),'entry_mode':int(memory['entry_mode'][i]),'entry_result':int(memory['entry_result'][i]),
         'gru_before':before[:16],'previous_action_before':before[16:],'gru_written':written[:16],'previous_action_written':written[16:],
         'gru_norm_before':float(np.linalg.norm(before[:16])),'gru_norm_written':float(np.linalg.norm(written[:16]))}
    if out['entry_mode']!=rini:problems.append(f'entry mode {out["entry_mode"]} != RINI {rini}')
    expected=None
    if rini==0:expected=np.zeros(20)
    elif rini==1:expected=before
    elif rini==4:
        stamp=int(memory['classic_actuator_timestamp'][i]);k,recomputed=matching_command(actuator,stamp,classic,mapping,tol)
        if k is None:problems.append('classic action at entry matches no logged classic command (independent conversion)')
        else:
            out['classic_command']={'px4_us':int(actuator['timestamp'][k]),'age_at_entry_ms':(out['px4_us']-int(actuator['timestamp'][k]))/1e3,
                'recomputed_action':recomputed,'commands_with_same_timestamp':len(classic_commands(actuator,stamp))}
            if out['classic_command']['age_at_entry_ms']>cfg['p3']['entry_check']['classic_command_max_age_ms']:problems.append('classic command too old at entry')
        expected=np.r_[before[:16],classic]
    elif rini==6:
        expected=exit_memory
        if exit_memory is None:problems.append('no exit memory row before the second entry')
    if rini>=2 and out['entry_result']!=1:problems.append(f'entry treatment not applied (result {out["entry_result"]})')
    if expected is None or not np.all(np.isfinite(expected)) or np.max(np.abs(written-expected))>tol:problems.append('written memory differs from treatment')
    else:out['max_abs_written_minus_expected']=float(np.max(np.abs(written-expected)))
    steps=np.flatnonzero((memory['kind']==KIND_STEP)&(memory['active']==1)&(memory['timestamp'].astype(np.int64)>=out['px4_us']))
    if not len(steps):problems.append('no inference row after entry')
    else:
        j=int(steps[0]);used=vec(memory,'previous_action',j,4);out['first_step']={'px4_us':int(memory['timestamp'][j]),'previous_action_used':used}
        if np.max(np.abs(used-written[16:]))>tol:problems.append('first inference did not use the written previous action')
    out['problems']=problems;out['status']='VERIFIED' if not problems else 'FAILED'
    return out

def exit_check(cfg,memory,timing,t_r2,t_c2):
    """The exit memory row at the N->C: stored on the first inactive cycle, equal to the committed GRU of the last active
    inference and the last active action output."""
    e=cfg['p3']['entry_check'];problems=[];off=e['exit_row_max_offset_ms']*1000
    rows=memory_rows(memory,KIND_EXIT,t_r2,t_c2+off)
    out={'rows_in_window':len(rows),'rows_total':int(np.sum(memory['kind']==KIND_EXIT))}
    if len(rows)!=1:return {**out,'status':'FAILED','problems':[f'{len(rows)} exit rows at the N->C (expected 1)']},None
    i=int(rows[0]);mt=memory['timestamp'].astype(np.int64);x=memory_vector(memory,i)
    out.update({'px4_us':int(mt[i]),'offset_to_owner_change_ms':(int(mt[i])-t_c2)/1e3,'gru':x[:16],'previous_action':x[16:],'gru_norm':float(np.linalg.norm(x[:16]))})
    if abs(int(mt[i])-t_c2)>off:problems.append('exit row too far from the N->C owner change')
    last=np.flatnonzero((memory['kind']==KIND_STEP)&(memory['active']==1)&(mt<mt[i]))
    tt=timing['timestamp'].astype(np.int64);lc=np.flatnonzero(timing['control_step'].astype(bool)&timing['active'].astype(bool)&(tt<=mt[i]))
    if not len(last) or not len(lc):problems.append('no active inference before the exit')
    else:
        g=vec(memory,'gru',int(last[-1]),16);a=np.array([float(timing[f'action[{k}]'][lc[-1]]) for k in range(4)])
        out['max_abs_minus_last_active_gru']=float(np.max(np.abs(x[:16]-g)));out['max_abs_minus_last_active_action']=float(np.max(np.abs(x[16:]-a)))
        if out['max_abs_minus_last_active_gru']>e['value_tolerance'] or out['max_abs_minus_last_active_action']>e['value_tolerance']:problems.append('exit memory differs from the last active GRU/action')
    out['problems']=problems;out['status']='VERIFIED' if not problems else 'FAILED'
    return out,x

def teacher_check(cfg,memory,actuator,t_c2,t_c3,t_tail,rini,mapping):
    e=cfg['p3']['entry_check'];mt=memory['timestamp'].astype(np.int64);step=memory['kind']==KIND_STEP;tf=memory['teacher_forced'].astype(bool)&step
    out={'teacher_forced_rows_total':int(tf.sum()),'clipped_total':int(memory['clipped_total'][-1]),'classic_unavailable_total':int(memory['classic_unavailable_total'][-1])};problems=[]
    if rini==4 and t_c2 is not None:
        # Rows after the classic's first command: the shadow inference in the owner-change tick runs before that command.
        w=step&(memory['active']==0)&(mt>t_c2)&(mt<t_c3);first=step&(memory['active']==0)&(mt>=t_c2-50000)&(mt<=t_c2)
        out['inactive_rows_in_deactivation']=int(w.sum());out['teacher_forced_fraction']=float(tf[w].mean()) if w.sum() else None
        out['inactive_rows_up_to_owner_change']=int(first.sum());out['teacher_forced_rows_up_to_owner_change']=int((first&tf).sum())
        if not w.sum() or out['teacher_forced_fraction']<e['teacher_forced_min_fraction']:problems.append('teacher forcing not in force during the deactivation')
        # RINI=4 stays set after the second entry, so the shadow is teacher-forced again after the final N->C (not measured).
        outside=tf&~((mt>=t_c2-50000)&(mt<t_c3))&~(mt>=t_tail)
        out['teacher_forced_rows_outside_deactivation_and_tail']=int(outside.sum());out['teacher_forced_rows_after_final_n_to_c']=int((tf&(mt>=t_tail)).sum())
        if outside.any():problems.append('teacher forcing outside the deactivation')
        bad=0;ages=[]
        for i in np.flatnonzero(w&tf):
            used=vec(memory,'previous_action',i,4);classic=vec(memory,'classic_action',i,4);stamp=int(memory['classic_actuator_timestamp'][i])
            k,_=matching_command(actuator,stamp,classic,mapping,e['value_tolerance'])
            if k is None or np.max(np.abs(used-classic))>e['value_tolerance']:bad+=1
            if k is not None:ages.append((int(mt[i])-int(actuator['timestamp'][k]))/1e3)
        out['rows_checked']=int((w&tf).sum());out['rows_mismatched']=bad;out['classic_command_age_ms']={'max':max(ages),'median':float(np.median(ages))} if ages else None
        if bad:problems.append('teacher-forced previous action differs from classic applied motors')
    elif tf.any():problems.append('teacher forcing without the N2 treatment')
    out['problems']=problems;out['status']='VERIFIED' if not problems else 'FAILED'
    return out

def gru_curve(memory,t_c,start_s=-1.0,end_s=3.0,t_end=None):
    mt=memory['timestamp'].astype(np.int64);hi=t_c+end_s*1e6 if t_end is None else min(t_c+end_s*1e6,t_end)
    idx=np.flatnonzero((memory['kind']==KIND_STEP)&(memory['native_step']==1)&(mt>=t_c+start_s*1e6)&(mt<hi))
    return {'t_s':(mt[idx]-t_c)/1e6,'gru':np.stack([memory[f'gru[{k}]'][idx] for k in range(16)],1),'active':memory['active'][idx].astype(bool),
            'teacher_forced':memory['teacher_forced'][idx].astype(bool)}

def deactivation_memory(memory,t_c2,t_c3,exit_x):
    """Shadow GRU during the deactivation relative to the stored exit memory (what N3 restores) and its end state."""
    mt=memory['timestamp'].astype(np.int64);idx=np.flatnonzero((memory['kind']==KIND_STEP)&(memory['native_step']==1)&(memory['active']==0)&(mt>=t_c2)&(mt<t_c3))
    if not len(idx) or exit_x is None:return None
    g=np.stack([memory[f'gru[{k}]'][idx] for k in range(16)],1);d=np.linalg.norm(g-exit_x[:16],axis=1)
    return {'native_rows':len(idx),'distance_to_exit_gru':{'first':float(d[0]),'max':float(d.max()),'last':float(d[-1]),'mean':float(d.mean())},
            't_s':(mt[idx]-t_c2)/1e6,'distance_curve':d}

def flight_outcome(cfg,events_measured,runner_failures):
    crit=cfg['p3']['flight_failures']['criteria'];reasons=[]
    for name,ev in events_measured.items():
        wc=ev['window_constraints']
        for key in ['tilt_safety_deg','angular_rate_component_rad_s','horizontal_radius_m','altitude_m']:
            if wc[key]['max']>=wc[key]['limit']:reasons.append(f'{name}:safety_envelope:{key}')
        jr=ev['joint_recovery']
        if jr['status']!='NOT_JUDGED' and (jr['status']!='SETTLED' or jr['from_change_s']>crit['no_joint_recovery_s']):reasons.append(f'{name}:no_joint_recovery')
        if ev['motor']['longest_continuous_saturation_s']>=crit['motor_saturation_continuous_s']:reasons.append(f'{name}:motor_saturation')
        if ev['min_altitude_m']<=crit['ground_altitude_m']:reasons.append(f'{name}:ground')
    if any('safety' in r for r in runner_failures):reasons.append('runner_safety_abort')
    return {'outcome':'FAILURE' if reasons else 'SUCCESS','reasons':reasons,'runner_failures':runner_failures,'criteria':crit}

def analyze(run):
    run=Path(run).resolve();cfg=json.loads((run/'config.json').read_text());meta=json.loads((run/'metadata.json').read_text())
    events=[json.loads(s) for s in (run/'events.jsonl').read_text().splitlines()];metrics=json.loads((run/'metrics.json').read_text())
    kind=meta['experiment_type'];baseline=kind=='p3_baseline_raptor';problems=[]
    out={'run':str(run),'kind':kind,'condition':cfg.get('p3_condition'),'treatment':cfg.get('p3_treatment'),'treatment_parameters':cfg.get('p3_treatment_parameters'),
         'ulog_sha256':hashlib.sha256((run/'flight.ulg').read_bytes()).hexdigest(),'time_base':'native PX4 us (simulation time)'}
    trig={e['subject']:e for e in events if e['event']=='p3_trigger'}
    phase_end={e['label']:int(e['px4_end_us']) for e in events if e['event']=='p3_phase_ended'}
    need=['first_C_to_N']+(['baseline_recapture'] if baseline else ['N_to_C','second_C_to_N'])
    if any(n not in trig for n in need) or 'post_event' not in phase_end:
        return clean({**out,'p3_status':'INCOMPLETE','problems':['P3 trigger or post_event phase missing']})
    ulog=ULog(str(run/'flight.ulg'),TOPICS);topics={d.name:d.data for d in ulog.data_list if d.multi_id==0}
    messages=[(int(m.timestamp),m.message) for m in ulog.logged_messages]
    transitions=metrics.get('actuator_owner_transitions',[]);intervals=neural_intervals(transitions,metrics['ulog_end_us'])
    captures=raptor_captures(messages,intervals);target=controller_target(topics['trajectory_setpoint'],captures)
    owner_seq=[(x['from'],x['to']) for x in transitions]
    want_seq=[(CLASSIC,NEURAL),(NEURAL,CLASSIC)] if baseline else [(CLASSIC,NEURAL),(NEURAL,CLASSIC),(CLASSIC,NEURAL),(NEURAL,CLASSIC)]
    out['owner_sequence']=owner_seq
    if owner_seq!=want_seq:problems.append(f'actuator owner sequence {owner_seq} != {want_seq}')
    def change(t_r,pair):
        tr=next((x for x in transitions if x['px4_us']>=t_r and (x['from'],x['to'])==pair),None)
        return (int(tr['px4_us']),tr) if tr else (None,None)
    t_r1=int(trig['first_C_to_N']['end_bound_px4_us']);t_c1,_=change(t_r1,(CLASSIC,NEURAL));t_end=phase_end['post_event']
    ev={}
    if baseline:
        t_rb=int(trig['baseline_recapture']['end_bound_px4_us']);cap=next((c for c in captures if c[0]>=t_rb),None)
        t_cb=int(cap[0]) if cap else None
        if t_c1 is None or t_cb is None:return clean({**out,'p3_status':'INCOMPLETE','problems':problems+['change missing']})
        ev['first_C_to_N']=measure(cfg,topics,target,t_r1,t_c1,t_rb);ev['first_C_to_N']['reference_at_takeover']=capture_check(topics,captures,t_c1,True)
        ev['baseline_recapture']=measure(cfg,topics,target,t_rb,t_cb,t_end);ev['baseline_recapture']['reference_at_takeover']=capture_check(topics,captures,t_cb,False)
        st=topics['trajectory_setpoint']['timestamp'].astype(np.int64);last=st[st<t_cb]
        ev['baseline_recapture']['reference_at_takeover']['last_external_setpoint_to_capture_ms']=(t_cb-int(last[-1]))/1e3 if len(last) else None
        t_c2=t_c3=None;t_r2=t_r3=None
    else:
        t_r2=int(trig['N_to_C']['end_bound_px4_us']);t_c2,_=change(t_r2,(NEURAL,CLASSIC))
        t_r3=int(trig['second_C_to_N']['end_bound_px4_us']);t_c3,_=change(t_r3,(CLASSIC,NEURAL))
        if None in (t_c1,t_c2,t_c3):return clean({**out,'p3_status':'INCOMPLETE','problems':problems+['owner change missing']})
        short=cfg['p3_condition_spec']['deactivation_s']<cfg['joint_recovery']['dwell_s']
        ev['first_C_to_N']=measure(cfg,topics,target,t_r1,t_c1,t_r2)
        ev['N_to_C']=measure(cfg,topics,target,t_r2,t_c2,t_c3,judge_recovery=not short)
        ev['second_C_to_N']=measure(cfg,topics,target,t_r3,t_c3,t_end)
        for name,t_c in [('first_C_to_N',t_c1),('second_C_to_N',t_c3)]:ev[name]['reference_at_takeover']=capture_check(topics,captures,t_c,True)
        # N->C motor deviation against the run's own classic stationary command before the first C->N.
        m=topics['actuator_motors'];mt=m['timestamp'].astype(np.int64);mv=np.stack([m[f'control[{i}]'] for i in range(4)],1).astype(float)
        ref=mv[(mt>=t_r1-500000)&(mt<t_r1)].mean(0);hi=min(t_c2+500000,t_r3);g=np.arange(t_c2,hi,1000);k=np.searchsorted(mt,g,side='right')-1
        ev['N_to_C']['motor_rms_vs_classic_hold_0_0p5s']=float(np.sqrt(np.mean((mv[k]-ref)**2)));ev['N_to_C']['motor_rms_window_s']=(hi-t_c2)/1e6
        cr=[e for e in events if e['event']=='command_requested' and e['command']==100001]
        def request_after(subject):
            t=trig[subject]['monotonic_ns'];return next((e['monotonic_ns'] for e in cr if e['monotonic_ns']>=t),None)
        a,b=request_after('N_to_C'),request_after('second_C_to_N')
        lt=topics['vehicle_local_position'];li=asof(lt['timestamp'].astype(np.int64),t_r3);l2=asof(lt['timestamp'].astype(np.int64),t_c2)
        out['deactivation']={'requested_s':cfg['p3_condition_spec']['deactivation_s'],'request_interval_s':(b-a)/1e9 if a and b else None,
            'actual_owner_s':(t_c3-t_c2)/1e6,'n_to_c_request_to_owner_ms':ev['N_to_C']['trigger_to_change_ms'],
            'displacement_ned_m':[float(lt[k][li]-lt[k][l2]) for k in 'xyz'],
            'yaw_change_deg':float((ev['second_C_to_N']['state_at_change']['yaw_deg']-ev['N_to_C']['state_at_change']['yaw_deg']+180)%360-180)}
        if abs(out['deactivation']['actual_owner_s']-out['deactivation']['requested_s'])>0.1:problems.append('actual deactivation differs from the request by more than 0.1 s')
        if not t_c2<t_r3:problems.append('classic did not own the actuators before the second C->N trigger')
    out['events']=ev
    for name,e in ev.items():
        r=e.get('reference_at_takeover',{})
        if name in ['first_C_to_N','second_C_to_N'] and not r.get('zero_velocity_capture'):problems.append(f'{name}: RAPTOR activation capture with zero velocity not confirmed')
        if name=='baseline_recapture' and r.get('classification')!='setpoint_timeout_hold':problems.append('baseline re-capture missing')
    # Parameters over time.
    rini=int(cfg['p3_treatment_parameters']['rini']);changes=[(int(t),n,v) for t,n,v in ulog.changed_parameters if n in ('MC_RAPTOR_RINI','MC_RAPTOR_NCO','MC_RAPTOR_RSH')]
    out['parameters']={'at_first_trigger':params_at(ulog,t_r1),'changes_after_first_trigger':[c for c in changes if c[0]>=t_r1]}
    if out['parameters']['at_first_trigger']!={'MC_RAPTOR_RINI':0,'MC_RAPTOR_NCO':0,'MC_RAPTOR_RSH':1}:problems.append('first C->N not under RINI=0/NCO=0/RSH=1')
    if not baseline:
        for name,t in [('at_n_to_c_change',t_c2),('at_second_trigger',t_r3),('at_second_change',t_c3)]:out['parameters'][name]=params_at(ulog,t)
        want={'MC_RAPTOR_RINI':rini,'MC_RAPTOR_NCO':0,'MC_RAPTOR_RSH':1}
        if any(out['parameters'][n]!=want for n in ['at_n_to_c_change','at_second_trigger','at_second_change']):problems.append(f'treatment parameters not {want} over the deactivation and second entry')
        late=[c for c in changes if t_c1<=c[0] and not c[0]<t_r2]
        if late:problems.append(f'parameter changes after the N->C trigger: {late}')
    elif any(c[2]!=0 and c[1]=='MC_RAPTOR_RINI' for c in changes):problems.append('baseline RINI changed from 0')
    # Memory evidence.
    memory=topics.get('research_memory');mapping=header_map()
    if memory is None:problems.append('research_memory missing')
    else:
        out['first_entry']=entry_check(cfg,memory,topics['research_actuator'],t_r1,t_c1,0,None,mapping);problems+=['first entry: '+p for p in out['first_entry']['problems']]
        exit_x=None
        if not baseline:
            out['exit'],exit_x=exit_check(cfg,memory,topics['research_timing'],t_r2,t_c2);problems+=['exit: '+p for p in out['exit']['problems']]
            out['second_entry']=entry_check(cfg,memory,topics['research_actuator'],t_r3,t_c3,rini,exit_x,mapping);problems+=['second entry: '+p for p in out['second_entry']['problems']]
            out['deactivation_memory']=deactivation_memory(memory,t_c2,t_c3,exit_x)
        t_tail=transitions[-1]['px4_us'] if transitions else None
        out['teacher_forcing']=teacher_check(cfg,memory,topics['research_actuator'],t_c2,t_c3,t_tail,0 if baseline else rini,mapping);problems+=out['teacher_forcing']['problems']
        out['gru_curves']={'first_C_to_N':gru_curve(memory,t_c1)}
        if baseline:out['gru_curves']['baseline_recapture']=gru_curve(memory,t_cb)
        else:
            out['gru_curves']['second_C_to_N']=gru_curve(memory,t_c3)
            out['gru_curves']['deactivation']=gru_curve(memory,t_c2,-0.5,(t_c3-t_c2)/1e6+0.5)
    # Recovery stages: only the pre-registered short deactivation may be exempt.
    stages=metrics.get('recovery_stages',[]);exempt=[i for i,s in enumerate(stages) if s.get('planned_short_stage')]
    expect_exempt=[] if baseline or cfg['p3_condition_spec']['deactivation_s']>=cfg['joint_recovery']['dwell_s'] else [2]
    out['recovery_stages']=[{'origin':s['origin'],'start_us':s['start_us'],'end_us':s['end_us'],'status':s['joint_recovery']['status'],'planned_short_stage':bool(s.get('planned_short_stage'))} for s in stages]
    if exempt!=expect_exempt:problems.append(f'short-stage exemption {exempt} != pre-registered {expect_exempt}')
    if any(s['joint_recovery']['status']!='SETTLED' for i,s in enumerate(stages) if i not in expect_exempt):problems.append('recovery stage not SETTLED')
    runner_failures=[e['reason'] for e in events if e['event']=='failure']
    out['flight_outcome']=flight_outcome(cfg,ev,runner_failures)
    out['problems']=problems;out['p3_status']='MEASURED' if not problems else 'INCOMPLETE'
    return clean(out)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);a=p.parse_args()
    result=analyze(a.run);(a.run/'p3-metrics.json').write_text(json.dumps(result,indent=1,ensure_ascii=False,allow_nan=False)+'\n')
    print(result['p3_status'],result.get('problems'),result.get('flight_outcome',{}).get('outcome'));raise SystemExit(0 if result['p3_status']=='MEASURED' else 1)

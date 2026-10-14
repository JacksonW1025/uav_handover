#!/usr/bin/env python3
"""P2 per-run measurement: the P1 subject-event measurement plus treatment evidence; writes only p2-metrics.json.

Adds to p1_metrics.analyze: the treatment parameters in force at the trigger (ULog parameters), verification of the
RAPTOR mode-entry write from research_memory (values expected for each treatment, recomputed independently from
research_actuator with the fitted action map), teacher forcing while inactive, the C2 integrator coordination log,
GRU curves, and the pre-registered exploration failure criteria. Exploration runs are measured even when aborted.
"""
import argparse,json,math
from pathlib import Path
import numpy as np
from pyulog import ULog
import p1_metrics
from p1_metrics import clean
from p2_action_map import motor_to_action,header_map

MEMORY_TOPICS=['research_memory','research_actuator','research_timing','actuator_motors','vehicle_local_position','vehicle_status']
KIND_STEP,KIND_ENTRY=1,2

def params_at(ulog,t):
    values=dict(ulog.initial_parameters)
    for stamp,name,value in sorted(ulog.changed_parameters,key=lambda x:x[0]):
        if stamp<=t:values[name]=value
    return {k:values.get(k) for k in ['MC_RAPTOR_RINI','MC_RAPTOR_NCO','MC_RAPTOR_RSH']}

def vec(topic,name,i,n):return np.array([float(topic[f'{name}[{k}]'][i]) for k in range(n)])

def longest_run(t,mask,end):
    """Longest continuous duration [s] of consecutive rows satisfying mask (zero-order hold to the next row)."""
    t=np.asarray(t,np.int64);nxt=np.r_[t[1:],end];best=cur=0
    for i in range(len(t)):
        if mask[i]:cur+=nxt[i]-t[i];best=max(best,cur)
        else:cur=0
    return best/1e6

def classic_command(actuator,stamp):
    """research_actuator row of the classic command with actuator_motors.timestamp == stamp."""
    rows=np.flatnonzero((actuator['owner']==2)&(actuator['actuator_timestamp'].astype(np.int64)==int(stamp)))
    return int(rows[-1]) if len(rows) else None

def entry_check(cfg,m,memory,actuator,t_r,t_c,treatment,mapping):
    tol=cfg['p2']['entry_check']['value_tolerance'];problems=[]
    rows=np.flatnonzero((memory['kind']==KIND_ENTRY)&(memory['timestamp'].astype(np.int64)>=t_r)&(memory['timestamp'].astype(np.int64)<=t_c+20000))
    if not len(rows):return {'status':'MISSING','problems':['mode-entry research_memory row missing']}
    i=int(rows[-1]);before=np.r_[vec(memory,'gru_before_entry',i,16),vec(memory,'previous_action_before_entry',i,4)]
    written=np.r_[vec(memory,'gru',i,16),vec(memory,'previous_action',i,4)];classic=vec(memory,'classic_action',i,4)
    rini=int(cfg['p2_treatment_parameters'].get('rini',0))
    out={'px4_us':int(memory['timestamp'][i]),'entry_mode':int(memory['entry_mode'][i]),'entry_result':int(memory['entry_result'][i]),
         'gru_before':before[:16],'previous_action_before':before[16:],'gru_written':written[:16],'previous_action_written':written[16:],
         'classic_action':classic,'gru_norm_before':float(np.linalg.norm(before[:16])),'gru_norm_written':float(np.linalg.norm(written[:16]))}
    if out['entry_mode']!=rini:problems.append(f'entry mode {out["entry_mode"]} != treatment RINI {rini}')
    expected=None
    if rini in (2,4):
        k=classic_command(actuator,int(memory['classic_actuator_timestamp'][i]))
        if k is None:problems.append('classic command used at entry not found in research_actuator')
        else:
            recomputed,clipped=motor_to_action(vec(actuator,'control',k,4),mapping)
            out['classic_command']={'px4_us':int(actuator['timestamp'][k]),'age_at_entry_ms':(out['px4_us']-int(actuator['timestamp'][k]))/1e3,
                                    'motors':vec(actuator,'control',k,4),'recomputed_action':recomputed,'clipped_components':clipped}
            if recomputed is None or np.max(np.abs(recomputed-classic))>tol:problems.append('classic action differs from independent conversion')
            if out['classic_command']['age_at_entry_ms']>cfg['p2']['entry_check']['classic_command_max_age_ms']:problems.append('classic command too old at entry')
    if rini==0:expected=np.zeros(20)
    elif rini==1:expected=before
    elif rini==2:expected=np.r_[np.zeros(16),classic]
    elif rini==3:expected=np.r_[before[:16],np.zeros(4)]
    elif rini==4:expected=np.r_[before[:16],classic]
    elif rini==5:expected=np.asarray(cfg['p2']['nstar_memory']['values'],float)
    if rini>=2 and out['entry_result']!=1:problems.append(f'entry treatment not applied (result {out["entry_result"]})')
    if expected is None or not np.all(np.isfinite(expected)) or np.max(np.abs(written-expected))>tol:problems.append('written memory differs from treatment')
    else:out['max_abs_written_minus_expected']=float(np.max(np.abs(written-expected)))
    # The first inference after entry uses the written previous action.
    steps=np.flatnonzero((memory['kind']==KIND_STEP)&(memory['active']==1)&(memory['timestamp'].astype(np.int64)>=out['px4_us']))
    if not len(steps):problems.append('no inference row after entry')
    else:
        j=int(steps[0]);used=vec(memory,'previous_action',j,4);out['first_step']={'px4_us':int(memory['timestamp'][j]),'previous_action_used':used}
        if np.max(np.abs(used-written[16:]))>tol:problems.append('first inference did not use the written previous action')
    out['problems']=problems;out['status']='VERIFIED' if not problems else 'FAILED'
    return out

def teacher_check(cfg,memory,actuator,t_c,treatment,mapping):
    e=cfg['p2']['entry_check'];rini=int(cfg['p2_treatment_parameters'].get('rini',0))
    step=memory['kind']==KIND_STEP;tf=memory['teacher_forced'].astype(bool)&step;mt=memory['timestamp'].astype(np.int64)
    out={'teacher_forced_rows_total':int(tf.sum()),'clipped_total':int(memory['clipped_total'][-1]),'classic_unavailable_total':int(memory['classic_unavailable_total'][-1])}
    problems=[]
    if rini in (3,4):
        w=step&(memory['active']==0)&(mt>=t_c-e['teacher_forcing_check_window_s']*1e6)&(mt<t_c)
        out['inactive_rows_before_change']=int(w.sum());out['teacher_forced_fraction']=float(tf[w].mean()) if w.sum() else None
        if not w.sum() or out['teacher_forced_fraction']<e['teacher_forced_min_fraction']:problems.append('teacher forcing not in force before the change')
        rows=np.flatnonzero(w&tf);bad=0;ages=[]
        for i in rows:
            used=vec(memory,'previous_action',i,4);classic=vec(memory,'classic_action',i,4)
            k=classic_command(actuator,int(memory['classic_actuator_timestamp'][i]))
            recomputed=motor_to_action(vec(actuator,'control',k,4),mapping)[0] if k is not None else None
            if recomputed is None or np.max(np.abs(used-classic))>e['value_tolerance'] or np.max(np.abs(recomputed-classic))>e['value_tolerance']:bad+=1
            if k is not None:ages.append((int(memory['timestamp'][i])-int(actuator['timestamp'][k]))/1e3)
        out['rows_checked']=len(rows);out['rows_mismatched']=bad;out['classic_command_age_ms']={'max':max(ages),'median':float(np.median(ages))} if ages else None
        if bad:problems.append('teacher-forced previous action differs from classic applied motors')
    elif tf.any():problems.append('teacher forcing active without a teacher-forcing treatment')
    out['problems']=problems;out['status']='VERIFIED' if not problems else 'FAILED'
    return out

def coordination_check(cfg,messages,t_c):
    nco=int(cfg['p2_treatment_parameters'].get('nco',0))
    hits=[(t,m) for t,m in messages if ('Research velocity integrator coordinat' in m or 'Research vel_int' in m) and t>=t_c-20000]
    out={'nco':nco,'messages':[{'px4_us':t,'text':m} for t,m in hits[:3]]}
    coordinated=[x for x in hits if 'coordinated:' in x[1] and x[0]<=t_c+200000]
    if nco==1:
        values={k:[float(v) for v in m.split(k)[1].split()[:3]] for _,m in hits[:3] for k in ['vel_int before','vel_int after'] if k in m}
        out['status']='VERIFIED' if coordinated and len(values)==2 and not any('unavailable' in m for _,m in hits[:1]) else 'FAILED'
        if coordinated:
            out['thrust']=float(coordinated[0][1].split('thrust ')[1].split()[0])
            out['vel_int_before'],out['vel_int_after']=values.get('vel_int before'),values.get('vel_int after')
    else:out['status']='VERIFIED' if not hits else 'FAILED'
    return out

def gru_curves(memory,timing,t_c,start_s=-1.0,end_s=3.0):
    mt=memory['timestamp'].astype(np.int64);w=(memory['kind']==KIND_STEP)&(memory['native_step']==1)&(mt>=t_c+start_s*1e6)&(mt<t_c+end_s*1e6)
    idx=np.flatnonzero(w)
    return {'t_s':(mt[idx]-t_c)/1e6,'gru':np.stack([memory[f'gru[{k}]'][idx] for k in range(16)],1),
            'previous_action':np.stack([memory[f'previous_action[{k}]'][idx] for k in range(4)],1),'active':memory['active'][idx].astype(bool)}

def flight_outcome(cfg,base,motors,local,t_r,t_e,t_c,events):
    crit=cfg['p2']['exploration']['failure_criteria'];pr=base.get('primary',{});reasons=[]
    wc=pr.get('window_constraints',{})
    for key in ['tilt_safety_deg','angular_rate_component_rad_s','horizontal_radius_m','altitude_m']:
        if key in wc and wc[key]['max']>=wc[key]['limit']:reasons.append('safety_envelope:'+key)
    failures=[e['reason'] for e in events if e['event']=='failure']
    if any('safety' in r for r in failures):reasons.append('runner_safety_abort')
    jr=pr.get('joint_recovery',{})
    if jr.get('status')!='SETTLED' or jr.get('from_change_s') is None or jr['from_change_s']>crit['no_joint_recovery_s']:reasons.append('no_joint_recovery')
    mt=motors['timestamp'].astype(np.int64);mv=np.stack([motors[f'control[{i}]'] for i in range(4)],1).astype(float);w=(mt>=t_r)&(mt<t_e)
    sat=cfg['p2']['motor_saturation'];mask=np.any(mv>=sat['upper'],1)|np.any(mv<=sat['lower'],1)
    longest=longest_run(mt[w],mask[w],t_e)
    if longest>=crit['motor_saturation_continuous_s']:reasons.append('motor_saturation')
    lt=local['timestamp'].astype(np.int64);lw=(lt>=t_r)&(lt<t_e);min_alt=float(np.min(-local['z'][lw])) if lw.any() else None
    if min_alt is None or min_alt<=crit['ground_altitude_m']:reasons.append('ground')
    return {'outcome':'FAILURE' if reasons else 'SUCCESS','reasons':reasons,'longest_continuous_saturation_s':longest,
            'min_altitude_m':min_alt,'runner_failures':failures,'criteria':crit}

def analyze(run):
    run=Path(run).resolve();cfg=json.loads((run/'config.json').read_text());meta=json.loads((run/'metadata.json').read_text())
    exploration=str(cfg.get('p1_condition','')).startswith('X')
    base=p1_metrics.analyze(run,allow_abort=exploration)
    out={**base,'treatment':cfg.get('p2_treatment'),'treatment_parameters':cfg.get('p2_treatment_parameters'),'exploration':exploration}
    problems=list(base.get('problems',[]))
    if 'trigger_px4_us' not in base or 'change_px4_us' not in base:
        out['p2_status']='INCOMPLETE';out['problems']=problems or ['subject event not measured'];return clean(out)
    events=[json.loads(s) for s in (run/'events.jsonl').read_text().splitlines()]
    ulog=ULog(str(run/'flight.ulg'),MEMORY_TOPICS);topics={d.name:d.data for d in ulog.data_list if d.multi_id==0}
    messages=[(int(m.timestamp),m.message) for m in ulog.logged_messages]
    t_r,t_c,t_e=base['trigger_px4_us'],base['change_px4_us'],base['window_end_px4_us']
    out['parameters_at_trigger']=params_at(ulog,t_r);tp=cfg['p2_treatment_parameters']
    want={'MC_RAPTOR_RINI':int(tp.get('rini',0)),'MC_RAPTOR_NCO':int(tp.get('nco',0)),'MC_RAPTOR_RSH':1}
    if out['parameters_at_trigger']!=want:problems.append(f'treatment parameters at trigger {out["parameters_at_trigger"]} != {want}')
    mapping=header_map();memory=topics.get('research_memory')
    if memory is None:problems.append('research_memory missing')
    else:
        kind=meta['experiment_type']
        if kind=='p2_c_to_n':
            out['entry']=entry_check(cfg,base,memory,topics['research_actuator'],t_r,t_c,cfg['p2_treatment'],mapping)
            problems+=out['entry']['problems']
        out['teacher_forcing']=teacher_check(cfg,memory,topics['research_actuator'],t_c,cfg['p2_treatment'],mapping)
        problems+=out['teacher_forcing']['problems']
        out['gru_curves']=gru_curves(memory,topics.get('research_timing'),t_c)
    if meta['experiment_type'] in ['p2_n_to_c']:
        out['coordination']=coordination_check(cfg,messages,t_c)
        if out['coordination']['status']!='VERIFIED':problems.append('velocity integrator coordination evidence does not match treatment')
    out['flight_outcome']=flight_outcome(cfg,base,topics['actuator_motors'],topics['vehicle_local_position'],t_r,t_e,t_c,events)
    out['problems']=problems
    # Exploration: a subject event that was measured but failed the flight criteria is a result, not a measurement fault.
    out['p2_status']='MEASURED' if not problems and (base['status']=='MEASURED' or exploration) else 'INCOMPLETE'
    return clean(out)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);a=p.parse_args()
    result=analyze(a.run);(a.run/'p2-metrics.json').write_text(json.dumps(result,indent=1,ensure_ascii=False,allow_nan=False)+'\n')
    print(result['p2_status'],result.get('problems'),result.get('flight_outcome',{}).get('outcome'));raise SystemExit(0 if result['p2_status']=='MEASURED' else 1)

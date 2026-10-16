"""P0 analysis. Never infer neural ownership from controller activity alone."""
import re
import numpy as np
from collections import Counter
from recovery import recovery,_recovery

NUM=r'([-+]?(?:\d+\.?\d*(?:[eE][-+]?\d+)?|nan|inf))'
CAPTURE=re.compile(r'trajectory_setpoint (?:turned stale|reset due to activation) at: '+NUM+' '+NUM+' '+NUM)

def raptor_captures(messages,intervals):
    """RAPTOR prints every internal-target capture (mode-entry reset or 200 ms setpoint timeout) with the exact
    position it stores. Only captures inside neural ownership intervals define the controller target; a capture
    logged in the same Run just before the owner change is placed at the owner change."""
    out=[]
    for stamp,text in messages:
        m=CAPTURE.search(text)
        if not m:continue
        for start,end in intervals:
            if start-20000<=stamp<end:out.append((max(int(stamp),int(start)),[float(m.group(i)) for i in (1,2,3)]));break
    return out

def raptor_target_profile(target,intervals):
    """P4-01c T1: after the activation capture RAPTOR's speed-matched target moves (research_target profile rows, one
    per cycle with mode 1). Inside neural ownership intervals these rows define the controller target, placed like
    captures (a row logged just before the owner change is placed at the owner change). No rows for T0 or older runs."""
    if target is None or 'kind' not in target:return []
    out=[]
    for i in np.flatnonzero((np.asarray(target['kind'])==2)&(np.asarray(target['mode'])==1)):
        stamp=int(target['timestamp'][i])
        for start,end in intervals:
            if start-20000<=stamp<end:out.append((max(stamp,int(start)),[float(target[f'position[{k}]'][i]) for k in range(3)]));break
    return out

def controller_target(setpoint,captures):
    """trajectory_setpoint samples merged with RAPTOR captures, ordered in time (capture after a same-time sample)."""
    rows=[(int(t),0,[setpoint[f'position[{k}]'][i] for k in range(3)]) for i,t in enumerate(setpoint['timestamp'])]
    rows+=[(t,1,p) for t,p in captures]
    rows.sort(key=lambda r:(r[0],r[1]))
    return {'timestamp':np.array([r[0] for r in rows],dtype=np.int64),
            **{f'position[{k}]':np.array([r[2][k] for r in rows],dtype=np.float64) for k in range(3)}}

def neural_intervals(transitions,end_us):
    out=[];start=None
    for tr in transitions:
        if tr['to']==1 and start is None:start=tr['px4_us']
        elif tr['from']==1 and start is not None:out.append((start,tr['px4_us']));start=None
    if start is not None:out.append((start,end_us))
    return out

def sampling(topic):
    t=np.asarray(topic.get('timestamp_sample',topic['timestamp']),dtype=np.int64)
    d=np.diff(t)
    return {'clock':'timestamp_sample' if 'timestamp_sample' in topic else 'timestamp',
            'samples':len(t),'median_us':float(np.median(d)) if len(d) else None,
            'p99_us':float(np.percentile(d,99)) if len(d) else None,'max_us':int(max(d)) if len(d) else None,
            'nonpositive_intervals':int(sum(d<=0)),'intervals_over_20ms':int(sum(d>20000))}

def dispatch_metrics(timing,mask,stats):
    called=mask & timing['executor_called'].astype(bool)
    now=timing['timestamp'].astype(np.int64);sample=timing['timestamp_sample'].astype(np.int64)
    neighbors=called[1:] & called[:-1] & (np.diff(timing['accepted_total'].astype(np.int64))==1)
    dt=np.diff(now)[neighbors];ds=np.diff(sample)[neighbors]
    return {'processing_period_us_logged_adjacent_calls':stats(dt),
        'same_processing_tick_distinct_acquisitions_logged':int(sum((dt==0)&(ds>0))),
        'nonincreasing_acquisition_time_logged_adjacent_calls':int(sum(ds<=0)),
        'processing_clock_regressions_logged':int(sum(dt<0)),
        'acquisition_to_processing_age_us_logged':stats(now[called]-sample[called]),
        'note':'Only adjacent accepted calls in the same scope; missing log pairs and phase gaps excluded. Queue catch-up can process distinct acquisitions at one HRT tick.'}

def executor_acceptance(scopes,source_missed,nonincreasing_commits):
    reasons=[]
    for name,s in scopes.items():
        if not s['calls_total']:reasons.append(name+': no calls observed')
        if s['hard_faults_total'] or s['input_rejections_total']:reasons.append(name+': hard fault or rejected input')
        if s['unclassified_warning_total'] is None or s['unclassified_warning_total']>0:reasons.append(name+': unclassified warning')
        if s['calls_total'] and not s['p99_budget_proven']:reasons.append(name+': p99 budget not proven')
    for name in ['active','neural_actuator_authority']:
        if scopes[name]['executor_warnings_total']:reasons.append(name+': executor warning')
    if source_missed:reasons.append('missed source publication')
    if nonincreasing_commits:reasons.append('nonincreasing GRU commit sample time')
    status='FAIL' if reasons else ('PASS_WITH_WARNINGS' if scopes['whole_run']['executor_warnings_total'] else 'PASS')
    return status,reasons

def add_p0(metrics,topics,cfg,events,windows,px4_time,variant,stats,messages=None):
    metrics['observation_sampling']={n:sampling(topics[topic]) for n,topic in
        [('position','vehicle_local_position'),('velocity','vehicle_local_position'),('angular_velocity','vehicle_angular_velocity')]}
    if 'joint_recovery' not in cfg:return
    local=dict(topics['vehicle_local_position']);angular=dict(topics.get('research_angular_velocity',topics['vehicle_angular_velocity']))
    metrics['joint_angular_observation_topic']='research_angular_velocity' if 'research_angular_velocity' in topics else 'vehicle_angular_velocity'
    if 'research_angular_velocity' in topics:metrics['observation_sampling']['neural_queued_angular_velocity']=sampling(topics['research_angular_velocity'])
    local['timestamp']=local.get('timestamp_sample',local['timestamp'])
    angular['timestamp']=angular.get('timestamp_sample',angular['timestamp'])
    # Keep acquisition order; duplicate/non-monotonic observation times invalidate
    # continuity instead of interpolation or sorting them into an invented history.
    boundary_events=[e for e in events if e['event'] in ['handover_requested','landing_requested']]
    metrics['request_boundary_status']='PASS' if boundary_events and all('end_bound_px4_us' in e for e in boundary_events) else 'FAIL'
    requests=[(e.get('end_bound_px4_us',px4_time(e['monotonic_ns'])-100000),
               e['event']+(' (native pre-request bound)' if 'end_bound_px4_us' in e else ' (estimated 100ms margin; not strict P0 evidence)')) for e in boundary_events]
    transitions=metrics.get('actuator_owner_transitions',[])
    setpoint=topics.get('trajectory_setpoint')
    controller=cfg['joint_recovery'].get('position_reference')=='active_controller_target'
    if controller:
        intervals=neural_intervals(transitions,metrics['ulog_end_us'])
        captures=raptor_captures(messages or [],intervals)
        metrics['controller_target']={'neural_intervals_us':[list(map(int,i)) for i in intervals],
            'raptor_captures':[{'px4_us':t,'position_ned_m':p} for t,p in captures],
            'source':'classic: trajectory_setpoint; RAPTOR ownership: logged internal-target captures'}
        profile=raptor_target_profile(topics.get('research_target'),intervals)
        if profile:metrics['controller_target']['raptor_target_profile_rows']=len(profile)
        setpoint=controller_target(setpoint,captures+profile)
    stages=[]
    if windows:
        stages.append({'start_us':windows[0][1],'owner':2,'origin':'initial_classic_hover'})
    stages += [{'start_us':x['px4_us'],'owner':x['to'],'origin':'actual_actuator_owner_change'} for x in transitions]
    metrics['recovery_stages']=[]
    for i,stage in enumerate(stages):
        start=stage['start_us'];end=metrics['ulog_end_us'];reason='ulog_end'
        if i+1<len(stages):end=stages[i+1]['start_us'];reason='next_actual_owner_change'
        # Request order follows ownership transitions. Exclude the initiating request
        # by ordinal, preserving even an equal-timestamp or very short next stage.
        for request,event in requests[i:]:
            if request<end:end=request;reason=event
            break
        result=recovery(local,angular,cfg['joint_recovery'],int(start),int(end),setpoint)
        if controller:
            rule=_recovery(local,angular,cfg['joint_recovery'],int(start),int(end),topics.get('trajectory_setpoint'))
            result['trajectory_setpoint_only_comparison']={'joint_recovery':rule['joint_recovery'],'position_band_entry':rule['position_band_entry'],
                'note':'Comparison only; trajectory_setpoint is not RAPTOR\'s target while RAPTOR owns the actuators.'}
        result.update(stage);result['end_reason']=reason
        result['observation_sampling']={}
        for name,topic in [('position',local),('velocity',local),('angular_velocity',angular)]:
            mask=(topic['timestamp']>=start)&(topic['timestamp']<end)
            result['observation_sampling'][name]=sampling({k:v[mask] for k,v in topic.items()})
        metrics['recovery_stages'].append(result)
    metrics['joint_recovery_status_counts']=dict(Counter(x['joint_recovery']['status'] for x in metrics['recovery_stages']))
    for state in ['SETTLED','NOT_SETTLED','INSUFFICIENT_OBSERVATION']:metrics['joint_recovery_status_counts'].setdefault(state,0)
    # P3 config pre-registers that a stage shorter than the dwell cannot settle by definition (thresholds unchanged).
    if (cfg.get('short_stage_rule') or {}).get('exempt_below_dwell'):
        for x in metrics['recovery_stages']:
            if x['joint_recovery']['status']=='INSUFFICIENT_OBSERVATION' and x['end_us']-x['start_us']<cfg['joint_recovery']['dwell_s']*1e6:x['planned_short_stage']=True
    metrics['recovery_status']='PASS' if stages and all(x['joint_recovery']['status']=='SETTLED' or x.get('planned_short_stage') for x in metrics['recovery_stages']) else 'FAIL'
    if variant!='raptor':return
    timing=topics.get('research_timing',{})
    if 'scope_calls[0]' not in timing:
        metrics['executor_acceptance']='FAIL';metrics['executor_missing_instrumentation']=True;return
    called=timing['executor_called'].astype(bool);active=timing['active'].astype(bool)
    owned=timing['actuator_published'].astype(bool)
    metrics['executor_scopes']={}
    for i,(name,mask) in enumerate([('whole_run',np.ones(len(called),bool)),('active',active),('neural_actuator_authority',owned)]):
        m=mask & called
        calls=int(timing[f'scope_calls[{i}]'][-1]);warn=int(timing[f'scope_warnings[{i}]'][-1])
        metrics['executor_scopes'][name]={
            'definition':['all executor calls including inactive shadow inference','controller active','this inference actually published actuator_motors under arbitration'][i],
            'calls_total':calls,'logged_calls':int(sum(m)),
            'executor_warnings_total':warn,
            'jitter_warnings_total':int(timing[f'scope_jitter[{i}]'][-1]),
            'bias_warnings_total':int(timing[f'scope_bias[{i}]'][-1]),
            'input_rejections_total':int(timing[f'scope_rejected[{i}]'][-1]),
            'hard_faults_total':int(timing[f'scope_hard[{i}]'][-1]),
            'unclassified_warning_total':int(timing[f'scope_unclassified_warning[{i}]'][-1]) if f'scope_unclassified_warning[{i}]' in timing else None,
            'duration_us_logged_distribution':stats(timing['inference_duration_us'][m]),
            'duration_us_runtime_mean':float(timing[f'scope_duration_sum_us[{i}]'][-1]/calls) if calls else None,
            'duration_us_runtime_max':int(timing[f'scope_duration_max_us[{i}]'][-1]),
            'duration_over_2500us_total':int(timing[f'scope_over_2500us[{i}]'][-1]) if f'scope_over_2500us[{i}]' in timing else None,
            'p99_budget_proven':bool(calls and cfg['inference_p99_us']==2500 and f'scope_over_2500us[{i}]' in timing and int(timing[f'scope_over_2500us[{i}]'][-1])*100<calls),
            'input_interval_us_logged':stats(timing['input_dt_us'][m & (timing['input_dt_us']>0)]),
            'executor_interval_us_logged':stats(timing['executor_dt_us'][m & (timing['executor_dt_us']>0)]),
            'native_interval_us_logged':stats(timing['native_dt_us'][m & timing['native_step'].astype(bool) & (timing['native_dt_us']>0)])}
    for name,mask in [('whole_run',np.ones(len(called),bool)),('active',active),('neural_actuator_authority',owned)]:
        metrics['executor_scopes'][name].update(dispatch_metrics(timing,mask,stats))
    scopes=metrics['executor_scopes'];whole=scopes['whole_run']
    metrics['executor_warning_count']=whole['executor_warnings_total']
    commits=timing['gru_committed'].astype(bool);ct=timing['timestamp_sample'][commits].astype(np.int64)
    metrics['state_advancement']={'accepted_total':int(timing['accepted_total'][-1]),
        'duplicate_rejected_total':int(timing['duplicate_total'][-1]),'regressed_rejected_total':int(timing['regressed_total'][-1]),
        'source_generations_missed_total':int(timing['source_missed_total'][-1]),
        'native_total':int(timing['native_total'][-1]),'gru_committed_total':int(timing['gru_commit_total'][-1]),
        'logged_commits_nonincreasing_sample_time':int(sum(np.diff(ct)<=0)),
        'log_omitted_accepted_rows_between_first_and_last':int(timing['accepted_total'][-1]-timing['accepted_total'][0]+1-sum(called)),
        'note':'Cumulative warning counts, duration mean/max and >2500us counts include omitted ULog rows. Percentiles/interval distributions use logged rows only. Fewer than 1% of all calls above2500us proves the p99 budget without assuming missing rows.'}
    metrics['executor_acceptance'],metrics['executor_failure_reasons']=executor_acceptance(scopes,
        metrics['state_advancement']['source_generations_missed_total'],int(sum(np.diff(ct)<=0)))
    metrics['inference_timing_status']='PASS' if all(s['p99_budget_proven'] for s in scopes.values()) and not any(s['hard_faults_total'] for s in scopes.values()) else 'FAIL'
    metrics['executor_acceptance_rules']={'FAIL':'hard fault, rejected input, missed source publication, nonincreasing GRU commit sample time, active/actual-neural warning, or p99 budget not proven by runtime threshold-exceedance counts',
        'PASS_WITH_WARNINGS':'all checks pass; only explained inactive shadow timing warnings remain',
        'PASS':'all checks pass with zero executor warnings'}

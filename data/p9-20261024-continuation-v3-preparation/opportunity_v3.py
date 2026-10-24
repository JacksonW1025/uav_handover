"""Independent evidence-opportunity wrapper. Never changes frozen P7 fields."""
import copy,json,sys
from pathlib import Path
import numpy as np
from pyulog import ULog
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(ROOT/'data/p9-20261024-continuation-v2-preparation'))
from measurement_v2 import evidence as open_evidence,validate_open_evidence
from p5_metrics import T_CAPTURE,T_PROFILE,t1_profile
MISSING='no research_recovery rows with MC_RAPTOR_RREC > 0'


def classify(e):
    """Pure decision, shared by raw extractor, runner and no-flight fixtures."""
    if e.get('rate',0)<=0:
        return 'REACHED_UNVERIFIED' if e.get('recovery_rows',0)>0 else 'NOT_REACHED'
    if e.get('legacy_verified'):
        return 'REACHED_VERIFIED' if e.get('eligible_resumes',0)>0 else 'NOT_REACHED'
    if e.get('eligible_resumes',0)>0:
        return 'REACHED_UNVERIFIED' if e.get('resume_tail_complete') else 'UNKNOWN'
    required=['safety_abort','native_open_anchor_valid','active_stale_coverage','memory_coverage','parameters_match','capture_profile_match','no_log_dropout','no_resume','activation_observed']
    if e.get('recovery_rows',0)>0:return 'UNKNOWN'
    return 'NOT_REACHED' if all(e.get(k) for k in required) else 'UNKNOWN'


def asof_parameter(u,name,stamp):
    value=u.initial_parameters.get(name)
    for t,k,v in u.changed_parameters:
        if k==name and t<=stamp:value=v
    return value


def profile_check(tg,cap,end,tp):
    diagnostic={}
    ix=np.flatnonzero((tg['kind']==T_CAPTURE)&(tg['activation']==0)&(tg['timestamp']==cap));j=int(ix[0]);mode=int(tg['mode'][j]);decel=float(tg['decel'][j]);v0=np.array([tg[f'vehicle_velocity[{k}]'][j] for k in range(3)],float);p0=np.array([tg[f'position[{k}]'][j] for k in range(3)],float)
    match=bool(mode==int(tp['rtgt']) and abs(decel-float(tp['rtdec']))<=1e-5 and all(abs(float(tg[f'position[{k}]'][j])-float(tg[f'vehicle_position[{k}]'][j]))<=1e-4 for k in range(3)))
    prof=np.flatnonzero((tg['kind']==T_PROFILE)&(tg['timestamp']>=cap)&(tg['timestamp']<=end))
    if mode==0:match=match and len(prof)==0 and all(abs(float(tg[f'velocity[{k}]'][j]))<1e-6 for k in range(3))
    else:
        target_v=np.array([v0[0],v0[1],0.]);match=match and all(abs(float(tg[f'velocity[{k}]'][j])-target_v[k])<=1e-5 for k in range(3)) and len(prof)>0
        if len(prof):
            times=(tg['timestamp_sample'][prof].astype(float)-float(tg['capture_sample'][j]))/1e6;pp,pv,_=t1_profile(p0,target_v,decel,times)
            rp=np.column_stack([tg[f'position[{k}]'][prof] for k in range(3)]);rv=np.column_stack([tg[f'velocity[{k}]'][prof] for k in range(3)])
            diagnostic['profile_max_position_error']=float(np.max(np.abs(pp-rp)));diagnostic['profile_max_velocity_error']=float(np.max(np.abs(pv-rv)))
            match=match and diagnostic['profile_max_position_error']<=1e-4 and diagnostic['profile_max_velocity_error']<=1e-4
    return bool(match),diagnostic


def extract(run):
    run=Path(run).resolve();cfg=json.loads((run/'config.json').read_text());base=json.loads((run/'p7-metrics.json').read_text());rate=float(cfg['p2_treatment_parameters'].get('rrec',0))
    recovery=(base.get('p7') or {}).get('recovery') or {};gaps=base.get('gaps') or []
    e={'rate':rate,'recovery_rows':int(recovery.get('rows',0)),'eligible_resumes':len(gaps),'legacy_verified':base.get('status')=='MEASURED','legacy_status':base.get('status'),'legacy_problems':base.get('problems',[])}
    if rate<=0 or e['legacy_verified']:return e
    try:
        u=ULog(str(run/'flight.ulg'),['raptor_status','research_memory','research_target','vehicle_status','research_recovery']);T={d.name:d.data for d in u.data_list if d.multi_id==0}
        st=T['raptor_status'];mem=T['research_memory'];tg=T['research_target']
        if gaps:
            last_resume=int(gaps[-1]['first_reception_px4_us']);active=st['timestamp'][(st['timestamp']>=last_resume)&(st['active']==1)]
            e['resume_tail_complete']=bool(len(active)>=3 and active[-1]>=last_resume+12000 and np.max(np.diff(active))<=20000)
            return e
        oe=open_evidence(run);anchor,reason=validate_open_evidence(oe);e['native_open_anchor_valid']=anchor is not None;e['anchor_problem']=reason
        if anchor is None:return e
        cap=oe['captures'][0];end=oe['ownership_end'];w=(st['timestamp']>=cap)&(st['timestamp']<=end)
        fresh=st['timestamp'][w&(st['trajectory_setpoint_stale']==0)&(st['active']==1)]
        if len(fresh):
            e['eligible_resumes']=1;e['resume_tail_complete']=bool(end>=int(fresh[0])+12000 and len(st['timestamp'][w])>=3 and np.max(np.diff(st['timestamp'][w]))<=20000);return e
        # KIND_STEP is the frozen message constant; do not assume numeric kind.
        from p5_metrics import KIND_STEP
        ms=(mem['kind']==KIND_STEP)&(mem['active']==1)&(mem['timestamp']>=cap)&(mem['timestamp']<=end)
        observed=st['timestamp'][w];mt=mem['timestamp'][ms]
        e.update(safety_abort=oe['safety_abort'],no_resume=not oe['later_reception'],no_log_dropout=not u.dropouts,
          active_stale_coverage=bool(len(observed)>=3 and observed[-1]>=end-8000 and np.max(np.diff(observed))<=20000 and np.all(st['active'][w]==1) and np.all(st['trajectory_setpoint_stale'][w]==1)),
          memory_coverage=bool(len(mt)>=3 and mt[0]<=cap+8000 and mt[-1]>=end-8000 and np.max(np.diff(mt))<=20000),
          activation_observed=bool(np.any((tg['kind']==T_CAPTURE)&(tg['activation']==1)&(tg['timestamp']<cap))),
          cap_native_us=int(cap),ownership_end_native_us=int(end),status_rows=int(w.sum()),memory_rows=int(ms.sum()))
        expected={'MC_RAPTOR_RREC':rate,'MC_RAPTOR_RSH':1,'MC_RAPTOR_RINI':int(cfg['p2_treatment_parameters']['rini']),'MC_RAPTOR_RTGT':int(cfg['p2_treatment_parameters']['rtgt'])}
        e['effective_parameters']={k:asof_parameter(u,k,cap) for k in expected}
        e['parameters_match']=all(e['effective_parameters'][k] is not None and abs(float(e['effective_parameters'][k])-v)<=1e-6 for k,v in expected.items()) and not any(k in expected and cap<t<=end and abs(float(v)-expected[k])>1e-6 for t,k,v in u.changed_parameters)
        match,profile_diagnostic=profile_check(tg,cap,end,cfg['p2_treatment_parameters']);e.update(profile_diagnostic);e['capture_profile_match']=match
        return e
    except Exception as exc:e['extract_error']=repr(exc);return e


def assess(run):
    try:e=extract(run);state=classify(e)
    except Exception as exc:e={'extract_error':repr(exc)};state='UNKNOWN'
    return {'version':'p9-recovery-opportunity-v3','state':state,'evidence':e,'recovery_success_claim':False,'limit':'NOT_REACHED means no exposure in observed window, never recovery success; original P7 unchanged'}


def decide(row,measurement,opportunity,p7):
    """New admission separate from inherited fields and observed flight outcome."""
    checks=row['checks'];required=['px4_exit','no_crash_markers','trace','output_chain','p9_measured','p9_reconstruction','remote_disconnected','candidate_unchanged']
    physical=all(checks.get(k) is True for k in required) and all(v for k,v in checks.items() if k not in ['execution','subject_measured','p7_measured'])
    e=opportunity['evidence'];m=measurement.get('measurement')
    exception=bool(p7.get('problems')==[MISSING] and p7.get('status')=='INCOMPLETE' and opportunity['state']=='NOT_REACHED' and e.get('rate',0)>0 and e.get('eligible_resumes')==0 and all(e.get(k) for k in ['safety_abort','native_open_anchor_valid','active_stale_coverage','memory_coverage','parameters_match','capture_profile_match','no_log_dropout','no_resume','activation_observed']) and measurement.get('kind')=='OPEN_GAP_CENSORED' and row.get('flight_outcome')=='FAILURE')
    measured=bool(m and m.get('status')=='MEASURED')
    return {'version':'p9-admission-v3','physical_and_other_evidence_ok':physical,'frozen_p7_measured':bool(checks.get('p7_measured')),'frozen_p7_status':p7.get('status'),'frozen_p7_problems':p7.get('problems',[]),'exception_not_reached':exception,'evidence_admissible':bool(physical and measured and opportunity['state'] in ['NOT_REACHED','REACHED_VERIFIED'] and (checks.get('p7_measured') or exception)),'observed_flight_failure':row.get('flight_outcome')=='FAILURE','opportunity_state':opportunity['state'],'recovery_outcome':'NOT_EXPOSED' if exception else 'SEE_FROZEN_P7_AND_P9','no_retroactive_old_admission':True}

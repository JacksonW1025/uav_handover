#!/usr/bin/env python3
"""Independent P9 measurement adapter v2. Original files are never rewritten.
Compatible path returns the EXACT frozen dictionary; only a proven first open
planned gap may use an explicitly separate, censored measurement version.
"""
import json,sys,types
from pathlib import Path
import numpy as np
from pyulog import ULog
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
import p9_metrics
from p9_model import sha
from p5_metrics import receptions,T_CAPTURE
VERSION='p9-open-gap-measurement-v2'


def validate_open_evidence(e):
    """Pure conservative evidence predicate, native microseconds throughout."""
    if not e.get('safety_abort'):return None,'not a recorded safety-aborted flight'
    if e.get('closed_count')!=0:return None,'fallback limited to first open gap'
    if not e.get('first_gap_started'):return None,'no planned first-gap start evidence'
    if not e.get('explicit_windows'):return None,'not an explicit-window condition'
    if not e.get('phase_matches'):return None,'gap event differs from frozen planned phase'
    if len(e.get('captures',[]))!=1:return None,'missing or ambiguous in-flight timeout capture'
    if not e.get('receptions'):return None,'no native external receptions'
    last=e['receptions'][-1];cap=e['captures'][0]
    if e.get('later_reception'):return None,'first gap is not open'
    if not e['delay_bounds'][0]<=cap-last<=e['delay_bounds'][1]:return None,'timeout delay outside original bounds'
    if not e.get('capture_parameters_match'):return None,'capture treatment differs'
    if not e.get('state_continuity'):return None,'state evidence has missing/invalid samples'
    if not e['profile_start']<=last<cap<=e['ownership_end']:return None,'native ordering invalid'
    if abs(last-e['expected_first_gap'])>50000:return None,'last reception outside planned gap timing allowance'
    return int(last),None


def evidence(run):
    cfg=json.loads((run/'config.json').read_text());base=json.loads((run/'p7-metrics.json').read_text())
    events=[json.loads(s) for s in (run/'events.jsonl').read_text().splitlines()]
    u=ULog(str(run/'flight.ulg'),['raptor_status','trajectory_setpoint','research_target','vehicle_status','vehicle_local_position'])
    t={d.name:d.data for d in u.data_list if d.multi_id==0}
    for name in ['raptor_status','trajectory_setpoint','research_target','vehicle_status','vehicle_local_position']:
        if name not in t:raise ValueError('missing raw topic '+name)
    profile=base['times_px4_us']['profile_start'];st=t['raptor_status'];active=np.asarray(st['timestamp'])[(st['active']==1)&(st['timestamp']>=profile)]
    if not len(active):raise ValueError('no active ownership')
    vt=t['vehicle_status'];disarm=vt['timestamp'][(vt['timestamp']>profile)&(vt['arming_state']!=2)]
    own=min(int(active[-1]),int(u.last_timestamp),int(disarm[0]) if len(disarm) else int(u.last_timestamp))
    rec=np.asarray(receptions(st,t['trajectory_setpoint']));rec=rec[(rec>=profile)&(rec<=own)]
    tg=t['research_target'];caps=np.flatnonzero((tg['kind']==T_CAPTURE)&(tg['activation']==0)&(tg['timestamp']>profile)&(tg['timestamp']<=own))
    plan=next((x for x in events if x['event']=='p5_gap_plan'),{})
    first=next((x for x in events if x['event']=='p5_gap_started' and x['index']==0),{})
    ws=plan.get('windows_profile_s') or [];windows=cfg['p2_profile']['gaps'].get('windows_s')
    a,b=ws[0] if ws else (0.,0.)
    phase=bool(first and ws and first.get('planned_profile_s')==ws[0] and a<=first['first_skip_profile_s']<=a+.04 and first['last_emit_profile_s']<=a+.02 and first['last_emit_profile_s']>=a-.04)
    tp=cfg['p2_treatment_parameters'];match=bool(len(caps)==1 and int(tg['mode'][caps[0]])==int(tp['rtgt']) and abs(float(tg['decel'][caps[0]])-float(tp['rtdec']))<=1e-5)
    cap_stamps=[int(tg['timestamp'][i]) for i in caps]
    bounds=cfg['p5']['gap_timing']['capture_delay_s']
    lp=t['vehicle_local_position'];lt=np.asarray(lp['timestamp_sample'],float);use=(lt>=profile+a*1e6-50000)&(lt<=own)
    continuity=bool(use.sum()>=3 and np.all(np.diff(lt[use])<=20000) and all(np.isfinite(lp[k][use]).all() for k in ['x','y','z','vx','vy','vz']))
    return {'safety_abort':bool(base.get('aborted') and str(base.get('failure_reason','')).startswith('safety:')),
        'closed_count':len(base.get('gaps') or []),'first_gap_started':bool(first),'explicit_windows':bool(windows),'phase_matches':phase,
        'captures':cap_stamps,'receptions':[int(x) for x in rec],'later_reception':bool(cap_stamps and len(rec) and rec[-1]>cap_stamps[0]),
        'delay_bounds':[int(round(x*1e6)) for x in bounds],'capture_parameters_match':match,'profile_start':profile,'ownership_end':own,
        'expected_first_gap':profile+int(round(a*1e6)),'state_continuity':continuity}


def extended_core(run,anchor):
    """Only anchor acquisition differs; numerical code is the frozen source body."""
    path=ROOT/'tools/p9_metrics.py';expected=json.loads((ROOT/'data/p9-20261024-freeze/manifest.json').read_text())['files']['tools/p9_metrics.py']
    if sha(path)!=expected:raise RuntimeError('frozen metric source drift')
    source=path.read_text();old="if first is None:raise ValueError('no observed first interruption; fixed-window origin cannot be established')"
    if source.count(old)!=1:raise RuntimeError('frozen anchor source not unique')
    mod=types.ModuleType('explicit_open_gap_core_v2');mod.__file__=str(path)
    exec(compile(source.replace(old,'if first is None:first='+str(int(anchor))),str(path),'exec'),mod.__dict__)
    return mod.analyze(run)


def analyze(run):
    run=Path(run).resolve()
    try:
        m=p9_metrics.analyze(run)
        if any(not np.isfinite(m[k]) for k in ['clock_origin_native_us','clock_origin_spread_us','max_tilt_deg','max_altitude_loss_m','max_lag_m','max_horizontal_distance_m','integrated_abs_lag_m_s']):raise ValueError('nonfinite measured values')
        return {'version':VERSION,'kind':'ORIGINAL_COMPATIBLE','measurement':m,'frozen_analyzer_error':None,'anchor_evidence':None}
    except ValueError as exc:
        error=str(exc)
        if error!='no observed first interruption; fixed-window origin cannot be established':
            return {'version':VERSION,'kind':'UNMEASURABLE','measurement':None,'frozen_analyzer_error':error,'reason':'non-anchor metric error; no inferred success'}
    except Exception as exc:
        return {'version':VERSION,'kind':'UNMEASURABLE','measurement':None,'frozen_analyzer_error':repr(exc),'reason':'missing/inconsistent evidence; no inferred success'}
    try:
        ev=evidence(run);anchor,reason=validate_open_evidence(ev)
        if anchor is None:return {'version':VERSION,'kind':'UNMEASURABLE','measurement':None,'frozen_analyzer_error':error,'reason':reason,'anchor_evidence':ev}
        m=extended_core(run,anchor)
        if m['status']!='MEASURED' or m['max_tilt_deg'] is None or any(not np.isfinite(m[k]) for k in ['max_tilt_deg','max_altitude_loss_m','max_lag_m','max_horizontal_distance_m','integrated_abs_lag_m_s']):raise ValueError('insufficient finite metric/clock evidence')
        if m['complete_window']:raise ValueError('open first-gap fallback unexpectedly has a complete window')
        m=dict(m,open_gap=True)
        return {'version':VERSION,'kind':'OPEN_GAP_CENSORED','measurement':m,'frozen_analyzer_error':error,'anchor_evidence':ev,
            'known_outcomes':{'tilt_failure':True if m['tilt_ge_45_failure'] else None,'altitude_failure':True if m['altitude_failure'] else None,'task_outcome':'FAILURE' if m['task_failure'] else 'CENSORED'},
            'limit':'new frozen measurement version only; observed extrema are lower bounds; no resume/catch-up imputed; original P9 result is not replaced'}
    except Exception as exc:
        return {'version':VERSION,'kind':'UNMEASURABLE','measurement':None,'frozen_analyzer_error':error,'reason':repr(exc)}

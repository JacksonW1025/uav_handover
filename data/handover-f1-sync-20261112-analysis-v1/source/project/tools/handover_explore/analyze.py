"""Independent multi-switch exploration analysis; all outputs in a NEW directory.

Usage: python tools/handover_explore/analyze.py --root NEW_BATCH --output NEW_ANALYSIS
       python tools/handover_explore/analyze.py --run FLIGHT --output NEW_ANALYSIS
Raw files and previous analyses are never changed. No missing evidence is a pass.
"""
import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
from pyulog import ULog
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from analyze import clean
from cn_reference.analyze import snapshot, state, window, row, vector, host_bracket, input_clipping
from cn_single.analyze import longest_continuous


def load(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def lines(path):
    return [json.loads(v) for v in path.read_text().splitlines() if v.strip()] if path.exists() else []


def transitions(z, field, time='timestamp'):
    values = np.asarray(z.get(field, []))
    return [{'index': int(i), 'timestamp_us': int(z[time][i]), 'from': int(values[i-1]), 'to': int(values[i])}
            for i in np.flatnonzero(values[1:] != values[:-1])+1]


def native_event(event, p):
    for key in ['px4_us', 'native_us', 'end_bound_px4_us', 'timestamp_us']:
        if event.get(key) is not None:
            return int(event[key])
    b = host_bracket(p, event.get('monotonic_ns'))
    return (b or {}).get('native_lower_us')


def enhanced_window(d, start, end):
    if start is None or end is None or end <= start:
        return None
    out = window(d, start, (end-start)/1e6)
    l = d.get('vehicle_local_position', {})
    t = np.asarray(l.get('timestamp', [])); mask = (t >= start) & (t <= end)
    if mask.any():
        v = np.column_stack([l[k][mask] for k in ['vx', 'vy', 'vz']])
        pos = np.column_stack([l[k][mask] for k in ['x', 'y', 'z']])
        out.update(max_horizontal_speed_m_s=float(np.linalg.norm(v[:, :2], axis=1).max()),
                   max_speed_m_s=float(np.linalg.norm(v, axis=1).max()),
                   max_abs_vertical_speed_m_s=float(np.abs(v[:, 2]).max()),
                   max_radius_m=float(np.linalg.norm(pos[:, :2], axis=1).max()),
                   max_altitude_m=float((-pos[:, 2]).max()),
                   position_change_m=(pos[-1]-pos[0]).tolist(), velocity_change_m_s=(v[-1]-v[0]).tolist())
        if not np.isfinite(pos).all() or not np.isfinite(v).all():
            out['observations_finite'] = out['complete'] = False
    m = d.get('actuator_motors', {}); mt = np.asarray(m.get('timestamp', [])); ix = np.flatnonzero((mt >= start) & (mt <= end))
    if len(ix):
        values = np.column_stack([m[f'control[{j}]'][ix] for j in range(4)])
        before = ix[0]-1
        ext = np.vstack([[m[f'control[{j}]'][before] for j in range(4)], values]) if before >= 0 else values
        out['motor_min_by_motor'] = values.min(0).tolist(); out['motor_max_by_motor'] = values.max(0).tolist()
        out['motor_max_abs_step_by_motor'] = np.abs(np.diff(ext, axis=0)).max(0).tolist() if len(ext)>1 else None
        out['motor_saturation_continuous_s'] = longest_continuous(mt[ix], np.any((values >= .999) | (values <= .001), axis=1))
    # Finite violations remain failures even if some unrelated evidence is missing.
    violation = any(out.get(k) is not None and out[k] > threshold for k, threshold in [('max_tilt_deg', 45), ('max_altitude_loss_m', 1)])
    out['local_task_envelope'] = 'FAILURE' if violation else ('SUCCESS' if out['complete'] else 'UNKNOWN')
    return clean(out)


def boundary_step(owner, i):
    out = {'source': 'research_actuator exact owner-tagged publication', 'finite': False}
    if i <= 0:
        return out
    before, after = vector(row(owner, i-1), 'control', 4), vector(row(owner, i), 'control', 4)
    out.update(before=before, after=after, previous_owner=int(owner['owner'][i-1]), first_owner=int(owner['owner'][i]),
               previous_publication_us=int(owner['actuator_timestamp'][i-1]), first_publication_us=int(owner['actuator_timestamp'][i]),
               previous_sample_age_us=int(owner['actuator_timestamp'][i])-int(owner['actuator_timestamp'][i-1]))
    if before is not None and after is not None:
        delta = np.asarray(after)-before
        out.update(signed_step_by_motor=delta.tolist(), max_abs_step=float(np.abs(delta).max()), finite=True)
    return out


def continuity(d, start):
    out = {}
    for topic, names in [('trajectory_setpoint', [('position', 3), ('velocity', 3), ('acceleration', 3)]),
                         ('research_p11', [('network_target_position', 3), ('network_target_velocity', 3)])]:
        z = d.get(topic, {}); t = np.asarray(z.get('timestamp', [])); before = np.flatnonzero(t < start); after = np.flatnonzero(t >= start)
        if not len(before) or not len(after):
            out[topic] = {'status': 'UNKNOWN'}; continue
        i, j = int(before[-1]), int(after[0])
        v = {'before_us': int(t[i]), 'after_us': int(t[j]), 'bracket_gap_us': int(t[j])-int(t[i]), 'fields': {}}
        for key, n in names:
            a, b = vector(row(z, i), key, n), vector(row(z, j), key, n)
            v['fields'][key] = {'before': a, 'after': b, 'delta': (np.asarray(b)-a).tolist() if a is not None and b is not None else None}
        v['note'] = 'Adjacent logged samples, not an inferred instantaneous discontinuity; NaN may represent an unset reference component.'
        out[topic] = v
    return out


def reference_evidence(p, sends, start, end):
    t = np.asarray(p.get('timestamp', [])); active = np.asarray(p.get('active', []), bool)
    ix = np.flatnonzero((t >= start) & (t <= end) & active)
    out = {'active_samples': int(len(ix)), 'first_active': row(p, int(ix[0])) if len(ix) else None,
           'sender_match': None, 'note': 'external_valid alone does not prove receipt of this runner reference.'}
    if not len(ix):
        return out
    valid = ix[np.asarray(p.get('external_valid', np.zeros(len(t))), bool)[ix]]
    out['first_any_source_valid'] = row(p, int(valid[0])) if len(valid) else None
    out['stale_samples'] = int(np.count_nonzero(np.asarray(p.get('stale', np.zeros(len(t))))[ix]))
    out['invalid_total_change'] = int(p['invalid_total'][ix[-1]])-int(p['invalid_total'][ix[0]]) if 'invalid_total' in p else None
    if 'read_wall_ns' not in p:
        return out
    # Match a consumed payload to the most recent send before its host read.
    # First payload need not be consumed in a latest-value interface.
    send_valid = [s for s in sends if s.get('before_ns') is not None and len(s.get('position', [])) == 3 and len(s.get('velocity', [])) == 3]
    if send_valid:
        send_valid.sort(key=lambda s: s['before_ns']); times = np.asarray([s['before_ns'] for s in send_valid], dtype=np.int64)
        for i in valid:
            read = int(p['read_wall_ns'][i]); k = int(np.searchsorted(times, read, side='right'))-1
            # A read can overlap publication. Search recent payloads, require completed send.
            for j in range(k, max(-1, k-5), -1):
                s = send_valid[j]
                if s.get('after_ns', s['before_ns']) > read:
                    continue
                actual = vector(row(p, int(i)), 'external_position'); velocity = vector(row(p, int(i)), 'external_velocity')
                if actual is not None and velocity is not None and np.allclose(actual+velocity, s['position']+s['velocity'], atol=1e-5, rtol=0):
                    out['sender_match'] = {'read_native_us': int(t[i]), 'read_wall_ns': read, 'send': s,
                                           'send_end_to_read_ms': (read-s.get('after_ns', s['before_ns']))/1e6,
                                           'limit': 'Payload+same-host clock match, no sequence ID; constant repeated payloads are ambiguous.'}
                    break
            if out['sender_match']:
                break
    try:
        out['input_clipping'] = input_clipping(p, ix)
    except KeyError:
        out['input_clipping'] = None
    return clean(out)


def joint_recovery(d, start, end, incoming):
    """Use original P0 recovery implementation and thresholds without modification.

    Recovery entry must be <=10s; its 2s dwell may confirm up to 12s.
    Velocity reference remains zero (not moving-target velocity).
    """
    from recovery import recovery
    cfg = load(ROOT/'config/p0.json')['joint_recovery'].copy()
    cfg['position_reference'] = 'active_controller_target'
    out = {'status':'INSUFFICIENT_OBSERVATION', 'entry_deadline_s':10., 'dwell_s':2.,
           'velocity_reference':'frozen zero velocity, NOT target velocity', 'reference':None}
    try:
        local=dict(d['vehicle_local_position']); local['timestamp']=local.get('timestamp_sample',local['timestamp'])
        angular=dict(d.get('research_angular_velocity',d['vehicle_angular_velocity']));angular['timestamp']=angular.get('timestamp_sample',angular['timestamp'])
        if incoming == 1:
            p=d['research_p11'];active=np.asarray(p['active'],bool)&np.asarray(p['native_step'],bool)
            target={'timestamp':p['timestamp'][active]}
            target.update({f'position[{j}]':p[f'network_target_position[{j}]'][active] for j in range(3)})
            out['reference']='exact active P11 network target position'
        else:
            target=d['trajectory_setpoint'];out['reference']='classic trajectory_setpoint as in frozen P0'
        stop=min(end,start+12_000_000)
        result=recovery(local,angular,cfg,start,stop,target)
        jr=result['joint_recovery'];out['raw_recovery']=result;out['from_change_s']=jr.get('time_s')
        if jr['status']=='SETTLED' and jr['time_s']<=10:
            out['status']='SETTLED'
        elif stop>=start+12_000_000 and jr['status']=='NOT_SETTLED' and not jr['true_first_recovery_uncertain']:
            out['status']='NOT_SETTLED'
        out['note']='A shortened interval or source gap is not evidence of recovery failure or success.'
    except (KeyError,ValueError,IndexError) as exc:
        out['error']=str(exc)
    return clean(out)


def frozen(w, recovery, safety=False):
    reasons, unknown = [], []
    if w is None:
        unknown.append('missing subject window')
    else:
        for k, limit, op in [('max_tilt_deg',45,'ge'), ('max_angular_rate_component_rad_s',8,'ge'), ('max_radius_m',10,'ge'), ('max_altitude_m',8,'ge'), ('min_altitude_m',.2,'le'), ('motor_saturation_continuous_s',.5,'ge')]:
            value = w.get(k)
            if value is None:
                unknown.append(k)
            elif (value >= limit if op == 'ge' else value <= limit):
                reasons.append(k)
        if not w.get('complete'):
            unknown.append('incomplete or nonfinite window')
    if safety:
        reasons.append('runner safety abort')
    if recovery['status'] == 'NOT_SETTLED':
        reasons.append('no joint recovery in 10 seconds')
    elif recovery['status'] != 'SETTLED':
        unknown.append('joint recovery insufficient observation')
    return {'status': 'FAILURE' if reasons else ('UNKNOWN' if unknown else 'SUCCESS'), 'reasons': reasons, 'unknown': unknown}


def active_reference(d, t):
    """Actual P11 target during N; frozen trajectory target during C, backward only."""
    t=np.asarray(t,dtype=np.int64);values=np.full((len(t),3),np.nan);source=np.full(len(t),'missing',dtype=object)
    sp=d.get('trajectory_setpoint',{});st=np.asarray(sp.get('timestamp',[]));owner=d.get('research_actuator',{});ot=np.asarray(owner.get('actuator_timestamp',[]))
    oi=np.searchsorted(ot,t,side='right')-1
    own=np.asarray(owner.get('owner',[]))[np.maximum(oi,0)] if len(ot) else np.zeros(len(t))
    if len(st):
        si=np.searchsorted(st,t,side='right')-1;valid=(si>=0)&(own==2)
        v=np.column_stack([sp[f'position[{j}]'][np.maximum(si,0)] for j in range(3)])
        values[valid]=v[valid];source[valid]='classic_trajectory'
    pp=d.get('research_p11',{});pt=np.asarray(pp.get('timestamp',[]))
    if len(pt):
        pi=np.searchsorted(pt,t,side='right')-1;safe=np.maximum(pi,0);valid=(pi>=0)&(own==1)&np.asarray(pp['active'],bool)[safe]&(t-pt[safe]<=20000)
        v=np.column_stack([pp[f'network_target_position[{j}]'][safe] for j in range(3)])
        values[valid]=v[valid];source[valid]='neural_consumed'
    return values,source


def reference_tracking(d,start,end):
    l=d.get('vehicle_local_position',{});t=np.asarray(l.get('timestamp',[]));ix=np.flatnonzero((t>=start)&(t<=end))
    if not len(ix):return {'status':'UNKNOWN'}
    ref,source=active_reference(d,t[ix]);pos=np.column_stack([l[k][ix] for k in 'xyz']);valid=np.isfinite(ref).all(1)&np.isfinite(pos).all(1)
    out={'status':'MEASURED' if valid.all() else 'INCOMPLETE','samples':len(ix),'valid_reference_samples':int(valid.sum()),'reference_sources':sorted(set(source.tolist())),
         'note':'z_actual - z_reference >0 is below the active target; intentional descent and fixed 1m altitude-loss criterion remain separate.'}
    if valid.any():
        e=pos[valid]-ref[valid];out.update(max_below_active_reference_m=float(max(0,e[:,2].max())),max_above_active_reference_m=float(max(0,-e[:,2].min())),max_position_error_m=float(np.linalg.norm(e,axis=1).max()),rmse_position_error_m=float(np.sqrt(np.mean(np.sum(e*e,axis=1)))))
    return clean(out)


def trajectory_export(result,path):
    """20Hz display trace, backward alignment <=20ms for state; not analysis input."""
    u=ULog(str(Path(result['source_run'])/'flight.ulg'));d={v.name:v.data for v in u.data_list if v.multi_id==0}
    boundaries=[b for b in result['boundaries'] if 'owner_boundary' in b]
    if not boundaries:return
    start=boundaries[0]['owner_boundary']['timestamp_us'];end=max(b['subject_end_us'] for b in boundaries)
    grid=np.unique(np.r_[np.arange(start-500000,end+1,50000),[b['owner_boundary']['timestamp_us'] for b in boundaries]]).astype(np.int64)
    ref,source=active_reference(d,grid);rows=[]
    def sample(topic,stamp,max_age=20000,time='timestamp'):
        z=d.get(topic,{});ts=np.asarray(z.get(time,[]));i=int(np.searchsorted(ts,stamp,side='right'))-1
        return row(z,i) if i>=0 and (max_age is None or stamp-int(ts[i])<=max_age) else None
    for k,t in enumerate(grid):
        l=sample('vehicle_local_position',t);a=sample('vehicle_attitude',t);m=sample('actuator_motors',t);n=sample('vehicle_status',t,None);o=sample('research_actuator',t,None,'actuator_timestamp')
        pos=[l[v] for v in 'xyz'] if l else None;vel=[l[v] for v in ['vx','vy','vz']] if l else None
        q=vector(a,'q',4);tilt=float(np.degrees(np.arccos(np.clip(1-2*(q[1]**2+q[2]**2),-1,1)))) if q else None
        rows.append({'t':(int(t)-start)/1e6,'native_us':int(t),'pos':pos,'ref':ref[k].tolist(),'ref_source':source[k],
                     'velocity':vel,'tilt':tilt,'alt':-l['z'] if l else None,'speed':float(np.linalg.norm(vel)) if vel else None,
                     'motors':vector(m,'control',4),'nav':n.get('nav_state') if n else None,'owner':o.get('owner') if o else None})
    value={'schema':'handover-explore-display-v1','note':'20Hz display only, raw full-rate metrics are in analysis JSON. Null means missing, not zero. Native time and NED coordinates.','source_run':result['source_run'],'rows':rows,
           'boundaries':[{'number':b['number'],'direction':b['direction'],'t':(b['owner_boundary']['timestamp_us']-start)/1e6} for b in boundaries]}
    path.write_text(json.dumps(clean(value),ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')


def analyze(folder):
    folder = Path(folder)
    out = {'source_run': str(folder), 'status': 'INCOMPLETE', 'errors': [], 'boundaries': [],
           'scope': 'Exploratory SITL description; one/few seeds do not establish probabilistic or causal safety bounds.'}
    try:
        u = ULog(str(folder/'flight.ulg')); d = {x.name:x.data for x in u.data_list if x.multi_id == 0}
        events = lines(folder/'events.jsonl'); sends = lines(folder/'explore-setpoints.jsonl'); meta = load(folder/'metadata.json', {})
    except Exception as exc:
        out['errors'].append(str(exc)); return out
    out['ulog_sha256'] = hashlib.sha256((folder/'flight.ulg').read_bytes()).hexdigest()
    out['ulog_dropouts'] = len(u.dropouts); out['metadata'] = meta; out['execution'] = load(folder/'validation.json')
    p = d.get('research_p11', {}); owner = d.get('research_actuator', {}); status = d.get('vehicle_status', {})
    config=load(folder/'config.json',{});out['explore']=config.get('explore',{})
    external_expected=out['explore'].get('reference_kind')!='native_capture'
    mode = meta.get('raptor_mode_id')
    nav = transitions(status, 'nav_state', 'nav_state_timestamp' if 'nav_state_timestamp' in status else 'timestamp')
    own = transitions(owner, 'owner', 'actuator_timestamp')
    out['native_navigation_transitions'] = nav; out['native_owner_transitions'] = own
    requests = [e for e in events if e.get('event') == 'handover_requested' and e.get('subject') is True]
    out['subject_requests'] = requests
    failures = [e for e in events if e.get('event') == 'failure']
    safety = [e for e in failures if 'safety' in str(e.get('reason', '')).lower()]
    end_events = [e for e in events if e.get('event') in ['explore_subject_finished', 'explore_finished', 'explore_subject_end', 'landing_requested', 'failure']]
    end_candidates = [(native_event(e,p), e['event']) for e in end_events]
    out['subject_end_candidates'] = end_candidates
    missing = [name for name in ['vehicle_status','vehicle_local_position','vehicle_attitude','vehicle_angular_velocity','actuator_motors','research_actuator','research_p11'] if name not in d]
    if not requests: missing.append('subject handover requests')
    if not sends and external_expected: missing.append('explore-setpoints.jsonl')
    if u.dropouts: missing.append('ULog contains dropouts')
    used = set()
    for number, req in enumerate(requests):
        lower = native_event(req,p); incoming = 1 if req.get('to_controller') == 'N' else 2
        next_lower = native_event(requests[number+1],p) if number+1<len(requests) else None
        candidates = [v for v in own if v['to']==incoming and v['index'] not in used and (lower is None or v['timestamp_us']>=lower) and (next_lower is None or v['timestamp_us']<next_lower)]
        b = {'number':number+1,'direction':'C→N' if incoming==1 else 'N→C','request':req,'request_native_lower_us':lower,'missing':[]}
        if not candidates or lower is None:
            b['missing'].append('request native bound or matching owner transition');out['boundaries'].append(b);continue
        change = candidates[0];used.add(change['index']);anchor = change['timestamp_us']
        b['owner_boundary'] = change; b['owner_boundary_step'] = boundary_step(owner, change['index'])
        nv = [v for v in nav if (v['to']==mode if incoming==1 else v['from']==mode) and v['timestamp_us']>=(lower or 0) and v['timestamp_us']<=anchor+100000]
        b['native_nav_boundary'] = nv[0] if nv else None
        b['nav_to_owner_us'] = anchor-nv[0]['timestamp_us'] if nv else None
        b['pre_takeover_snapshot'] = snapshot(d,anchor-1); b['pre_takeover_state'] = state(b['pre_takeover_snapshot'])
        ends = [(t,label) for t,label in end_candidates if t is not None and t>anchor]
        next_owner = next((v['timestamp_us'] for v in own if v['timestamp_us']>anchor),None)
        if next_owner is not None: ends.append((next_owner-1,'next_owner_boundary_exclusive'))
        if ends: end, end_reason = min(ends)
        else: end, end_reason = int(u.last_timestamp), 'ULog end; no observed subject closure'
        b['subject_end_us'] = end; b['subject_end_reason'] = end_reason
        b['windows'] = {f'first_{s}s':enhanced_window(d,anchor,min(anchor+s*1000000,end)) for s in [1,2]}
        for s in [1,2]:
            w=b['windows'][f'first_{s}s']
            if w is not None:w['truncated_by_next_boundary_or_subject_end']=end<anchor+s*1000000
        b['windows']['subject'] = enhanced_window(d,anchor,end)
        b['reference_tracking'] = reference_tracking(d,anchor,end)
        b['setpoint_continuity'] = continuity(d,anchor)
        b['reference_evidence'] = reference_evidence(p,sends,anchor,end)
        b['frozen_joint_recovery'] = joint_recovery(d,anchor,end,incoming)
        b['frozen_primary_outcome'] = frozen(b['windows']['subject'],b['frozen_joint_recovery'],bool(safety and end_reason=='failure'))
        b['task_outcome'] = {'status':(b['windows']['subject'] or {}).get('local_task_envelope','UNKNOWN'), 'criteria':'tilt >45° or altitude loss >1m from pre-takeover altitude; same subject interval'}
        if not nv:b['missing'].append('native nav boundary')
        if not b['pre_takeover_state'] or b['pre_takeover_state']['max_age_us']>20000:b['missing'].append('fresh finite pre-takeover state')
        if not b['owner_boundary_step'].get('finite') or b['owner_boundary_step'].get('previous_sample_age_us',1e9)>20000:b['missing'].append('fresh finite owner boundary motor pair')
        if not b['windows']['subject'] or not b['windows']['subject']['complete']:b['missing'].append('complete subject coverage')
        if incoming==1 and external_expected and not b['reference_evidence'].get('sender_match'):b['missing'].append('sender-matched active reference read')
        if end_reason.startswith('ULog'):b['missing'].append('subject end evidence')
        if b['missing'] and b['task_outcome']['status']=='SUCCESS':b['task_outcome']['status']='UNKNOWN'
        if b['missing'] and b['frozen_primary_outcome']['status']=='SUCCESS':
            b['frozen_primary_outcome']['status']='UNKNOWN';b['frozen_primary_outcome']['unknown']+=b['missing']
        out['boundaries'].append(b)
    landed = any(e.get('event')=='ready' and e.get('condition')=='landing' for e in events)
    disarmed = any(e.get('event')=='ready' and e.get('condition')=='disarmed' for e in events)
    out['completion'] = {'safety_protection_triggered':bool(safety),'safety_events':safety,'failures':failures,'landing_requested':any(e.get('event')=='landing_requested' for e in events),'landed_observed':landed,'disarmed_observed':disarmed,'normal_landing_disarm':landed and disarmed and not failures,
                         'process_stops':[e for e in events if e.get('event')=='process_stopped']}
    out['setpoint_send_summary'] = {'count':len(sends),'max_send_gap_ms':float(np.diff([s['before_ns'] for s in sends]).max()/1e6) if len(sends)>1 and all('before_ns' in s for s in sends) else None}
    for b in out['boundaries']:
        missing += [f"boundary {b['number']}: {m}" for m in b['missing']]
    out['evidence_completion']={'complete':not missing,'missing':missing}
    out['status']='MEASURED' if not missing else 'INCOMPLETE'
    # Batch-wide missing evidence cannot produce an overall pass.
    def combine(key):
        values=[b.get(key,{}).get('status','UNKNOWN') for b in out['boundaries']]
        return 'FAILURE' if 'FAILURE' in values else ('SUCCESS' if values and all(v=='SUCCESS' for v in values) and not missing else 'UNKNOWN')
    out['frozen_primary_status']=combine('frozen_primary_outcome');out['task_status']=combine('task_outcome')
    bs=[b for b in out['boundaries'] if 'owner_boundary' in b]
    if bs:
        start=bs[0]['owner_boundary']['timestamp_us'];end=max(b['subject_end_us'] for b in bs)
        out['whole_subject_window']=enhanced_window(d,start,end)
        out['whole_subject_reference_tracking']=reference_tracking(d,start,end)
        whole=(out['whole_subject_window'] or {}).get('local_task_envelope','UNKNOWN')
        if whole=='FAILURE':out['task_status']='FAILURE'
        elif whole=='UNKNOWN' and out['task_status']=='SUCCESS':out['task_status']='UNKNOWN'
    return clean(out)


def plot(result, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    font_path='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
    font_manager.fontManager.addfont(font_path)
    plt.rcParams['font.family']=font_manager.FontProperties(fname=font_path).get_name()
    plt.rcParams['axes.unicode_minus']=False
    u=ULog(str(Path(result['source_run'])/'flight.ulg'));d={x.name:x.data for x in u.data_list if x.multi_id==0}
    boundaries=[b for b in result['boundaries'] if 'owner_boundary' in b]
    if not boundaries:return
    start=boundaries[0]['owner_boundary']['timestamp_us'];end=max(b['subject_end_us'] for b in boundaries)
    fig,ax=plt.subplots(5,1,figsize=(13,13),sharex=True,constrained_layout=True)
    def time(z):return (np.asarray(z['timestamp'],np.int64)-start)/1e6
    a=d.get('vehicle_attitude',{});l=d.get('vehicle_local_position',{});m=d.get('actuator_motors',{});p=d.get('research_p11',{})
    if a:ax[0].plot(time(a),np.degrees(np.arccos(np.clip(1-2*(a['q[1]']**2+a['q[2]']**2),-1,1))))
    ax[0].axhline(45,color='red',ls='--',label='45°标准')
    if l:
        ax[1].plot(time(l),-l['z'],label='实际高度');ax[2].plot(time(l),np.hypot(l['vx'],l['vy']),label='水平速度');ax[2].plot(time(l),l['vz'],label='垂直速度NED')
    if p:
        active=np.asarray(p['active'],bool)
        ax[1].plot(time(p)[active],-p['network_target_position[2]'][active],ls='--',label='N实际使用目标')
        ax[4].plot(time(p),p['active'],label='active');ax[4].plot(time(p),p['external_valid']+.05,label='外部有效(+0.05)');ax[4].plot(time(p),p['stale']+.1,label='超时(+0.1)')
    if m:
        for j in range(4):ax[3].plot(time(m),m[f'control[{j}]'],label=f'电机{j}',alpha=.75)
    for b in boundaries:
        x=(b['owner_boundary']['timestamp_us']-start)/1e6
        for a in ax:a.axvline(x,color='black',ls=':',alpha=.6)
        ax[0].text(x,47,f"{b['number']} {b['direction']}",fontsize=9)
    for a,label in zip(ax,['倾角 / °','高度 / m','速度 / m/s','归一化电机指令','读取证据']):
        a.set_ylabel(label);a.grid(alpha=.25)
        if a.get_legend_handles_labels()[0]:a.legend(fontsize=8,ncol=3)
    ax[-1].set_xlim(-.5,(end-start)/1e6+.2);ax[-1].set_xlabel('相对首次owner交接的原生PX4时间 / s')
    fig.suptitle(f"{Path(result['source_run']).parent.name}：冻结={result['frozen_primary_status']}，任务={result['task_status']}，证据={result['status']}")
    fig.savefig(path,dpi=145);plt.close(fig)


def combined(runs, output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    results=[];rows=[];report=['# 正常RAPTOR交接探索：独立分析','', '所有数据只读重算。单种子描述性结果不是总体安全认证。缺失证据为UNKNOWN，保护触发与正常落地disarm分别报告。', '', '冻结标准：倾角≥45°、角速度分量≥8rad/s、半径≥10m、高度≥8m或≤0.2m、连续电机饱和≥0.5s、10秒内未完成2秒联合恢复。任务标准：倾角>45°或相对接管前高度损失>1m。', '', '短驻留未提供完整恢复观察时，冻结恢复为UNKNOWN，不改阈值。冻结联合恢复复用P0原实现：速度对零，位置对实际活动目标，dwell起点≤10秒且持续2秒；运动参考跟踪不是冻结恢复。', '']
    for n,run in enumerate(runs,1):
        r=analyze(run);results.append(r);name=f'{n:02d}-{run.parent.name}-{run.name}'
        (output/(name+'.json')).write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
        if r.get('boundaries'):
            try:
                plot(r,output/(name+'.png'))
                trajectory_export(r,output/(name+'.trajectory.json'))
            except Exception as exc:r['errors'].append('plot: '+str(exc))
        report += [f"## {name}",f"证据：{r['status']}；冻结：{r.get('frozen_primary_status','UNKNOWN')}；任务：{r.get('task_status','UNKNOWN')}。",f"正常落地disarm：{r.get('completion',{}).get('normal_landing_disarm')}；安全保护：{r.get('completion',{}).get('safety_protection_triggered')}。"]
        for b in r.get('boundaries',[]):
            w=b.get('windows',{}).get('subject') or {};step=b.get('owner_boundary_step',{})
            v={'run':str(run),'switch':b['number'],'direction':b['direction'],'frozen':b.get('frozen_primary_outcome',{}).get('status','UNKNOWN'),'task':b.get('task_outcome',{}).get('status','UNKNOWN'),'max_tilt_deg':w.get('max_tilt_deg'),'altitude_loss_m':w.get('max_altitude_loss_m'),'max_speed_m_s':w.get('max_speed_m_s'),'motor_boundary_step':step.get('max_abs_step'),'window_s':w.get('requested_duration_s'),'missing':'; '.join(b['missing'])};rows.append(v)
            report += [f"- 第{b['number']}次{b['direction']}：倾角{v['max_tilt_deg']}°，高度损失{v['altitude_loss_m']}m，最大速度{v['max_speed_m_s']}m/s，边界电机跳变{v['motor_boundary_step']}；冻结{v['frozen']} / 任务{v['task']}。"]
        report += ['证据缺口：'+'；'.join(r.get('evidence_completion',{}).get('missing',r['errors'])),'']
    (output/'summary.json').write_text(json.dumps(clean(results),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    (output/'report.zh.md').write_text('\n'.join(report)+'\n')
    if rows:
        with (output/'boundaries.csv').open('x') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    return results


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--run',type=Path);group.add_argument('--root',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();runs=[args.run] if args.run else sorted({p.parent for p in args.root.rglob('flight.ulg')})
    combined(runs,args.output)

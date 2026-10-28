#!/usr/bin/env python3
"""Separate sanitized past+plan inputs from future measurement/scoring records."""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import numpy as np
from pyulog import ULog

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from p9_model import sha,write
from run_experiment import Experiment
from p5_metrics import window_basics
from recovery import recovery
from p11.models import tilt


def source_plan(cfg,origin,yaw):
    ns=SimpleNamespace(cfg=cfg,pcfg=cfg['p2_profile'])
    p=cfg['p2_profile'];axis=np.array(p['motion_axis_ned']);total=Experiment.profile_duration(ns)+p['end_hold_s']
    base=Experiment.reposition(ns,0.)[3]+p['reference_hold_s']+p['accel_s']+p['pre_gap_s']
    full=[[base+a,base+b] for a,b in p['gaps']['windows_s']]
    mask=cfg['p11']['event_mask'];shift=cfg['p11'].get('event_shift_s',0.)
    windows=[[a+shift,b+shift] for i,(a,b) in enumerate(full) if i in mask]
    times=np.arange(-.02,total+.008,.004);table=[]
    for t in times:
        s,v,_=Experiment.p1_profile(ns,float(t));table.append(np.r_[np.array(origin)+axis*s,axis*v].tolist())
    return {'profile':{'table_t0_s':-.02,'table':table,'yaw':float(yaw)},'windows_profile_s':windows,
        'full_source_windows_profile_s':full,'common_first_gap_profile_s':full[0][0],
        'stream_end_profile_s':float(total),'nominal_horizon_profile_s':float(total+p['post_stream_s']),
        'terminal_timing_slack_s':float(cfg['p11'].get('prediction_terminal_slack_s',.5)),
        'horizon_profile_s':float(total+p['post_stream_s']+cfg['p11'].get('prediction_terminal_slack_s',.5)),
        'publish_period_s':float(p['setpoint_period_s']),'treatment':cfg['p2_treatment_parameters'],
        'axis':axis.tolist(),'clock_model':'nominal4ms / LP8ms / attitude one-step; no future actual scheduler input'}


def pack(run,sync,out):
    run=run.resolve();sync=sync.resolve()
    out.mkdir(parents=True,exist_ok=False);D=dict(np.load(sync));cfg=json.loads((run/'config.json').read_text())
    events=[json.loads(x) for x in (run/'events.jsonl').read_text().splitlines()]
    origin=next(e for e in events if e['event']=='p1_reference_origin')
    sends=[json.loads(x) for x in (run/'p11-sends.jsonl').read_text().splitlines()]
    first=next(x for x in sends if x['stream_t0_monotonic_s'] is not None);t0_ns=int(round(first['stream_t0_monotonic_s']*1e9))
    prefix=np.flatnonzero(D['run_wall_ns'].astype(np.int64)<t0_ns)
    if not len(prefix):raise RuntimeError('no known pre-stream prefix')
    i=int(prefix[-1]);p=source_plan(cfg,origin['origin_ned_m'],origin['yaw_rad'])
    lower=int(D['native_query_wall_lower_ns'][i]);upper=int(D['native_query_wall_upper_ns'][i])
    if lower<0:raise RuntimeError('pre-stream initial clock not bracketed')
    init={'position':D['position'][i].tolist(),'velocity':D['velocity'][i].tolist(),
        'attitude':D['attitude'][i].tolist(),'omega':D['omega'][i].tolist(),'h':D['h_after'][i].tolist(),
        'previous':D['action'][i].tolist(),'history':D['input'][i,18:].tolist(),'history_count':0 if D['native_step'][i] else 1,
        'target_p':D['target_p'][i].tolist(),'target_v':D['target_v'][i].tolist(),'target_yaw':float(D['target_yaw'][i]),
        'stale':bool(D['stale'][i]),'last_read_us':int(D['last_read'][i]) if D['last_read'][i] else None,
        'sample_us':int(D['sample_us'][i]),'native_us':int(D['native_us'][i]),
        'lp_phase_us':int(D['lp_sample'][i])%8000,
        'commit_phase_us':int(D['sample_us'][np.flatnonzero(D['native_step'][:i+1])[-1]])%8000,
        'profile_s':((lower+upper)/2-t0_ns)/1e9,'profile_interval_s':[(lower-t0_ns)/1e9,(upper-t0_ns)/1e9]}
    if np.linalg.norm(init['target_v'])>1e-5:raise RuntimeError('initial moving capture profile not admitted')
    if cfg['p2_treatment_parameters']['rrec']!=0:raise RuntimeError('formal initial recovery state currently not supported; not silently zeroed')
    doc={'schema':'p11-causal-input-1','identity':out.parent.name,'initial':init,'plan':p,'model_sha256':None,
        'policy_sha256':json.loads((run/'metadata.json').read_text())['policy_sha256']}
    write(out/'prediction-input.json',doc)
    # These separate arrays are for fitting/scoring ONLY and are hidden in the prediction sandbox.
    profile_s=(D['run_wall_ns'].astype(np.int64)-t0_ns)/1e9
    np.savez_compressed(out/'measurement.npz',**D,profile_s=profile_s)
    source={'run':str(run.relative_to(ROOT)),'initial_index':i,'initial_cutoff_host_ns':t0_ns,
        'initial_max_host_ns':upper,'prefix_only':upper<t0_ns,'clock_uncertainty_s':(upper-lower)/1e9,
        'known_origin_event_host_ns':origin['monotonic_ns'],'reference_generation':'literal Experiment.p1_profile and merged recorded source config; no future messages/targets',
        'input_sha256':sha(out/'prediction-input.json'),'measurement_sha256':sha(out/'measurement.npz'),
        'sync_sha256':sha(sync),'raw_ulog_sha256':sha(run/'flight.ulg')}
    write(out/'manifest.json',source)
    return source


def measure(run,sync,out):
    run=run.resolve();sync=sync.resolve()
    out.mkdir(parents=True,exist_ok=False);d=dict(np.load(sync));cfg=json.loads((run/'config.json').read_text())
    events=[json.loads(x) for x in (run/'events.jsonl').read_text().splitlines()]
    origin=next(e for e in events if e['event']=='p1_reference_origin')
    plan=source_plan(cfg,origin['origin_ned_m'],origin['yaw_rad'])
    sends=[json.loads(x) for x in (run/'p11-sends.jsonl').read_text().splitlines()]
    t0=int(round(next(x for x in sends if x['stream_t0_monotonic_s'] is not None)['stream_t0_monotonic_s']*1e9))
    times=(d['run_wall_ns'].astype(np.int64)-t0)/1e9
    failure=next((e for e in events if e['event']=='failure'),None)
    ended=next((e for e in events if e['event']=='p5_stream_ended'),None)
    post=next((e for e in events if e['event']=='p1_phase_ended' and e['label']=='post_stream'),None)
    j=int(np.searchsorted(times,plan['common_first_gap_profile_s']));j=min(j,len(times)-1)
    start=int(d['native_us'][j]);stop=int(post['px4_end_us']) if post else int(d['native_us'][-1])+4000
    if failure:
        k=max(0,int(np.searchsorted(d['run_wall_ns'],failure['monotonic_ns'],side='right')-1));stop=min(stop,int(d['native_us'][k])+4000)
    names=['vehicle_local_position','vehicle_attitude','vehicle_angular_velocity','research_angular_velocity','actuator_motors','research_target']
    T={x.name:x.data for x in ULog(str(run/'flight.ulg'),names).data_list if x.multi_id==0}
    whole=window_basics(cfg,T,start,stop,start);jr={'status':'NOT_MEASURED','from_final_capture_s':None};final_capture=None
    target=T['research_target'];tt=target['timestamp'].astype(np.int64)
    if ended and not failure:
        stream_end=int(ended['end_bound_px4_us']);caps=np.flatnonzero((target['kind']==1)&(tt>stream_end-300000)&(tt<=stream_end+400000))
        if len(caps):
            c=int(caps[0]);final_capture=int(tt[c]);idx=np.flatnonzero((tt>=final_capture)&(tt<stop)&np.isin(target['kind'],[1,2]))
            tgt={'timestamp':tt[idx],**{f'position[{k}]':target[f'position[{k}]'][idx] for k in range(3)}}
            loc=dict(T['vehicle_local_position']);loc['timestamp']=loc['timestamp_sample']
            angular=dict(T['research_angular_velocity']);angular['timestamp']=angular['timestamp_sample']
            r=recovery(loc,angular,cfg['joint_recovery'],final_capture,stop,tgt)['joint_recovery'];jr={'status':r['status'],'from_final_capture_s':r['time_s']}
    reasons=[];crit=cfg['p5']['failure_criteria']
    for key,threshold,why in [('max_tilt_deg',45,'tilt'),('max_angular_rate_rad_s',8,'angular_rate'),('max_horizontal_radius_m',10,'radius')]:
        if whole.get(key) is not None and whole[key]>=threshold:reasons.append('safety_envelope:'+why)
    if whole['motor_longest_continuous_saturation_s']>=crit['motor_saturation_continuous_s']:reasons.append('motor_saturation')
    if whole['min_altitude_m'] is not None and whole['min_altitude_m']<=crit['ground_altitude_m']:reasons.append('ground')
    if failure and 'safety' in failure['reason']:reasons.append('runner_safety_abort')
    if not failure and (jr['status']!='SETTLED' or jr['from_final_capture_s'] is None or jr['from_final_capture_s']>10.):reasons.append('no_joint_recovery')
    complete=post is not None and failure is None
    task_failed=(whole['max_tilt_deg'] is not None and whole['max_tilt_deg']>45.) or (whole['max_altitude_loss_m'] is not None and whole['max_altitude_loss_m']>1.)
    task='FAILURE' if task_failed else ('SUCCESS' if complete else 'UNKNOWN_CENSORED')
    problem=[]
    if failure and not reasons:problem.append('non-safety execution abort')
    report={'schema':'p11-measurement-1','run':str(run.relative_to(ROOT)),'status':'MEASURED' if not problem else 'FAIL',
        'problems':problem,'frozen_flight_outcome':{'outcome':'FAILURE' if reasons else ('SUCCESS' if complete else 'UNKNOWN_CENSORED'),'reasons':reasons},
        'task_outcome':task,'task_operator':'tilt>45deg or altitude_loss>1m; primary frozen envelope retains>=45',
        'whole':whole,'censored':not complete,'window_native_us':[start,stop],
        'window_native_alignment':'planned common profile time via observed Run wall pairs; source native query bracket retained, no actual capture alignment',
        'observed_profile_end_s':float(times[-1]),'planned_profile_end_s':plan['nominal_horizon_profile_s'],
        'prediction_clock_max_s':plan['horizon_profile_s'],
        'final_capture_us':final_capture,'joint_recovery_after_final_capture':jr,
        'failure':failure,'all_events_retained':True,'raw_ulog_sha256':sha(run/'flight.ulg')}
    write(out/'measurement.json',report);return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('operation',choices=['pack','measure']);p.add_argument('run',type=Path)
    p.add_argument('--sync',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=(pack if a.operation=='pack' else measure)(a.run,a.sync,a.output);print(json.dumps(r,ensure_ascii=False))

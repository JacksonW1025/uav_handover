#!/usr/bin/env python3
"""Read-only P9 development diagnostic of the A2 error/clock interface.

Measured residual maxima are diagnostics, never replacements for hard bounds.
"""
import argparse
import json
import math
from pathlib import Path
import sys

import numpy as np
from pyulog import ULog

from source import ROOT, sha
sys.path.insert(0,str(ROOT/'tools'))
from p6_export import TOPICS, reconstruct


def diagnose(output):
    output.mkdir(parents=True,exist_ok=False)
    run=ROOT/'data/p9-20261024-dev-01/run';raw=run/'flight.ulg'
    u=ULog(str(raw),TOPICS);tables={d.name:d.data for d in u.data_list if d.multi_id==0}
    rec=reconstruct(tables);tm=tables['research_timing'];att=tables['vehicle_attitude']
    required=['attitude_sample','timestamp_sample','executor_called']
    if any(k not in tm for k in required) or 'timestamp_sample' not in att:
        raise ValueError('NOT_CHECKABLE_MISSING_ATTITUDE_OR_CLOCK_FIELD; never fill zero')
    called=np.flatnonzero(np.asarray(tm['executor_called']).astype(bool))
    ts=np.asarray(tm['timestamp_sample'],np.int64)[called]
    ix=np.searchsorted(ts,rec['s']);ix=np.minimum(ix,len(ts)-1)
    matched=ts[ix]==rec['s'];at_sample=np.asarray(tm['attitude_sample'],np.int64)[called[ix]]
    ats=np.asarray(att['timestamp_sample'],np.int64);ai=np.minimum(np.searchsorted(ats,at_sample),len(ats)-1)
    matched&=ats[ai]==at_sample;matched&=rec['ok']
    w,x,y,z=[np.asarray(att[f'q[{i}]'],float)[ai] for i in range(4)]
    bzx=2*(x*z+w*y);bzy=2*(y*z-w*x);bzz=1-2*(x*x+y*y)
    matched&=bzz>.1
    c,s=np.cos(rec['yaw']),np.sin(rec['yaw'])
    # Same geometric proxy as P9, now matched to the EXACT named attitude sample.
    q=(-9.80665*(c*bzx+s*bzy)/bzz)
    model=json.loads((ROOT/'data/p9-20261024-freeze/model.json').read_text())
    kp,kv=model['kp'][0],model['kv'][0];rho=math.exp(-.05)
    ep=np.clip(rec['pf'][:,0],-.5,.5);dv=np.clip(rec['vf'][:,0],-1,1)
    # Require all 23 relevant samples present at exact 4ms spacing and fixed yaw.
    valid=[];samples=[]
    events=[json.loads(line) for line in (run/'events.jsonl').read_text().splitlines()]
    profile=next(e['px4_bound_us'] for e in events if e['event']=='p1_profile_started')
    for k in range(22,len(q)-1):
        if rec['s'][k]<profile or not matched[k-22:k+2].all():continue
        if not np.all(np.diff(rec['s'][k-22:k+2])==4000):continue
        if not np.all(rec['yaw'][k-22:k+2]==rec['yaw'][k]):continue
        command=-kp*ep[k-22]-kv*dv[k-22]
        residual=float(q[k+1]-rho*q[k]-(1-rho)*command)
        valid.append((k,residual))
    if not valid:raise ValueError('NOT_CHECKABLE_NO_ALIGNED_WINDOW')
    failing=[(k,r) for k,r in valid if abs(r)>.633e-7]
    selected=[]
    for row in (failing[:3]+sorted(valid,key=lambda x:abs(x[1]),reverse=True)[:3]):
        if row[0] not in selected:selected.append(row[0])
    for k in selected:
        samples.append({'index':k,'sample_us':int(rec['s'][k]),'next_sample_us':int(rec['s'][k+1]),
            'profile_bound_offset_us':int(rec['s'][k]-profile),
            'attitude_sample_us':int(at_sample[k]),'next_attitude_sample_us':int(at_sample[k+1]),
            'yaw_rad':float(rec['yaw'][k]),'yaw_constant_24_samples':True,
            'quaternion':[[float(att[f'q[{i}]'][ai[j]]) for i in range(4)] for j in [k,k+1]],
            'cos_yaw':float(c[k]),'sin_yaw':float(s[k]),'q':[float(q[k]),float(q[k+1])],
            'delayed_clipped_position':float(ep[k-22]),'delayed_clipped_velocity':float(dv[k-22]),
            'kp':kp,'kv':kv,'residual_q':float(q[k+1]-rho*q[k]-(1-rho)*(-kp*ep[k-22]-kv*dv[k-22]))})
    st=tables['raptor_status'];subscription=np.asarray(st['subscription_update_trajectory_setpoint']).astype(bool)
    now=np.asarray(st['timestamp'],np.int64);last=np.asarray(st['timestamp_last_trajectory_setpoint'],np.int64)
    # An updated subscription may contain an invalid message; the read clock is
    # only confirmed if the successful-read assignment actually took place.
    scope=(now>=profile)&np.asarray(st['active']).astype(bool)
    read=subscription&scope&(last==now)&(last>0)
    reads=np.unique(last[read])
    unique,counts=np.unique(np.diff(rec['s']),return_counts=True)
    result={'schema':'p10-a3-development-interface-diagnostic-1','status':'MAPPED_P9_DATA_REFUTES_A2_W_BOUND' if failing else 'NO_COUNTEREXAMPLE_NOT_A_HARD_BOUND',
        'raw_file':str(raw.relative_to(ROOT)),'raw_sha256':sha(raw),
        'inputs':{str(p.relative_to(ROOT)):sha(p) for p in [run/'config.json',run/'events.jsonl',ROOT/'tools/p6_export.py',ROOT/'data/p9-20261024-freeze/model.json']},
        'mapping':'p/v/errors from research_timing named local position sample and reconstructed actual active target; q=-g R_body_z_xy/Rzz rotated into target-yaw frame, using EXACT named attitude_sample',
        'clock_alignment':'native gyro sample time, not DDS UTC or line-profile seconds; require all 24 rows 4ms and fixed yaw',
        'model_step':'q_next=rho*q-(1-rho)*(kp*clip(e[k-22])+kv*clip(d[k-22]))+w_q',
        'necessary_bound':'|w_q| <= sqrt(.4)*1e-7 < .633e-7 if ||w||_P<=1e-7',
        'state_mapping_scope':'refutes this specified logged estimator/attitude-proxy mapping; not a statement about unobserved true acceleration',
        'rows':len(rec['s']),'unmatched_attitude_or_state_rows':int((~matched).sum()),
        'reconstruction':rec['resid'],'tested_aligned_steps':len(valid),'q_coordinate_violations':len(failing),
        'max_abs_q_residual':max(abs(r) for _,r in valid),'first_violation_index':failing[0][0] if failing else None,
        'portable_counterexamples':samples,'inference_sample_deltas_us':dict(zip(map(str,unique.tolist()),counts.tolist())),
        'read_clock':{'rows':int(read.sum()),'unique_confirmed_reads':len(reads),
            'confirmation':'active profile scope, subscription updated AND last_read==native status.timestamp>0; deduplicated',
            'excluded_updated_subscriptions_in_scope':int((subscription&scope&~read).sum()),
            'distinct_native_read_intervals_us':sorted(set(np.diff(reads).tolist())),
            'exact_A3_publish_read_schedule_verified':False,'reason':'profile-start bound and callback/receive phase are not an exact timing identity'},
        'target_float_envelope':'binary32 cast envelope may be checked for finite magnitudes; EP/EV are not bounds on stream timing or source reference mismatch',
        'target_magnitude_development_check':{'max_abs_position_ned_m':float(np.max(np.abs(rec['pos']-rec['e']))),
            'max_abs_velocity_ned_m_s':float(np.max(np.abs(rec['vel']-rec['ev']))),
            'actual_publication_profile_clock_per_message':'NOT_CHECKABLE_FROM_SAVED_MONOTONIC_EVENTS_ALONE',
            'interpretation':'range check supports cast-ULP premise only; does not verify a temporal target-error envelope'},
        'unobserved_fields':'GRU influence is not assigned zero; this residual diagnostic does not identify each causal component',
        'no_new_empirical_bound':True,'new_flights':0,'B_C_D_started':False}
    with (output/'compatibility.json').open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({k:result[k] for k in ['status','tested_aligned_steps','q_coordinate_violations','max_abs_q_residual']}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path)
    diagnose(p.parse_args().output)

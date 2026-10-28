#!/usr/bin/env python3
"""Read-only P11 observation acceptance and known-input network replay.

Outputs only a NEW directory. Continuous replay carries GRU, previous action and
executor action-history mean; only the 18 exogenous observation coordinates and
native schedule are supplied from the record. This is NOT a plant prediction.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np
from pyulog import ULog

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from p3_memory import load_policy, gru_step, rotation, example_check
from p9_model import sha, write


def matrix(d,name,n):return np.column_stack([d[f'{name}[{i}]'] for i in range(n)]).astype(float)


def multiply(a,b):
    w,x,y,z=a;v,p,q,r=b
    return np.array([w*v-x*p-y*q-z*r,w*p+x*v+y*r-z*q,w*q-x*r+y*v+z*p,w*r+x*q-y*p+z*v])


def inputs(p,v,q,omega,r,s,yaw):
    c=np.cos(yaw);z=np.sin(yaw)
    frame=np.array([[c,z,0],[z,-c,0],[0,0,-1]])
    qr=q*np.array([1,1,-1,-1]);qc=np.array([np.cos(yaw/2),0,0,np.sin(yaw/2)])
    return np.r_[np.clip(frame@(p-r),-.5,.5),rotation(multiply(qc,qr)),
                 np.clip(frame@(v-s),-1,1),omega*np.array([1,-1,-1])]


def network(P,h,x):
    updated=gru_step(P,h,x)
    raw=updated@P['W2'].T+P['b2']
    return updated,raw,np.clip(raw,-1,1)


def stats(x):
    x=np.asarray(x,dtype=float)
    if not x.size:return None
    return {'n':int(x.size),'min':float(np.min(x)),'p50':float(np.median(x)),
            'p95':float(np.quantile(x,.95)),'p99':float(np.quantile(x,.99)),'max':float(np.max(x))}


def baseline(run):
    topics={d.name:d.data for d in ULog(str(run/'flight.ulg'),['research_timing','vehicle_attitude','vehicle_local_position']).data_list if d.multi_id==0}
    t=topics['research_timing'];sel=t['active'].astype(bool)&t['executor_called'].astype(bool)
    q=matrix(topics['vehicle_attitude'],'q',4)
    tilt=np.degrees(np.arccos(np.clip(1-2*(q[:,1]**2+q[:,2]**2),-1,1)))
    result={'inference_duration_us':stats(t['inference_duration_us'][sel]),
            'control_sample_dt_us':stats(np.diff(t['timestamp_sample'][sel].astype(np.int64))),
            'native_sample_dt_us':stats(np.diff(t['timestamp_sample'][sel&t['native_step'].astype(bool)].astype(np.int64))),
            'sample_missed_total':int(t['source_missed_total'][-1]),
            'duplicate_total':int(t['duplicate_total'][-1]),'regressed_total':int(t['regressed_total'][-1]),
            'max_tilt_deg_whole_log':float(tilt.max()),'ulog_sha256':sha(run/'flight.ulg')}
    if 'p11_cycle_wall_end_ns' in t:
        good=sel&(t['p11_cycle_wall_end_ns']>t['p11_cycle_wall_start_ns'])
        result['whole_observation_cycle_us']=stats((t['p11_cycle_wall_end_ns'][good].astype(np.int64)-t['p11_cycle_wall_start_ns'][good].astype(np.int64))/1000)
        for key in ['p11_setup_ns','p11_pre_ns','p11_post_copy_ns','p11_publication_ns']:result[key]=stats(t[key][good]/1000)
        result['units_p11_parts']='microseconds; exact observed parts include full publication; full span also includes ordinary controller work'
    return result


def analyze(run,out):
    run=run.resolve();out.mkdir(parents=True,exist_ok=False)
    cfg=json.loads((run/'config.json').read_text());meta=json.loads((run/'metadata.json').read_text())
    names=['research_p11','research_timing','research_memory','research_target','research_recovery',
           'raptor_status','vehicle_local_position_groundtruth','vehicle_attitude_groundtruth','vehicle_angular_velocity_groundtruth']
    u=ULog(str(run/'flight.ulg'),names);T={d.name:d.data for d in u.data_list if d.multi_id==0}
    report={'schema':'p11-observation-1','run':str(run.relative_to(ROOT)),'baseline':baseline(run),'problems':[],
            'tolerances':{'single_h':1e-5,'single_action':1e-5,'continuous_h':1e-4,'continuous_action':1e-4,'input':1e-4},
            'scope':'all contiguous active logged control calls; exogenous18 inputs and schedule known; no future-free plant claim',
            'executor_action_field':'CLIPPED executor output before (a+1)/2; unclipped Dense output reconstructed from exact prestate/input/weights and verified clipped output',
            'missing_truth':'never filled with zeros; gz angular topic contains finite-difference Euler rates, not body angular velocity'}
    if 'research_p11' not in T:
        report.update(status='BASELINE_ONLY',observations=0);write(out/'observation.json',report);return report
    d=T['research_p11'];active=d['active'].astype(bool);n=int(active.sum())
    if not n:raise RuntimeError('no active P11 observations')
    D={k:v[active] for k,v in d.items()};ts=D['timestamp_sample'].astype(np.int64)
    p=matrix(D,'position',3);v=matrix(D,'velocity',3);q=matrix(D,'attitude',4);omega=matrix(D,'angular_velocity',3)
    r=matrix(D,'network_target_position',3);s=matrix(D,'network_target_velocity',3)
    hb=matrix(D,'gru_before',16);ha=matrix(D,'gru_after',16);x=matrix(D,'policy_input',22)
    prev=matrix(D,'previous_action_before',4);after=matrix(D,'previous_action_after',4);a=matrix(D,'executor_action',4)
    P=load_policy();report['policy_matches_run']=P['sha256']==meta['policy_sha256']
    report['example_max_abs_error']=example_check(P)
    if not report['policy_matches_run']:report['problems'].append('policy hash differs')
    native=D['native_step'].astype(bool);committed=D['gru_committed'].astype(bool)
    hnew,raw,clipped=network(P,hb,x)
    expect=np.where(committed[:,None],hnew,hb)
    one_h=float(np.max(np.abs(expect-ha)));one_a=float(np.max(np.abs(clipped-a)))
    report['single_step']={'rows':n,'native':int(native.sum()),'h_max':one_h,'action_max':one_a,
                           'previous_action_write_max':float(np.max(np.abs(after-a))),'unclipped_peak':float(np.max(np.abs(raw)))}
    reconstructed=np.array([inputs(*row) for row in zip(p,v,q,omega,r,s,D['target_yaw'])])
    input_error=float(np.max(np.abs(reconstructed-x[:,:18])))
    report['input_reconstruction']={'max_abs':input_error,'components_over_1e-4':int(np.sum(np.abs(reconstructed-x[:,:18])>1e-4))}
    # Begin once, then carry ALL controller memory, including intermediate outputs.
    # An omitted call ends the replay. It is not silently bridged or reinitialized.
    boundaries=np.flatnonzero(np.diff(ts)!=4000)+1
    end=int(boundaries[0]) if len(boundaries) else n
    h=hb[0].copy();previous=prev[0].copy();mean=previous.copy();count=0;eh=[];ea=[];ex=[];pred=[]
    started=time.perf_counter()
    for k in range(end):
        mean=(mean*count+previous)/(count+1) if count else previous.copy()
        xx=np.r_[x[k,:18],mean]
        hh,rr,aa=network(P,h,xx)
        if committed[k]:h=hh
        previous=aa;count=0 if native[k] else count+1
        eh.append(float(np.max(np.abs(h-ha[k]))));ea.append(float(np.max(np.abs(aa-a[k]))));ex.append(float(np.max(np.abs(xx-x[k]))))
        pred.append(np.r_[h,aa,mean])
    report['continuous']={'rows':end,'total_active_rows':n,'complete_active_interval':end==n,
        'h_max':max(eh),'action_max':max(ea),'input_history_max':max(ex),
        'seconds':float((ts[end-1]-ts[0])/1e6),'compute_s':time.perf_counter()-started,
        'initialization':'first active pre-GRU and previous_action exactly once; history counter reset by original activation',
        'missing_call_boundaries':boundaries.tolist()}
    timing=T['research_timing'];wanted=timing['timestamp_sample'][timing['active'].astype(bool)&timing['control_step'].astype(bool)].astype(np.int64)
    report['coverage']={'observed_control_calls':n,'timing_control_calls':len(wanted),'missing':int(len(set(wanted)-set(ts))),
        'extra':int(len(set(ts)-set(wanted))),'unique':len(np.unique(ts))==n,'non4ms_edges':int(np.sum(np.diff(ts)!=4000)),
        'native_commit_mismatch':int(np.sum(native!=committed))}
    for name in ['local_position_sample','attitude_sample']:
        report[name]={'advance_us':stats(np.diff(D[name].astype(np.int64))),
                      'age_us':stats(ts-D[name].astype(np.int64))}
    # Each row pairs native time with host monotonic time. Wall scheduling interval is explicit.
    # The pair brackets Run timestamp acquisition -> input-read; it is not an affine global clock fit.
    active_indices=np.flatnonzero(active);lower=np.full(n,-1,dtype=np.int64)
    have_previous=active_indices>0
    lower[have_previous]=d['read_wall_ns'][active_indices[have_previous]-1].astype(np.int64)
    upper=D['run_wall_ns'].astype(np.int64)
    report['clock']={'pairs':n,'bracketed_pairs':int(have_previous.sum()),
        'native_query_bracket_width_us':stats((upper[have_previous]-lower[have_previous])/1000),
        'run_to_read_us':stats((D['read_wall_ns'].astype(np.int64)-D['run_wall_ns'].astype(np.int64))/1000),
        'wall_per_sim_tick_ratio':stats(np.diff(D['run_wall_ns'].astype(np.int64))/np.diff(D['timestamp'].astype(np.int64))/1000),
        'alignment':'native timestamp and Run CLOCK_MONOTONIC pair each call; target read is within run_wall..read_wall; runner uses same host CLOCK_MONOTONIC',
        'mapping_uncertainty':'Each native hrt query is causally bracketed by previous serialized Run read_wall and current run_wall. Width is recorded, not assumed4ms. First unbracketed row stays unknown. No global affine zero-error clock assertion.'}
    # Truth never substituted for controller samples. Export separate held truth + ages.
    arrays={'sample_us':ts,'native_us':D['timestamp'],'run_wall_ns':D['run_wall_ns'],'read_wall_ns':D['read_wall_ns'],
        'position':p,'velocity':v,'attitude':q,'omega':omega,'target_p':r,'target_v':s,'target_yaw':D['target_yaw'],
        'h_before':hb,'h_after':ha,'input':x,'action':a,'previous':prev,'raw_reconstructed':raw,
        'native_step':native,'committed':committed,'lp_sample':D['local_position_sample'],'att_sample':D['attitude_sample'],
        'stale':D['stale'],'read_valid':D['external_valid'],'last_read':D['last_valid_read_us'],
        'activation':D['activation'],'recovery_active':D['recovery_active'],'sequence':D['sequence'],
        'subscription_updated':D['subscription_updated'],'invalid_total':D['invalid_total'],'external_timestamp':D['external_timestamp'],
        'external_p':matrix(D,'external_position',3),'external_v':matrix(D,'external_velocity',3),'external_yaw':D['external_yaw'],
        'continuous_replayed':np.asarray(pred),'native_query_wall_lower_ns':lower,'native_query_wall_upper_ns':upper}
    truth={}
    for topic,key,fields in [('vehicle_local_position_groundtruth','truth_pv',['x','y','z','vx','vy','vz','ax','ay','az']),
                             ('vehicle_attitude_groundtruth','truth_q',[f'q[{i}]' for i in range(4)])]:
        if topic not in T:
            truth[topic]={'available':False};report['problems'].append('missing '+topic);continue
        g=T[topic];gt=g['timestamp_sample'].astype(np.int64);j=np.searchsorted(gt,ts,side='right')-1;valid=j>=0
        values=np.full((n,len(fields)),np.nan);values[valid]=np.column_stack([g[f][j[valid]] for f in fields])
        arrays[key]=values;arrays[key+'_sample']=np.where(valid,gt[np.maximum(j,0)],-1)
        truth[topic]={'available':True,'source_rows':len(gt),'valid_aligned_rows':int(valid.sum()),'hold_age_us':stats(ts[valid]-gt[j[valid]])}
    report['truth']=truth
    for k in ['external_position[0]','external_yaw']:
        if k in D:report.setdefault('extra_external_fields',[]).append(k)
    np.savez_compressed(out/'synchronized.npz',**arrays)
    write(out/'source-manifest.json',{'files':{str(f.relative_to(ROOT)):sha(f) for f in [run/'flight.ulg',run/'metadata.json',run/'config.json',run/'events.jsonl']},
        'outputs':{'synchronized.npz':sha(out/'synchronized.npz')},'policy_sha256':P['sha256']})
    gates={'single_h':one_h<1e-5,'single_action':one_a<1e-5,'continuous_h':max(eh)<1e-4,
        'continuous_action':max(ea)<1e-4,'input_reconstruction':input_error<1e-4,
        'complete_continuous':end==n,'all_control_calls':report['coverage']['missing']==0 and report['coverage']['extra']==0,
        'truth_present':all(g['available'] for g in truth.values()),'policy':report['policy_matches_run']}
    report['gates']=gates;report['status']='PASS' if all(gates.values()) and not report['problems'] else 'FAIL'
    write(out/'observation.json',report)
    print(json.dumps({'status':report['status'],'rows':n,'single':report['single_step'],'continuous':report['continuous'],'gates':gates},ensure_ascii=False))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=analyze(a.run,a.output);raise SystemExit(0 if r['status'] in ['PASS','BASELINE_ONLY'] else 1)

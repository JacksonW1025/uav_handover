#!/usr/bin/env python3
"""Per-physics-step output-chain measurement: which PX4 sample each Gazebo motor step applied.

Every layer (uORB queue 1, ESC work item, Gazebo motor slot) keeps only the latest command, so
the measured quantities are the age of the command in effect at each physics step and how many
commands were overwritten, not whether every published action was executed.
"""
import argparse,json
from pathlib import Path
import numpy as np

ROW=np.dtype([('sim_us','<u8'),('new_sample_us','<u8'),('applied_sample_us','<u8'),('step_wall_ns','<u8'),
              ('arrival_wall_ns','<u8'),('received','<u4'),('flags','<u4'),('ref_motor_input','<f8')])
TARGET_US=4000

def read_trace(path):
    raw=path.read_bytes()
    if raw[:8]!=b'HOMTRC01':raise ValueError('bad trace magic: '+str(path))
    size,motor=np.frombuffer(raw[8:16],'<u4')
    if size!=ROW.itemsize:raise ValueError('trace row size mismatch: '+str(path))
    body=raw[16:];whole=len(body)//ROW.itemsize
    return int(motor),np.frombuffer(body[:whole*ROW.itemsize],ROW),len(body)%ROW.itemsize

def stats(a):
    a=np.asarray(a,dtype=np.float64)
    if not len(a):return None
    return {'count':int(len(a)),'min':float(a.min()),'p50':float(np.percentile(a,50)),'p95':float(np.percentile(a,95)),
            'p99':float(np.percentile(a,99)),'max':float(a.max())}

def longest_run(mask):
    best=run=0
    for v in mask:
        run=run+1 if v else 0;best=max(best,run)
    return best

def in_intervals(t,intervals):
    mask=np.zeros(len(t),bool)
    for start,end in intervals:mask|=(t>=start)&(t<end)
    return mask

def neural_intervals(transitions,end_us):
    out=[];start=None
    for tr in sorted(transitions,key=lambda x:x['px4_us']):
        if tr['to']==1 and start is None:start=tr['px4_us']
        elif tr['from']==1 and start is not None:out.append((start,tr['px4_us']));start=None
    if start is not None:out.append((start,end_us))
    return out

def open_interval_end(trace_end_us,ulog_end_us):
    """End of a neural interval that no owner change closes (only after a runner safety abort). PX4 stops at the abort
    while Gazebo may still step without commands, so the interval ends where PX4's log ends (P4-01c dev-10 diagnosis).
    Gate values are unchanged; steps after PX4 stopped are not commands of a running controller."""
    return min(int(trace_end_us),int(ulog_end_us)) if ulog_end_us else int(trace_end_us)

def step_summary(rows,mask):
    r=rows[mask];applied=r['applied_sample_us'].astype(np.int64);valid=applied>0
    age=r['sim_us'].astype(np.int64)[valid]-applied[valid]
    new=(r['flags']&1).astype(bool)
    host=(r['step_wall_ns'].astype(np.int64)-r['arrival_wall_ns'].astype(np.int64))[new&(r['arrival_wall_ns']>0)]/1000
    return {'steps':int(len(r)),'steps_with_new_command':int(new.sum()),'hold_steps':int((~new).sum()),
            'commands_received':int(r['received'].sum()),
            'commands_overwritten_in_gazebo':int(np.maximum(r['received'].astype(np.int64)-1,0).sum()),
            'component_path_steps':int(((r['flags']&2)>0).sum()),
            'applied_age_us':stats(age),'negative_age_steps':int((age<0).sum()),
            'over_target_steps':int((age>TARGET_US).sum()),'over_target_fraction':float((age>TARGET_US).mean()) if len(age) else None,
            'longest_over_target_steps':longest_run(age>TARGET_US),'arrival_to_step_host_us':stats(host)}

def counter_delta(t,total,intervals):
    """Bracket each interval with logged cumulative rows; robust to missing ULog rows."""
    delta=0
    for start,end in intervals:
        lo=np.searchsorted(t,start,side='right')-1;hi=np.searchsorted(t,end,side='left')
        if lo<0 or hi>=len(t):return None
        delta+=int(total[hi])-int(total[lo])
    return delta

def summarize(motors,intervals,skipped=None,published=None):
    out={'scope':'Gazebo per-physics-step applied command; latest-value semantics at every layer.',
         'target_us':TARGET_US,'hard_gate':None,'neural_intervals_us':[list(map(int,i)) for i in intervals],'motors':{}}
    for motor,rows in sorted(motors.items()):
        armed=rows['applied_sample_us']>0
        out['motors'][str(motor)]={'whole_after_first_command':step_summary(rows,armed),
                                   'neural':step_summary(rows,in_intervals(rows['sim_us'].astype(np.int64),intervals))}
    if len(motors)>1:
        common=None
        for rows in motors.values():
            s=set(rows['sim_us'].tolist());common=s if common is None else common&s
        keys=np.array(sorted(common),dtype=np.uint64);applied=[]
        for rows in motors.values():
            idx=np.searchsorted(rows['sim_us'],keys);applied.append(rows['applied_sample_us'][idx])
        applied=np.stack(applied)
        out['motors_disagree_steps']=int((applied.max(0)!=applied.min(0)).sum());out['motors_common_steps']=int(len(keys))
    if skipped is not None:
        t,total=skipped
        out['px4_overwritten_publications']={'whole_run':int(total[-1]) if len(total) else None,
            'neural_bracketed':counter_delta(t,total,intervals),
            'meaning':'actuator_motors publications replaced before the ESC mixer read them (runtime uORB generation gaps).'}
    if published is not None and 0 in motors:
        t,samples=published;neural=samples[in_intervals(t,intervals)]
        applied=set(motors[0]['new_sample_us'].tolist())
        hit=np.array([int(s) in applied for s in neural],bool)
        out['neural_published_actions_logged']={'count':int(len(neural)),'applied_by_a_physics_step':int(hit.sum()),
            'not_applied':int((~hit).sum()),'coverage':'research_timing logged rows only'}
    return out

def analyze(run):
    from pyulog import ULog
    traces=sorted((run/'gz-motor').glob('motor-*.bin')) if (run/'gz-motor').is_dir() else []
    if not traces:return {'status':'MISSING_TRACE'}
    motors={};partial={}
    for path in traces:
        motor,rows,tail=read_trace(path);motors[motor]=rows;partial[str(motor)]=tail
    metrics=json.loads((run/'metrics.json').read_text()) if (run/'metrics.json').exists() else {}
    topics={d.name:d.data for d in ULog(str(run/'flight.ulg'),['research_output','research_timing']).data_list if d.multi_id==0}
    trace_end=int(max(r['sim_us'][-1] for r in motors.values()));end=open_interval_end(trace_end,metrics.get('ulog_end_us'))
    intervals=neural_intervals(metrics.get('actuator_owner_transitions',[]),end)
    o=topics.get('research_output',{});t=topics.get('research_timing',{})
    skipped=(o['timestamp'].astype(np.int64),o['skipped_publication_total'].astype(np.int64)) if 'skipped_publication_total' in o else None
    published=None
    if t:
        m=t['executor_called'].astype(bool)&t['actuator_published'].astype(bool)
        published=(t['timestamp'][m].astype(np.int64),t['timestamp_sample'][m].astype(np.int64))
    out=summarize(motors,intervals,skipped,published)
    out['partial_tail_bytes']=partial;out['open_interval_end']={'trace_end_us':trace_end,'ulog_end_us':metrics.get('ulog_end_us'),'used_us':end}
    ok=len(motors)==4 and all(v['whole_after_first_command']['steps']>0 for v in out['motors'].values()) and skipped is not None and bool(intervals)
    out['status']='MEASURED' if ok else 'INCOMPLETE'
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);args=p.parse_args()
    result=analyze(args.run.resolve());(args.run/'output-chain.json').write_text(json.dumps(result,indent=2)+'\n')
    print(result['status']);raise SystemExit(0 if result['status']=='MEASURED' else 1)

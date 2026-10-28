#!/usr/bin/env python3
"""Send/read correspondence with intervals, actual phases, no exact-clock assumption."""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
from pyulog import ULog
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from p11.observe import matrix,stats

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from p9_model import sha,write


def check(run,out):
    run=run.resolve();out.mkdir(parents=True,exist_ok=False)
    sends=[json.loads(x) for x in (run/'p11-sends.jsonl').read_text().splitlines()]
    t=next(x.data for x in ULog(str(run/'flight.ulg'),['research_p11']).data_list if x.name=='research_p11')
    ep=matrix(t,'external_position',3);ev=matrix(t,'external_velocity',3)
    before=np.array([s['before_ns'] for s in sends],dtype=np.int64)
    after=np.array([s['after_ns'] for s in sends],dtype=np.int64)
    send_p=np.array([s['position'] for s in sends],np.float32).astype(float)
    send_v=np.array([s['velocity'] for s in sends],np.float32).astype(float)
    send_y=np.array([s['yaw'] for s in sends],np.float32).astype(float)
    matched=[];ambiguous=[];unknown=[];used=set();previous=0;last_id=-1
    for k in np.flatnonzero(t['external_valid']):
        wall=int(t['read_wall_ns'][k]);start=int(t['run_wall_ns'][k])
        if wall<before[0] or start>after[-1]+20_000_000:continue
        eligible=np.flatnonzero((before<=wall)&(np.arange(len(sends))>last_id)&
            np.all(send_p==ep[k],axis=1)&np.all(send_v==ev[k],axis=1)&(send_y==float(t['external_yaw'][k])))
        if len(eligible)!=1:
            record={'native_us':int(t['timestamp'][k]),'candidates':[int(sends[j]['send_id']) for j in eligible]}
            (ambiguous if len(eligible)>1 else unknown).append(record);continue
        j=int(eligible[0]);last_id=j;used.add(j)
        matched.append({'send_id':sends[j]['send_id'],'native_read_us':int(t['timestamp'][k]),
            'sample_us':int(t['timestamp_sample'][k]),'LP_sample_us':int(t['local_position_sample'][k]),
            'sample_minus_LP_us':int(t['timestamp_sample'][k])-int(t['local_position_sample'][k]),
            'send_profile_s':sends[j]['profile_s'],
            'host_read_interval_ns':[start,wall],
            'send_to_read_interval_us':[max(0.,(start-after[j])/1000),max(0.,(wall-before[j])/1000)]})
    events=[];stale=t['stale'].astype(bool);active=t['active'].astype(bool)
    for k in np.flatnonzero(active & np.r_[False,stale[1:]!=stale[:-1]]):
        events.append({'kind':'CAPTURE_OR_STALE' if stale[k] else 'RESUME','native_us':int(t['timestamp'][k]),
            'sample_us':int(t['timestamp_sample'][k]),'LP_age_us':int(t['timestamp_sample'][k])-int(t['local_position_sample'][k]),
            'last_read_age_us':int(t['timestamp'][k])-int(t['last_valid_read_us'][k]) if t['last_valid_read_us'][k] else None,
            'native_query_host_interval_ns':[int(t['read_wall_ns'][k-1]) if k else None,int(t['run_wall_ns'][k])],
            'read_host_interval_ns':[int(t['run_wall_ns'][k]),int(t['read_wall_ns'][k])]})
    intervals=[x['send_to_read_interval_us'] for x in matched]
    durations=[x['previous_sidecar_ns']/1000 for x in sends if x.get('previous_sidecar_ns') is not None]
    report={'schema':'p11-sync-check-1','raw_send_sha256':sha(run/'p11-sends.jsonl'),'sends':len(sends),
        'matched_valid_reads':len(matched),'ambiguous_reads':ambiguous,'unmatched_valid_reads':unknown,
        'unconsumed_or_unmatched_send_ids':[sends[k]['send_id'] for k in range(len(sends)) if k not in used],
        'latency_lower_us':stats([x[0] for x in intervals]),'latency_upper_us':stats([x[1] for x in intervals]),
        'publish_call_us':stats((after-before)/1000),'publish_plus_sidecar_us':stats(durations),
        'whole_sidecar_accounting':'each emission logs preceding complete duration; last duration is retained in p1_reference_stopped event',
        'phase_bins_sample_minus_LP_us':{str(x):sum(m['sample_minus_LP_us']==x for m in matched) for x in sorted({m['sample_minus_LP_us'] for m in matched})},
        'event_transitions':events,'phase_interpretation':'measured read/capture phases only; intent is not native phase. Group overlap must be reported NOT_IDENTIFIABLE.',
        'status':'PASS' if not ambiguous and not unknown and len(matched)>0 else 'FAIL',
        'latest_value_semantics':'unconsumed send IDs are recorded, not automatically called logger loss; every native control row is checked separately'}
    write(out/'matching.json',{'matches':matched});write(out/'synchronization.json',report)
    print(json.dumps({k:report[k] for k in ['status','sends','matched_valid_reads','ambiguous_reads','unmatched_valid_reads','latency_upper_us','publish_plus_sidecar_us']}))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=check(a.run,a.output);raise SystemExit(0 if r['status']=='PASS' else 1)

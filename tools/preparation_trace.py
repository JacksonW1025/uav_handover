#!/usr/bin/env python3
"""Describe observation skew and ESC bridge selection; never claim physics acknowledgement."""
import argparse,json
from pathlib import Path
import numpy as np
from pyulog import ULog

def stats(values):
    a=np.asarray(values,dtype=np.float64)
    if not len(a):return None
    return {'count':len(a),'min':float(a.min()),'p50':float(np.percentile(a,50)),
            'p95':float(np.percentile(a,95)),'p99':float(np.percentile(a,99)),'max':float(a.max())}

def analyze(folder):
    topics={d.name:d.data for d in ULog(str(folder/'flight.ulg')).data_list if d.multi_id==0}
    out={'scope':'Preparation measurement; no new latency FAIL threshold.',
         'physics_consumption_proven':False,'coverage':'Row distributions cover logged rows only; bridge counters cover calls through the final recorded snapshot.',
         'observations':{},'bridge':{}}
    t=topics.get('research_timing',{});b=topics.get('research_output',{})
    if not t or 'attitude_sample' not in t or not b:
        out['status']='MISSING_TRACE';return out
    called=t['executor_called'].astype(bool)
    for label,scope in [('whole',called),('active',called&t['active'].astype(bool)),('neural_publication',called&t['actuator_published'].astype(bool))]:
        sample=t['timestamp_sample'][scope].astype(np.int64)
        local=t['local_position_sample'][scope].astype(np.int64);att=t['attitude_sample'][scope].astype(np.int64)
        publish=t['actuator_publish_sim_us'][scope].astype(np.int64)
        start=t['control_start_wall_ns'][scope].astype(np.int64);end=t['control_end_wall_ns'][scope].astype(np.int64)
        out['observations'][label]={'gyro_minus_position_us':stats(sample-local),'gyro_minus_attitude_us':stats(sample-att),
            'position_later_than_gyro_rows':int(sum(local>sample)),'attitude_later_than_gyro_rows':int(sum(att>sample)),
            'run_sim_age_us':stats(t['timestamp'][scope].astype(np.int64)-sample),
            'control_wall_duration_us':stats((end-start)/1000),
            'publish_sim_age_us':stats(publish[publish>0]-sample[publish>0])}
    sample=b['timestamp_sample'].astype(np.int64);now=b['timestamp'].astype(np.int64)
    mask=(sample>0)&b['transport_published'].astype(bool)&b['armed'].astype(bool)
    out['bridge']={'attempts_total':int(b['attempts_total'][-1]),'published_total':int(b['published_total'][-1]),
        'repeated_selected_sample_total':int(b['repeated_sample_total'][-1]),
        'regressed_selected_sample_total':int(b['regressed_sample_total'][-1]),'negative_age_total':int(b['negative_age_total'][-1]),
        'age_bins_all_runtime':{label:int(b[f'age_bins[{i}]'][-1]) for i,label in enumerate(['<=0ms','(0,4]ms','(4,8]ms','(8,12]ms','(12,20]ms','(20,40]ms','(40,100]ms','>100ms'])},
        'armed_published_age_us_logged':stats(now[mask]-sample[mask]),
        'meaning':'Output provider selected timestamp_sample and GZ transport Publish returned success; repeated sample means command hold, not duplicate GRU commit.'}
    owner=topics.get('research_actuator',{})
    if owner and sum(mask):
        idx=np.searchsorted(owner['timestamp'],now,side='right')-1
        authority=np.where(idx>=0,owner['owner'][np.maximum(idx,0)],0)
        neural=mask&(authority==1)
        out['bridge']['neural_owner_interval_age_us_logged']=stats(now[neural]-sample[neural])
        # Match only a prior neural action with the same acquisition ID in host monotonic time.
        published=called&t['actuator_published'].astype(bool)
        by_sample={int(t['timestamp_sample'][i]):i for i in np.flatnonzero(published)}
        durations=[];matched=0
        for i in np.flatnonzero(neural):
            j=by_sample.get(int(sample[i]))
            if j is not None:
                elapsed=int(b['wall_monotonic_ns'][i])-int(t['actuator_publish_wall_ns'][j])
                if elapsed>=0:durations.append(elapsed/1000);matched+=1
        out['bridge']['neural_logged_sample_matches']=matched
        out['bridge']['neural_publish_to_bridge_wall_us_matched_logged']=stats(durations)
        out['bridge']['authority_limit']='Backward publisher interval uses discrete HRT timestamps; tied handover rows have ordering uncertainty.'
    out['status']='MEASURED';return out

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);args=p.parse_args()
    result=analyze(args.run);(args.run/'preparation-trace.json').write_text(json.dumps(result,indent=2)+'\n')
    print(result['status'])

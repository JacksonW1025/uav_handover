#!/usr/bin/env python3
"""Read-only latency/publication audit of selected ULogs; never claim downstream delivery."""
import hashlib,json
from pathlib import Path
import numpy as np
from pyulog import ULog
ROOT=Path(__file__).resolve().parents[1]
def distribution(a):
    return ({'count':len(a),**{f'p{p}_us':float(np.percentile(a,p)) for p in [50,95,99]},'max_us':int(max(a)),
             'negative_count':int(sum(a<0)),'over_4000_count':int(sum(a>4000)),'over_4000_ratio':float(np.mean(a>4000))} if len(a) else None)
def scope(t,mask):
    valid=t['executor_called'].astype(bool)&mask
    sample=t['timestamp_sample'].astype(np.int64);now=t['timestamp'].astype(np.int64)
    accepted=t['accepted_total'].astype(np.int64);age=now-sample
    runs=[];current=[]
    for i in range(len(now)):
        if valid[i] and age[i]>4000:
            if current and (i!=current[-1]+1 or accepted[i]!=accepted[current[-1]]+1):runs.append(current);current=[]
            current.append(i)
        elif current:runs.append(current);current=[]
    if current:runs.append(current)
    episodes=[{'calls':len(r),'first_sample_us':int(sample[r[0]]),'last_sample_us':int(sample[r[-1]]),
               'sample_span_us':int(sample[r[-1]]-sample[r[0]]),'processing_span_us':int(now[r[-1]]-now[r[0]]),
               'max_age_us':int(max(age[r]))} for r in runs]
    pairs=valid[1:]&valid[:-1]&(np.diff(accepted)==1)
    same=pairs&(np.diff(now)==0)&(np.diff(sample)>0)
    right=np.flatnonzero(same)+1
    return {'latency':distribution(age[valid]),'same_tick_distinct_sample_pairs':len(right),
            'same_tick_pairs_right_gru_committed':int(sum(t['gru_committed'][right])),
            'same_tick_pairs_right_actuator_published':int(sum(t['actuator_published'][right])),
            'nonincreasing_sample_pairs':int(sum(pairs&(np.diff(sample)<=0))),
            'over_target_episodes':episodes,'longest_observed_episode_calls':max([len(r) for r in runs],default=0),
            'longest_observed_episode_sample_span_us':max([e['sample_span_us'] for e in episodes],default=0)}
def main():
    selection=json.loads((ROOT/'data/p0-20261010/selection.json').read_text());out={'target_us':4000,'hard_gate':False,'status':'OPEN',
      'coverage':'Logged rows only. Missing accepted rows break episodes; episode lengths are lower bounds. HRT is simulation time, not host wall time. actuator_published proves uORB publication only, not ESC/Gazebo consumption.', 'runs':{}}
    for kind,folder in selection['raw_runs'].items():
        if kind=='classic_hover':continue
        path=ROOT/folder/'flight.ulg';topics={d.name:d.data for d in ULog(str(path)).data_list if d.multi_id==0};t=topics['research_timing']
        owner=topics['research_actuator'];idx=np.searchsorted(owner['timestamp'],t['timestamp'],side='right')-1
        neural=(idx>=0)&(owner['owner'][np.maximum(idx,0)]==1)|t['actuator_published'].astype(bool)
        out['runs'][kind]={'ulog_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
          'omitted_rows_between_first_last':int(t['accepted_total'][-1]-t['accepted_total'][0]+1-sum(t['executor_called'].astype(bool))),
          'active':scope(t,t['active'].astype(bool)),
          'exact_neural_publication':scope(t,t['actuator_published'].astype(bool)),
          'neural_ownership_interval':scope(t,neural)}
    out['analysis_code_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (ROOT/'data/p0-20261010/latency-audit.json').write_text(json.dumps(out,indent=2)+'\n')
if __name__=='__main__':main()

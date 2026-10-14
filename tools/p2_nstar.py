#!/usr/bin/env python3
"""Extract the N* memory (GRU 16 + previous action 4) from a RAPTOR S1 baseline at the handover phase.

Phase = trigger + the C->N trigger-to-owner-change delay (median of the given C->N runs). The staged memory is the
state RAPTOR itself had before the next inference at that phase: the committed GRU after native step k and the
action output by step k (research_timing, same timestamp_sample). Writes nstar-memory.json; never edits runs.
"""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from pyulog import ULog
ROOT=Path(__file__).resolve().parents[1]

def state_at(run,t):
    u=ULog(str(run/'flight.ulg'),['research_memory','research_timing'])
    d={x.name:x.data for x in u.data_list if x.multi_id==0};m,rt=d['research_memory'],d['research_timing']
    rows=np.flatnonzero((m['kind']==1)&(m['native_step']==1)&(m['active']==1)&(m['timestamp'].astype(np.int64)>=t))
    k=int(rows[0]);sample=int(m['timestamp_sample'][k])
    j=np.flatnonzero((rt['timestamp_sample'].astype(np.int64)==sample)&(rt['control_step']==1))
    gru=[float(m[f'gru[{i}]'][k]) for i in range(16)];action=[float(rt[f'action[{i}]'][j[-1]]) for i in range(4)]
    # Variability of the committed GRU over +-0.5 s around the phase (stationarity of the hover state).
    w=np.flatnonzero((m['kind']==1)&(m['native_step']==1)&(m['active']==1)&(np.abs(m['timestamp'].astype(np.int64)-t)<=500000))
    g=np.stack([m[f'gru[{i}]'][w] for i in range(16)],1)
    return {'px4_us':int(m['timestamp'][k]),'timestamp_sample':sample,'gru':gru,'action':action,
            'gru_std_pm_0p5s':g.std(0).tolist(),'gru_norm':float(np.linalg.norm(gru))}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path)
    p.add_argument('--baselines',type=Path,nargs='+',required=True);p.add_argument('--c-to-n',type=Path,nargs='+',required=True)
    p.add_argument('--use',type=int,default=0,help='index of the baseline whose state is staged');a=p.parse_args()
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    delays=[json.loads((r/'p2-metrics.json').read_text())['delays_ms']['trigger_to_change'] for r in a.c_to_n]
    phase_ms=float(np.median(delays));states=[]
    for b in a.baselines:
        trig=json.loads((b/'p2-metrics.json').read_text())['trigger_px4_us']
        states.append({'run':str(b.resolve().relative_to(ROOT)),'trigger_px4_us':trig,**state_at(b.resolve(),trig+int(phase_ms*1000)),
                       'ulog_sha256':hashlib.sha256((b/'flight.ulg').read_bytes()).hexdigest()})
    chosen=states[a.use];values=chosen['gru']+chosen['action']
    spread=np.max([np.linalg.norm(np.array(s['gru'])-np.array(chosen['gru'])) for s in states])
    result={'values':values,'source':chosen['run'],'phase':{'definition':'trigger + median C->N trigger-to-owner-change delay','delay_ms':phase_ms,'c_to_n_runs':[str(r.resolve().relative_to(ROOT)) for r in a.c_to_n],'delays_ms':delays},
            'layout':'GRU hidden state [0:16] committed after native step k, previous action [16:20] = action output by step k',
            'baselines':states,'max_gru_distance_between_baselines':float(spread)}
    (out/'nstar-memory.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'values':values,'phase_ms':phase_ms,'spread':spread}))
if __name__=='__main__':main()

#!/usr/bin/env python3
"""P4 pre-batch verification that the independent run conditions take effect; writes <output>/independence.json.

(1) Seed: startup-only runs (never armed) with Gazebo seeds A, A, B. Gazebo sensor noise is drawn from one global
generator; the at-rest raw gyro samples (sensor_gyro x, y, z, rounded to 1e-7) of two runs are compared as sets of
exact triplets. Same seed -> shared exact noise draws; different seed -> none. (Sample-by-sample identity is not
expected: the IMU, barometer and magnetometer systems draw from the shared generator in a run-dependent order.)
(2) Development flights: planned seed on the Gazebo command line, heading before arming = heading_at_zero - yaw, and
the measured takeover values of runs with different seeds/headings.
"""
import argparse,json
from pathlib import Path
import numpy as np
from pyulog import ULog
ROOT=Path(__file__).resolve().parents[1]

def gyro_triplets(run):
    g=ULog(str(run/'flight.ulg'),['sensor_gyro']).data_list[0].data
    return [tuple(np.round([g[k][i] for k in 'xyz'],7)) for i in range(len(g['x']))]

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path)
    p.add_argument('--startup',nargs='+',required=True,help='startup-only run directories (label=dir)')
    p.add_argument('--flights',nargs='*',default=[],help='development flight run directories')
    a=p.parse_args();out={'startup':{},'pairs':[],'flights':[]}
    runs={}
    for item in a.startup:
        label,_,d=item.partition('=');run=(ROOT/d).resolve();meta=json.loads((run/'metadata.json').read_text())
        gz=next(x['command'] for x in meta['processes'] if x['name']=='gazebo');t=gyro_triplets(run);runs[label]=(meta.get('sim_seed'),t)
        out['startup'][label]={'run':str(run.relative_to(ROOT)),'sim_seed':meta.get('sim_seed'),'gazebo_seed_argument':gz[gz.index('--seed')+1] if '--seed' in gz else None,
            'gyro_samples':len(t),'distinct_triplets':len(set(t))}
    labels=list(runs)
    for i in range(len(labels)):
        for j in range(i+1,len(labels)):
            (sa,ta),(sb,tb)=runs[labels[i]],runs[labels[j]];pos={x:k for k,x in enumerate(tb)}
            hits=[(k,pos[x]) for k,x in enumerate(ta) if x in pos]
            out['pairs'].append({'a':labels[i],'b':labels[j],'same_seed':sa==sb,'shared_exact_gyro_triplets':len(hits),
                                 'shared_index_range_a':[hits[0][0],hits[-1][0]] if hits else None,'index_offset_b_minus_a':sorted({b-a_ for a_,b in hits})[:5] if hits else None})
    out['seed_effective']=all((x['shared_exact_gyro_triplets']>0)==x['same_seed'] for x in out['pairs'])
    for d in a.flights:
        run=(ROOT/d).resolve();m4=json.loads((run/'p4-metrics.json').read_text()) if (run/'p4-metrics.json').exists() else {}
        mname='p3-metrics.json' if (run/'p3-metrics.json').exists() else 'p2-metrics.json';m=json.loads((run/mname).read_text())
        if mname=='p3-metrics.json':
            ev={n:{'motor_step_at_change':e['motor']['step_at_change'],'max_altitude_loss_m':e['max_altitude_loss_m'],'yaw_at_change_deg':e['state_at_change']['yaw_deg']} for n,e in m.get('events',{}).items()}
        else:ev={'subject':{'motor_step_at_change':m['auxiliary']['motor']['step_at_change'],'max_altitude_loss_m':m['primary']['max_altitude_loss_m']}}
        out['flights'].append({'run':str(run.relative_to(ROOT)),'independence':m4.get('independence'),'p4_status':m4.get('status'),'events':ev})
    (a.output).mkdir(parents=True,exist_ok=True);(a.output/'independence.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
    print('seed_effective',out['seed_effective']);[print(x) for x in out['pairs']]
    return 0 if out['seed_effective'] else 1
if __name__=='__main__':raise SystemExit(main())

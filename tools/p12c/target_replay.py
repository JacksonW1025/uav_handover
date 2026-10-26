#!/usr/bin/env python3
"""Independent P12 capture branch replay with actual exogenous inputs, not prediction."""
import argparse,json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p12.state import EventTarget
from p9_model import write,sha


def replay(sync,config,out):
    out.mkdir(parents=True,exist_ok=False);d=dict(np.load(sync));cfg=json.loads(config.read_text())
    events=[json.loads(x) for x in (config.parent/'events.jsonl').read_text().splitlines()]
    gate=next((e['not_before_sample_ms']*1000 for e in events if e['event']=='p12_planned_repair_window'),None)
    if cfg['p12'].get('repair_sample_window') and gate is None:raise RuntimeError('missing actual repair-window readback event')
    state=EventTarget(cfg['p12']['repair']);errors=[];stale=0;prediction=[]
    for k in range(len(d['sample_us'])):
        state.repair=cfg['p12']['repair'] and (gate is None or int(d['sample_us'][k])>=gate)
        message=(d['external_p'][k],d['external_v'][k],d['external_yaw'][k]) if d['read_valid'][k] else None
        r,v,y,s=state.step(int(d['native_us'][k]),int(d['sample_us'][k]),d['position'][k],d['velocity'][k],d['attitude'][k],message,k==0)
        errors.append([max(abs(r-d['target_p'][k])),max(abs(v-d['target_v'][k])),abs(np.arctan2(np.sin(y-d['target_yaw'][k]),np.cos(y-d['target_yaw'][k])))])
        stale+=s!=bool(d['stale'][k]);prediction.append(np.r_[r,v,y])
    maxima=np.max(errors,axis=0)
    result={'schema':'p12-cont-target-replay-2','status':'PASS' if max(maxima)<1e-5 and stale==0 else 'FAIL',
        'rows':len(errors),'max_position_m':float(maxima[0]),'max_velocity_m_s':float(maxima[1]),'max_yaw_rad':float(maxima[2]),
        'stale_mismatch':int(stale),'events':state.events,'sync_sha256':sha(sync),'config_sha256':sha(config),
        'scope':'actual exogenous p/v/q, read messages and clocks; one target initialization; NOT blind closed-loop prediction'}
    np.savez_compressed(out/'target.npz',target=np.array(prediction));write(out/'target-replay.json',result)
    print(json.dumps(result));return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('sync',type=Path);p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=replay(a.sync,a.config,a.output);raise SystemExit(r['status']!='PASS')

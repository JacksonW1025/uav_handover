#!/usr/bin/env python3
"""Blind M3/M4 baselines and ONE P13 source-vertical COM candidate."""
import sys,json,hashlib,time
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from p12.models import forecast as M3
from p12c.models import forecast as M4
from p13.models import forecast as M5

def main():
 import argparse
 p=argparse.ArgumentParser()
 for k in ['input','models','policy','output']:p.add_argument('--'+k,type=Path,required=True)
 a=p.parse_args();doc=json.load(open(a.input));models=json.load(open(a.models));policy=dict(np.load(a.policy));digest=lambda x:hashlib.sha256(x.read_bytes()).hexdigest()
 if doc['model_sha256']!=digest(a.models):raise RuntimeError('model identity mismatch')
 visible=any(Path('/home/car/uav_handover/data').iterdir())
 if visible:raise RuntimeError('future data accessible')
 a.output.mkdir(parents=True,exist_ok=False);meta={'schema':'p13-forecast-1','models':{},'input_sha256':digest(a.input),'model_sha256':digest(a.models),'policy_arrays_sha256':digest(a.policy),'filesystem_future_data_visible':visible,'formal_validation':doc['plan']['evaluation_split']=='heldout','one_new_candidate':'M5 source vertical COM; inherited empirical angular/horizontal/cache closures, no coverage certificate'}
 for name,f in [('M3',M3),('M4',M4),('M5',M5)]:
  t=time.perf_counter();r=f(doc,models['M2'],policy);trace=r.pop('trace');nt=r.pop('native_us');np.savez_compressed(a.output/(name+'.npz'),trace=trace,native_us=nt);meta['models'][name]=dict(r,compute_s=time.perf_counter()-t)
 (a.output/'prediction.json').write_text(json.dumps(meta,indent=2,allow_nan=False)+'\n')
 print({k:{'stop':v['stop'],'compute_s':v['compute_s']} for k,v in meta['models'].items()})
if __name__=='__main__':main()

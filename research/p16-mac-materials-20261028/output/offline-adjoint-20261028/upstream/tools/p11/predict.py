#!/usr/bin/env python3
"""Sandbox prediction entry: sanitized input+model+policy only. No scoring/log loading."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import numpy as np
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from p11.models import forecast,assert_input


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True)
    p.add_argument('--models',type=Path,required=True);p.add_argument('--policy',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    doc=json.loads(a.input.read_text());assert_input(doc)
    if doc['model_sha256']!=sha(a.models):raise RuntimeError('frozen model hash mismatch')
    models=json.loads(a.models.read_text());P=dict(np.load(a.policy));a.output.mkdir(parents=True,exist_ok=False)
    meta={'input_sha256':sha(a.input),'model_sha256':sha(a.models),'policy_arrays_sha256':sha(a.policy),
        'filesystem_future_data_visible':any(Path('/home/car/uav_handover/data').iterdir()),'models':{}}
    if meta['filesystem_future_data_visible']:raise RuntimeError('run the prediction entry with future data hidden')
    for name,model in models.items():
        started=time.perf_counter();r=forecast(doc,model,P)
        np.savez_compressed(a.output/(name+'.npz'),trace=r.pop('trace'))
        meta['models'][name]={**r,'compute_s':time.perf_counter()-started}
    (a.output/'prediction.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(meta))


if __name__=='__main__':main()

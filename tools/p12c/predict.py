#!/usr/bin/env python3
"""Isolated M3 candidate + four fixed ablations; same initial/plan/coefficients."""
import argparse,hashlib,json,time,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from p11.models import forecast as baseline
from p12.models import forecast as M3_forecast
from p12c.models import forecast


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['input','models','policy','output']:p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();doc=json.loads(a.input.read_text());models=json.loads(a.models.read_text());P=dict(np.load(a.policy))
    if doc['model_sha256']!=sha(a.models):raise RuntimeError('model hash mismatch')
    visible=any(Path('/home/car/uav_handover/data').iterdir())
    if visible:raise RuntimeError('future data visible; isolated entry required')
    a.output.mkdir(parents=True,exist_ok=False)
    meta={'input_sha256':sha(a.input),'model_sha256':sha(a.models),'policy_arrays_sha256':sha(a.policy),
        'filesystem_future_data_visible':visible,'models':{},'formal_validation':doc['plan'].get('evaluation_split')=='heldout',
        'meaning':'autonomous empirical closed-loop candidate; actual futures inaccessible; no coverage certificate'}
    for name,abl in [('M4',None),('single_clock','single_clock'),('no_history','no_history'),
                      ('no_filter','no_filter'),('uncorrelated_capture','uncorrelated_capture')]:
        started=time.perf_counter();r=forecast(doc,models['M2'],P,abl)
        np.savez_compressed(a.output/(name+'.npz'),trace=r.pop('trace'),native_us=r.pop('native_us'))
        meta['models'][name]={**r,'compute_s':time.perf_counter()-started}
    started=time.perf_counter();r=M3_forecast(doc,models['M2'],P)
    np.savez_compressed(a.output/'M3.npz',trace=r.pop('trace'),native_us=r.pop('native_us'))
    meta['models']['M3']={**r,'compute_s':time.perf_counter()-started,'baseline_scope':'P12 M3 unchanged, no explicit continuation sample-window'}
    started=time.perf_counter();r=baseline(doc,models['M2'],P)
    np.savez_compressed(a.output/'M2.npz',trace=r.pop('trace'))
    meta['models']['M2']={**r,'compute_s':time.perf_counter()-started,
        'baseline_scope':'P11 frozen M2 unchanged; its repair semantics differ from P12 when P12R enabled'}
    (a.output/'prediction.json').write_text(json.dumps(meta,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'models':list(meta['models']),'future_data_hidden':True}))


if __name__=='__main__':main()

#!/usr/bin/env python3
"""Offline P12 continuation numerical reproduction in a NEW directory; no SITL."""
import argparse,json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p9_model import sha,write
from p12c.workflow import process

def main():
 p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--models',type=Path,default=ROOT/'data/p12-cont-20261026-freeze/models');p.add_argument('--compare',type=Path);a=p.parse_args()
 seal=json.loads((a.models/'seal.json').read_text())
 for name,key in [('models.json','model_sha256'),('policy.npz','policy_arrays_sha256'),('fit.json','fit_sha256')]:
  if sha(a.models/name)!=seal[key]:raise RuntimeError('sealed model drift')
 process(a.run,a.output,a.models);checks={}
 if a.compare:
  for file in (a.output/'prediction').glob('*.npz'):
   old=np.load(a.compare/'prediction'/file.name);fresh=np.load(file)
   checks[file.name]=fresh.files==old.files and all(np.array_equal(fresh[k],old[k],equal_nan=True) for k in fresh.files)
  fresh_models=json.loads((a.output/'score/score.json').read_text())['models'];old_models=json.loads((a.compare/'score/score.json').read_text())['models']
  checks['score_metrics_excluding_compute_time']={k:{j:v for j,v in d.items() if j!='compute_s'} for k,d in fresh_models.items()}=={k:{j:v for j,v in d.items() if j!='compute_s'} for k,d in old_models.items()}
  if not all(checks.values()):raise RuntimeError('reproduction differs; retained new outputs')
 write(a.output/'reproduction.json',{'schema':'p12-cont-reproduction-1','status':'PASS','new_SITL_starts':0,'all_arrays_and_scores':checks,'model_seal_sha256':sha(a.models/'seal.json'),'future_logs_hidden':True,'scope':'known-input replay and isolated empirical predictions, not flight re-execution or full plant certificate'})
 print('PASS offline; SITL starts0')
if __name__=='__main__':main()

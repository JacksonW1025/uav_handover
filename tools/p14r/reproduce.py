"""Offline-only reproductions. Never imports or invokes an experiment launcher.

All targets must be new. Long set calculations are opt-in, bounded by resources.
"""
import argparse,json,time,resource
from pathlib import Path
import sys
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p14.common import write,sha

def main():
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['quick','no-compression','continue']);p.add_argument('output',type=Path);p.add_argument('--cpu-seconds',type=int,default=900);a=p.parse_args();out=a.output;out.mkdir(parents=True,exist_ok=False);b=R/'data/p14r-20261027';doc=json.load(open(b/'source-inputs-v3/d02/input.json'));other=json.load(open(b/'source-inputs-v3/d03/input.json'));P=dict(np.load(R/'data/p13-20261026-freeze/models/policy.npz'));lib=b/'offline-build-v2/libop.bin'
 write(out/'before-compute.json',{'mode':a.mode,'source':sha(Path(__file__)),'cpu_seconds':a.cpu_seconds,'memory_GiB':48,'scope':'offline only; no future actual input, no new flight; long cases repeat one named quarter/clock fiber only'})
 if a.mode=='quick':
  from p14r.model import forecast
  end=doc['initial']['profile_s']+.08;r=forecast(doc,{},P,observer_library=lib,limit=end);z=forecast(doc,{},P,observer_library=lib,limit=end);err={k:float(np.max(abs(r[k]-z[k]))) for k in ['states','trace','inputs'] if np.isfinite(r[k]).all()};assert all(v==0 for v in err.values());write(out/'result.json',{'repeat_max_difference':err,'first_input_nan_is_intentional':bool(np.isnan(r['inputs'][0]).all()),'new_SITL':0});return
 resource.setrlimit(resource.RLIMIT_CPU,(a.cpu_seconds,a.cpu_seconds));resource.setrlimit(resource.RLIMIT_AS,(48*1024**3,48*1024**3))
 from p14r.affine import install
 from p14r import tube
 install(True);cp=None
 if a.mode=='continue':
  cp=b/'C-no-compression-full-v1/regions/resume';windows=doc['plan']['full_source_windows_profile_s'];doc['plan']['windows_profile_s']=[windows[0],windows[1]];end=windows[1][0]+.25
 else:end=doc['plan']['full_source_windows_profile_s'][1][1]+2
 old=tube.metrics
 def metric(s,nom):
  r=old(s,nom)
  with (out/'metric-prefix.jsonl').open('a') as f:f.write(json.dumps(r)+'\n')
  return r
 tube.metrics=metric
 result,s=tube.run(doc,P,0,end=end,compress_rank=None,group=True,observer_library=lib,joint_doc=other,joint_segment=(0,.25),liveness=True,restore_region=cp,region_output=out/'regions');write(out/'result.json',result)
 np.savez_compressed(out/'last-region.npz',**{k+'_center':v.c for k,v in s.items()},**{k+'_generators':v.pad() for k,v in s.items()})
if __name__=='__main__':main()

"""Short conditional-real-map point inclusion and source relation audit."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from p14g.common import *

def main():
 out=Path(sys.argv[1]);register(out,'before batch: real-map endpoint membership, copy and source graph relations; no float32 coverage claim');from p14r.affine import install
 install(True)
 from p14g.tube import run
 d=doc('d02');e=doc('d03');P=dict(np.load(R/'data/p13-20261026-freeze/models/policy.npz'));lib=OLD/'offline-build-v2/libop.bin';end=d['initial']['profile_s']+.064;result,s=run(d,P,0,end=end,compress_rank=-512,group=True,observer_library=lib,joint_doc=e,joint_segment=(0,.25),liveness=True,relations='all');rows=[]
 for endpoint in [0,.25]:
  r,p=run(d,P,0,end=end,compress_rank=None,group=True,observer_library=lib,joint_doc=e,joint_segment=(endpoint,endpoint),liveness=True,relations='all');missing={}
  for key in s:
   low,high=s[key].bounds();v=p[key].c;missing[key]=float(max(np.max(low-v),np.max(v-high),0))
  rows.append({'endpoint':endpoint,'component_centers_outside_max':max(missing.values()),'not_claimed':'real-algebra center inclusion regression, not continuous nonlinear proof or source-float certificate'});assert max(missing.values())<1e-9
 write(out/'result.json',{'rows':rows,'copy_capture':result['capture_alias'],'same_G_origin':True,'D0_never_reset':result['D_joint_state'],'active_prefix_calls':len(result['rows'])})
if __name__=='__main__':main()

"""Essential actual runtime snapshots and source/hash gate; no SITL."""
import sys,json,shutil,subprocess
from pathlib import Path
import numpy as np
from p16.common import *
from preparation_batch import identity
from p16.greybox import MAT,OUT,ENTRY,core

def make(out):
 out=Path(out);out.mkdir(exist_ok=False,parents=True);anchor=identity();files=dict(anchor['files']);lab=R/'uav_lab/.local/checkouts/px4-raptor';runtime=[lab/'build/px4_sitl_raptor/bin/px4',lab/'src/modules/mc_raptor/blob/policy.tar',lab/'build/px4_sitl_raptor/src/modules/simulation/gz_plugins/libResearchMulticopterMotorModel.so']
 for p in runtime:
  q=out/(p.name+'.bin');shutil.copyfile(p,q);files[str(p.relative_to(R))]=sha(p);assert sha(q)==sha(p)
 from p3_memory import load_policy
 P=load_policy(runtime[1]);checks={k:float(np.max(abs(np.asarray(v)-np.asarray(P[k])))) for k,v in core.reference.P.items() if k in P and isinstance(P[k],np.ndarray)};assert checks and max(checks.values())==0.,checks
 for f in ['p11/state.py','p11/observe.py','p11/models.py','p12/state.py','p12/execution.py']:
  assert sha(R/'tools'/f)==sha(OUT/'offline-adjoint-20261028/upstream/tools'/f)
 write(out/'candidate.json',anchor);write(out/'gate.json',dict(status='PASS',time=now(),files=files,policy_array_maxdiff=checks,source='existingbinary/plugin/weights, P16 minimal observer off for heavyOP/fullP, no builds',model_adoption=verify_model_adoption(B/'model-adoption.json')))
 return out/'gate.json'
if __name__=='__main__':print(make(sys.argv[1]))

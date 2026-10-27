"""Finite C second stage: fair512 directions, analytic local Hessian,4 seed splits."""
import sys,json,subprocess,time
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p14.common import write,sha
out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False)
old='data/p14-motion-20261027/inputs-v3/p13-F2-b1-AB-short/edge-input.json';new='data/p14r-20261027/source-inputs-v2/d02/input.json';joint='data/p14r-20261027/source-inputs-v2/d03/input.json'
jobs=[dict(input=old,source_observer=False,improved=True,scale=r,horizon='full',rank=512) for r in [0,.001,1]]
jobs += [dict(input=new,source_observer=True,improved=True,scale=0,horizon='full',rank=512)]
jobs += [dict(input=new,joint_input=joint,source_observer=True,improved=True,quadratic=True,scale=0,horizon='full',rank=512,segment=[a,a+.25]) for a in [0,.25,.5,.75]]
write(out/'before-compute.json',{'jobs':jobs,'reason':'rank64 v1 loses feedback directions; restore original512 fair scale. Local analytic sigmoid/tanh Hessian bounds and4 predeclared seed-origin subintervals; no threshold or actual initial domain narrowing','previous_failure':'C-tubes-v1 preserved including baseline accounting exception','source_hashes':{str(p.relative_to(R)):sha(p) for p in (R/'tools/p14r').glob('*.py')},'CPU_remaining_s':6500,'future_EKF_budget':'held initial innovation conditional, no claim true record coverage','state_domain':'physical normalized source q; estimated q and LP frame independent'})
rows=[]
for n,job in enumerate(jobs):
 target=out/f'{n:02d}';target.mkdir();write(target/'job.json',job);st=time.perf_counter()
 with (target/'compute.log').open('w') as log:
  try:rc=subprocess.run([str(R/'uav_lab/.local/venv/bin/python'),str(R/'tools/p14r/run_tubes.py'),'child',str(target/'job.json'),str(target)],stdout=log,stderr=subprocess.STDOUT,timeout=min(1000,max(1,6500-sum(x['elapsed_s'] for x in rows)))).returncode
  except subprocess.TimeoutExpired:rc='COMPUTE_BUDGET'
 rows.append({'job':n,'rc':rc,'elapsed_s':time.perf_counter()-st});write(out/f'progress-{n:02d}.json',rows[-1]);print(rows[-1],flush=True)
write(out/'execution.json',rows)

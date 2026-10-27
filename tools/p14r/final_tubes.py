"""C final semantic rerun; queue survives forbidden native reads.
Prior v1-v4 results retained as implementation-affected, no safety relabel.
"""
import sys,json,time,subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p14.common import write,sha
out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);old='data/p14-motion-20261027/inputs-v3/p13-F2-b1-AB-short/edge-input.json';new='data/p14r-20261027/source-inputs-v3/d02/input.json';other='data/p14r-20261027/source-inputs-v3/d03/input.json'
jobs=[]
for source,scale in [(False,0),(False,.001),(False,1),(True,0),(True,.001)]:jobs.append(dict(input=new if source else old,source_observer=source,improved=True,scale=scale,horizon='full',rank=512))
jobs += [dict(input=old,source_observer=False,improved=True,scale=.001,horizon=.064,rank=512,variant='box_each_call')]
for split in [None,[0,.25],[.25,.5],[.5,.75],[.75,1]]:jobs.append(dict(input=new,joint_input=other,source_observer=True,improved=True,quadratic=True,scale=0,horizon='full',rank=512,segment=split or [0,1]))
write(out/'before-compute.json',{'jobs':jobs,'reason':'new tube publisher returned None on non-publish calls and inadvertently overwrote unconsumed target slot before forbidden PH1 read. Pure offline semantic implementation error, prior C affected. Preserve queued message until actual allowed read, as Controller and real source. All previous attempts retained; scales/criteria/source platform unchanged.','first_affected':'C-tubes-v1/v2 and polynomial-v3/v4, not real controller or experiments','CPU_remaining_s':5000,'files':{str(p.relative_to(R)):sha(p) for p in (R/'tools/p14r').glob('*.py')}})
rows=[]
for n,job in enumerate(jobs):
 f=out/f'{n:02d}';f.mkdir();write(f/'job.json',job);st=time.perf_counter()
 with (f/'compute.log').open('w') as log:
  try:rc=subprocess.run([str(R/'uav_lab/.local/venv/bin/python'),str(R/'tools/p14r/run_tubes.py'),'child',str(f/'job.json'),str(f)],stdout=log,stderr=subprocess.STDOUT,timeout=500).returncode
  except subprocess.TimeoutExpired:rc='CPU_BUDGET'
 rows.append({'job':n,'rc':rc,'elapsed_s':time.perf_counter()-st});write(out/f'progress-{n:02d}.json',rows[-1]);print(rows[-1],flush=True)
write(out/'execution.json',rows)

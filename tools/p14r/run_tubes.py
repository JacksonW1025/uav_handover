"""Finite pre-registered propagation comparison; subprocesses isolate algebra."""
import sys,json,time,subprocess,resource
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p14.common import write,sha

def child(job,out):
 from p14r.affine import install
 if job['improved']:install(job.get('quadratic',False))
 from p14r.tube import run
 doc=json.load(open(R/job['input']));other=json.load(open(R/job['joint_input'])) if job.get('joint_input') else None;P=dict(np.load(R/'data/p13-20261026-freeze/models/policy.npz'));lib=R/'data/p14r-20261027/offline-build-v2/libop.bin' if job['source_observer'] else None
 if job['horizon']=='full':end=max(doc['plan']['full_source_windows_profile_s'][0][1]+2.1,doc['plan']['full_source_windows_profile_s'][1][1]+.5)
 else:end=doc['initial']['profile_s']+float(job['horizon'])
 result,s=run(doc,P,job['scale'],variant=job.get('variant','joint'),end=end,compress_rank=-job.get('rank',64),group=True,region_output=out/'regions',observer_library=lib,joint_doc=other,joint_segment=job.get('segment',(0.,1.)),liveness=job.get('liveness',False),relations=job.get('relations',False),capture_copy_exact=job.get('capture_copy_exact',False),innovation_budget=job.get('innovation_budget'))
 result.update(job=job,proof_scope='real conditional projected model; source-float32/libm/geodesy/future EKF and physical defects remain separate coverage obligations');write(out/'tube.json',result);np.savez_compressed(out/'last-region.npz',**{k+'_center':v.c for k,v in s.items()},**{k+'_generators':v.pad() for k,v in s.items()});print('C_RESULT',out.name,len(result['rows']),result['first_precision_loss'],result['first_domain_loss'],result['elapsed_s'],flush=True)

def main():
 if sys.argv[1]=='child':child(json.load(open(sys.argv[2])),Path(sys.argv[3]));return
 out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);inp='data/p14r-20261027/source-inputs-v2/d02/input.json';joint='data/p14r-20261027/source-inputs-v2/d03/input.json';old='data/p14-motion-20261027/inputs-v3/p13-F2-b1-AB-short/edge-input.json';jobs=[]
 for improved,source,scale,horizon,variant in [(False,False,0,.064,'joint'),(True,False,0,'full','joint'),(True,False,.001,'full','joint'),(True,False,1,'full','joint'),(True,False,.001,.064,'box_each_call'),(True,True,0,'full','joint'),(True,True,.001,'full','joint')]:
  jobs.append(dict(input=inp if source else old,improved=improved,source_observer=source,scale=scale,horizon=horizon,variant=variant))
 for polynomial in [False,True]:jobs.append(dict(input=inp,joint_input=joint,improved=True,quadratic=polynomial,source_observer=True,scale=0,horizon='full'))
 write(out/'before-compute.json',{'jobs':jobs,'maximum_total_CPU_s':7200,'scope':'finite source-NED observer projection plus old complement baseline, not complete EKF; all horizons fixed before results','no_threshold_or_support_selection':True,'code':{str(p.relative_to(R)):sha(p) for p in (R/'tools/p14r').glob('*.py')},'old_original_algebra_unchanged':sha(R/'tools/p14/affine.py')})
 rows=[];start=time.perf_counter()
 for n,job in enumerate(jobs):
  folder=out/f'{n:02d}';folder.mkdir();write(folder/'job.json',job);st=time.perf_counter()
  remaining=max(1,7200-sum(x['elapsed_s'] for x in rows))
  with (folder/'compute.log').open('w') as log:
   try:rc=subprocess.run([str(R/'uav_lab/.local/venv/bin/python'),str(Path(__file__)),'child',str(folder/'job.json'),str(folder)],stdout=log,stderr=subprocess.STDOUT,timeout=min(remaining,1200)).returncode
   except subprocess.TimeoutExpired:rc='COMPUTE_BUDGET'
  row={'job':n,'rc':rc,'elapsed_s':time.perf_counter()-st};rows.append(row);write(out/f'progress-{n:02d}.json',row);print('C_JOB',row,flush=True)
  if sum(x['elapsed_s'] for x in rows)>=7200:break
 write(out/'execution.json',{'rows':rows,'elapsed_s':time.perf_counter()-start,'failure_preserved':True})
if __name__=='__main__':main()

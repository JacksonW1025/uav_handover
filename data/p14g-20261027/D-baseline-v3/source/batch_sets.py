"""Bounded full-domain comparison, each job isolated and identically capped."""
import sys,json,time,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from p14g.common import *

def execute(job,out):
 limit(90);from p14r.affine import install
 install(True)
 from p14g import tube
 from p14g.compress import SETTINGS
 d=doc(job['fiber']);other=doc('d03' if job['fiber']=='d02' else 'd02') if job['panel']=='joint' else None
 if job.get('dynamic'):
  d=json.load(open(B/'inputs-v1'/job['fiber']/'input.json'));other=json.load(open(B/'inputs-v1'/('d03' if job['fiber']=='d02' else 'd02')/'input.json')) if other else None
 if job['variant']=='weighted':
  folder=B/('B-weights-v1' if job['fiber']=='d02' else 'B-weights-d03-v1');SETTINGS.update(weights=np.load(folder/'weights.npz'),layout=json.load(open(folder/'result.json'))['layout'])
 # Streaming each complete post-call metric saves information even at resource stop.
 old=tube.metrics
 def metric(s,nom):
  r=old(s,nom)
  with (out/'metric-prefix.jsonl').open('a') as f:f.write(json.dumps(r)+'\n')
  return r
 tube.metrics=metric;rank=None if job['variant']=='none' else -512;relations='all' if job['variant'] in ['relations','weighted'] else False;end=d['initial']['profile_s']+job['horizon_s'];t=time.perf_counter()
 result,s=tube.run(d,dict(np.load(R/'data/p13-20261026-freeze/models/policy.npz')),job['scale'],end=end,compress_rank=rank,group=True,region_output=out/'regions',observer_library=OLD/'offline-build-v2/libop.bin',joint_doc=other,joint_segment=job.get('segment',[0,1]),liveness=True,relations=relations,innovation_budget=job.get('innovation_budget'))
 result.update(job=job,wall_s=time.perf_counter()-t);write(out/'result.json',result);np.savez_compressed(out/'last-region.npz',**{k+'_center':v.c for k,v in s.items()},**{k+'_generators':v.pad() for k,v in s.items()});print('SET_DONE',len(result['rows']),result['first_domain_loss'])

def main():
 if sys.argv[1]=='child':execute(json.load(open(sys.argv[2])),Path(sys.argv[3]));return
 kind=sys.argv[1];out=Path(sys.argv[2]);jobs=[]
 if kind=='B':
  for panel in ['zero','small','joint']:
   for fiber in (['d02','d03'] if panel=='joint' else ['d02']):
    for segment in ([[a,a+.25] for a in [0,.25,.5,.75]] if panel=='joint' else [[0,1]]):
     for variant in ['default','none','relations','weighted']:jobs.append(dict(panel=panel,fiber=fiber,segment=segment,variant=variant,scale=.001 if panel=='small' else 0,horizon_s=.8 if panel=='joint' else .064))
 else:
  small=protocol()['C']['parameter_boxes']['small']
  for dynamic,mode in [(False,'persistent'),(False,'per_fusion'),(True,'persistent')]:
   for fiber in ['d02','d03']:
    for a in [0,.25,.5,.75]:jobs.append(dict(panel='joint',fiber=fiber,segment=[a,a+.25],variant='default',scale=0,horizon_s=.32,dynamic=dynamic,innovation_budget=dict(small,mode=mode)))
 register(out,kind+': all specified domain members, no selected bestquarter',jobs=jobs,same_job_CPU_s=90,same_job_wall_s=110);rows=[];budget=3300 if kind=='B' else 600
 for n,job in enumerate(jobs):
  previous=Path(sys.argv[3]) if len(sys.argv)>3 else None
  if previous and (previous/f'{n:03d}'/'result.json').exists():
   old=json.load(open(previous/f'{n:03d}'/'result.json'));assert old['job']==job;rows.append({'n':n,'job':job,'rc':0,'wall_s':old['wall_s'],'reused_completed_result':str(previous/f'{n:03d}'/'result.json'),'pure_manager_serialization_fix':True});write(out/f'execution-{n:03d}.json',rows[-1]);continue
  if sum(x['wall_s'] for x in rows)>=budget:write(out/'unstarted.json',jobs[n:]);break
  path=out/f'{n:03d}';jobpath=out/f'job-{n:03d}.json';write(jobpath,job);record=child([str(Path(__file__)),'child',str(jobpath),str(path)],path,cpu=90,wall=min(110,max(1,budget-sum(x['wall_s'] for x in rows))));record.update(n=n,job=job);rows.append(record);write(out/f'execution-{n:03d}.json',record);print(kind,n,record['rc'],round(record['wall_s'],2),flush=True)
 write(out/'execution.json',rows)
if __name__=='__main__':main()

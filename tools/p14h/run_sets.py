"""Same original jointdomain, identical perjob budget and finite W comparison."""
import sys,json,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from p14h.common import *

def execute(job,out):
 out.mkdir();limit(180);from p14r.affine import install
 install(True)
 import p14g.tube as T
 from p14h.compress import compress,METRIC
 from p14g.rich_sets import annotate
 source=json.load(open(R/'config/p14h/protocol-v1.json'))['cases'];d=json.load(open(R/source[job['fiber']]['input']));other=json.load(open(R/source['d03' if job['fiber']=='d02' else 'd02']['input'])) if job['panel']=='joint' else None
 if job.get('actual_AB'):
  for doc in [d,other]:
   if doc is not None:doc['plan']['windows_profile_s']=doc['plan']['full_source_windows_profile_s'][:2]
 if job['variant']=='full-W':
  path=B/'gramian-v1'/job['fiber']/'result';meta=json.load(open(path/'result.json'));z=np.load(path/'metric.npz');METRIC.update(layout=meta['layout'],Ps=[z['P'+str(k)] for k in range(meta['calls']+1)]);T.compress=compress
 old=T.metrics
 def metrics(s,nom):
  r=annotate(s,old(s,nom))
  with (out/'metric-prefix.jsonl').open('a') as f:f.write(json.dumps(r)+'\n')
  return r
 T.metrics=metrics;r,s=T.run(d,dict(np.load(R/'data/p13-20261026-freeze/models/policy.npz')),job['scale'],end=d['initial']['profile_s']+job['horizon_s'],compress_rank=-512,group=True,region_output=out/'regions',observer_library=R/'data/p14r-20261027/offline-build-v2/libop.bin',joint_doc=other,joint_segment=job['segment'],liveness=True,relations='all');r['job']=job;write(out/'result.json',r);np.savez_compressed(out/'last-region.npz',**{k+'_center':v.c for k,v in s.items()},**{k+'_generators':v.pad() for k,v in s.items()});print('P14H_SET',job,len(r['rows']),r['first_precision_loss'],r['first_domain_loss'])

def main():
 if sys.argv[1]=='child':execute(json.load(open(sys.argv[2])),Path(sys.argv[3]));return
 if len(sys.argv)>2 and sys.argv[2]=='AB':
  out=register(sys.argv[1],'C2 genuine A/hold/resume/recovery/B: same original eight union fibers, explicit two-event plan; W priority covers .768s only; first loss returns UNKNOWN, no B bookmark claim',prior_C_CPU=1516.431714,remaining_C_CPU=1483.568286,requested_horizon_s=2.,new_model_fits=0)
  jobs=[dict(panel='joint',fiber=fiber,segment=[a,a+.25],variant='full-W',scale=0,horizon_s=2.,actual_AB=True) for fiber in ['d02','d03'] for a in [0,.25,.5,.75]]
  write(out/'jobs.json',jobs);used=1516.431714;rows=[]
  for n,job in enumerate(jobs):
   if used+180>3000:write(out/'unstarted.json',{'jobs':jobs[n:],'reason':'C whole scope cap includes prior work'});break
   path=out/f'job-{n:03d}.json';write(path,job);row=run([PY,Path(__file__),'child',path,out/f'{n:03d}/result'],out/f'{n:03d}',cpu=180,wall=210,scope='C2 actual two-event joint propagation');used+=row['CPU_s'];rows.append(row);print('AB_SET_TERMINAL',n,row['rc'],round(used,2),flush=True)
  write(out/'execution.json',{'rows':rows,'CPU_including_prior_C':used,'expected':len(jobs),'attempted':len(rows),'whole_C_CPU_cap':3000,'W_futureimportance_scope_s':.768,'full_EKF_future_error_coverage':'UNKNOWN'});return
 out=register(sys.argv[1],'C: full-output pullback W vsrelations onalloriginalfibers/segments, no shrinking; requested2s includingA/resume/recovery/B; same180CPU/210wall',panel='Gsameoriginalunion',C_total_CPU_cap=3000,weights_actual_CPU=253.05);jobs=[]
 for panel in ['zero','small','joint']:
  for fiber in ['d02','d03'] if panel=='joint' else ['d02']:
   for seg in [[a,a+.25] for a in [0,.25,.5,.75]] if panel=='joint' else [[0,1]]:
    for variant in ['relations','full-W']:jobs.append({'panel':panel,'fiber':fiber,'segment':seg,'variant':variant,'scale':.001 if panel=='small' else 0,'horizon_s':2.0 if panel=='joint' else .064})
 write(out/'jobs.json',jobs);used=253.05;rows=[]
 for n,job in enumerate(jobs):
  if used+180>3000:write(out/'unstarted.json',{'jobs':jobs[n:],'reason':'Ctheory cap3000 inclmetrics'});break
  path=out/f'job-{n:03d}.json';write(path,job);row=run([PY,Path(__file__),'child',path,out/f'{n:03d}/result'],out/f'{n:03d}',cpu=180,wall=210,scope='C sameoriginaldomain Wcomparison');used+=row['CPU_s'];rows.append(row);print('SET_TERMINAL',n,row['rc'],round(used,2),flush=True)
 write(out/'execution.json',{'rows':rows,'CPU_including_metric_charge':used,'completed_attempts':len(rows),'expected':len(jobs),'wholeCPUcap':3000,'metric_is_localconditional_not_actualfutureproof':True})
if __name__=='__main__':main()

"""Finite development comparison: held, one rejected-error prototype, sourcequeue.
All useactualpastinitial only; futurelogs restricted to separate scoring.
"""
import sys,json,copy,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from p14h.common import *
from p14h.predict_past import planned_cell
from p14h.model import forecast
from p14h.delivery import Word

def worker(inp,job,out):
 out.mkdir();limit(30);d=json.load(open(inp/(job['case']+'.json')))
 if job['model']=='held':d['initial'].pop('p14h_schedule_model',None)
 if job['model']=='error-prototype':d['initial'].pop('p14h_schedule_model',None);d['initial']['p14h_error_model']=json.load(open(inp/'error-model.json'))
 d=planned_cell(d,job['side']);P=dict(np.load(inp/'policy.npz'));r=forecast(d,{},P,word=Word(),observer_library=inp/'libop.bin',checkpoint_times=job.get('checkpoints',()));np.savez_compressed(out/'trace.npz',**{k:v for k,v in r.items() if isinstance(v,np.ndarray)});write(out/'result.json',{k:v for k,v in r.items() if not isinstance(v,np.ndarray)});print('RESPONSE_TRIAL',job)

def main():
 if sys.argv[1]=='child':worker(Path(sys.argv[2]),json.load(open(sys.argv[3])),Path(sys.argv[4]));return
 out=register(sys.argv[1],'finite onefeedbackrevision: sourceproducer initialization vsoldheld andempiricalerrorprototype; all4twosides',new_fits=0);inp=out/'inputs';inp.mkdir()
 for j in range(1,5):shutil.copyfile(B/'cadence-recovery-v2'/f'd{j:02d}/input.json',inp/f'd{j:02d}.json')
 for a,p in [('policy.npz',R/'data/p13-20261026-freeze/models/policy.npz'),('libop.bin',R/'data/p14r-20261027/offline-build-v2/libop.bin'),('cadence.bin',B/'cadence-recovery-v2/cadence.bin'),('error-model.json',B/'feedback-fit-v1/model.json')]:shutil.copyfile(p,inp/a)
 jobs=[]
 for n in range(1,5):
  for model in (['source-queue'] if len(sys.argv)>2 and sys.argv[2]=='source-only' else ['held','error-prototype','source-queue']):
   for side in ['BEFORE','AFTER']:jobs.append({'case':f'd{n:02d}','model':model,'side':side})
 write(out/'jobs.json',jobs)
 for n,job in enumerate(jobs):
  jf=out/f'job-{n:03d}.json';write(jf,job);r=run([PY,Path(__file__),'child',inp,jf,out/f'{n:03d}/result'],out/f'{n:03d}',cpu=30,wall=40,scope='development response trial, no futurelabels');print(n,r['rc'],flush=True)
if __name__=='__main__':main()

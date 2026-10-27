"""Known future timestamp/phase replacement ONLY. Not an autonomous model.
No future physical, fused-state, gyro, LP or attitude payload is injected.
"""
import sys,json,copy,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
import numpy as np
from p14h.common import *
from p12c.features import load
from p14r.observer import read,CORE
from p14h.predict_past import planned_cell
from p14h.score_response import angle,first

def compute(case,mode,out):
 import p14h.model as M
 from p14h.causal_observer import Observer as Source
 out=Path(out);out.mkdir();target=next((B/'runs').glob(f'p14h-{case}-*'));info=json.load(open(target/('information-v2.json' if (target/'information-v2.json').exists() else 'information.json')));analysis=R/info['source_analysis'] if info.get('source_analysis') else target/'analysis-v1';obs=load(target/'run',analysis);d=json.load(open(B/f'cadence-recovery-v2/{case}/input.json'));i=d['initial'];side=json.load(open(target/'plan.json'))['side'];d=planned_cell(d,side);core,_=read(target/'run/gz-motor/observer-core.bin',CORE,b'P14RCORE',True);post=core[core['kind']==2];mapping={}
 for j,sample in enumerate(obs['sample_us']):
  z=int(np.searchsorted(post['wall_ns'],obs['run_wall_ns'][j],side='right')-1)
  if z>=0:mapping[int(sample)]=(int(post['sample_us'][z]),int(obs['lp_sample'][j]),int(obs['att_sample'][j]))
 class Replaced(Source):
  def __init__(self,*a,**k):
   super().__init__(*a,**k);self.payloads={('LP',self.lp_sample):np.r_[self.p,self.v].copy(),('att',self.att_sample):self.q.copy()}
   for _,kind,v,s in self.queue:self.payloads[kind,s]=v.copy()
  def publish(self,control,fused):
   super().publish(control,fused)
   for _,kind,v,s in self.queue:self.payloads[kind,s]=v.copy()
  def step(self,control,*args):
   target,lp,att=mapping[control];self.lag=int(control-target);value=super().step(control,*args)
   if mode=='producer+cache-timestamps':
    if ('LP',lp) not in self.payloads or ('att',att) not in self.payloads:raise ValueError('actual timestamp has no corresponding model-produced payload; source fusion/callback word differs')
    self.p=self.payloads['LP',lp][:3].copy();self.v=self.payloads['LP',lp][3:].copy();self.q=self.payloads['att',att].copy();self.lp_sample=lp;self.att_sample=att;value=self.p.copy(),self.v.copy(),self.q.copy(),self.gyro.copy()
   return value
 M.Observer=Replaced;tmp=out/'inputs';tmp.mkdir();shutil.copyfile(R/'data/p14r-20261027/offline-build-v2/libop.bin',tmp/'libop.bin');shutil.copyfile(B/'cadence-recovery-v2/cadence.bin',tmp/'cadence.bin');end=i['profile_s']+.004*((int(obs['sample_us'][-1])-i['sample_us'])//4000);r=M.forecast(d,{},dict(np.load(R/'data/p13-20261026-freeze/models/policy.npz')),limit=end,observer_library=tmp/'libop.bin');np.savez_compressed(out/'trace.npz',**{k:v for k,v in r.items() if isinstance(v,np.ndarray)});tr=r['trace'];ix=np.flatnonzero((obs['sample_us']>i['sample_us'])&(obs['sample_us']<=i['sample_us']+4000*(len(tr)-1)));k=((obs['sample_us'][ix]-i['sample_us'])//4000).astype(int);b=d['plan']['windows_profile_s'][0][1];errs={'input':np.linalg.norm(r['inputs'][k]-obs['input'][ix],axis=1),'action':np.linalg.norm(tr[k,8:12]-obs['action'][ix],axis=1),'h':np.linalg.norm(tr[k,12:28]-obs['h_after'][ix],axis=1),'LP':np.linalg.norm(tr[k,42:45]-obs['position'][ix],axis=1),'attitude_deg':angle(tr[k,48:52],obs['attitude'][ix])};t=obs['t'][ix];windows=[]
 for width in [.064,.5,2.]:
  mask=(t>=b)&(t<=b+width);windows.append(dict(window=width,complete=bool(t[-1]>=b+width-.004),RMSE={key:float(np.sqrt(np.mean(v[mask]**2))) if np.any(mask) else None for key,v in errs.items()}))
 write(out/'result.json',dict(case=case,mode=mode,stop=r['stop'],source_inputs='actual future OP-completion sample and optional actual consumed cache timestamps, NO future payloads; diagnostic ONLY',windows=windows,full_prefix_RMSE={key:float(np.sqrt(np.mean(v*v))) for key,v in errs.items()},first_errors={key:first(t,e,dict(input=.05,action=.02,h=.1,LP=.1,attitude_deg=2.5)[key]) for key,e in errs.items()},not_in_autonomous_scores=True));print('TIMESTAMP_REPLACEMENT',case,mode)

if __name__=='__main__':
 if sys.argv[1]=='child':compute(sys.argv[2],sys.argv[3],sys.argv[4])
 else:
  out=register(sys.argv[1],'finite future-timestamp-only diagnostic: why sourcequeue worsens d02 and improves d03; all four mechanism records, frozen model unchanged',cases=['d01','d02','d03','d04'],modes=['producer-completion','producer+cache-timestamps'],CPU_cap=240,no_model_fit=True,not_independent_validation=True)
  for case in ['d01','d02','d03','d04']:
   for j,mode in enumerate(['producer-completion','producer+cache-timestamps']):
    name=case+'-'+str(j);r=run(['/usr/bin/taskset','-c','0-3',PY,Path(__file__),'child',case,mode,out/name/'result'],out/name,cpu=30,wall=45,scope='known future timestamp diagnostic only, no new candidate');print(name,r['rc'],flush=True)

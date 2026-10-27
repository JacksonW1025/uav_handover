"""Six predeclared retrospective future-cache replacements, never autonomous.

Interception is scoped to this process and keeps source model files unchanged.
The causal predictor has no file I/O and the autonomous driver never imports it.
"""
import sys,json,time
from pathlib import Path
from unittest.mock import patch
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p14_motion.core import forecast,Ctl
from p14.common import write,sha,records
from p12c.features import load
from p14.evaluate import stats,crossing

def main():
 out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False)
 cases=['p13-F4-b1-A','p13-F2-b1-AB-short'];variants=['actual_attitude_cache','actual_gyro_cache','actual_LP_attitude_gyro_caches']
 write(out/'before-compute.json',{'cases':cases,'variants':variants,'source':sha(ROOT/'tools/p14_motion/core.py'),'role':'future measured inputs, diagnostic only; no autonomous score or certificate','initial_scope':'same A-pre edge initial state as tube, conditioning on past full history; v1/v2 task0 variants retained','replacement_time':'exact timestamp_sample ID; if missing latest past sample marked, never optimize time shift','new_SITL':0})
 P=dict(np.load(ROOT/'data/p13-20261026-freeze/models/policy.npz'));rr={r['id']:r for r in records()};summary=[]
 for case in cases:
  rec=rr[case];d=load(rec['target']/'run',rec['analysis']);doc=json.load(open(ROOT/'data/p14-motion-20261027/inputs-v3'/case/'edge-input.json'));M=json.load(open(ROOT/'data/p13-20261026-freeze/models/models.json'));initial=doc['initial'];original=Ctl.step
  for variant in variants:
   consumed=[];missing=[]
   def intercepted(self,now,sample,p,v,q,w,msg,policy):
    t=initial['profile_s']+(sample-initial['sample_us'])*1e-6;j=np.searchsorted(d['sample_us'],sample,side='right')-1
    if d['sample_us'][j]!=sample:missing.append(int(sample))
    if variant in ['actual_attitude_cache','actual_LP_attitude_gyro_caches']:q=d['attitude'][j].copy()
    if variant in ['actual_gyro_cache','actual_LP_attitude_gyro_caches']:w=d['omega'][j].copy()
    if variant=='actual_LP_attitude_gyro_caches':p=d['position'][j].copy();v=d['velocity'][j].copy()
    consumed.append(np.r_[t,p,v,q,w]);return original(self,now,sample,p,v,q,w,msg,policy)
   st=time.perf_counter()
   with patch.object(Ctl,'step',intercepted):pred=forecast(doc,M,P)
   tr=pred['trace'];t=tr[:,0];sample=initial['sample_us']+4000*np.arange(len(t));ii=np.searchsorted(d['sample_us'],sample,side='right')-1;valid=(ii>=0)&(t<=d['t'][-1])&np.isfinite(pred['inputs']).all(axis=1)&(d['sample_us'][np.maximum(ii,0)]==sample);ii=ii[valid];tt=t[valid]
   errors={'input_l2':np.linalg.norm(pred['inputs'][valid]-d['input'][ii],axis=1),'h_l2':np.linalg.norm(tr[valid,12:28]-d['h_after'][ii],axis=1),'action_l2':np.linalg.norm(tr[valid,8:12]-d['action'][ii],axis=1)}
   thresholds={'input_l2':.1,'h_l2':.5,'action_l2':.1}
   row={'case':case,'variant':variant,'future_inputs':variant,'autonomous':False,'certificate':False,'missing_exact_sample_rows':len(missing),'error':{k:stats(v) for k,v in errors.items()},'first':{k:crossing(tt,v,thresholds[k]) for k,v in errors.items()},'stop':pred['stop'],'elapsed_s':time.perf_counter()-st,'physical_source_not_reset':True,'h_history_not_reset':True,'replace_order':'attitude alone, gyro alone, then joint LP/att/gyro; differences are coupled sensitivities, no additive attribution'}
   write(out/case/(variant+'.json'),row);np.savez_compressed(out/case/(variant+'.npz'),trace=tr,states=pred['states'],inputs=pred['inputs'],consumed_cache=np.array(consumed));summary.append(row);print('CACHE_DIAGNOSTIC',case,variant,row['first'],flush=True)
 write(out/'summary.json',summary)

if __name__=='__main__':main()

"""Finite semantic-correction rerun; no fitting or radius search.

Original SVD24, unsupported nav-yaw and A-relative height attempts remain.
The correction separates navigation axes, preserves task H0/D, retains the
unit-group invariant, and preserves original generator directions.
"""
import sys,json,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p14_motion.tube import run
from p14.common import write,sha

def main():
 out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False)
 cfg=json.load(open(ROOT/'config/p14-motion-offline.json'))
 P=dict(np.load(ROOT/'data/p13-20261026-freeze/models/policy.npz'))
 f2='p13-F2-b1-AB-short'
 jobs=[(c,r,'joint',True,False,False) for c in cfg['tube_cases'] for r in [1,.001]]
 jobs += [(f2,.001,'box_each_call',True,False,False),
          (f2,.001,'joint',True,False,True),
          (f2,.001,'joint',False,False,False),
          (f2,1,'joint',True,True,False),
          (f2,0,'joint',True,False,False)]
 write(out/'before-compute.json',{'jobs':jobs,'source_hashes':{str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'tools/p14_motion').glob('*.py')},'inputs':'inputs-v3','protocol':sha(ROOT/'config/p14-motion-offline.json'),'changes':'coordinate/H0/q-norm corrections; finite direction-preserving/group structural comparisons, no empirical fit','new_SITL':0})
 summary=[];previous=Path(sys.argv[2]) if len(sys.argv)>2 else None
 if previous is not None:
  old=json.load(open(previous/'before-compute.json'))
  for key in ['core.py','tube.py','algebra.py']:
   assert old['source_hashes']['tools/p14_motion/'+key]==sha(ROOT/'tools/p14_motion'/key),'model changed: cannot reuse prior output'
 for number,(case,scale,variant,group,conditioned,rebox) in enumerate(jobs):
  name=f'{number:02d}-{case}-r{scale}-{variant}-group{int(group)}-obs{int(conditioned)}-joinbox{int(rebox)}'
  doc=json.load(open(ROOT/'data/p14-motion-20261027/inputs-v3'/case/'edge-input.json'))
  if previous is not None and (previous/name/'tube.json').is_file():
   result=json.load(open(previous/name/'tube.json'))
   summary.append({k:v for k,v in result.items() if k not in ['rows','compression']}|{'name':name,'evidence_path':str(previous/name),'compression_count':len(result['compression'])})
   print('REUSE_COMPLETED_OFFLINE',name,flush=True);continue
  A,B=doc['plan']['full_source_windows_profile_s'];end=max(A[1]+2.1,B[1]+.5)
  target=out/name
  result,state=run(doc,P,scale,variant,end,compress_rank=-512,conditioned=conditioned,group=group,region_output=target/'regions',rebox_join=rebox)
  result.update(case=case,conditioned_observation_scenario=conditioned,nominal_timing_branches=1,actual_initial_membership='NOT_ASSERTED',future_actual_inputs=False)
  result['stage_reached']={label:label in result['regions'] for label in ['64ms','resume','resume_plus_p5','resume_plus2','B_pre']}
  result['composition']={'A_to_B_without_state_reset':True,'historical_D_reset':False,'B_start':B[0],'B_pre_valid':('B_pre' in result['regions'] and (result['first_domain_loss'] is None or result['regions']['B_pre']['t']<result['first_domain_loss']['t'])),'boundary_rebox':rebox,'successor':result['successor']}
  write(target/'tube.json',result)
  np.savez_compressed(target/'last-region.npz',**{key+'_center':value.c for key,value in state.items()},**{key+'_generators':value.pad() for key,value in state.items()})
  summary.append({k:v for k,v in result.items() if k not in ['rows','compression'] }|{'name':name,'evidence_path':str(target),'compression_count':len(result['compression'])})
  print('FINAL_TUBE',name,'calls',len(result['rows']),'first_loss',None if result['first_precision_loss'] is None else result['first_precision_loss']['call'],'domain',result['first_domain_loss'],'seconds',result['elapsed_s'],flush=True)
  write(out/f'progress-{number:02d}.json',summary[-1])
 write(out/'summary.json',summary)

if __name__=='__main__':main()

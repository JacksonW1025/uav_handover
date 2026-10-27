"""Developed mixed-prefix four-method design materialization. No formal labels."""
import json,copy,random,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from p15.common import *
from p15.prepare import materialize

def main():
 draft=json.load(open(B/'search-design-before-development-outcomes-v1.json'));rng=random.Random(152710000);rows=[]
 for block,seed in enumerate(draft['blocks']):
  for method in draft['methods']:
   for t in draft['trials']:
    n=t['trial'];prefix=t['partitioned_prefix'] if method!='M0' else random.Random(seed+1009*n).choice(['B','AB']);Ds=t['allowed_D'] if method!='M0' else [.24,.30,.38];ident=f'p15-e-b{block+1}-{method}-t{n+1}-{t["family"]}-{prefix}'
    rows.append(dict(id=ident,seed=seed,family=t['family'],prefix=prefix,budget_class='search',method=method,decision_phase=t['information'],trial=n,block=block+1,allowed_D=Ds,fixed_candidate=None,question='sameinformation/cost prefixcoverage and directional successor sorting, finite2block independent evaluation',selection_rule=draft[method],prestart_information='new actual state unavailable before launch. Frozen warmup+live query costs paid; prior dev diagnostics only, actual candidate ranking saved at legal decision, no actual future label',state_origin='own run completed preA/postA; same seed not same state'))
 rng.shuffle(rows);materialize(rows,B/'search-freeze-v1');maps=[]
 for n,(family,seed,source) in enumerate([('F2',152710301,None),('F4',152710302,None),('F2',152710303,'p15-m01-F2'),('F4',152710304,'p15-m02-F4')]):
  row=dict(id=f'p15-m{n+1:02d}-{family}',family=family,seed=seed,prefix='AB',budget_class='map',method='M3',decision_phase='postA',trial=n,allowed_D=[.30],fixed_candidate=None,map_loop=source is None,question='own preA successor -> actualA legal recovery update -> B choice, then pastupdate independently tested without refitting')
  if source:row['local_update_path']=f'data/p15-20261027/runs/{source}/run/p15-local-update.json'
  maps.append(row)
 materialize(maps,B/'map-freeze-v1')
 # Validate quotas, same conditions/information and actual source trajectory.
 from run_experiment import p5_profile,Experiment
 from types import SimpleNamespace
 import numpy as np
 for block in [1,2]:
  for method in draft['methods']:
   rr=[r for r in rows if r['block']==block and r['method']==method];assert len(rr)==4
   if method!='M0':assert sorted(r['prefix'] for r in rr)==['AB','AB','B','B']
 for family in ['F2','F4']:
  ref=None
  for r in rows:
   if r['family']!=family:continue
   c=json.load(open(R/'config/p15'/f'{r["id"]}.json'));s=c['p5']['conditions']['p11-case'];p=p5_profile(c['p5'],s);ns=SimpleNamespace(cfg={'p1_speed_m_s':s['speed_m_s']},pcfg=p);table=np.array([Experiment.p1_profile(ns,float(t)) for t in np.arange(0,31,.004)])
   if ref is None:ref=table
   else:assert np.array_equal(ref,table)
 write(B/'design-acceptance-v1.json',dict(status='PASS',search=32,map=4,method_credit_per_block=4,blocks=2,prefix_quota=['B','AB','B','AB'],same_information_schedule=['preA','preA','postA','postA'],common_trajectory_exact=True,oldH_fullFAILmatrix_not_repeated=True,fullpool_relation='M0 samples union; M1-3 fixed prefix/severity strata. M1-M0 estimates partition policy effect, M2-M1 cheap ordering, M3-M2 added direction and closedloop rollout. Not four unrelated pools.',randomized_order_seed=152710000,rule_sources=draft))
if __name__=='__main__':main()

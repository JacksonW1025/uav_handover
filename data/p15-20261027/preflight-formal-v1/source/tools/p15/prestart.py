"""Prior conditional predictions computed before new search data exist.
Live policy may change choice using legitimately acquired own-run state later.
"""
import sys,json,numpy as np
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from p15.common import *
from p15.model import rank

def main():
 out=register(sys.argv[1],'prelaunch past-only prior scores for every formal family/information; not actual new initial');P=dict(np.load(R/'data/p13-20261026-freeze/models/policy.npz'));params=json.load(open(R/'config/p15/model-v1.json'));pool=json.load(open(R/'config/p15/candidate-pool-v1.json'))['candidates'];priors={}
 for family,phase,ident in [('F2','preA','p15-d03-F2-B-mild'),('F2','postA','p15-d05-F2-AB-mild-v2'),('F4','preA','p15-d04-F4-AB-boundary-v2'),('F4','postA','p15-d02-F4-A-post')]:
  doc=json.load(open(B/'runs'/ident/'run/p15-selection-input.json'))
  for prefix in ['B','AB']:
   pp=[dict(c,prefix=prefix) for c in pool];x=rank(doc['snapshot'],pp,doc['context'],params,P,'M3',np.random.default_rng(1));key=f'{family}-{phase}-{prefix}';priors[key]=dict(source=ident,source_input_sha256=sha(B/'runs'/ident/'run/p15-selection-input.json'),state_available_by_ns=doc['snapshot']['available_by_ns'],source_prefix=doc['context']['prefix'],target_prefix=prefix,initial_difference='historical development prior, actual new initial unknown; postA fromsingleA may differ from Bonly and is not claimed equivalent',scores=[dict(candidate=r['candidate'],score=r['score'],Bpre=r['prediction']['Bpre'],peak_tilt=r['prediction']['peak_tilt_deg'],peak_D=r['prediction']['peak_LP_D_m'],stop=r['prediction']['stop']) for r in x['rows']],CPU_s=x['CPU_s'],future_new_data_used=False)
 write(out/'priors.json',priors)
 for stage in ['search','map']:
  plan=json.load(open(B/f'{stage}-freeze-v1/plan.json'));rr=[]
  for r in plan['rows']:rr.append(dict(r,prestart_prediction=priors[f'{r["family"]}-{r["decision_phase"]}-{r["prefix"]}']))
  path=B/f'{stage}-freeze-v2';path.mkdir();write(path/'plan.json',dict(plan,rows=rr,prior_source=str((out/'priors.json').relative_to(R)),exposure='before all32 independentstarts; development only used tofreeze model and finite pool'))
 print('P15_PRIORS_FROZEN',len(priors))
if __name__=='__main__':main()

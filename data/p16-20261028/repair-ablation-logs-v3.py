"""Fix before-alias metadata on every affected ablation, preserve scores/oldfiles."""
import sys,json,copy
from pathlib import Path
sys.path.insert(0,'tools')
from p16.common import B,write,sha,now
from p16.sequential import calibrated
from p16.reuse import apply
from p16.quality import evaluate
out=Path(sys.argv[1]);out.mkdir(exist_ok=False,parents=True);pool=json.load(open(B/'frozen/pool.json'));initial=json.load(open(B/'frozen/initial-predictions.json'));truth=json.load(open(B/'analysis-v2-results/truth.json'));audit=[]
for name,kw in [('drop_state_timing',dict(drop_state=True)),('drop_L_D_prefixTilt',dict(drop_ledger=True))]:
 path=B/f'analysis-v2-results/ablation-{name}.json';old=json.load(open(path));new=copy.deepcopy(old)
 for x in new:
  q=x['query'];h={}
  for i in range(1,q+1):
   t=json.load(open(B/f'policies/R/queries/q{i:02d}/return.json'));h[t['cell_id']]=t['record']
  base=calibrated(pool,initial,h);pred,tr=apply(pool,initial,h,base,**kw);assert pred==x['prediction'];assert evaluate(pool,truth,pred)==x['quality']
  for t in x['transfers']:
   if not t['accepted']:continue
   before={k:base[t['receiver']][k] for k in ['tilt','height','task']};after={k:pred[t['receiver']][k] for k in ['tilt','height','task']};t['original_v2_classification_changed']=t['classification_changed'];t['before']=before;t['after']=after;t['classification_changed']=before!=after;audit.append(dict(ablation=name,query=q,donor=t['donor'],receiver=t['receiver'],old_changed=t['original_v2_classification_changed'],corrected_changed=t['classification_changed']))
 write(out/f'ablation-{name}.json',new)
write(out/'receipt.json',dict(time=now(),source='analysis-v2-results ablations retained',rows=audit,maps_verified=18,predictions_and_scores_changed=False,new_START=0,scope='beforealias metadata fix reaches all affectedablation logs, no parameter/group/threshold changes'))
print('ABLATION_LOG_REPAIR',len(audit),sum(x['corrected_changed']!=x['old_changed'] for x in audit))

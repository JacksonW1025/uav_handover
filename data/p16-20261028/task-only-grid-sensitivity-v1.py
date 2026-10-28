"""One retrospective baseline-design diagnostic. Frozen primary Grid unchanged.
Same oracle and exact frozen choose(); jointly interpolate known task labels,
so an UNKNOWN height component does not erase a known joint failure witness.
No per-axis prediction is claimed by this diagnostic joint classifier.
"""
import sys,json,time
from pathlib import Path
sys.path.insert(0,'tools')
from p16.common import B,write,now
from p16.baseline import choose
from p16.quality import evaluate,curve_key
st=time.process_time();out=Path(sys.argv[1]);out.mkdir(exist_ok=False,parents=True);pool=json.load(open(B/'frozen/pool.json'));rows=json.load(open(B/'frozen/rows.json'));truth={k:json.load(open(B/'runs'/r['id']/'analysis-v1/result.json')) for k,r in rows.items()};history={};maps=[]
for q in range(25):
 pred={}
 for curve in sorted({curve_key(c) for c in pool}):
  cc=sorted([c for c in pool if curve_key(c)==curve],key=lambda x:x['G']);known=[(i,history[c['id']]) for i,c in enumerate(cc) if c['id'] in history and history[c['id']]['valid']]
  for i,c in enumerate(cc):
   task='UNKNOWN'
   if c['id'] in history:task=history[c['id']]['task']
   elif known:
    l=next(((j,r) for j,r in reversed(known) if j<i),known[0]);r=next(((j,r) for j,r in known if j>i),known[-1]);a,b=l[1]['task'],r[1]['task']
    if 'UNKNOWN' not in [a,b]:
     t=0 if r[0]==l[0] else (c['G']-cc[l[0]]['G'])/(cc[r[0]]['G']-cc[l[0]]['G']);prob=(a=='FAIL')*(1-t)+(b=='FAIL')*t;task='FAIL' if prob>=.5 else 'SUCCESS'
   pred[c['id']]=dict(tilt='UNKNOWN',height='UNKNOWN',task=task)
 m=dict(query=q,seen=list(history),prediction=pred,quality=evaluate(pool,truth,pred));maps.append(m)
 if q<24:
  selected=choose(pool,history);m['selected']=selected;history[selected['id']]=truth[selected['id']]
persistent=next((m['query'] for i,m in enumerate(maps) if all(x['quality']['same_quality'] for x in maps[i:])),None)
write(out/'result.json',dict(time=now(),maps=maps,first_persistent=persistent,CPU_s=time.process_time()-st,primary_frozen_Grid_first_persistent=13,scope='retrospective design sensitivity motivated after full main exposure; not replacement primary, no peraxis forecasts or newSITL',new_START=0,parameters_tuned=False))
print('TASK_ONLY_DIAGNOSTIC_FIRST_PERSISTENT',persistent)

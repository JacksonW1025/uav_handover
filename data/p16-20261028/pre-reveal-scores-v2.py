"""Policy-information pre-reveal predictions, not labels overwritten afterquery."""
import sys,json
from pathlib import Path
sys.path.insert(0,'tools')
from p16.common import B,write,now
from p16.dual import both_terminal
out=Path(sys.argv[1]);out.mkdir(exist_ok=False,parents=True);sealed=both_terminal();result={};initial=json.load(open(B/'frozen/initial-predictions.json'))
for p in ['G','R']:
 rows=[]
 for q in range(1,9):
  folder=B/f'policies/{p}/queries/q{q:02d}';d=json.load(open(folder/'decision.json'));r=json.load(open(folder/'return.json'));cost=json.load(open(folder/'reveal-cost.json'));rows.append(dict(query=q,cell=d['cell']['id'],initial_prediction={k:initial[d['cell']['id']][k] for k in ['tilt','height','task']},prediction={k:d['selected_prediction'][k] for k in ['tilt','height','task']},actual={k:r['record'][k] for k in ['tilt','height','task']},valid=r['record']['valid'],complete=r['record']['complete'],new_physical_START=cost['new_physical_START'],decision_time=d['created_at'],reveal_time=r['time']))
 metric={}
 for comp in ['tilt','height','task']:
  valid=[r for r in rows if r['valid']];metric[comp]=dict(N=len(valid),correct=sum(x['prediction'][comp]==x['actual'][comp] and x['actual'][comp]!='UNKNOWN' for x in valid),danger_as_safe=sum(x['actual'][comp]=='FAIL' and x['prediction'][comp]=='SUCCESS' for x in valid),false_alarm=sum(x['actual'][comp]=='SUCCESS' and x['prediction'][comp]=='FAIL' for x in valid),truth_unknown=sum(x['actual'][comp]=='UNKNOWN' for x in valid),prediction_unknown=sum(x['prediction'][comp]=='UNKNOWN' for x in valid),initial_correct=sum(x['initial_prediction'][comp]==x['actual'][comp] and x['actual'][comp]!='UNKNOWN' for x in valid),initial_danger_as_safe=sum(x['actual'][comp]=='FAIL' and x['initial_prediction'][comp]=='SUCCESS' for x in valid),changed_before_reveal=[x['cell'] for x in valid if x['prediction'][comp]!=x['initial_prediction'][comp]])
 result[p]=dict(rows=rows,metrics=metric,actual_new_START=sum(x['new_physical_START'] for x in rows))
write(out/'scores.json',dict(time=now(),terminal_hashes=sealed,policies=result,scope='own-information pre-reveal; R cachedsamephysical only after ownchoice, not newindependent preflight predictions; no model or map update',N_physical_independent_not16=True))
print(json.dumps({p:x['metrics'] for p,x in result.items()},indent=2))

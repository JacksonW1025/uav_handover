import json,copy
import numpy as np
from audit import ROOT,ALPHAS,Predictor,aggregate,folds,cv_score,evaluate,dump,sha
rows=json.loads((ROOT/'records.json').read_text());primary=json.loads((ROOT/'results.json').read_text())['results'];ss=json.loads((ROOT/'sensitivity_results.json').read_text())['results'];out=[]
for ds in ['P13','P3']:
 for name,tr,te in folds(ds,[r for r in rows if r['dataset']==ds]):
  base=next(r for r in primary if r['dataset']==ds and r['fold']==name);train=aggregate(tr);pred=copy.deepcopy(base['predictions']);details={}
  fixed=next(r for r in ss if r['dataset']==ds and r['fold']==name and r['variant']=='fixed_max_2')
  pred['state_split']={i:p for pool in fixed['pools'] for i,p in zip(pool['ids'],pool['predictions']['state_split'])}
  # Include non-B auxiliary test predictions, used only by map_mse_all_heldout.
  model=Predictor(fixed['model']['spec']).fit(train);pp=model.predict(te)
  pred['state_split']={r['id']:float(p) for r,p in zip(te,pp)}
  specs={
    'cheap_rank':[dict(kind='tree',depth=2,min_leaf=l) for l in [1,2]],
    'cheap_tree':[dict(kind='tree',depth=4,min_leaf=l) for l in [1,2]],
    'cheap_ridge':[dict(kind='ridge',degree=2,alpha=a) for a in ALPHAS]}
  for m,sp in specs.items():
   cv=[cv_score(s,train) for s in sp];j=int(np.argmin(cv));model=Predictor(sp[j]).fit(train);pp=model.predict(te)
   pred[m]={r['id']:float(p) for r,p in zip(te,pp)};details[m]=dict(spec=sp[j],cv_mse=cv[j])
  r=dict(dataset=ds,fold=name,models=details,**evaluate(ds,te,pred));out.append(r)
  print(ds,name,{m:round(r['summary'][m]['top1'],5) for m in ['state_split','cheap_rank','cheap_tree','cheap_ridge','lookup']})
dump(ROOT/'capacity_results.json',dict(protocol_sha256=sha(ROOT/'capacity_protocol.json'),results=out))

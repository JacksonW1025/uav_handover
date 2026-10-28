import json,copy
import numpy as np
from audit import ROOT,ALPHAS,Predictor,aggregate,folds,cv_score,evaluate,dump,sha

rows=json.loads((ROOT/'records.json').read_text())
primary=json.loads((ROOT/'results.json').read_text())['results']
results=[]
for ds in ['P13','P3']:
    for name,tr,te in folds(ds,[r for r in rows if r['dataset']==ds]):
        base=next(r for r in primary if r['dataset']==ds and r['fold']==name);train=aggregate(tr)
        for states in [2,4]:
            specs=[dict(kind='state',states=states,alpha=a) for a in ALPHAS];scores=[cv_score(s,train) for s in specs];j=int(np.argmin(scores))
            model=Predictor(specs[j]).fit(train);p=model.predict(te)
            pred=copy.deepcopy(base['predictions']);pred['state_split']={r['id']:float(z) for r,z in zip(te,p)}
            results.append(dict(dataset=ds,fold=name,variant='fixed_max_'+str(states),model=dict(**model.details(),cv_mse=scores[j]),**evaluate(ds,te,pred)))
dump(ROOT/'sensitivity_results.json',dict(protocol_sha256=sha(ROOT/'sensitivity_protocol.json'),results=results))
for r in results:
    print(r['dataset'],r['fold'],r['variant'],'actual states',r['model']['states'],'top1',round(r['summary']['state_split']['top1'],5),'mse',round(r['summary']['state_split']['map_mse'],5))

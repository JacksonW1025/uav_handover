from pathlib import Path
import json,numpy as np
import h2_preflight as h2
ROOT=Path(__file__).resolve().parent;OLD=ROOT.parent/'offline-adjoint-20261028';d=json.loads((ROOT/'h5_identification.json').read_text());selected=next(r for r in d['results'] if r['span_steps']==d['selected_span']);h2.M=selected['model'];rows=[r for r in json.loads((OLD/'upstream/data/p13-20261026-results-v3/cases.json').read_text())['rows'] if r['branch']=='AB'];rr=[]
for r in rows:z,t=h2.forecast(r);rr.append(z)
complete=[r for r in rr if not r['actual_censored']];hp=[r for r in rr if r['actual']>1];hn=[r for r in complete if r['actual']<=1];tp=[r for r in rr if r['actual_tilt']>45];tn=[r for r in complete if r['actual_tilt']<=45]
metrics=dict(height_MAE=float(np.mean([abs(r['prediction']-r['actual']) for r in complete])),tilt_MAE=float(np.mean([abs(r['predicted_tilt']-r['actual_tilt']) for r in complete])),height_FN=sum(r['prediction']<=1 for r in hp),height_FP=sum(r['prediction']>1 for r in hn),tilt_FN=sum(r['predicted_tilt']<=45 for r in tp),tilt_FP=sum(r['predicted_tilt']>45 for r in tn),domain_exits=sum(r['stop'] is not None for r in rr))
(ROOT/'h5_results.json').write_text(json.dumps(dict(selected=selected,metrics=metrics,results=rr),indent=2));print(metrics)

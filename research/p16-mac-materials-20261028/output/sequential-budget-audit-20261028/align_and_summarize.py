from pathlib import Path
import json,numpy as np,hashlib
ROOT=Path(__file__).resolve().parent
p=ROOT/'trajectory_results.json';backup=ROOT/'trajectory_results_realization_metrics.json'
if not backup.exists():backup.write_bytes(p.read_bytes())
before=json.loads(backup.read_text())
cache=json.loads((ROOT/'trajectory_prediction_cache.json').read_text());cache={tuple(sorted(r['selected'])):r for r in cache};data=json.loads((ROOT/'prepared.json').read_text())
for policy in before['results']:
 for row in policy['steps']:
  rr=cache[tuple(sorted(row['selected']))]['predictions'];acc=[];bs=[];he=[]
  for group in data['groups']:
   subset=[r for r in rr if r['family']+'|'+r['arm']==group['id']];prob=float(np.mean([r['predicted_tilt']>45 or r['prediction']>1 for r in subset]));hm=float(np.mean([r['prediction'] for r in subset]));ys=[r['y'] for r in group['cases']];acc.extend([(prob>.5)==y for y in ys]);bs.append((prob-np.mean(ys))**2);he.extend([abs(hm-r['height']) for r in group['cases'] if r['height_known']])
  row['realization_metrics']=row['greybox'];row['greybox']=dict(accuracy=float(np.mean(acc)),brier=float(np.mean(bs)),height_MAE=float(np.mean(he)),domain_exits=row['realization_metrics']['domain_exits'])
before['metric_alignment']='Use the same configuration-map prediction as the direct-query protocol: mean source prediction over previously observed normal-state templates, evaluated against the fixed target records. Per-realization diagnostic metrics are retained separately; no model was refit during scoring.'
p.write_text(json.dumps(before,indent=2))
from sequential import threshold
for r in before['results']:
 print(r['policy'],[(x['budget'],round(x['greybox']['accuracy'],3),round(x['greybox']['height_MAE']*100,2)) for x in r['steps']]);print('thresholds',threshold(np.array([x['greybox']['accuracy'] for x in r['steps']]),.9,True),threshold(np.array([x['greybox']['height_MAE'] for x in r['steps']]),.1,False))
main=json.loads((ROOT/'sequential_results.json').read_text());rob=json.loads((ROOT/'robustness_results.json').read_text());tree=json.loads((ROOT/'semantic_tree_results.json').read_text());summ=[]
for r in main['results']+rob['results']+tree['results']:
 curve=r['curve'];summ.append(dict(learner=r['learner'],policy=r['policy'],accuracy90=threshold(np.array([x['accuracy'] for x in curve]),.9,True),height10cm=threshold(np.array([x['height_MAE'] for x in curve]),.1,False),start=curve[0],end=curve[-1]))
source={r['policy']:r['curve'] for r in main['results'] if r['learner']=='greybox_gp'}
comparison={str(k):dict(map_height_cm=source['map_variance'][k]['height_MAE']*100,random_height_cm=source['random'][k]['height_MAE']*100,risk_height_cm=source['risk'][k]['height_MAE']*100) for k in [0,1,2,4,8,12]}
# Overlapping folds are not treated as independent replications.
a=np.load(ROOT/'sequential_scores.npz')['scores'];li=main['learners'].index('greybox_gp');mi=main['policies'].index('map_variance');ri=main['policies'].index('random');fold_effects=[]
for k in [1,2,4,8]:
 x=np.sum(a[li,mi,:,:,k,2],axis=1)/np.sum(a[li,mi,:,:,k,3],axis=1);y=np.sum(a[li,ri,:,:,k,2],axis=1)/np.sum(a[li,ri,:,:,k,3],axis=1);fold_effects.append(dict(budget=k,map_better=int(np.sum(x<y-1e-9)),map_worse=int(np.sum(x>y+1e-9)),ties=int(np.sum(abs(x-y)<=1e-9)),median_delta_cm=float(np.median(x-y)*100),range_delta_cm=[float((x-y).min()*100),float((x-y).max()*100)]))
summary=dict(scope='Retrospective fixed-budget transfer to fixed never-queried configurations; incremental observation counts, not zero historical cost or a certified online stopping rule.',thresholds=summ,greybox_height_policy_comparison=comparison,overlapping_fold_descriptive_effects=fold_effects,initial_history_records=48,direct_budget=12,distinct_AB_configurations=6,observed_AB_flights=18,physical_trajectory_study=before['results'])
(ROOT/'summary.json').write_text(json.dumps(summary,indent=2));print('policy height',comparison);print('fold effects',fold_effects)
files=['protocol.json','prepared.json','sequential_results.json','robustness_results.json','semantic_tree_results.json','trajectory_results.json','sequential_integrity.json']
(ROOT/'manifest.json').write_text(json.dumps(dict(files=[dict(path=n,sha256=hashlib.sha256((ROOT/n).read_bytes()).hexdigest()) for n in files]),indent=2))

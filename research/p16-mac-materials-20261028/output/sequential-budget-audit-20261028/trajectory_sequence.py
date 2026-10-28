from pathlib import Path
import json,sys,copy,numpy as np,time
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
ROOT=Path(__file__).resolve().parent;OLD=ROOT.parent/'model-search-20261028';sys.path.insert(0,str(OLD))
from h4_design import stats,fit_stats,add,predicted_stats,P
from p11.models import forecast as p11_forecast
from h2_strict_compare import features
import h2_preflight as h2
prepared=json.loads((ROOT/'prepared.json').read_text());config=json.loads((OLD/'upstream/config/p11.json').read_text());base=OLD/'upstream/data/p11-20261025-formal';raw=json.loads((ROOT.parent/'offline-adjoint-20261028/upstream/data/p13-20261026-results-v3/cases.json').read_text())['rows']
normal=[r for r in config['rows'] if r['split']=='development' and r['branch']=='NORMAL'];candidates=[r for r in config['rows'] if r['split']=='development' and r['branch'] in ['A','B']];H=[];G=[];docs={};stats_cache={}
for r in normal:
 doc=json.loads((base/r['id']/'packed/prediction-input.json').read_text());docs[r['id']]=doc;hh,gg=stats(dict(np.load(base/r['id']/'packed/measurement.npz')));H.append(hh);G.append(gg)
H0=add(H);G0=add(G)
for r in candidates:
 doc=json.loads((base/r['id']/'packed/prediction-input.json').read_text());template=docs[r['family']+'-r'+str(r['rep'])+'-NORMAL']['initial'];doc['initial']=copy.deepcopy(template);docs[r['id']]=doc
# All initial P13 single outcomes are available to the inexpensive endpoint ranker.
initial=[r for r in prepared['training'] if r['stage']=='P13' or r['branch']=='NORMAL'];mapplans=np.array([r['plan'] for r in prepared['groups']]);source_cases=[]
for r in raw:
 if r['branch']!='AB':continue
 q=copy.deepcopy(r);q['initial']=copy.deepcopy(next(x['initial'] for x in raw if x['family']==r['family'] and x['block']==r['block'] and x['branch']=='NORMAL'));source_cases.append(q)
source_cases=sorted(source_cases,key=lambda r:r['id']);xlookup={r['id'].replace('p11-',''):r for r in prepared['training'] if r['stage']=='P11'}

def cheap_fit(observed):
 tr=initial+observed;sc=StandardScaler().fit([r['plan'] for r in initial]);m=Ridge(alpha=1).fit(sc.transform([r['plan'] for r in tr]),[r['y'] for r in tr]);return lambda xx:m.predict(sc.transform(xx))

def metrics(rr):
 comp=[r for r in rr if not r['actual_censored']];correct=sum((r['predicted_tilt']>45 or r['prediction']>1)==(r['actual_tilt']>45 or r['actual']>1) for r in rr);freq=[]
 for f in ['F2','F4']:
  for arm in ['AB-short','AB-medium','AB-long']:
   a=[r for r in rr if r['family']==f and r['arm']==arm];p=np.mean([r['predicted_tilt']>45 or r['prediction']>1 for r in a]);y=np.mean([r['actual_tilt']>45 or r['actual']>1 for r in a]);freq.append((p-y)**2)
 return dict(accuracy=correct/len(rr),brier=float(np.mean(freq)),height_MAE=float(np.mean([abs(r['prediction']-r['actual']) for r in comp])),domain_exits=sum(r['stop'] is not None for r in rr))
cache={};results=[];started=time.perf_counter()
for policy in ['predicted_information','cheap_risk','short_duration_first']:
 selected=[];observed=[];hh=H0;gg=G0;steps=[]
 for budget in range(7):
  key=tuple(sorted(selected));model=fit_stats(hh,gg);h2.M=model
  if key not in cache:
   rr=[]
   for r in source_cases:z,t=h2.forecast(r);rr.append(z)
   cache[key]=dict(metrics=metrics(rr),predictions=rr)
  source=cache[key];cheap=cheap_fit(observed);cp=np.clip(cheap(mapplans),0,1);yy=np.array([np.mean([r['y'] for r in g['cases']]) for g in prepared['groups']]);ca=np.mean([np.mean([(cp[j]>.5)==r['y'] for r in g['cases']]) for j,g in enumerate(prepared['groups'])]);cm=dict(accuracy=float(ca),brier=float(np.mean((cp-yy)**2)))
  step=dict(budget=budget,selected=selected.copy(),model=model,greybox=source['metrics'],cheap_endpoint_mapper=cm);steps.append(step);print(policy,budget,source['metrics'],flush=True)
  if budget==6:break
  remaining=[r for r in candidates if r['id'] not in selected];scores=[]
  for r in remaining:
   if policy=='predicted_information':
    z=p11_forecast(docs[r['id']],model,P);hp=predicted_stats(z['trace'],docs[r['id']]);value=0
    for a,b in zip(hh,hp):
     ridge=1e-6*np.diag(np.maximum(np.diag(a),1));value+=np.linalg.slogdet(a+b+ridge)[1]-np.linalg.slogdet(a+ridge)[1]
   elif policy=='cheap_risk':value=float(cheap([xlookup[r['id']]['plan']])[0])
   else:value=-sum(b-a for a,b in docs[r['id']]['plan']['windows_profile_s'])
   scores.append(float(value))
  best=max(scores);indices=[i for i,s in enumerate(scores) if abs(s-best)<1e-9];chosen=sorted([remaining[i] for i in indices],key=lambda r:r['id'])[0];rid=chosen['id'];step['query_scores']={r['id']:s for r,s in zip(remaining,scores)};step['next_query']=rid
  # The full trajectory and scalar outcome are revealed only for the chosen test.
  if rid not in stats_cache:stats_cache[rid]=stats(dict(np.load(base/rid/'packed/measurement.npz')))
  a,b=stats_cache[rid];hh=add([hh,a]);gg=add([gg,b]);selected.append(rid);observed.append(xlookup[rid])
 results.append(dict(policy=policy,steps=steps));(ROOT/'trajectory_results.json').write_text(json.dumps(dict(protocol='Six normal trajectories initially; additional P13 single scalar outcomes shared with the endpoint baseline. Query one P11 single-event flight at each step, never any P13 AB. Known normal initial-state templates used in all forecasts. All policies share the identical grey-box parameter updater to isolate query choice.',initial_physical_trajectories=6,initial_scalar_history=len(initial),results=results,elapsed_s=time.perf_counter()-started),indent=2))
(ROOT/'trajectory_prediction_cache.json').write_text(json.dumps([dict(selected=list(k),**v) for k,v in cache.items()],indent=2))

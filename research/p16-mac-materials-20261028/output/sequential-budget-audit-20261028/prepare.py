from pathlib import Path
import sys,json,copy,numpy as np
ROOT=Path(__file__).resolve().parent;OLD=ROOT.parent/'model-search-20261028';sys.path.insert(0,str(OLD))
import h2_preflight as h2
from h2_strict_compare import load,features
from h2_continuation import DOCS
from h1_probe import spec_model
raw=json.loads((ROOT.parent/'offline-adjoint-20261028/upstream/data/p13-20261026-results-v3/cases.json').read_text())['rows'];original=load();training=[dict(r,y=float(r['task']=='FAILURE')) for r in original if r['branch'] in ['NORMAL','A','B']];trheight=[dict(r,y=r['height']) for r in training if not r['censored']]
h2.M=json.loads((OLD/'h2_strict_singles.json').read_text())['model'];results=[]
for r in sorted([r for r in raw if r['branch']=='AB'],key=lambda r:r['id']):
 q=copy.deepcopy(r);init=next(x['initial'] for x in raw if x['family']==r['family'] and x['block']==r['block'] and x['branch']=='NORMAL');q['initial']=copy.deepcopy(init);p,t=h2.forecast(q);f=features(init,DOCS[r['family']]['plan'],r['branch'],r['gap_s']);results.append(dict(**p,group=r['family']+'|'+r['arm'],gap=r['gap_s'],label=float(r['task']=='FAILURE'),task=r['task'],plan=f['plan'],kernel=[(f['angle']-15)/30,r['gap_s']/1.45]));print(r['id'],round(p['predicted_tilt'],2),round(p['prediction'],3),flush=True)
from sklearn.ensemble import ExtraTreesRegressor
oldstrong=json.loads((OLD/'h2_strong_baselines.json').read_text());spec=next(r for r in oldstrong['results'] if r['outcome']=='height')['specs']['ExtraTrees_plan'];hm=ExtraTreesRegressor(n_estimators=100,max_depth=spec['depth'],min_samples_leaf=spec['leaf'],random_state=0,n_jobs=1).fit([r['plan'] for r in trheight],[r['height'] for r in trheight])
# Frozen cheap task ranker from the previous training-only CV: degree1,alpha1.
cm=spec_model(dict(kind='ridge',degree=1,alpha=1)).fit([r['plan'] for r in training],[r['y'] for r in training]);groups=[]
for group in sorted(set(r['group'] for r in results)):
 rr=[r for r in results if r['group']==group];r=rr[0];same=[q for q in training if q['branch']=='B'];dist=np.array([abs(q['angle']-(15+30*r['kernel'][0]))+abs(q['gap']-r['gap']) for q in same]);match=[q for q,d in zip(same,dist) if abs(d-dist.min())<1e-7];heightmatch=[q for q in match if not q['censored']]
 if not heightmatch:raise ValueError('No complete lookup template')
 groups.append(dict(id=group,plan=r['plan'],kernel=r['kernel'],family=r['family'],gap=r['gap'],cases=[dict(id=q['id'],block=q['block'],y=q['label'],height=q['actual'],height_known=not q['actual_censored'],tilt=q['actual_tilt']) for q in sorted(rr,key=lambda q:q['block'])],priors=dict(greybox=float(np.mean([q['predicted_tilt']>45 or q['prediction']>1 for q in rr])),cheap=float(cm.predict([r['plan']])[0]),lookup=float(np.mean([q['y'] for q in match]))),height_priors=dict(greybox=float(np.mean([q['prediction'] for q in rr])),cheap=float(hm.predict([r['plan']])[0]),lookup=float(np.mean([q['height'] for q in heightmatch])))))
(ROOT/'prepared.json').write_text(json.dumps(dict(training=training,training_height=trheight,groups=groups,nominal_forecasts=results,height_cheap_spec=spec),indent=2));print('PRIORS',[(r['id'],r['priors'],r['height_priors']) for r in groups],flush=True)

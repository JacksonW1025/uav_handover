from pathlib import Path
import json,sys,numpy as np
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.kernel_ridge import KernelRidge
from sklearn.ensemble import ExtraTreesRegressor,GradientBoostingRegressor
from h2_strict_compare import load
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT.parent/'heldout-composition-audit-20261028'));from audit import StateSplit

def main():
 rr=load();out=[]
 for outcome in ['height','tilt','task']:
  tr=[dict(r,y=float(r['task']=='FAILURE') if outcome=='task' else r[outcome]) for r in rr if r['branch'] in ['NORMAL','A','B'] and (outcome!='height' or not r['censored'])];te=[dict(r,y=float(r['task']=='FAILURE') if outcome=='task' else r[outcome]) for r in rr if r['stage']=='P13' and r['branch']=='AB'];groups=np.array([r['group'] for r in tr]);y=np.array([r['y'] for r in tr]);pred={};specs={}
  for feature in ['plan','norms']:
   X=np.array([r[feature] for r in tr]);T=np.array([r[feature] for r in te]);candidates=[]
   for alpha in [.001,.1,1.,10.]:
    for gamma in [.03,.3,3.]:candidates.append((dict(kind='RBF',alpha=alpha,gamma=gamma),lambda alpha=alpha,gamma=gamma:make_pipeline(StandardScaler(),KernelRidge(alpha=alpha,kernel='rbf',gamma=gamma))))
   for depth in [2,4,None]:
    for leaf in [1,3]:candidates.append((dict(kind='ExtraTrees',depth=depth,leaf=leaf),lambda depth=depth,leaf=leaf:ExtraTreesRegressor(n_estimators=100,max_depth=depth,min_samples_leaf=leaf,random_state=0,n_jobs=1)))
   for depth in [1,2,3]:candidates.append((dict(kind='GBR',depth=depth),lambda depth=depth:GradientBoostingRegressor(n_estimators=100,max_depth=depth,learning_rate=.05,random_state=0)))
   best={}
   for spec,build in candidates:
    errors=[]
    for g in sorted(set(groups)):
     mask=groups!=g;m=build().fit(X[mask],y[mask]);errors.extend((m.predict(X[~mask])-y[~mask])**2)
    err=float(np.mean(errors));kind=spec['kind']
    if kind not in best or err<best[kind][0]:best[kind]=(err,spec,build)
   for kind,(err,spec,build) in best.items():key=kind+'_'+feature;pred[key]=build().fit(X,y).predict(T).tolist();specs[key]=dict(**spec,cv_mse=err)
  # State partition has the same historical conditions; repeats are grouped.
  h=lambda r:[float(r['branch']=='A'),0.];s=lambda r:[r['angle']/90,float(r['branch']=='B'),r['gap']/2 if r['branch']=='B' else 0.]
  best=None
  for states in [1,2,3,4]:
   for alpha in [.01,.1,1,10]:
    errors=[]
    for group in sorted(set(groups)):
     train=[r for r,g in zip(tr,groups) if g!=group];test=[r for r,g in zip(tr,groups) if g==group];m=StateSplit(states,alpha).fit(np.array([h(r) for r in train]),np.array([s(r) for r in train]),np.array([r['y'] for r in train]));pp=m.predict(np.array([h(r) for r in test]),np.array([s(r) for r in test]));errors.extend((pp-np.array([r['y'] for r in test]))**2)
    err=float(np.mean(errors))
    if best is None or err<best[0]:best=(err,states,alpha)
  m=StateSplit(best[1],best[2]).fit(np.array([h(r) for r in tr]),np.array([s(r) for r in tr]),y);pred['state_partition']=m.predict(np.array([[1.,0.] for r in te]),np.array([[r['angle']/90,1.,r['gap']/2] for r in te])).tolist();specs['state_partition']=dict(cv_mse=best[0],states=best[1],alpha=best[2]);stats={};threshold=1 if outcome=='height' else 45 if outcome=='tilt' else .5
  for name,values in pred.items():
   p=np.array(values);yte=np.array([r['y'] for r in te]);complete=np.array([not r['censored'] for r in te]);positive=yte>threshold;negative=(np.ones(len(te),bool) if outcome=='task' else complete)&~positive;choices=[]
   for block in [1,2,3]:
    ix=[i for i,r in enumerate(te) if r['block']==block];bestscore=max(p[ix]);chosen=[i for i in ix if abs(p[i]-bestscore)<1e-9];choices.append(dict(block=block,ids=[te[i]['id'] for i in chosen],task_yield=float(np.mean([te[i]['task']=='FAILURE' for i in chosen])),observed_tilt=float(np.mean([te[i]['tilt'] for i in chosen]))))
   stats[name]=dict(MAE=float(np.mean(abs(p[complete]-yte[complete]))),FN=int(np.sum(p[positive]<=threshold)),FP=int(np.sum(p[negative]>threshold)),choices=choices)
  result=dict(outcome=outcome,ids=[r['id'] for r in te],actual=[r['y'] for r in te],predictions=pred,specs=specs,metrics=stats);out.append(result);print(outcome,{k:(round(v['MAE'],4),v['FN'],v['FP']) for k,v in stats.items()},flush=True);(ROOT/'h2_strong_baselines.json').write_text(json.dumps(dict(scope='Strict all-combinations-heldout P11/P13 protocol; RBF, ExtraTrees, gradient boosting and state partition. Hyperparameters selected by whole-single-condition CV. All18 AB candidates remain in decision pool.',results=out),indent=2))
if __name__=='__main__':main()

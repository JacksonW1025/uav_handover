from pathlib import Path
import json,numpy as np
from sklearn.ensemble import ExtraTreesRegressor
import sequential as s
ROOT=Path(__file__).resolve().parent;OLD=ROOT.parent/'model-search-20261028';TR=s.TR

def duration(r):
 a=b=0.
 if r['stage']=='P11':
  rid=r['id'].replace('p11-','');d=json.loads((OLD/'upstream/data/p11-20261025-formal'/rid/'packed/prediction-input.json').read_text());length=sum(z-y for y,z in d['plan']['windows_profile_s']);a=length if r['branch']=='A' else 0;b=length if r['branch']=='B' else 0
 else:a=.36 if r['branch'] in ['A','AB','REPAIR'] else 0;b=.36 if r['branch'] in ['B','AB','REPAIR'] else 0
 return [a,b,a+b,max(a,b),max(0,a-.2)+max(0,b-.2),max(0,a-.2)**2+max(0,b-.2)**2]
X=np.array([r['plan']+duration(r) for r in TR]);Y=s.Y0;Q=np.array([r['plan']+duration(dict(stage='P13',branch='AB')) for r in s.GROUPS]);cache={}
def predict(counts,sums):
 key=tuple(counts.tolist()+sums.astype(int).tolist())
 if key not in cache:
  xx=[X];yy=[Y]
  for i,n in enumerate(counts):
   if n:xx.append(np.repeat(Q[i:i+1],n,axis=0));yy.append(np.r_[np.ones(int(sums[i])),np.zeros(int(n-sums[i]))])
  model=ExtraTreesRegressor(n_estimators=64,max_depth=None,min_samples_leaf=1,random_state=0,n_jobs=1).fit(np.concatenate(xx),np.concatenate(yy));cache[key]=model.predict(Q)
 return cache[key].copy()
base=s.Learner
class Tree(base):
 def __init__(self,name,K,task_noise=.25,height_ratio=.16):super().__init__('cheap_gp',K,task_noise,height_ratio)
 def predict(self):return predict(self.count,self.ys),self.hm.copy()
s.Learner=Tree
results=[];arrays={};repeats=30
for policy in ['map_variance','risk','random']:
 arr=np.zeros((15,repeats,13,4))
 for f,fold in enumerate(s.FOLDS):
  for i in range(repeats):arr[f,i]=s.run('semantic_tree',policy,fold,10000*f+i,s.kernel())[0]
 curve=s.aggregate(arr);results.append(dict(learner='semantic_tree',policy=policy,curve=[dict(budget=i,accuracy=float(v[0]),brier=float(v[1]),height_MAE=float(v[2])) for i,v in enumerate(curve)]));arrays[policy]=arr;print(policy,[(i,round(curve[i,0],3),round(curve[i,1],3)) for i in [0,1,2,4,8,12]],'cached_models',len(cache),flush=True)
np.savez_compressed(ROOT/'semantic_tree_scores.npz',**arrays);(ROOT/'semantic_tree_results.json').write_text(json.dumps(dict(scope='Post-primary strong cheap baseline: full-depth ExtraTrees refit after each revealed test, with actual planned A/B durations and timeout-exposure features. Fixed64 trees/leaf1, no heldout tuning.30 repeat schedules. Height retains shared residual updater; task endpoint is native tree refitting.',results=results,repetitions=repeats,cached_models=len(cache)),indent=2))

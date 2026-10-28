from pathlib import Path
import json,sys,numpy as np
from sklearn.preprocessing import PolynomialFeatures,StandardScaler
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
import sequential as s
ROOT=Path(__file__).resolve().parent
X=s.X0;y=s.Y0;groups=np.array([r['group'] for r in s.TR]);cv=[]
for alpha in [.01,.1,1,10,100]:
 err=[]
 for group in sorted(set(groups)):
  tr=groups!=group;m=make_pipeline(StandardScaler(),PolynomialFeatures(2,include_bias=False),Ridge(alpha=alpha)).fit(X[tr],y[tr]);err.extend((m.predict(X[~tr])-y[~tr])**2)
 cv.append((float(np.mean(err)),alpha))
alpha=min(cv)[1];sc=StandardScaler().fit(X);poly=PolynomialFeatures(2,include_bias=False).fit(sc.transform(X));A=np.c_[np.ones(len(X)),poly.transform(sc.transform(X))];Q=np.c_[np.ones(6),poly.transform(sc.transform(s.PLANS))];pen=np.diag([0.]+[alpha]*(A.shape[1]-1));iv=np.linalg.inv(A.T@A+pen);QM=Q@iv@A.T@y;QC=Q@iv@Q.T
class Extended(s.Learner):
 def __init__(self,name,K,task_noise=.25,height_ratio=.16):
  super().__init__('cheap_gp' if name=='cheap_quadratic' else 'lookup_native' if name=='lookup_shrunk' else name,K,task_noise,height_ratio);self.extension=name;self.qm=QM.copy();self.qc=QC.copy()
 def predict(self):
  mu,hm=super().predict()
  if self.extension=='cheap_quadratic':return self.qm.copy(),hm
  if self.extension=='lookup_shrunk':
   mu=s.PRIORS['lookup'].copy();hm=s.HPRIORS['lookup'].copy()
   for j in range(6):
    for val,cnt,total,prior in [(mu,self.count,self.ys,s.PRIORS['lookup']),(hm,self.hcount,self.hs,s.HPRIORS['lookup'])]:
     avail=[i for i in range(6) if cnt[i]>0 and s.GROUPS[i]['family']==s.GROUPS[j]['family']]
     if not avail:continue
     dist=np.array([abs(s.GROUPS[i]['gap']-s.GROUPS[j]['gap']) for i in avail]);near=[i for i,d in zip(avail,dist) if abs(d-dist.min())<1e-10];n=sum(cnt[i] for i in near);val[j]=(sum(total[i] for i in near)+6*prior[j])/(n+6)
  return mu,hm
 def update(self,j,observation):
  super().update(j,observation)
  if self.extension=='cheap_quadratic':
   gain=self.qc[:,j]/(1+self.qc[j,j]);self.qm+=gain*(observation['y']-self.qm[j]);self.qc-=np.outer(gain,self.qc[j,:]);self.qc=(self.qc+self.qc.T)/2
s.Learner=Extended
oldchoose=s.choose
def choose(model,policy,remaining,target,rng):
 if policy!='height_variance':return oldchoose(model,policy,remaining,target,rng)
 available=np.flatnonzero(remaining>0);completion=(model.hcount[available]+1)/(model.count[available]+2);score=np.sum(model.HC[np.ix_(target,available)]**2,axis=0)/(model.height_ratio+np.diag(model.HC)[available])*completion;best=available[np.isclose(score,score.max(),rtol=0,atol=1e-10)];return int(rng.choice(best))
s.choose=choose
results=[];arrays={};repeats=120
for name in ['cheap_quadratic','lookup_shrunk','greybox_gp']:
 for policy in (['map_variance','risk','random','height_variance'] if name!='greybox_gp' else ['height_variance']):
  a=np.zeros((15,repeats,13,4))
  for f,fold in enumerate(s.FOLDS):
   for i in range(repeats):a[f,i]=s.run(name,policy,fold,10000*f+i,s.kernel())[0]
  curve=s.aggregate(a);key=name+'__'+policy;arrays[key]=a;results.append(dict(learner=name,policy=policy,curve=[dict(budget=i,accuracy=float(v[0]),brier=float(v[1]),height_MAE=float(v[2])) for i,v in enumerate(curve)]));print(name,policy,[(i,round(curve[i,0],3),round(curve[i,1],3),round(curve[i,2],3)) for i in [0,1,2,4,8,12]],flush=True)
# Sensitivity is reported as a range; no setting is selected from held-out outcomes.
sensitivity=[]
for length in [.25,.5,1.]:
 for noise in [.1,.25,1.]:
  for name in ['greybox_gp','cheap_gp','lookup_gp']:
   a=np.zeros((15,30,13,4))
   for f,fold in enumerate(s.FOLDS):
    for i in range(30):a[f,i]=s.run(name,'map_variance',fold,10000*f+i,s.kernel(length),task_noise=noise,height_ratio=noise)[0]
   curve=s.aggregate(a);sensitivity.append(dict(length=length,noise_ratio=noise,learner=name,curve=curve.tolist()))
np.savez_compressed(ROOT/'robustness_scores.npz',**arrays);(ROOT/'robustness_results.json').write_text(json.dumps(dict(interpretation='Post-primary robustness checks, not held-out-selected replacements. Quadratic ridge alpha selected only by initial-history whole-condition CV. Shrunk lookup uses fixed6 prior pseudo-observations. Height-directed acquisition uses only past completion evidence. Sensitivity settings are all retained.',quadratic_initial_cv=cv,quadratic_alpha=alpha,results=results,sensitivity=sensitivity),indent=2));print('DONE',flush=True)

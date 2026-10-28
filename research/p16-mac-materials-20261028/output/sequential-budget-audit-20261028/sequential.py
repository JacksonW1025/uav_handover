from pathlib import Path
import itertools,json,numpy as np,time
from sklearn.preprocessing import StandardScaler
ROOT=Path(__file__).resolve().parent
DATA=json.loads((ROOT/'prepared.json').read_text());GROUPS=DATA['groups'];N=6
LEARNERS=['greybox_gp','cheap_ridge','lookup_native','cheap_gp','lookup_gp'];POLICIES=['map_variance','risk','random'];FOLDS=list(itertools.combinations(range(N),2))
FEATURES=np.array([r['kernel'] for r in GROUPS]);PLANS=np.array([r['plan'] for r in GROUPS]);TR=DATA['training'];X0=np.array([r['plan'] for r in TR]);Y0=np.array([r['y'] for r in TR]);SC=StandardScaler().fit(X0);Z0=np.c_[np.ones(len(X0)),SC.transform(X0)];Z=np.c_[np.ones(N),SC.transform(PLANS)];PEN=np.diag([0.]+[1.]*(Z0.shape[1]-1));INV=np.linalg.inv(Z0.T@Z0+PEN);BETA=INV@Z0.T@Y0
PRIORS={k:np.array([r['priors'][k] for r in GROUPS]) for k in ['greybox','cheap','lookup']};HPRIORS={k:np.array([r['height_priors'][k] for r in GROUPS]) for k in PRIORS}
assert np.max(abs(Z@BETA-PRIORS['cheap']))<1e-8

def kernel(length=.5):
 d=FEATURES[:,None,:]-FEATURES[None,:,:];return np.exp(-np.sum(d*d,axis=2)/(2*length**2))

class Learner:
 def __init__(self,name,K,task_noise=.25,height_ratio=.16):
  self.name=name;self.prior='greybox' if name.startswith('greybox') else 'cheap' if name.startswith('cheap') else 'lookup';self.mu=PRIORS[self.prior].copy();self.hm=HPRIORS[self.prior].copy();self.C=K.copy();self.HC=K.copy();self.noise=task_noise;self.height_ratio=height_ratio;self.inv=INV.copy();self.beta=BETA.copy();self.count=np.zeros(N,int);self.ys=np.zeros(N);self.hcount=np.zeros(N,int);self.hs=np.zeros(N)
 def predict(self):
  if self.name=='cheap_ridge':return Z@self.beta,self.hm.copy()
  if self.name=='lookup_native':
   mu=PRIORS['lookup'].copy();hm=HPRIORS['lookup'].copy()
   for j in range(N):
    for val,cnt,total in [(mu,self.count,self.ys),(hm,self.hcount,self.hs)]:
     available=[i for i in range(N) if cnt[i]>0 and GROUPS[i]['family']==GROUPS[j]['family']]
     if not available:continue
     d=np.array([abs(GROUPS[i]['gap']-GROUPS[j]['gap']) for i in available]);near=[i for i,dist in zip(available,d) if abs(dist-d.min())<1e-10];val[j]=sum(total[i] for i in near)/sum(cnt[i] for i in near)
   return mu,hm
  return self.mu.copy(),self.hm.copy()
 def update(self,j,observation):
  y=observation['y'];gain=self.C[:,j]/(self.noise+self.C[j,j]);self.mu+=gain*(y-self.mu[j]);self.C-=np.outer(gain,self.C[j,:]);self.C=(self.C+self.C.T)/2
  if self.name=='cheap_ridge':
   a=self.inv@Z[j];den=1+Z[j]@a;self.beta+=a/den*(y-Z[j]@self.beta);self.inv-=np.outer(a,a)/den
  self.count[j]+=1;self.ys[j]+=y
  if observation['height_known']:
   y=observation['height'];gain=self.HC[:,j]/(self.height_ratio+self.HC[j,j]);self.hm+=gain*(y-self.hm[j]);self.HC-=np.outer(gain,self.HC[j,:]);self.HC=(self.HC+self.HC.T)/2;self.hcount[j]+=1;self.hs[j]+=y

def choose(model,policy,remaining,target,rng):
 available=np.flatnonzero(remaining>0)
 if policy=='random':return int(rng.choice(available,p=remaining[available]/remaining[available].sum()))
 if policy=='risk':score=model.predict()[0][available]
 else:score=np.sum(model.C[np.ix_(target,available)]**2,axis=0)/(model.noise+np.diag(model.C)[available])
 best=available[np.isclose(score,score.max(),rtol=0,atol=1e-10)];return int(rng.choice(best))

def score(mu,hm,target,groups=GROUPS):
 p=np.clip(mu,0,1);correct=0;count=0;brier=[];hsum=0.;hn=0
 for j in target:
  outcomes=groups[j]['cases'];y=np.array([r['y'] for r in outcomes]);correct+=np.sum((p[j]>.5)==y);count+=len(y);brier.append((p[j]-y.mean())**2)
  for r in outcomes:
   if r['height_known']:hsum+=abs(max(0,hm[j])-r['height']);hn+=1
 return [correct/count,float(np.mean(brier)),hsum,hn]

def run(name,policy,fold,seed,K,task_noise=.25,height_ratio=.16,groups=GROUPS):
 target=list(fold);available=[j for j in range(N) if j not in target];remaining=np.zeros(N,int);remaining[available]=3;counts=np.zeros(N,int);rng=np.random.default_rng(seed);orders=[rng.permutation(3) for _ in range(N)];model=Learner(name,K,task_noise,height_ratio);metrics=[];sequence=[];predictions=[]
 for budget in range(13):
  mu,hm=model.predict();metrics.append(score(mu,hm,target,groups));predictions.append(np.r_[mu,hm].tolist())
  if budget==12:break
  j=choose(model,policy,remaining,target,rng);assert j not in target;rep=int(orders[j][counts[j]]);observation=groups[j]['cases'][rep];model.update(j,observation);sequence.append(dict(group=groups[j]['id'],case=observation['id'],label=observation['y'],height_revealed=observation['height_known']));counts[j]+=1;remaining[j]-=1
 return np.array(metrics),sequence,np.array(predictions)

def aggregate(arr):
 # arr dimensions fold,repeat,budget,metric; each target case appears equally often.
 avg=np.mean(arr,axis=(0,1));avg[:,2]=np.sum(arr[:,:,:,2],axis=(0,1))/np.sum(arr[:,:,:,3],axis=(0,1));return avg[:,:3]

def threshold(curve,threshold,larger):
 mask=curve>=threshold-1e-12 if larger else curve<=threshold+1e-12;idx=np.flatnonzero(mask);persistent=[i for i in idx if mask[i:].all()];return dict(first=int(idx[0]) if len(idx) else None,persistent=int(persistent[0]) if persistent else None)

def main():
 started=time.perf_counter();repeats=120;K=kernel();all_scores=np.zeros((len(LEARNERS),len(POLICIES),15,repeats,13,4));examples=[];summary=[]
 for a,name in enumerate(LEARNERS):
  for b,policy in enumerate(POLICIES):
   for f,fold in enumerate(FOLDS):
    for s in range(repeats):
     metrics,sequence,pred=run(name,policy,fold,10000*f+s,K);all_scores[a,b,f,s]=metrics
     if s==0:examples.append(dict(learner=name,policy=policy,heldout=[GROUPS[j]['id'] for j in fold],sequence=sequence,predictions=pred.tolist(),metrics=metrics.tolist()))
   curve=aggregate(all_scores[a,b]);hits=dict(accuracy={str(t):threshold(curve[:,0],t,True) for t in [.8,.9]},brier={str(t):threshold(curve[:,1],t,False) for t in [.1,.05,.02]},height_MAE={str(t):threshold(curve[:,2],t,False) for t in [.15,.1]});summary.append(dict(learner=name,policy=policy,curve=[dict(budget=i,accuracy=float(v[0]),brier=float(v[1]),height_MAE=float(v[2])) for i,v in enumerate(curve)],thresholds=hits));print(name,policy,[(i,round(curve[i,0],3),round(curve[i,1],3),round(curve[i,2],3)) for i in [0,1,2,4,8,12]],flush=True)
 np.savez_compressed(ROOT/'sequential_scores.npz',scores=all_scores);(ROOT/'sequential_examples.json').write_text(json.dumps(examples,indent=2));(ROOT/'sequential_results.json').write_text(json.dumps(dict(protocol='protocol.json',groups=[r['id'] for r in GROUPS],folds=[[GROUPS[j]['id'] for j in f] for f in FOLDS],repetitions=repeats,metrics=['task_accuracy','configuration_failure_frequency_Brier','height_MAE'],learners=LEARNERS,policies=POLICIES,results=summary,elapsed_s=time.perf_counter()-started),indent=2))
 # Targets cannot influence the query policy or update path.
 import copy
 changed=copy.deepcopy(GROUPS);fold=FOLDS[0]
 for j in fold:
  for r in changed[j]['cases']:r['y']=1-r['y'];r['height']+=7
 audit=[]
 for name in LEARNERS:
  for policy in POLICIES:
   a,s,p=run(name,policy,fold,901,K);b,t,q=run(name,policy,fold,901,K,groups=changed);assert s==t and np.array_equal(p,q);audit.append(dict(learner=name,policy=policy,target_label_invariance=True))
 (ROOT/'sequential_integrity.json').write_text(json.dumps(dict(target_mutation_checks=audit,evaluation_targets_never_queried=True,budget_unit='one archived individual-flight result',unqueried_realized_initial_states_used=False),indent=2))
if __name__=='__main__':main()

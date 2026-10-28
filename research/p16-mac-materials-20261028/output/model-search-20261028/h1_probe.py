from pathlib import Path
import json,itertools,time,hashlib
import numpy as np
from sklearn.preprocessing import StandardScaler,PolynomialFeatures
from sklearn.linear_model import Ridge
from sklearn.tree import DecisionTreeRegressor
from sklearn.pipeline import make_pipeline

ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parent.parent
P=dict(np.load(PROJECT/'output/offline-adjoint-20261028/upstream/data/p11-20261025-formal/models/policy.npz'))
def policy(h,prev):
 x=np.r_[np.zeros(3),np.eye(3).flatten(),np.zeros(6),prev]
 e=np.maximum(0,P['W0']@x+P['b0']);gi=P['Wi']@e+P['bi'];gh=P['Wh']@h+P['bh'];sig=lambda z:1/(1+np.exp(-z))
 reset=sig(gi[:16]+gh[:16]);update=sig(gi[16:32]+gh[16:32]);candidate=np.tanh(gi[32:]+reset*gh[32:]);new=(1-update)*candidate+update*h
 return new,np.clip(P['W2']@new+P['b2'],-1,1)
def motors(a):return .5*(a[[0,2,3,1]]+1)
def action(u):return 2*u[[0,3,1,2]]-1
def replay(h,a,n,phase):
 hist=a.copy();h=h.copy();a=a.copy()
 for k in range(n):
  commit=k%2==phase
  if k:hist=(hist+a)/2 if commit else a.copy()
  hh,a=policy(h,hist)
  if commit:h=hh
 return motors(a)
def load():
 out=[]
 for p in sorted((PROJECT/'output/heldout-composition-audit-20261028/upstream/data').glob('*/p3-metrics.json')):
  r=json.loads(p.read_text());e=r['second_entry'];ev=r['events']['second_C_to_N'];entry=e['px4_us'];t=np.array(ev['curves']['motor_t_s'])*1e6+ev['change_px4_us'];idx=np.flatnonzero(t<entry-1e-3)[-1];classic=np.array(ev['curves']['motor'][idx]);tr=r['treatment']
  if tr=='N0':h=np.zeros(16);a=np.zeros(4)
  elif tr=='N3':h=np.array(r['exit']['gru']);a=np.array(r['exit']['previous_action'])
  else:h=np.array(e['gru_before']);a=action(classic) if tr=='N2' else np.array(e['previous_action_before'])
  # The written state is checked only as a diagnostic, never used by predictors.
  consistency=float(np.max(np.abs(np.r_[h,a]-np.r_[e['gru_written'],e['previous_action_written']])))
  native_pred={}
  for n in [1,3,4,5]:native_pred['source_'+str(n)+'calls']=float(np.mean([np.max(np.abs(replay(h,a,n,ph)-classic)) for ph in [0,1]]))
  native_pred['previous_only']=float(np.max(np.abs(motors(a)-classic)));native_pred['readout_only']=float(np.max(np.abs(motors(np.clip(P['W2']@h+P['b2'],-1,1))-classic)))
  plan=np.r_[r['deactivation']['requested_s']/10,float(r['condition']=='D3'),[float(tr==z) for z in ['N0','N2','N2s','N3']]]
  numeric=np.r_[h,a,classic,plan];norms=np.r_[np.linalg.norm(h),np.linalg.norm(a),np.max(np.abs(a)),np.mean(a),np.linalg.norm(a-action(classic)),np.mean(classic),plan]
  out.append(dict(id=p.parent.name,condition=r['condition'],treatment=tr,rep=int(p.parent.name[-1]),group=r['condition']+'|'+tr,x=numeric.tolist(),norms=norms.tolist(),pred=native_pred,y=ev['motor']['step_at_change'],h=h.tolist(),previous=a.tolist(),classic=classic.tolist(),source_rewrite_check=consistency))
 return out
def spec_model(spec):
 if spec['kind']=='ridge':return make_pipeline(StandardScaler(),PolynomialFeatures(spec['degree'],include_bias=False),Ridge(alpha=spec['alpha']))
 return DecisionTreeRegressor(max_depth=spec['depth'],min_samples_leaf=spec['leaf'],random_state=0)
def fit_baseline(train,feature):
 specs=[dict(kind='ridge',degree=d,alpha=a) for d in [1,2] for a in [.01,.1,1,10,100]]+[dict(kind='tree',depth=d,leaf=l) for d in [1,2,3,4] for l in [1,3]]
 x=np.array([r[feature] for r in train]);y=np.array([r['y'] for r in train]);g=np.array([r['group'] for r in train]);cv=[]
 for spec in specs:
  errors=[]
  for group in sorted(set(g)):
   model=spec_model(spec).fit(x[g!=group],y[g!=group]);errors.extend((model.predict(x[g==group])-y[g==group])**2)
  cv.append(float(np.mean(errors)))
 i=int(np.argmin(cv));return spec_model(specs[i]).fit(x,y),dict(spec=specs[i],cv_mse=cv[i])
def metrics(rows,pred):
 y=np.array([r['y'] for r in rows]);p=np.array(pred);pools=[]
 for cond,rep in sorted(set((r['condition'],r['rep']) for r in rows)):
  ix=[i for i,r in enumerate(rows) if r['condition']==cond and r['rep']==rep]
  if len(ix)<2:continue
  yy=y[ix];pp=np.round(p[ix],10);worst=pp==pp.max();best=pp==pp.min()
  pools.append(dict(condition=cond,rep=rep,arms=[rows[i]['treatment'] for i in ix],pred=pp.tolist(),actual=yy.tolist(),worst_regret=float(yy.max()-np.mean(yy[worst])),best_regret=float(np.mean(yy[best])-yy.min()),worst_hit=float(np.mean(np.isclose(yy[worst],yy.max()))),best_hit=float(np.mean(np.isclose(yy[best],yy.min())))))
 return dict(mae=float(np.mean(np.abs(p-y))),rmse=float(np.sqrt(np.mean((p-y)**2))),pools=pools,worst_regret=float(np.mean([z['worst_regret'] for z in pools])) if pools else None,best_regret=float(np.mean([z['best_regret'] for z in pools])) if pools else None)
def main():
 rows=load();results=[];start=time.perf_counter()
 for field,values in [('treatment',['N0','N2','N2s','N3']),('condition',['D1','D2','D3'])]:
  for v in values:
   train=[r for r in rows if r[field]!=v];test=[r for r in rows if r[field]==v];pred={k:[r['pred'][k] for r in test] for k in rows[0]['pred']};details={}
   for f in ['x','norms']:
    model,info=fit_baseline(train,f);pred['cheap_'+f]=model.predict([r[f] for r in test]).tolist();details[f]=info
   # Historical planned-context nearest-neighbor and numeric-state NN, trained only.
   for f in ['x','norms']:
    x=np.array([r[f] for r in train]);sc=StandardScaler().fit(x);xx=sc.transform(x);p=[]
    for r in test:
     dist=np.sum((xx-sc.transform([r[f]])[0])**2,axis=1);p.append(float(np.mean([train[i]['y'] for i in np.flatnonzero(np.isclose(dist,dist.min(),atol=1e-12,rtol=0))])))
    pred['nearest_'+f]=p
   result=dict(fold=field+'_'+v,train_n=len(train),test_n=len(test),models=details,ids=[r['id'] for r in test],predictions=pred,metrics={k:metrics(test,p) for k,p in pred.items()});results.append(result)
   print(result['fold'],{k:round(z['mae'],4) for k,z in result['metrics'].items()},flush=True)
 out=dict(scope='At reentry, given past history; not pre-inactivity planning. No future physical state or observed latency used.',elapsed_s=time.perf_counter()-start,rows=rows,results=results,protocol_sha256=hashlib.sha256((ROOT/'h1_protocol.json').read_bytes()).hexdigest())
 (ROOT/'h1_results.json').write_text(json.dumps(out,indent=2,allow_nan=False))
if __name__=='__main__':main()

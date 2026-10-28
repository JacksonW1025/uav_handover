"""Predicted-information design of single-event identification queries."""
from pathlib import Path
import sys,json,time,hashlib,numpy as np
from scipy.optimize import lsq_linear
ROOT=Path(__file__).resolve().parent;OLD=ROOT.parent/'offline-adjoint-20261028';sys.path.insert(0,str(ROOT/'upstream/tools'));sys.path.insert(0,str(OLD/'upstream/tools'))
from p11.models import R,speeds,features,motor_step,G,forecast
P=dict(np.load(OLD/'upstream/data/p11-20261025-formal/models/policy.npz'))

def stats(d):
 command=np.array([speeds(a) for a in d['action']]);rot=command.copy()
 for k in range(1,len(rot)):rot[k]=motor_step(rot[k-1],command[max(0,k-2)])
 total=np.sum(rot**2,axis=1)/1e6;diff=np.array([features(a)[1] for a in rot]);st=d['sample_us'].astype(np.int64);lp=d['lp_sample'].astype(np.int64);X=[];Y=[]
 for k in np.flatnonzero(np.diff(lp)>0)+1:
  old=k-1;start=int(np.searchsorted(st,lp[old],side='left'));end=int(np.searchsorted(st,lp[k],side='right'))
  if start<1 or end>len(st) or end<=start:continue
  dt=(lp[k]-lp[old])/1e6;acc=(d['velocity'][k]-d['velocity'][old])/dt;bz=R(d['attitude'][old])[:,2];u=float(np.mean(total[start:end]))
  for axis in range(3):
   x=np.zeros(4);x[0]=-bz[axis]*u;x[axis+1]=-d['velocity'][old,axis];X.append(x);Y.append(acc[axis]-(G if axis==2 else 0.))
 X=np.array(X);Y=np.array(Y);H=[X.T@X];g=[X.T@Y]
 idx=np.flatnonzero(np.diff(st)==4000)+1;wd=(d['omega'][idx]-d['omega'][idx-1])/.004
 for axis in range(3):
  X=np.c_[diff[idx-1,axis],-d['omega'][idx-1,axis]];Y=wd[:,axis];H.append(X.T@X);g.append(X.T@Y)
 return H,g

def predicted_stats(trace,doc):
 n=len(trace);st=doc['initial']['sample_us']+4000*np.arange(n);lp=st-(st-doc['initial']['lp_phase_us'])%8000
 d=dict(action=trace[:,8:12],sample_us=st,lp_sample=lp,velocity=trace[:,45:48],attitude=trace[:,48:52],omega=trace[:,39:42])
 return stats(d)[0]

def fit_stats(H,g):
 coeff=[]
 for i,(a,b) in enumerate(zip(H,g)):
  # Exact sufficient-statistic reconstruction, regularized below machine-level
  # relative scale only to stabilize Cholesky in an inactive channel.
  L=np.linalg.cholesky(a+1e-12*np.diag(np.maximum(np.diag(a),1)))
  X=L.T;y=np.linalg.solve(L,b);bounds=([0]*4,[20,5,5,5]) if i==0 else ([-1000,0],[1000,20]);coef=lsq_linear(X,y,bounds=bounds,tol=1e-12,max_iter=1000).x;coeff.append(coef)
 return dict(kind='M2',thrust=float(coeff[0][0]),drag=coeff[0][1:].tolist(),torque=[float(x[0]) for x in coeff[1:]],angular_drag=[float(x[1]) for x in coeff[1:]])

def add(items):return [sum(x[i] for x in items) for i in range(4)]
def main():
 config=json.loads((ROOT/'upstream/config/p11.json').read_text());base=ROOT/'upstream/data/p11-20261025-formal';normal=[r for r in config['rows'] if r['split']=='development' and r['branch']=='NORMAL'];candidates=[r for r in config['rows'] if r['split']=='development' and r['branch'] in ['A','B']];groups=sorted(set(r['family']+'|'+r['branch'] for r in candidates));h0=[];g0=[]
 for r in normal:
  h,g=stats(dict(np.load(base/r['id']/'packed/measurement.npz')));h0.append(h);g0.append(g)
 H0=add(h0);G0=add(g0);model=fit_stats(H0,G0);known=json.loads((ROOT/'h2_strict_normal_only.json').read_text())['model'];delta=max(abs(np.r_[model['thrust'],model['drag'],model['torque'],model['angular_drag']]-np.r_[known['thrust'],known['drag'],known['torque'],known['angular_drag']]));assert delta<1e-6,delta
 pred=[]
 for group in groups:
  rs=[r for r in candidates if r['family']+'|'+r['branch']==group];hh=[];risk=[];duration=[]
  for r in rs:
   doc=json.loads((base/r['id']/'packed/prediction-input.json').read_text());z=forecast(doc,model,P);hh.append(predicted_stats(z['trace'],doc));risk.append(float(z['trace'][:,7].max()));duration.append(float(z['trace'][-1,0]-z['trace'][0,0]))
  H=add(hh);pred.append(dict(group=group,ids=[r['id'] for r in rs],H=[h.tolist() for h in H],predicted_peak=float(np.mean(risk)),predicted_duration=float(np.mean(duration))))
 scores=[]
 for c in pred:
  H=[np.array(x) for x in c['H']];gains=[]
  for a,b in zip(H0,H):
   diag=np.diag(a);prior=1e-6*np.diag(np.maximum(diag,1));gains.append(float(np.linalg.slogdet(a+b+prior)[1]-np.linalg.slogdet(a+prior)[1]))
  scores.append(dict(group=c['group'],D_gain=sum(gains),block_gains=gains,source_peak=c['predicted_peak'],duration=c['predicted_duration']))
 selected=max(scores,key=lambda x:x['D_gain'])['group'];riskselected=max(scores,key=lambda x:x['source_peak'])['group']
 plan=dict(protocol='Start from6 archived normal trajectories. Candidate groups are6 single-event conditions, each costs2 flights. Choose by predicted Fisher information before reading candidate measured regressions. No P13 outcomes enter choice. Normal model source dynamics forecast gives candidate excitation. Compare D-optimal to maximum predicted tilt and all6 single-query choices.',initial_fit_check=delta,base_model=model,normal_ids=[r['id'] for r in normal],scores=scores,selected_D=selected,selected_maxrisk=riskselected)
 (ROOT/'h4_design_decision.json').write_text(json.dumps(plan,indent=2));print('DECISION',json.dumps(plan),flush=True)
 # Only after selection, fit every choice for exhaustive offline regret audit.
 variants=[]
 for c in pred:
  H=[];gg=[]
  for rid in c['ids']:
   h,g=stats(dict(np.load(base/rid/'packed/measurement.npz')));H.append(h);gg.append(g)
  m=fit_stats(add([H0,*H]),add([G0,*gg]));variants.append(dict(group=c['group'],queried_ids=c['ids'],model=m))
 (ROOT/'h4_query_models.json').write_text(json.dumps(dict(decision_sha256=hashlib.sha256((ROOT/'h4_design_decision.json').read_bytes()).hexdigest(),variants=variants),indent=2))
if __name__=='__main__':main()

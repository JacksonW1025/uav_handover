from pathlib import Path
import json,sys,numpy as np,time
from scipy.optimize import lsq_linear
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
ROOT=Path(__file__).resolve().parent;OLD=ROOT.parent/'offline-adjoint-20261028'
import h2_preflight as h2
from p11.models import R,speeds,features,motor_step,G,plant as physical_plant,qstep
base=ROOT/'upstream/data/p11-20261025-formal';src=json.loads((ROOT/'h2_strict_singles.json').read_text());normal_ids=set(r['id'] for r in json.loads((ROOT/'h2_strict_normal_only.json').read_text())['training']);records=[];normal_collective=[]
for r in src['training']:
 rid=r['id'];d=dict(np.load(base/rid/'packed/measurement.npz'));command=np.array([speeds(a) for a in d['action']]);rot=command.copy()
 for k in range(1,len(rot)):rot[k]=motor_step(rot[k-1],command[max(0,k-2)])
 total=np.sum(rot**2,axis=1)/1e6;st=d['sample_us'].astype(np.int64);lp=d['lp_sample'].astype(np.int64)
 if rid in normal_ids:normal_collective.extend(total.tolist())
 for k in np.flatnonzero(np.diff(lp)>0)+1:
  old=k-1;start=int(np.searchsorted(st,lp[old],side='left'));end=int(np.searchsorted(st,lp[k],side='right'))
  if start<1 or end>len(st) or end<=start:continue
  acc=(d['velocity'][k]-d['velocity'][old])/((lp[k]-lp[old])/1e6);bz=R(d['attitude'][old])[:,2];u=float(np.mean(total[start:end]));records.append((rid,bz,u,d['velocity'][old],acc-np.array([0.,0.,G])))
T0=float(np.mean(normal_collective));X=[];Y=[];affx=[];affy=[];groups=[]
for rid,bz,u,v,y in records:
 lin=T0*bz+np.array([0.,0.,u-T0])
 for axis in range(3):
  x=np.zeros(4);x[0]=-lin[axis];x[1+axis]=-v[axis];X.append(x);Y.append(y[axis])
 affx.append(np.r_[bz,u,v]);affy.append(y);groups.append(rid.split('-r')[0]+'|'+rid.split('-')[-1])
X=np.array(X);Y=np.array(Y);linear=lsq_linear(X,Y,bounds=([0]*4,[20,5,5,5]),tol=1e-12,max_iter=1000).x
X=np.array(affx);Y=np.array(affy);groups=np.array(groups);cv=[]
for alpha in [.001,.01,.1,1.,10.,100.,1000.]:
 err=[]
 for group in sorted(set(groups)):
  tr=groups!=group;sc=StandardScaler().fit(X[tr]);m=Ridge(alpha=alpha).fit(sc.transform(X[tr]),Y[tr]);err.append(float(np.mean((m.predict(sc.transform(X[~tr]))-Y[~tr])**2)))
 cv.append((float(np.mean(err)),alpha))
alpha=min(cv)[1];sc=StandardScaler().fit(X);m=Ridge(alpha=alpha).fit(sc.transform(X),Y);coef=m.coef_/sc.scale_;inter=m.intercept_-coef@sc.mean_
protocol=dict(scope='Same18 P11 normal/single-event trajectories and identical source controller/event logic/angular dynamics. Two translational plant alternatives: local hover force linearization with4 bounded coefficients, and affine8-feature response with group-CV ridge. No P13 labels for fit/selection. Physics model preserves multiplicative thrust-direction geometry.',T0=T0,linear_parameters=linear.tolist(),affine_coefficients=coef.tolist(),affine_intercept=inter.tolist(),affine_cv=cv,affine_selected_alpha=alpha)
(ROOT/'h6_geometry_protocol.json').write_text(json.dumps(protocol,indent=2));rr=[r for r in json.loads((OLD/'upstream/data/p13-20261026-results-v3/cases.json').read_text())['rows'] if r['branch']=='AB'];results=[]
for kind in ['local_linearization','affine_ridge']:
 def plant(p,v,q,w,rot,M):
  pp,vv,qq,ww,_=physical_plant(p,v,q,w,rot,M);u,_=features(rot);bz=R(q)[:,2]
  if kind=='local_linearization':acc=np.array([0.,0.,G])-linear[0]*(T0*bz+np.array([0.,0.,u-T0]))-linear[1:]*v
  else:acc=np.array([0.,0.,G])+coef@np.r_[bz,u,v]+inter
  vv=v+.004*acc;pp=p+.004*(v+vv)/2;return pp,vv,qq,ww,acc
 h2.plant=plant;h2.M=src['model'];out=[]
 for r in rr:
  z,t=h2.forecast(r);out.append(z)
 complete=[r for r in out if not r['actual_censored'] and r['stop'] is None];hp=[r for r in out if r['actual']>1];hn=[r for r in out if not r['actual_censored'] and r['actual']<=1];tp=[r for r in out if r['actual_tilt']>45];tn=[r for r in out if not r['actual_censored'] and r['actual_tilt']<=45]
 metrics=dict(complete_forecast_pairs=len(complete),height_MAE=float(np.mean([abs(r['prediction']-r['actual']) for r in complete])) if complete else None,tilt_MAE=float(np.mean([abs(r['predicted_tilt']-r['actual_tilt']) for r in complete])) if complete else None,height_FN=sum(r['prediction']<=1 for r in hp),height_FP=sum(r['prediction']>1 for r in hn),tilt_FN=sum(r['predicted_tilt']<=45 for r in tp),tilt_FP=sum(r['predicted_tilt']>45 for r in tn),domain_exits=sum(r['stop'] is not None for r in out));results.append(dict(kind=kind,metrics=metrics,results=out));print(kind,metrics,flush=True)
 (ROOT/'h6_geometry_results.json').write_text(json.dumps(dict(protocol=protocol,results=results),indent=2))

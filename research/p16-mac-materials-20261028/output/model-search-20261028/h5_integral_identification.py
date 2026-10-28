from pathlib import Path
import json,sys,numpy as np
from scipy.optimize import lsq_linear
ROOT=Path(__file__).resolve().parent;OLD=ROOT.parent/'offline-adjoint-20261028';sys.path.insert(0,str(ROOT/'upstream/tools'));sys.path.insert(0,str(OLD/'upstream/tools'))
from p11.models import motor_step,speeds,features
base=ROOT/'upstream/data/p11-20261025-formal';normal=json.loads((ROOT/'h2_strict_normal_only.json').read_text());ids=[r['id'] for r in normal['training']];ds=[]
for rid in ids:
 d=dict(np.load(base/rid/'packed/measurement.npz'));command=np.array([speeds(a) for a in d['action']]);rot=command.copy()
 for k in range(1,len(rot)):rot[k]=motor_step(rot[k-1],command[max(0,k-2)])
 dif=np.array([features(a)[1] for a in rot]);ds.append((rid,d,dif))
results=[]
for span in [1,2,4,8,16,32,64,128,256]:
 axes=[];cv=[]
 for axis in range(3):
  xx=[];yy=[];gg=[]
  for rid,d,dif in ds:
   n=len(d['omega']);valid=(d['sample_us'][span:].astype(float)-d['sample_us'][:-span])/1e6==span*.004
   X=np.c_[dif[:,axis],-d['omega'][:,axis]]*.004;c=np.r_[np.zeros((1,2)),np.cumsum(X,axis=0)];integ=c[span:n]-c[:n-span];target=d['omega'][span:,axis]-d['omega'][:-span,axis]
   xx.append(integ[valid]);yy.append(target[valid]);gg.extend([rid]*int(valid.sum()))
  X=np.concatenate(xx);Y=np.concatenate(yy);g=np.array(gg);fit=lsq_linear(X,Y,bounds=([-1000,0],[1000,20]),tol=1e-12,max_iter=1000);axes.append(fit.x.tolist())
  # Comparability: held-flight prediction is assessed on a fixed64ms integral,
  # independent of each candidate fit's integration window.
  errors=[]
  for held in ids:
   model=lsq_linear(X[g!=held],Y[g!=held],bounds=([-1000,0],[1000,20]),tol=1e-10,max_iter=1000).x
   rid,d,dif=next(z for z in ds if z[0]==held);n=len(d['omega']);nwin=16;Z=np.c_[dif[:,axis],-d['omega'][:,axis]]*.004;c=np.r_[np.zeros((1,2)),np.cumsum(Z,axis=0)];integ=c[nwin:n]-c[:n-nwin];target=d['omega'][nwin:,axis]-d['omega'][:-nwin,axis];errors.extend((integ@model-target)**2)
  cv.append(float(np.mean(errors)))
 model=dict(normal['model']);model['torque']=[x[0] for x in axes];model['angular_drag']=[x[1] for x in axes];result=dict(span_steps=span,span_s=span*.004,model=model,cv_fixed64ms_mse=cv,cv_mean=float(np.mean(cv)));results.append(result);print(span,axes,'cv',cv,flush=True)
best=min(results,key=lambda r:r['cv_mean']);(ROOT/'h5_identification.json').write_text(json.dumps(dict(protocol='Normal-only angular dynamics identification by integrated equations. Integration window selected by whole-flight CV on fixed64ms validation increments, before P13 evaluation. Translation coefficients unchanged. No failure/combination outcomes in model selection.',selected_span=best['span_steps'],results=results),indent=2))

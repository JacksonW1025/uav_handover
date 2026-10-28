"""Whole-combination conditional height-map evaluation; never pre-A gap ranking."""
from pathlib import Path
import json,sys,time
import numpy as np
from sklearn.preprocessing import StandardScaler
from h1_probe import fit_baseline
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parent.parent
def rows():
 original=json.loads((PROJECT/'output/offline-adjoint-20261028/upstream/data/p13-20261026-results-v3/cases.json').read_text())['rows'];source={r['id']:r for r in json.loads((ROOT/'h2_source_results.json').read_text())['results']};out=[]
 for r in original:
  if r['id'] not in source:continue
  b=r['B_before']['state'];pred=source[r['id']];has_B=r['branch'] in ['B','AB','REPAIR'];repair=r['branch']=='REPAIR';plan=[float(r['family']=='F4'),float(r['branch'] in ['A','AB','REPAIR']),float(repair),float(has_B),r['gap_s']/2 if has_B else 0,r['phase']/2]
  h=np.array(b['h_before']);prev=np.array(b['previous_action_before']);q=np.array(b['attitude_quaternion']);w=np.array(b['angular_velocity_body_rad_s']);v=np.array(b['velocity_ned_m_s']);e=np.array(b['position_ned_m'])-np.array(b['target_p_ned_m']);dv=v-np.array(b['target_v_ned_m_s'])
  basic=[b['LP_current_loss_m'],b['LP_historical_loss_m'],b['LP_down_velocity_m_s'],max(0,b['LP_down_velocity_m_s'])**2,b['tilt_deg']/45,np.linalg.norm(v[:2]),np.linalg.norm(e[:2]),e[2],np.linalg.norm(dv[:2]),np.linalg.norm(w),np.mean(prev),np.std(prev),np.linalg.norm(h)]
  capture_jump=(1-float(repair))*float(has_B)*np.linalg.norm(v[:2]);semantics=[capture_jump,capture_jump**2,float(has_B)*max(0,.36-.2),float(repair)*.16*2]
  x=np.r_[basic,plan,e,dv,q,w,h,prev,b['history_mean_before'],semantics].tolist();norms=basic+plan+semantics
  out.append(dict(id=r['id'],group=r['family']+'|'+r['arm'],family=r['family'],branch=r['branch'],arm=r['arm'],block=r['block'],gap=r['gap_s'],has_B=has_B,plan=plan,x=x,norms=norms,source=pred['prediction'],y=float(r['LP_max_loss_m']),censored=r['censored'],D=b['LP_historical_loss_m'],L=b['LP_current_loss_m'],W=b['LP_down_velocity_m_s']))
 return out
def summarize(te,p):
 y=np.array([r['y'] for r in te]);p=np.array(p);complete=np.array([not r['censored'] for r in te]);positive=y>1;negative=complete&~positive
 return dict(complete_n=int(complete.sum()),positive_n=int(positive.sum()),negative_n=int(negative.sum()),mae=float(np.mean(abs(p[complete]-y[complete]))) if complete.any() else None,rmse=float(np.sqrt(np.mean((p[complete]-y[complete])**2))) if complete.any() else None,FN=int(np.sum(p[positive]<=1)),FP=int(np.sum(p[negative]>1)))
def main():
 rr=rows();definitions=[('all_AB',lambda r:r['branch']=='AB'),('all_B',lambda r:r['branch']=='B'),('all_REPAIR',lambda r:r['branch']=='REPAIR'),('F2_AB',lambda r:r['family']=='F2' and r['branch']=='AB'),('F4_AB',lambda r:r['family']=='F4' and r['branch']=='AB')]
 for f in ['F2','F4']:definitions.append(('family_'+f,lambda r,f=f:r['family']==f))
 for name,g in [('short',.55),('medium',1.2),('long',2)]:definitions.append(('gap_'+name,lambda r,g=g:r['has_B'] and abs(r['gap']-g)<1e-6))
 results=[]
 for name,fn in definitions:
  tr=[r for r in rr if not fn(r) and not r['censored']];te=[r for r in rr if fn(r) and r['has_B']];pred={'source':[r['source'] for r in te]};models={}
  for feat in ['x','norms']:
   model,spec=fit_baseline(tr,feat);pred['cheap_'+feat]=model.predict([r[feat] for r in te]).tolist();models[feat]=spec
   scale=StandardScaler().fit([r[feat] for r in tr]);x=scale.transform([r[feat] for r in tr]);pp=[]
   for r in te:
    dist=np.sum((x-scale.transform([r[feat]])[0])**2,axis=1);pp.append(float(np.mean([tr[i]['y'] for i in np.flatnonzero(np.isclose(dist,dist.min(),atol=1e-12,rtol=0))])))
   pred['nearest_'+feat]=pp
  # Plan-only lookup with fixed source-semantic fallback, and a context-level
  # estimate that pools unrepaired single/composed events rather than mixing repair.
  xp=np.array([r['plan'] for r in tr]);pp=[];backoff=[]
  for r in te:
   dist=np.sum((xp-np.array(r['plan']))**2,axis=1);pp.append(float(np.mean([tr[i]['y'] for i in np.flatnonzero(np.isclose(dist,dist.min(),atol=1e-12,rtol=0))])))
   matched=[q for q in tr if q['family']==r['family'] and (q['branch']=='REPAIR')==(r['branch']=='REPAIR') and q['has_B']==r['has_B']]
   if not matched:matched=[q for q in tr if (q['branch']=='REPAIR')==(r['branch']=='REPAIR') and q['has_B']==r['has_B']]
   if not matched:matched=tr
   backoff.append(float(np.mean([q['y'] for q in matched])))
  pred['plan_lookup']=pp;pred['semantic_backoff']=backoff
  # Source residual calibration: fixed 1 or 2 parameter maps, with no held-out labels.
  residual=np.array([r['y']-r['source'] for r in tr]);pred['source_offset']=[r['source']+float(residual.mean()) for r in te]
  a=np.array([[1,r['source']] for r in tr]);coef=np.linalg.solve(a.T@a+np.diag([.01,.1]),a.T@residual);pred['source_affine']=[r['source']+float(np.array([1,r['source']])@coef) for r in te];models['source_affine']={'residual_coefficients':coef.tolist(),'ridge_penalty':[.01,.1]}
  # Cheap remaining-height template: historical groups, translated by current L,
  # and a single fitted coefficient for downward velocity (plus current max latch).
  Z=lambda r:np.array([1,float(r['family']=='F4'),float(r['branch']=='REPAIR'),r['W'],float(r['has_B'])])
  z=np.array([Z(r) for r in tr]);y=np.array([r['y']-r['L'] for r in tr]);coef=np.linalg.solve(z.T@z+.1*np.eye(5),z.T@y);pred['height_template']=[max(r['D'],r['L']+float(Z(r)@coef)) for r in te]
  # Every head must respect the observed historical maximum. No fabricated reset.
  pred={m:[max(r['D'],float(v)) for r,v in zip(te,p)] for m,p in pred.items()}
  result=dict(fold=name,train_n=len(tr),test_n=len(te),train_groups=sorted(set(r['group'] for r in tr)),test_groups=sorted(set(r['group'] for r in te)),ids=[r['id'] for r in te],predictions=pred,models=models,metrics={m:summarize(te,p) for m,p in pred.items()});results.append(result)
  print(name,{m:(round(v['mae'],4) if v['mae'] is not None else None,v['FN'],v['FP']) for m,v in result['metrics'].items()},flush=True)
 (ROOT/'h2_comparison.json').write_text(json.dumps(dict(scope='Conditional height response map. No pre-A or pre-recovery candidate choice claim.',rows=rr,results=results),indent=2))
if __name__=='__main__':main()

from pathlib import Path
import json,numpy as np
from h1_probe import fit_baseline
from h2_preflight_compare import metrics
ROOT=Path(__file__).resolve().parent;OLD=ROOT.parent/'offline-adjoint-20261028'

def features(z,plan,branch,gap=None):
 a=float(branch in ['A','AB','REPAIR']);b=float(branch in ['B','AB','REPAIR']);repair=float(branch=='REPAIR');windows=plan['windows_profile_s'];table=np.array(plan['profile']['table']);tt=plan['profile']['table_t0_s']+.004*np.arange(len(table));start=plan['common_first_gap_profile_s']
 if gap is None:
  gb=windows[-1][0]-start-.36 if b else 0;gap=max(0,gb)
 else:gap=gap if b else 0
 ast=start;bst=start+.36+gap;axis=np.array(plan['axis']);theta=np.arctan2(axis[1],axis[0]);pl=[a,b,repair,theta/(np.pi/2),gap/2,np.sin(theta),np.cos(theta),ast/15,bst/15 if b else 0]
 stress=[]
 for t,enabled in [(ast,bool(a)),(bst,bool(b))]:
  vr=np.array([np.interp(t+.2,tt,table[:,3+j]) for j in range(3)]);stress.extend((vr*float(enabled)*(1-repair)).tolist())
 nominal=[np.max(np.linalg.norm(table[:,3:5],axis=1)),np.max(np.linalg.norm(np.diff(table[:,3:5],axis=0)/.004,axis=1))]
 norms=np.r_[np.linalg.norm(z['velocity']),np.linalg.norm(z['omega']),np.linalg.norm(z['h']),np.mean(z['previous']),np.std(z['previous']),np.linalg.norm(np.array(z['position'])-z['target_p'])]
 x=np.r_[pl,stress,nominal,z['position'],z['velocity'],z['attitude'],z['omega'],z['h'],z['previous'],z['history']]
 return dict(plan=np.r_[pl,stress,nominal].tolist(),norms=np.r_[pl,stress,nominal,norms].tolist(),x=x.tolist(),angle=float(theta*180/np.pi))

def load():
 from h2_continuation import DOCS
 config=json.loads((ROOT/'upstream/config/p11.json').read_text());out=[]
 for r in config['rows']:
  if r['split']!='development' or r['branch'] not in ['NORMAL','A','B']:continue
  p=ROOT/'upstream/data/p11-20261025-formal'/r['id'];d=json.loads((p/'packed/prediction-input.json').read_text());m=json.loads((p/'measured/measurement.json').read_text());f=features(d['initial'],d['plan'],r['branch']);out.append(dict(id='p11-'+r['id'],stage='P11',group='P11|'+r['family']+'|'+r['branch'],family=r['family'],arm=r['branch'],branch=r['branch'],block=r['rep'],censored=m['censored'],height=m['whole']['max_altitude_loss_m'],tilt=m['whole']['max_tilt_deg'],task=m['task_outcome'],has_B=r['branch']=='B',gap=f['plan'][4]*2,**f))
 raw=json.loads((OLD/'upstream/data/p13-20261026-results-v3/cases.json').read_text())['rows']
 for r in raw:
  plan=DOCS[r['family']]['plan'];f=features(r['initial'],plan,r['branch'],r['gap_s']);out.append(dict(id=r['id'],stage='P13',group='P13|'+r['family']+'|'+r['arm'],family=r['family'],arm=r['arm'],branch=r['branch'],block=r['block'],censored=r['censored'],height=r['LP_max_loss_m'],tilt=r['LP_peak_tilt_deg'],task=r['task'],has_B=r['branch'] in ['B','AB','REPAIR'],gap=r['gap_s'],**f))
 return out

def main():
 rr=load();modelpred={name:{r['id']:r for r in json.loads((ROOT/f'h2_strict_{name}.json').read_text())['results']} for name in ['singles','normal_only']};results=[]
 for outcome in ['height','tilt','task_probability','tilt_probability','height_probability']:
  base=outcome.split('_')[0];is_probability='probability' in outcome
  labeled=[]
  for r0 in rr:
   r=r0.copy()
   if base=='task':r['y']=float(r['task']=='FAILURE')
   elif is_probability:r['y']=float(r[base]>(1 if base=='height' else 45))
   else:r['y']=r[base]
   # Keep all candidates at selection time; unknown height negatives are
   # excluded only from supervised training and scoring, never from the pool.
   labeled.append(r)
  tr=[r for r in labeled if r['branch'] in ['NORMAL','A','B'] and (base!='height' or not r['censored'] or (is_probability and r['height']>1))]
  te=[r for r in labeled if r['stage']=='P13' and r['branch']=='AB'];pred={};specs={}
  for name,pp in modelpred.items():
   if base=='task':vv=[float(max(pp[r['id']]['predicted_tilt']/45,pp[r['id']]['prediction'])>1) for r in te]
   elif is_probability:vv=[float(pp[r['id']]['predicted_tilt' if base=='tilt' else 'prediction']>(45 if base=='tilt' else 1)) for r in te]
   else:vv=[pp[r['id']]['predicted_tilt' if base=='tilt' else 'prediction'] for r in te]
   pred['source_'+name]=vv
  for f in ['plan','norms','x']:
   model,spec=fit_baseline(tr,f);pred['cheap_'+f]=model.predict([r[f] for r in te]).tolist();specs[f]=spec
  # Entire historical trajectories are available to direct outcome learners. Static
  # semantic lookup shares source-known event branch and planned reference angle.
  sem=[];add=[];maximum=[];lookup=[]
  X=np.array([r['plan'] for r in tr]);scale=np.std(X,axis=0);scale[scale<1e-8]=1
  for r in te:
   dist=np.sum(((X-r['plan'])/scale)**2,axis=1);lookup.append(float(np.mean([tr[i]['y'] for i in np.flatnonzero(np.isclose(dist,dist.min(),atol=1e-12,rtol=0))])))
   def backoff(branch):
    pool=[q for q in tr if q['branch']==branch];d=np.array([abs(q['angle']-r['angle'])+abs(q['gap']-r['gap'])*(1 if branch=='B' else 0) for q in pool]);return float(np.mean([q['y'] for q,z in zip(pool,d) if abs(z-d.min())<1e-7]))
   aa=backoff('A');bb=backoff('B');nn=backoff('NORMAL');sem.append(bb);add.append(aa+bb-nn);maximum.append(max(aa,bb))
  pred.update(plan_lookup=lookup,suffix_lookup=sem,single_additive=add,single_max=maximum)
  threshold=.5 if is_probability else 1 if outcome=='height' else 45
  stats={}
  for name,pp in pred.items():
   y=np.array([r['y'] for r in te]);p=np.array(pp);complete=np.array([not r['censored'] for r in te]);positive=y>threshold;negative=(np.array([not r['censored'] or (base=='task' and r['task']=='SUCCESS') for r in te]) if base=='height' else (np.ones(len(te),bool) if is_probability else complete))&~positive
   chosen=[]
   for block in [1,2,3]:
    ix=[i for i,r in enumerate(te) if r['block']==block];best=max(p[ix]);inds=[i for i in ix if abs(p[i]-best)<1e-9];chosen.append(dict(block=block,ids=[te[i]['id'] for i in inds],observed_mean=float(np.mean(y[inds])),observed_tilt=float(np.mean([te[i]['tilt'] for i in inds])),failure_yield=float(np.mean([te[i]['task']=='FAILURE' for i in inds]))))
   stats[name]=dict(MAE=float(np.mean(abs(p[complete]-y[complete]))),FN=int(np.sum(p[positive]<=threshold)),FP=int(np.sum(p[negative]>threshold)),chosen=chosen)
  result=dict(outcome=outcome,train_n=len(tr),train_ids=[r['id'] for r in tr],test_ids=[r['id'] for r in te],actual=[r['y'] for r in te],predictions=pred,specs=specs,metrics=stats);results.append(result);print(outcome,{k:(round(v['MAE'],4),v['FN'],v['FP']) for k,v in stats.items()},flush=True)
 (ROOT/'h2_strict_comparison.json').write_text(json.dumps(dict(scope='All AB and all repaired combinations withheld across P11 identification and P13 direct outcome training. Extra P13 single-event labels are available to cheap baselines. P11 model structure/source knowledge is shared in semantic features; no future or Bpre state.',rows=rr,results=results),indent=2))
if __name__=='__main__':main()

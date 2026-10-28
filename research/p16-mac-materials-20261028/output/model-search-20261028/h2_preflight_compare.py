"""Exploratory whole-combination response-map and continuous-risk ranking audit."""
from pathlib import Path
import sys,json,numpy as np
from sklearn.preprocessing import StandardScaler
from h1_probe import fit_baseline
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parent.parent
sys.path.insert(0,str(PROJECT/'output/heldout-composition-audit-20261028'))
from audit import StateSplit

def rows(outcome):
 raw=json.loads((PROJECT/'output/offline-adjoint-20261028/upstream/data/p13-20261026-results-v3/cases.json').read_text())['rows'];source={r['id']:r for r in json.loads((ROOT/'h2_preflight_results.json').read_text())['results']};rr=[]
 for r in raw:
  z=r['initial'];a=float(r['branch'] in ['A','AB','REPAIR']);b=float(r['branch'] in ['B','AB','REPAIR']);repair=float(r['branch']=='REPAIR');f=float(r['family']=='F4');g=r['gap_s']/2 if b else 0;plan=[a,b,repair,f,g,r['phase']/2]
  initial=np.r_[z['position'],z['velocity'],z['attitude'],z['omega'],z['h'],z['previous'],z['history'],z['history_count'],z['rotor_filter'],z['pending_command']];norms=np.r_[np.linalg.norm(z['velocity']),np.linalg.norm(z['omega']),np.linalg.norm(z['h']),np.mean(z['previous']),np.std(z['previous']),np.linalg.norm(np.array(z['position'])-z['target_p'])]
  y=r['LP_max_loss_m'] if outcome=='height' else r['LP_peak_tilt_deg'];pred=source[r['id']]['prediction' if outcome=='height' else 'predicted_tilt']
  rr.append(dict(id=r['id'],group=r['family']+'|'+r['arm'],family=r['family'],arm=r['arm'],branch=r['branch'],block=r['block'],has_B=bool(b),gap=r['gap_s'],censored=r['censored'],y=y,source=pred,plan=plan,norms=np.r_[plan,norms].tolist(),x=np.r_[plan,initial].tolist(),h=[a,repair],s=[f,b,repair,g],task=r['task']))
 return rr

def metrics(te,p,outcome):
 y=np.array([r['y'] for r in te]);p=np.array(p);complete=np.array([not r['censored'] for r in te]);threshold=1 if outcome=='height' else 45;pos=y>threshold;neg=complete&~pos
 pools=[]
 # Equal-weight tie handling; no outcome-dependent tie breaking.
 for fam in ['F2','F4','ALL']:
  for block in [1,2,3]:
   ix=[i for i,r in enumerate(te) if r['block']==block and (fam=='ALL' or r['family']==fam)]
   if len(ix)<2:continue
   best=max(p[ix]);chosen=[i for i in ix if abs(p[i]-best)<1e-9];obsmax=max(y[ix]);pools.append(dict(family=fam,block=block,chosen=[te[i]['id'] for i in chosen],observed_top_value=float(np.mean(y[chosen])),observed_regret=float(obsmax-np.mean(y[chosen])),failure_yield=float(np.mean([te[i]['task']=='FAILURE' for i in chosen])),censored_selected=sum(te[i]['censored'] for i in chosen)))
 return dict(n=len(te),complete_n=int(complete.sum()),MAE=float(np.mean(abs(p[complete]-y[complete]))),FN=int(np.sum(p[pos]<=threshold)),FP=int(np.sum(p[neg]>threshold)),pools=pools)

def main():
 results=[]
 for outcome in ['height','tilt']:
  rr=rows(outcome)
  defs=[('all_AB',lambda r:r['branch']=='AB'),('F2_AB',lambda r:r['family']=='F2' and r['branch']=='AB'),('F4_AB',lambda r:r['family']=='F4' and r['branch']=='AB'),('family_F2',lambda r:r['family']=='F2'),('family_F4',lambda r:r['family']=='F4')]
  for name,fn in defs:
   tr=[r for r in rr if not fn(r) and (outcome=='tilt' or not r['censored'])];te=[r for r in rr if fn(r) and r['has_B']];pred={'source':[r['source'] for r in te]};specs={}
   for f in ['plan','norms','x']:
    model,spec=fit_baseline(tr,f);pred['cheap_'+f]=model.predict([r[f] for r in te]).tolist();specs[f]=spec
   # Entire configuration holdout for state partition hyperparameters.
   groups=sorted(set(r['group'] for r in tr));ag=[dict(group=g,h=next(r['h'] for r in tr if r['group']==g),s=next(r['s'] for r in tr if r['group']==g),y=float(np.mean([r['y'] for r in tr if r['group']==g]))) for g in groups]
   best=None
   for states in [1,2,3,4]:
    for alpha in [.01,.1,1.,10.]:
     losses=[]
     for i in range(len(ag)):
      aa=ag[:i]+ag[i+1:];m=StateSplit(states,alpha).fit(np.array([r['h'] for r in aa]),np.array([r['s'] for r in aa]),np.array([r['y'] for r in aa]));pp=m.predict(np.array([ag[i]['h']]),np.array([ag[i]['s']]))[0];losses.append((pp-ag[i]['y'])**2)
     score=float(np.mean(losses))
     if best is None or score<best[0]:best=(score,states,alpha)
   m=StateSplit(best[1],best[2]).fit(np.array([r['h'] for r in ag]),np.array([r['s'] for r in ag]),np.array([r['y'] for r in ag]));pred['state_split']=m.predict(np.array([r['h'] for r in te]),np.array([r['s'] for r in te])).tolist();specs['state_split']=best
   xp=np.array([r['plan'] for r in tr]);lookup=[];sem=[];add=[];singlemax=[]
   for r in te:
    dist=np.sum((xp-r['plan'])**2,axis=1);lookup.append(float(np.mean([tr[i]['y'] for i in np.flatnonzero(np.isclose(dist,dist.min(),atol=1e-12,rtol=0))])))
    matched=[q for q in tr if q['family']==r['family'] and (q['branch']=='REPAIR')==(r['branch']=='REPAIR') and q['has_B']==r['has_B']]
    if not matched:matched=[q for q in tr if (q['branch']=='REPAIR')==(r['branch']=='REPAIR') and q['has_B']==r['has_B']]
    if not matched:matched=tr
    sem.append(float(np.mean([q['y'] for q in matched])))
    def lookup_arm(arm):
     # Archived censored records are usable only as lower-bound templates; this
     # inexpensive heuristic is deliberately included and flagged accordingly.
     pool=[q for q in rr if not fn(q) and q['family']==r['family'] and q['arm']==arm]
     return float(np.mean([q['y'] for q in pool])) if pool else sem[-1]
    aa=lookup_arm('A');bb=lookup_arm('B-'+r['arm'].split('-')[-1]);nn=lookup_arm('NORMAL');add.append(aa+bb-nn if r['branch']=='AB' else sem[-1]);singlemax.append(max(aa,bb) if r['branch']=='AB' else sem[-1])
   pred['plan_lookup']=lookup;pred['semantic_backoff']=sem;pred['single_additive_lowerbound_heuristic']=add;pred['single_max_lowerbound_heuristic']=singlemax
   result=dict(outcome=outcome,fold=name,train_n=len(tr),test_n=len(te),ids=[r['id'] for r in te],actual=[r['y'] for r in te],predictions=pred,specs=specs,metrics={k:metrics(te,v,outcome) for k,v in pred.items()});results.append(result)
   print(outcome,name,{k:(round(v['MAE'],4),v['FN'],v['FP']) for k,v in result['metrics'].items()},flush=True)
 (ROOT/'h2_preflight_comparison.json').write_text(json.dumps(dict(scope='All inputs pre-stream. Complete-run map errors; censored peak ranks are observed lower-bound ranks only.',results=results),indent=2))
if __name__=='__main__':main()

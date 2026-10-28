"""Predeclared strong cheap plan-ridge using exposed historical P13 outcomes.
No P16 full truth reaches fitting/selection. Same history available to G/R.
"""
import json,numpy as np
from pathlib import Path
from p16.greybox import OUT
from p16.quality import label,task,curve_key
from p16.sequential import choose

def features(c):
 f=float(c['family']=='F4');a=float(c['prefix']=='AB');g=(c['G']-.55)/1.45
 return np.array([1,f,a,g,g*g,g*g*g,a*g,f*g,f*g*g,f*a,a*g*g])

def fit():
 rows=json.load(open(OUT/'offline-adjoint-20261028/upstream/data/p13-20261026-results-v3/cases.json'))['rows'];use=[r for r in rows if r['family'] in ['F2','F4'] and r['branch'] in ['B','AB']];X=np.array([features(dict(family=r['family'],prefix=r['branch'],G=r['gap_s'])) for r in use]);weights={}
 for field,source in [('peak_tilt','LP_peak_tilt_deg'),('peak_loss','LP_max_loss_m')]:
  ids=[i for i,r in enumerate(use) if not r['censored']];x=X[ids];y=np.array([use[i][source] for i in ids]);reg=np.eye(x.shape[1])*.1;reg[0,0]=1e-6;weights[field]=np.linalg.solve(x.T@x+reg,x.T@y)
 return weights,dict(ids=[r['id'] for r in use],continuous_complete_only=True,regularizer=.1,features='fixed cubicG+family/prefix interaction, no newlabel hyperparameter tuning',history_exposed_to_all=True)

def replay(pool,oracle):
 w,meta=fit();history={};maps=[];raw={c['id']:{k:float(features(c)@v) for k,v in w.items()} for c in pool}
 for q in range(len(pool)+1):
  pred={}
  for c in pool:
   d=dict(raw[c['id']]);seen=[x for x in pool if x['id'] in history and curve_key(x)==curve_key(c) and history[x['id']].get('valid')]
   for k in ['peak_tilt','peak_loss']:
    ww=[(np.exp(-.5*((c['G']-x['G'])/.35)**2),history[x['id']][k]-raw[x['id']][k]) for x in seen if history[x['id']].get('complete') and history[x['id']].get(k) is not None]
    if ww:d[k]+=sum(a*b for a,b in ww)/(1+sum(a for a,b in ww))
   d.update(tilt=label(d['peak_tilt'],45,True),height=label(d['peak_loss'],1,True));d['task']=task(d['tilt'],d['height'])
   if c['id'] in history and history[c['id']].get('valid'):d.update({k:history[c['id']][k] for k in ['tilt','height','task']})
   pred[c['id']]=d
  maps.append(dict(query=q,seen_ids=list(history),prediction=pred))
  if q==len(pool):break
  selected,why=choose(pool,pred,history,q);maps[-1]['next_choice']=selected;maps[-1]['reason']=why;history[selected['id']]=oracle(selected['id'])
 return maps,meta

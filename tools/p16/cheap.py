"""Strong cheap historical RBF boundary learner, plus own-query updates.
Fixed kernel/noise from the supplied sequential audit, no P16 hyperparameterfit.
Censored witnesses enter binary labels; unknown negatives never enter as safe.
"""
import json,numpy as np,time
from p16.greybox import OUT
from p16.quality import label,task

def features(c):return np.array([3.*(c['family']=='F4'),3.*(c['prefix']=='AB'),(c['G']-.55)/1.45])
def kernel(a,b):return np.exp(-.5*np.sum((a[:,None,:]-b[None,:,:])**2,axis=2)/.5**2)
def historical():
 rows=json.load(open(OUT/'offline-adjoint-20261028/upstream/data/p13-20261026-results-v3/cases.json'))['rows'];r=[x for x in rows if x['branch'] in ['B','AB']];return [dict(id=x['id'],family=x['family'],prefix=x['branch'],G=x['gap_s'],tilt=label(x['LP_peak_tilt_deg'],45,not x['censored']),height=label(x['LP_max_loss_m'],1,not x['censored'])) for x in r]

def predict(pool,history):
 old=historical();data=old+[dict(c,**{k:history[c['id']][k] for k in ['tilt','height']}) for c in pool if c['id'] in history and history[c['id']].get('valid')];xp=np.array([features(c) for c in pool]);scores={}
 for component in ['tilt','height']:
  use=[r for r in data if r[component]!='UNKNOWN'];x=np.array([features(c) for c in use]);y=np.array([r[component]=='FAIL' for r in use],float);K=kernel(x,x)+.25*np.eye(len(x));scores[component]=np.clip(.5+kernel(xp,x)@np.linalg.solve(K,y-.5),0,1)
 pred={}
 for i,c in enumerate(pool):
  a='FAIL' if scores['tilt'][i]>=.5 else 'SUCCESS';b='FAIL' if scores['height'][i]>=.5 else 'SUCCESS';d=dict(tilt=a,height=b,task=task(a,b),scores={k:float(scores[k][i]) for k in scores},not_certified_safe=True)
  if c['id'] in history and history[c['id']].get('valid'):d.update({k:history[c['id']][k] for k in ['tilt','height','task']})
  pred[c['id']]=d
 return pred

def replay(pool,oracle):
 history={};maps=[];cpu=time.process_time()
 for q in range(len(pool)+1):
  pred=predict(pool,history);maps.append(dict(query=q,seen_ids=list(history),prediction=pred,CPU_s_cumulative=time.process_time()-cpu))
  if q==len(pool):break
  # Fixed near-boundary uncertainty plus the same two uniform-exploration slots.
  remain=[c for c in pool if c['id'] not in history]
  if q in [3,6]:
   def key(c):
    d=min([abs(c['G']-x['G']) for x in pool if x['family']==c['family'] and x['prefix']==c['prefix'] and x['id'] in history],default=10);return (-d,c['id'])
  else:
   def key(c):
    p=pred[c['id']]['scores'];s=1-(1-p['tilt'])*(1-p['height']);return (abs(s-.5),c['id'])
  chosen=min(remain,key=key);maps[-1]['next_choice']=chosen;history[chosen['id']]=oracle(chosen['id'])
 return maps,dict(history_ids=[r['id'] for r in historical()],kernel='RBF family/prefix/G length.5, noise.25 fixed from materialprotocol',binary_censoring='positive witnessedFAIL used, unknown negatives excluded',protocol_frozen_before_main=True)

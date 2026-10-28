"""Own-query-only calibration and selection. Fulltruth is never an argument.
Initial dynamics predictions are supplied by separately frozen greybox adapter.
"""
import math
from p16.quality import label,task
WIDTH=.35
SHRINK=.65

def finite(value):
 return value is not None and math.isfinite(value)

def residual_evidence(initial,record):
 # Unknown initial predictions do not have a numeric residual. No zero fill.
 out={}
 for field in ['peak_tilt','peak_loss']:
  value=float(record[field])-float(initial[field]) if finite(record.get(field)) and finite(initial.get(field)) else None
  out[field]=None if value is not None and not record.get('complete',False) and value<0 else value
 return out

def calibrated(pool,initial,history):
 out={}
 for c in pool:
  prior=initial[c['id']];d={k:prior.get(k) for k in ['peak_tilt','peak_loss']};weights={k:[] for k in d}
  for seen_id,record in history.items():
   assert seen_id in {x['id'] for x in pool},'query outside frozen pool'
   if not record.get('valid',False):continue
   known=next(x for x in pool if x['id']==seen_id)
   if known['family']!=c['family']:continue
   weight=math.exp(-.5*((c['G']-known['G'])/WIDTH)**2)
   for field in d:
    actual=record.get(field);base=initial[seen_id].get(field)
    if not finite(actual) or not finite(base):continue
    residual=float(actual)-float(base)
    # Truncated peaks are lowerbounds, so never fit a negative residual from them.
    if not record.get('complete',False) and residual<0:continue
    weights[field].append((weight,residual))
  for field,ww in weights.items():
   if d[field] is not None and ww:d[field]+=SHRINK*sum(w*r for w,r in ww)/(1+sum(w for w,r in ww))
  complete=prior.get('model_complete',False);a=label(d['peak_tilt'],45,complete);b=label(d['peak_loss'],1,complete);d.update(tilt=a,height=b,task=task(a,b),model_complete=complete,nominal_only=True,not_certified_safe=True)
  # Exact queried task witnesses override the map at that point, not at other G.
  if c['id'] in history and history[c['id']].get('valid',False):d.update({k:history[c['id']][k] for k in ['tilt','height','task']})
  d['prefix_failed_before_B']=prior.get('prefix_failed_before_B')
  if d['prefix_failed_before_B'] is True:d['task']='FAIL'
  if c['id'] in history and history[c['id']].get('valid',False):
   record=history[c['id']];d['prefix_failed_before_B']=record.get('prefix_failed_before_B');d['own_error_evidence']=residual_evidence(prior,record);d['observed_peaks']={k:record.get(k) for k in ['peak_tilt','peak_loss']};d['own_error_scope']='exact full measured window if complete, otherwise positive lowerbound residual only; None means no numeric evidence'
   if d['prefix_failed_before_B'] is True:d['task']='FAIL'
  out[c['id']]=d
 return out

def choose(pool,pred,history,query_index):
 remaining=[c for c in pool if c['id'] not in history];assert remaining
 if query_index in [3,6]:
  # Two of eight queries reserve source-independent grid exploration.
  def key(c):
   same=[x for x in pool if x['family']==c['family'] and x['id'] in history];dist=min([abs(c['G']-x['G']) for x in same],default=10)
   return (-dist,c['family'],c['G'],c['id'])
  return min(remaining,key=key),'fixed uniform/farthest exploration'
 def key(c):
  d=pred[c['id']];v=[d.get('peak_tilt'),d.get('peak_loss')]
  if not all(finite(x) for x in v):return (-1.,c['family'],c['G'],c['id'])
  margin=abs(max(v[0]/45,v[1])-1);local=[]
  for ident,r in history.items():
   other=next(x for x in pool if x['id']==ident)
   if other['family']!=c['family'] or not r.get('valid'):continue
   evidence=pred[ident].get('own_error_evidence',{})
   rr=[abs(evidence[k])/scale for k,scale in [('peak_tilt',45),('peak_loss',1)] if finite(evidence.get(k))]
   if rr:local.append(math.exp(-.5*((c['G']-other['G'])/WIDTH)**2)*max(rr))
  return (margin/(1+max(local,default=0)),c['family'],c['G'],c['id'])
 return min(remaining,key=key),'near nominal taskthreshold / own local measured residual priority'

def next_query(pool,initial,history):
 assert len(history)<8,'B query cap8'
 prediction=calibrated(pool,initial,history);selected,why=choose(pool,prediction,history,len(history));return dict(query=len(history)+1,selected=selected,reason=why,seen_ids=list(history),prediction=prediction,rules=dict(width_G_s=WIDTH,shrink=SHRINK,exploration_query_numbers=[4,7]),future_truth_used=False)

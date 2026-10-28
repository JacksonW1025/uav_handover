"""Finite-grid empirical quality. UNKNOWN never counts as correct/safe."""
import math
LABELS={'SUCCESS','FAIL','UNKNOWN'}
def label(peak,threshold,complete):
 if peak is None or not math.isfinite(peak):return 'UNKNOWN'
 return 'FAIL' if peak>threshold else 'SUCCESS' if complete else 'UNKNOWN'
def task(tilt,height):
 assert tilt in LABELS and height in LABELS
 return 'FAIL' if 'FAIL' in [tilt,height] else 'SUCCESS' if tilt==height=='SUCCESS' else 'UNKNOWN'
def transitions(labels):return [i+.5 for i,(a,b) in enumerate(zip(labels,labels[1:])) if a in ['SUCCESS','FAIL'] and b in ['SUCCESS','FAIL'] and a!=b]
def boundary_error(a,p):
 aa=transitions(a);pp=transitions(p)
 if not aa and not pp:return dict(error_cells=0.,status='NO_TRANSITION',actual=[],predicted=[])
 if len(aa)!=len(pp):return dict(error_cells=None,status='UNMATCHED_TRANSITION',actual=aa,predicted=pp)
 # Ordered one-to-one matching preserves every nonmonotone transition; one
 # predicted edge cannot silently stand in for two true edges.
 e=max(abs(x-y) for x,y in zip(aa,pp))
 return dict(error_cells=e,status='MATCHED',actual=aa,predicted=pp)
def evaluate(pool,truth,pred):
 # Invalid identities/time excluded from valid-N, still explicit fixed pool count.
 valid=[c for c in pool if truth.get(c['id'],{}).get('valid',False)];N=len(valid);out={}
 for component in ['tilt','height','task']:
  a=[truth[c['id']][component] for c in valid];p=[pred.get(c['id'],{}).get(component,'UNKNOWN') for c in valid]
  assert all(x in LABELS for x in a+p)
  known=sum(x!='UNKNOWN' for x in p);correct=sum(x==y and x!='UNKNOWN' for x,y in zip(a,p));miss=sum(x=='FAIL' and y=='SUCCESS' for x,y in zip(a,p));fa=sum(x=='SUCCESS' and y=='FAIL' for x,y in zip(a,p));edges=[]
  for family in sorted({c['family'] for c in pool}):
   cc=sorted([c for c in pool if c['family']==family],key=lambda c:c['G']);aa=[truth.get(c['id'],{}).get(component,'UNKNOWN') if truth.get(c['id'],{}).get('valid',False) else 'UNKNOWN' for c in cc];pp=[pred.get(c['id'],{}).get(component,'UNKNOWN') for c in cc];e=boundary_error(aa,pp);e.update(family=family,truth_unknown=aa.count('UNKNOWN'),full_boundary_observed=all(x!='UNKNOWN' for x in aa));edges.append(e)
  boundary=all(e['full_boundary_observed'] and e['error_cells'] is not None and e['error_cells']<=1 for e in edges)
  out[component]=dict(N_valid=N,N_fixed=len(pool),prediction_known=known,coverage=known/N if N else 0,correct=correct,accuracy=correct/N if N else 0,danger_as_safe=miss,false_alarm=fa,truth_unknown=a.count('UNKNOWN'),prediction_unknown=p.count('UNKNOWN'),edges=edges,boundary_pass=boundary)
 d=out['task'];rules=dict(coverage=d['coverage']>=.9 and N>0,accuracy=d['accuracy']>=.9 and N>0,no_danger_as_safe=d['danger_as_safe']==0,boundary=d['boundary_pass']);return dict(components=out,quality_conditions=rules,same_quality=all(rules.values()),fixed_grid_valid=len(valid),fixed_grid_invalid=len(pool)-len(valid),scope='finite valid-grid empirical, no continuous safety guarantee')

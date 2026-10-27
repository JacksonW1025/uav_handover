"""Full prefix pullback-metric priorities; discarded columns remain rowL1outer.
Priority is not nonlinear/FP certification. All future-state rows survive.
"""
import numpy as np
from p14.affine import A,cat
from p14r.affine import compress as baseline
from p14g.compress import SETTINGS
METRIC={}
def compress(state,initial_n,rank=512,box=False):
 if not METRIC or box:return baseline(state,initial_n,rank,box)
 keys=list(state);sizes=[len(state[k].c) for k in keys];x=cat(*(state[k] for k in keys));G=x.pad();C=x.ctx;old=C.n;tags=np.array(C.tags);layout=METRIC['layout'];Ps=METRIC['Ps'];k=min(SETTINGS.get('call',1),len(Ps)-1);N=Ps[k].shape[0];Z=np.zeros((N,old));offset=0;aux=np.zeros(old)
 scales=[]
 for key,n in zip(keys,sizes):
  if key in layout:
   a,b=layout[key];Z[a:b]=G[offset:offset+n]
  if key=='hh':aux+=np.sum((G[offset:offset+n]/.01)**2,axis=0)
  scales.extend([{'p':.1,'v':.15,'q':.01,'w':.1,'h':.01,'hh':.01,'previous':.1,'f':10,'pending':10}.get(key,.1)]*n);offset+=n
 quadratic=np.einsum('ij,ij->j',Z,Ps[k]@Z);score=np.sqrt(np.maximum(quadratic,0)+.0025*aux)+.05*np.linalg.norm(G/np.array(scales)[:,None],axis=0);protected=sorted(set(range(min(initial_n,old)))|set(getattr(C,'monomials',{}).values()));eligible=np.setdiff1d(np.arange(old),protected);idx=eligible[np.argsort(-score[eligible],kind='stable')[:abs(rank)]];keep=np.array(protected+idx.tolist());discard=np.ones(old,bool);discard[keep]=False;parts=[G[:,keep]];newtags=tags[keep].tolist();lost={}
 for tag in sorted(set(tags[discard])):
  radius=np.sum(abs(G[:,discard&(tags==tag)]),axis=1);sel=np.flatnonzero(radius>0);tail=np.zeros((len(x.c),len(sel)));tail[sel,np.arange(len(sel))]=np.nextafter(radius[sel],np.inf);parts.append(tail);newtags.extend([tag]*len(sel));lost[tag]=float(max(radius))
 new=np.column_stack(parts);mapping={int(k):j for j,k in enumerate(keep)};C.monomials={pair:mapping[j] for pair,j in getattr(C,'monomials',{}).items() if j in mapping};C.n=new.shape[1];C.tags=newtags;offset=0;out={}
 for key,n in zip(keys,sizes):out[key]=A(C,x.c[offset:offset+n],new[offset:offset+n]);offset+=n
 return out,{'before':old,'after':C.n,'mode':'full-prefix poststate W quadratic priority +auxhhnorm +source relations; discardedtagrowL1outer','kept':len(keep),'discarded_category_row_radius':lost,'numeric_negative_quadratic_min':float(min(quadratic)),'priorityclamp_not_containmentproof':True,'metric_horizon_calls':len(Ps)-1,'all_state_rows_retained':True}

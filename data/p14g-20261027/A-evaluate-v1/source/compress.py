"""Source-compatible outer reduction with optional safety adjoint priorities.
No directions deleted: unretained columns become row-L1 boxes by origin tag.
No claim that a sketch score bounds nonlinear future response.
"""
import numpy as np
from p14.affine import A,cat
from p14r.affine import compress as baseline
SETTINGS={}
def compress(state,initial_n,rank=512,box=False):
 if not SETTINGS.get('weights') or box:return baseline(state,initial_n,rank,box)
 keys=list(state);sizes=[len(state[k].c) for k in keys];x=cat(*(state[k] for k in keys));G=x.pad();C=x.ctx;old=C.n;tags=np.array(C.tags);layout=SETTINGS['layout'];weights=SETTINGS['weights'];call=SETTINGS.get('call',1);W=weights['W'+str(min(call,len(weights.files)-1))];Q=np.zeros((8,len(x.c)));offset=0
 for k,n in zip(keys,sizes):
  if k in layout:
   a,b=layout[k];Q[:,offset:offset+n]=W[:,a:b]
  elif k=='hh':
   a,b=layout['h'];Q[:,offset:offset+n]=W[:,a:b]
  offset+=n
 scale=[]
 for k,n in zip(keys,sizes):scale.extend([{'p':.1,'v':.15,'q':.01,'w':.1,'h':.01,'hh':.01,'previous':.1,'f':10,'pending':10}.get(k,.1)]*n)
 # Small state-norm floor retains feedback directions not visible to the sketch.
 score=np.linalg.norm(Q@G,axis=0)+.05*np.linalg.norm(G/np.array(scale)[:,None],axis=0);protected=sorted(set(range(min(initial_n,old)))|set(getattr(C,'monomials',{}).values()));eligible=np.setdiff1d(np.arange(old),protected);idx=eligible[np.argsort(-score[eligible],kind='stable')[:abs(rank)]];keep=np.array(protected+idx.tolist());discard=np.ones(old,bool);discard[keep]=False;parts=[G[:,keep]];newtags=tags[keep].tolist();lost={}
 for tag in sorted(set(tags[discard])):
  radius=np.sum(abs(G[:,discard&(tags==tag)]),axis=1);sel=np.flatnonzero(radius>0);tail=np.zeros((len(x.c),len(sel)));tail[sel,np.arange(len(sel))]=np.nextafter(radius[sel],np.inf);parts.append(tail);newtags.extend([tag]*len(sel));lost[tag]=float(max(radius))
 new=np.column_stack(parts);mapping={int(k):j for j,k in enumerate(keep)};C.monomials={pair:mapping[j] for pair,j in getattr(C,'monomials',{}).items() if j in mapping};C.n=new.shape[1];C.tags=newtags;offset=0;out={}
 for k,n in zip(keys,sizes):out[k]=A(C,x.c[offset:offset+n],new[offset:offset+n]);offset+=n
 return out,{'before':old,'after':C.n,'mode':'source relations + all-prefix adjoint sketch priority, discarded direction row-L1outer','kept':len(keep),'discarded_category_row_radius':lost,'initial_origins_retained':initial_n,'nonlinear_or_FP_certificate':False}

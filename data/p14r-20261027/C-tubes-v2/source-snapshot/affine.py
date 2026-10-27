"""Finite correlated-real enclosure improvements; old implementation untouched.

Operation-count gamma, exact stable clip/ReLU, and optional shared quadratic
monomials. These are real-map enclosures with conditional FP/libm budgets,
not certified coverage of PX4 float32/DART/EKF defects.
"""
import numpy as np
from p14.affine import A,Context
ORIGINAL={n:getattr(A,n) for n in ['noise','rounding','__add__','__mul__','linear','relu','clip']}
def install(quadratic=False):
 def noise(self,r,tag=None):
  r=np.broadcast_to(np.maximum(0,np.asarray(r)),self.c.shape).copy();sel=np.flatnonzero(r>0)
  if not len(sel):return self
  r[sel]=np.nextafter(r[sel],np.inf);g=self.pad();new=np.zeros((len(self.c),len(sel)));new[sel,np.arange(len(sel))]=r[sel];g=np.column_stack([g,new]);self.ctx.n+=len(sel)
  if not hasattr(self.ctx,'tags'):self.ctx.tags=['initial']*(self.ctx.n-len(sel))
  self.ctx.tags.extend([tag or getattr(self.ctx,'tag','nonlinear')]*len(sel));return A(self.ctx,self.c,g)
 def rounding(self,magnitude,n=1):
  eps=np.finfo(float).eps/2;gamma=(n+8)*eps/(1-(n+8)*eps)
  y=noise(self,gamma*np.asarray(magnitude)+1e-16,'round_libm')
  return self.ctx.variable(y.c,y.radius()) if self.ctx.box else y
 def add(self,y):
  if not isinstance(y,A):y=self.ctx.constant(np.broadcast_to(y,self.c.shape))
  z=A(self.ctx,self.c+y.c,self.pad()+y.pad());return rounding(z,abs(self.c)+self.radius()+abs(y.c)+y.radius(),1)
 def mul(self,y):
  if not isinstance(y,A):
   yy=np.asarray(y);z=A(self.ctx,self.c*yy,self.g*np.broadcast_to(yy,self.c.shape)[:,None]);return rounding(z,(abs(self.c)+self.radius())*abs(yy),1)
  z=A(self.ctx,self.c*y.c,self.pad()*y.c[:,None]+y.pad()*self.c[:,None]);rx,ry=self.radius(),y.radius()
  k=min(getattr(self.ctx,'initial_n',0),8) if quadratic else 0
  if k:
   gx,gy=self.pad()[:,:k],y.pad()[:,:k];ix,iy=np.sum(abs(gx),axis=1),np.sum(abs(gy),axis=1);cache=getattr(self.ctx,'monomials',{});self.ctx.monomials=cache
   for a in range(k):
    for b in range(a,k):
     coefficient=gx[:,a]*gy[:,b] if a==b else gx[:,a]*gy[:,b]+gx[:,b]*gy[:,a]
     if not np.any(coefficient):continue
     if (a,b) not in cache:
      cache[a,b]=self.ctx.n;self.ctx.n+=1;self.ctx.tags.append('shared_quadratic')
     g=z.pad()
     if a==b:z=A(self.ctx,z.c+.5*coefficient,g);g=z.pad();g[:,cache[a,b]]+=.5*coefficient
     else:g[:,cache[a,b]]+=coefficient
     z=A(self.ctx,z.c,g)
   remainder=ix*np.maximum(0,ry-iy)+iy*np.maximum(0,rx-ix)+np.maximum(0,rx-ix)*np.maximum(0,ry-iy)
  else:remainder=rx*ry
  z=noise(z,remainder,'nonlinear');return rounding(z,(abs(self.c)+rx)*(abs(y.c)+ry),3)
 def linear(self,W,b=None):
  W=np.asarray(W);b=np.zeros(W.shape[0]) if b is None else np.asarray(b);z=A(self.ctx,W@self.c+b,W@self.g)
  return rounding(z,abs(W)@(abs(self.c)+self.radius())+abs(b),W.shape[1])
 def relu(self):
  lo,hi=self.bounds();cross=(lo<0)&(hi>0);s=np.where(lo>=0,1.,np.where(hi<=0,0.,hi/np.maximum(hi-lo,1e-300)));err=np.where(cross,-hi*lo/(2*np.maximum(hi-lo,1e-300)),0.)
  z=A(self.ctx,s*self.c+err,s[:,None]*self.g)
  if not cross.any():return z
  return rounding(noise(z,err,'clip_crossing'),abs(z.c)+z.radius(),3)
 def clip(self,L):
  lo,hi=self.bounds();inside=(lo>=-L)&(hi<=L);above=lo>=L;below=hi<=-L;cross=~(inside|above|below)
  if not cross.any():
   c=self.c.copy();g=self.g.copy();c[above]=L;c[below]=-L;g[above|below]=0;return A(self.ctx,c,g)
  return ORIGINAL['clip'](self,L)
 def smooth(self,kind):
  lo,hi=self.bounds()
  if kind=='tanh':
   fc=np.tanh(self.c);slope=1-fc*fc;f=lambda x:2*abs(np.tanh(x))*(1-np.tanh(x)**2);M=np.maximum(f(lo),f(hi));critical=np.arctanh(1/np.sqrt(3))
   M=np.where(((lo<=critical)&(hi>=critical))|((lo<=-critical)&(hi>=-critical)),4/(3*np.sqrt(3)),M)
  elif kind=='sigmoid':
   sig=lambda x:1/(1+np.exp(-np.clip(x,-700,700)));fc=sig(self.c);slope=fc*(1-fc);f=lambda x:abs(sig(x)*(1-sig(x))*(1-2*sig(x)));M=np.maximum(f(lo),f(hi));critical=np.log((3+np.sqrt(3))/(3-np.sqrt(3)))
   M=np.where(((lo<=critical)&(hi>=critical))|((lo<=-critical)&(hi>=-critical)),1/(6*np.sqrt(3)),M)
  else:raise ValueError(kind)
  z=A(self.ctx,fc,slope[:,None]*self.g);z=noise(z,.5*M*self.radius()**2+1e-14,'nonlinear');return rounding(z,abs(z.c)+z.radius(),4)
 A.smooth=smooth
 A.noise=noise;A.rounding=rounding;A.__add__=A.__radd__=add;A.__mul__=A.__rmul__=mul;A.linear=linear;A.relu=relu;A.clip=clip

def contributions(state,keys):
 out={};C=next(iter(state.values())).ctx;tags=getattr(C,'tags',['unclassified']*C.n);tags=tags+['unclassified']*max(0,C.n-len(tags))
 for key in keys:
  x=state[key];g=x.pad();out[key]={tag:float(max(np.sum(abs(g[:,np.array(tags)==tag]),axis=1))) for tag in sorted(set(tags))}
 return out

def compress(state,initial_n,rank=64,box=False):
 """Preserve initial origins and rank actual tail directions; tag separated tail.
 Outer row sums enclose discarded columns. No SVD/new coordinate independence.
 """
 from p14.affine import cat
 keys=list(state);sizes=[len(state[k].c) for k in keys];x=cat(*(state[k] for k in keys));G=x.pad();C=x.ctx;tags=np.array(getattr(C,'tags',['initial']*C.n));old=C.n
 if box:
  new=np.diag(np.sum(abs(G),axis=1));newtags=['independent_box']*len(x.c)
 else:
  start=min(initial_n,G.shape[1]);scale=[]
  for k,n in zip(keys,sizes):scale.extend([{'p':.1,'v':.15,'q':.01,'w':.1,'h':.01,'previous':.1,'f':10,'pending':10}.get(k,.1)]*n)
  score=np.linalg.norm(G[:,start:]/np.array(scale)[:,None],axis=0);idx=np.argsort(score)[::-1][:min(abs(rank),len(score))]+start;keep=np.r_[np.arange(start),idx];discard=np.ones(old,bool);discard[keep]=False;parts=[G[:,keep]];newtags=tags[keep].tolist()
  for tag in sorted(set(tags[discard])):
   rad=np.sum(abs(G[:,discard&(tags==tag)]),axis=1);sel=np.flatnonzero(rad>0);tail=np.zeros((len(x.c),len(sel)));tail[sel,np.arange(len(sel))]=np.nextafter(rad[sel],np.inf);parts.append(tail);newtags.extend([tag]*len(sel))
  new=np.column_stack(parts)
 C.n=new.shape[1];C.tags=newtags;C.monomials={};offset=0;out={}
 for k,n in zip(keys,sizes):out[k]=A(C,x.c[offset:offset+n],new[offset:offset+n]);offset+=n
 return out,{'before':old,'after':C.n,'initial_columns':0 if box else initial_n,'tail_directions_kept':min(abs(rank),old-initial_n),'mode':'outer row sum by origin category, initial columns retained','monomial_cache_reset':'new monomial relaxation independent of old tail; safe outer projection, correlation loss counted','FP':'numpy rowL1/reduction outward margin conditional; not verified floating interval'}

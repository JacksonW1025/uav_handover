"""Finite shared-generator real enclosures, NOT sampled Jacobians.

Product remainder <= radius(x)*radius(y). Sigmoid/tanh Taylor remainder uses
analytic global second derivative bounds 1/10 and 1 respectively. ReLU crossing
uses the exact secant strip. Double arithmetic receives an explicit gamma_n
roundoff enlargement; libm evaluations additionally get 1e-14. This budget is
an assumption on installed arithmetic, not a certified DART/EKF implementation.
"""
import numpy as np

class Context:
 def __init__(self,box=False):self.n=0;self.box=box
 def constant(self,c):return A(self,np.atleast_1d(np.asarray(c,float)),np.zeros((np.size(c),self.n)))
 def variable(self,c,r):return self.constant(c).noise(np.broadcast_to(r,np.shape(np.atleast_1d(c))))

class A:
 def __init__(self,ctx,c,g):self.ctx=ctx;self.c=np.atleast_1d(c);self.g=g
 def pad(self):return np.pad(self.g,((0,0),(0,self.ctx.n-self.g.shape[1])))
 def radius(self):return np.sum(abs(self.g),axis=1)
 def bounds(self):
  r=self.radius();return np.nextafter(self.c-r,-np.inf),np.nextafter(self.c+r,np.inf)
 def noise(self,r):
  r=np.nextafter(np.maximum(0,np.asarray(r)),np.inf);g=self.pad();n=len(self.c);g=np.column_stack([g,np.diag(r)]);self.ctx.n+=n
  return A(self.ctx,self.c,g)
 def rounding(self,magnitude,n=1):
  eps=np.finfo(float).eps/2;gamma=(n+8)*eps/(1-(n+8)*eps)
  y=self.noise(gamma*np.asarray(magnitude)+1e-16)
  if self.ctx.box:
   # Independent outer-box comparison explicitly discards all correlation.
   return self.ctx.variable(y.c,y.radius())
  return y
 def __getitem__(self,k):
  ix=np.atleast_1d(np.arange(len(self.c))[k]);return A(self.ctx,self.c[ix],self.g[ix])
 def __neg__(self):return A(self.ctx,-self.c,-self.g)
 def __add__(self,y):
  if not isinstance(y,A):y=self.ctx.constant(np.broadcast_to(y,self.c.shape))
  if len(self.c)!=len(y.c):raise ValueError('shape')
  z=A(self.ctx,self.c+y.c,self.pad()+y.pad());return z.rounding(abs(self.c)+self.radius()+abs(y.c)+y.radius(),self.ctx.n)
 __radd__=__add__
 def __sub__(self,y):return self+(-y if isinstance(y,A) else -np.asarray(y))
 def __rsub__(self,y):return -self+y
 def __mul__(self,y):
  if not isinstance(y,A):
   yy=np.asarray(y);z=A(self.ctx,self.c*yy,self.g*np.broadcast_to(yy,self.c.shape)[:,None]);return z.rounding((abs(self.c)+self.radius())*abs(yy),self.ctx.n)
  z=A(self.ctx,self.c*y.c,self.pad()*y.c[:,None]+y.pad()*self.c[:,None]);z=z.noise(self.radius()*y.radius())
  return z.rounding((abs(self.c)+self.radius())*(abs(y.c)+y.radius()),self.ctx.n)
 __rmul__=__mul__
 def linear(self,W,b=None):
  W=np.asarray(W);b=np.zeros(W.shape[0]) if b is None else np.asarray(b)
  z=A(self.ctx,W@self.c+b,W@self.g);return z.rounding(abs(W)@(abs(self.c)+self.radius())+abs(b),max(W.shape[1],self.ctx.n))
 def relu(self):
  lo,hi=self.bounds();s=np.where(lo>=0,1.,np.where(hi<=0,0.,hi/np.maximum(hi-lo,1e-300)))
  err=np.where((lo<0)&(hi>0),-hi*lo/(2*np.maximum(hi-lo,1e-300)),0.)
  z=A(self.ctx,s*self.c+err,s[:,None]*self.g).noise(err)
  return z.rounding(abs(z.c)+z.radius(),self.ctx.n)
 def restrict(self,lo,hi):
  l,u=self.bounds();ll=np.maximum(l,lo);uu=np.minimum(u,hi)
  if np.any(ll>uu):raise ValueError('empty proven invariant intersection')
  changed=(l<lo)|(u>hi)
  if not changed.any():return self
  c=self.c.copy();g=self.pad();c[changed]=(ll[changed]+uu[changed])/2;g[changed]=0
  r=np.where(changed,(uu-ll)/2,0.)
  return A(self.ctx,c,g).noise(r)
 def clip(self,L):return (-L+(self+L).relu()-(self-L).relu()).restrict(-L,L)
 def smooth(self,kind):
  if kind=='sigmoid':
   fc=1/(1+np.exp(-np.clip(self.c,-700,700)));s=fc*(1-fc);M=.1
  elif kind=='tanh':fc=np.tanh(self.c);s=1-fc*fc;M=1.
  else:raise ValueError(kind)
  z=A(self.ctx,fc,s[:,None]*self.g).noise(.5*M*self.radius()**2+1e-14)
  return z.rounding(abs(z.c)+z.radius(),self.ctx.n)

def cat(*xs):
 ctx=xs[0].ctx;return A(ctx,np.concatenate([x.c for x in xs]),np.vstack([x.pad() for x in xs]))

def network(P,h,x):
 e=x.linear(P['W0'],P['b0']).relu();gi=e.linear(P['Wi'],P['bi']);gh=h.linear(P['Wh'],P['bh'])
 r=(gi[:16]+gh[:16]).smooth('sigmoid');z=(gi[16:32]+gh[16:32]).smooth('sigmoid')
 n=(gi[32:]+r*gh[32:]).smooth('tanh');hh=(1-z)*n+z*h
 hh=hh.restrict(-1.,1.)
 return hh,hh.linear(P['W2'],P['b2']).clip(1.)

def filter_step(f,u):
 up=np.exp(-.004/.0125);down=np.exp(-.004/.025)
 return (down*f+(1-down)*u-(up-down)*(u-f).relu()).restrict(0.,1000.)

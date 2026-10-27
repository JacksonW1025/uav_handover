"""Analytic affine remainders for moving SO(3)/source feedback, no sampled J.
Numerical gamma/libm budgets inherited from P14 remain conditional obligations.
"""
import numpy as np
from p14.affine import A,Context,cat,network,filter_step

def cross(a,b):return cat(a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def dot(a,b):return (a*b).linear(np.ones((1,len(a.c))))
def mat(rows):return cat(*rows)
def mv(m,v):return cat(*(dot(m[3*i:3*i+3],v) for i in range(3)))
def transpose(m):return m[[0,3,6,1,4,7,2,5,8]]
def mm(a,b):return cat(*(dot(a[3*i:3*i+3],b[[j,3+j,6+j]]) for i in range(3) for j in range(3)))
def trig(x,kind):
 c=x.c;f=np.sin(c) if kind=='sin' else np.cos(c);d=np.cos(c) if kind=='sin' else -np.sin(c)
 return A(x.ctx,f,d[:,None]*x.g).noise(.5*x.radius()**2+1e-14).rounding(abs(f)+abs(d)*x.radius(),x.ctx.n)
def invsqrt(x):
 lo,hi=x.bounds()
 if min(lo)<=0:raise ValueError('inverse sqrt interval crosses zero')
 fc=1/np.sqrt(x.c);s=-.5*x.c**(-1.5);M=.75*lo**(-2.5)
 return A(x.ctx,fc,s[:,None]*x.g).noise(.5*M*x.radius()**2+1e-14).rounding(abs(fc)+abs(s)*x.radius(),x.ctx.n)
def normalize(q):return cat(*(q[k]*invsqrt(dot(q,q)) for k in range(4)))
def qmul(a,b):
 w,x,y,z=(a[i] for i in range(4));r,s,t,u=(b[i] for i in range(4))
 return cat(w*r-x*s-y*t-z*u,w*s+x*r+y*u-z*t,w*t-x*u+y*r+z*s,w*u+x*t-y*s+z*r)
def qconj(a):return a*np.array([1.,-1,-1,-1])
def rotation(q):
 w,x,y,z=(q[i] for i in range(4))
 return cat(1-2*(y*y+z*z),2*(x*y-w*z),2*(x*z+w*y),2*(x*y+w*z),1-2*(x*x+z*z),2*(y*z-w*x),2*(x*z-w*y),2*(y*z+w*x),1-2*(x*x+y*y))
def qexp(v):
 # Entire scalar functions of s=|v|² avoid norm singularity at zero.
 import math
 s=dot(v,v);sc=max(abs(s.bounds()[0][0]),abs(s.bounds()[1][0]));C=v.ctx
 if sc>4:raise ValueError('rotation exponential remainder domain |dt omega|²<=4')
 cs=C.constant([0.]);sn=C.constant([0.]);power=C.constant([1.])
 for k in range(7):
  cs=cs+((-1)**k/(4**k*math.factorial(2*k)))*power
  sn=sn+((-1)**k/(2*4**k*math.factorial(2*k+1)))*power;power=power*s
 cs=cs.noise([sc**7/(4**7*math.factorial(14))/(1-sc/(4*15*16))+1e-15]);sn=sn.noise([sc**7/(2*4**7*math.factorial(15))/(1-sc/(4*16*17))+1e-15])
 return normalize(cat(cs,v[0]*sn,v[1]*sn,v[2]*sn))
def atan2(y,x):
 yl,yu=y.bounds();xl,xu=x.bounds()
 if min(xl)<0 and min(yl)<=0<=max(yu):raise ValueError('capture yaw branch cut requires mode split')
 rr=np.sqrt(x.c*x.c+y.c*y.c);rmin=rr-np.sqrt(x.radius()**2+y.radius()**2)
 if min(rmin)<=0:raise ValueError('capture yaw atan2 rectangle crosses origin')
 z=(y-y.c)*(x.c/(rr*rr))+(x-x.c)*(-y.c/(rr*rr))+np.arctan2(y.c,x.c)
 return z.noise(.5*(x.radius()**2+y.radius()**2)/(rmin*rmin)+1e-5)
def yaw(q):
 return atan2(2*(q[1]*q[2]+q[0]*q[3]),1-2*(q[2]*q[2]+q[3]*q[3]))
def solve(I,rhs):
 ic=I.c.reshape(3,3);inv=np.linalg.inv(ic);delta=np.max(I.radius().reshape(3,3).sum(axis=1));beta=np.linalg.norm(inv,np.inf)*delta
 if beta>=1:raise ValueError('inertia Neumann condition lost')
 center=inv@rhs.c;g=rhs.pad().copy()
 for i in range(3):
  for j in range(3):g[i]-=I.pad()[3*i+j]*center[j]
 lg=inv@g;rem=beta/(1-beta)*np.max(np.sum(abs(lg),axis=1))
 return A(I.ctx,center,lg).noise(np.full(3,rem+1e-14)).rounding(abs(center)+np.sum(abs(lg),axis=1)+rem,I.ctx.n)

def compress(state,initial_n,rank=24,box=False):
 keys=list(state);sizes=[len(state[k].c) for k in keys];allx=cat(*(state[k] for k in keys));G=allx.pad();old=G.shape[1]
 if box:
  new=np.diag(np.sum(abs(G),axis=1));lost=float(np.max(np.sum(abs(G),axis=1)));kept=0
 else:
  head=G[:,:initial_n];tail=G[:,initial_n:]
  if tail.shape[1]==0:return state,{'before':old,'after':old,'discarded_row_radius_max':0.}
  if rank<0:
   # Preserve actual shared directions, rather than independentizing SVD
   # coordinates. Ranking uses declared physical error scales, not mixed units.
   scale=[]
   for key,n in zip(keys,sizes):scale.extend([{'p':.1,'op':.1,'lp':.1,'origin':.1,'r':.1,'capture_p':.1,'v':.15,'ov':.15,'lv':.15,'bpold':.15,'q':.01,'att':.01,'align':.01,'w':.1,'gyro':.1,'d1':.1,'d2':.1,'h':.01,'previous':.1,'mean':.1,'f':10.,'pending':10.}.get(key,.1)]*n)
   weights=np.linalg.norm(tail/np.array(scale)[:,None],axis=0);idx=np.argsort(weights)[::-1][:min(-rank,tail.shape[1])];discard=np.ones(tail.shape[1],bool);discard[idx]=False
   radius=np.sum(abs(tail[:,discard]),axis=1)+1e-13*(np.sum(abs(tail),axis=1)+1);new=np.column_stack([head,tail[:,idx],np.diag(radius)]);lost=float(max(radius));kept=len(idx)
  else:
   U,s,V=np.linalg.svd(tail,full_matrices=False);k=min(rank,len(s));basis=U[:,:k]*s[:k];amps=np.sum(abs(V[:k]),axis=1)
   remainder=tail-basis@V[:k];radius=np.sum(abs(remainder),axis=1)+1e-13*(np.sum(abs(tail),axis=1)+1)
   new=np.column_stack([head,basis*amps,np.diag(radius)]);lost=float(max(radius));kept=k
 state2={};offset=0;allx.ctx.n=new.shape[1]
 for key,n in zip(keys,sizes):state2[key]=A(allx.ctx,allx.c[offset:offset+n],new[offset:offset+n]);offset+=n
 return state2,{'before':old,'after':new.shape[1],'discarded_row_radius_max':lost,'rank':kept,'initial_columns':0 if box else initial_n,'scope':'linear projection plus rowL1 outer enclosure, not exact set equality; FP/SVD budgeting conditional'}

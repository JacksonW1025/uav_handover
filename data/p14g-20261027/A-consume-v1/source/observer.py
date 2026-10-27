"""Conditional source-OP innovation dynamics, no file or future-data access.
The source controls how fusion errors correct output; it does NOT constrain
unknown future EKF target errors. Fading slope is an explicitly tested proxy.
"""
import copy,numpy as np
from p14r.exact_observer import Observer as Base
from p14_motion.core import mul

def qexp(v):
 a=np.linalg.norm(v);return np.r_[np.cos(a/2),v*(np.sin(a/2)/a if a>1e-16 else .5)]
class Observer(Base):
 def __init__(self,i,library,extra_delay=0,producer_order='PRE'):
  super().__init__(copy.deepcopy(i),library,extra_delay,producer_order);mode=i.get('p14g_innovation',{'mode':'held'});self.mode=mode;old=self.op.fuse
  if mode['mode']=='fading':
   def fuse(t,q,v,g,bg,ba):
    dt=max(0,(t-mode['past_delayed_sample_us'])*1e-6);amp=mode['tau_s']*(1-np.exp(-dt/mode['tau_s']));theta=amp*np.array(mode['rates']['theta']);vv=amp*np.array(mode['rates']['velocity']);pp=amp*np.array(mode['rates']['position']);return old(t,mul(qexp(theta),q),np.array(v)+vv,self.op.add(g,pp),bg,ba)
   self.op.fuse=fuse

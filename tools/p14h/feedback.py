"""One stateful, physics-coupled fused-target error approximation.
Empirical aiding rates come only from diagnostic development; no OP-tau decay,
future logs, diagonal-as-fullP, or safety-certificate claim.
"""
import numpy as np
from p14r.exact_observer import Observer as Base
from p14_motion.core import mul,conjugate
from p11.models import R

def qexp(x):
 x=np.asarray(x);a=np.linalg.norm(x);return np.r_[np.cos(a/2),x*(np.sin(a/2)/a if a>1e-16 else .5)]
def unit(q):return np.asarray(q)/np.linalg.norm(q)
def coefficients(rate,dt):
 rho=np.exp(-rate*dt);return rho,(1-rho)/rate if rate>1e-12 else dt
class Observer(Base):
 def __init__(self,i,library,extra_delay=0,producer_order='PRE'):
  super().__init__(i,library,extra_delay,producer_order);self.error_model=i.get('p14h_error_model');self.error_live=None
  if not self.error_model:return
  p=self.par;self.anchor=unit(p['fusion_attitude_alignment']);self.ep0=np.array(p['fusion_position_error_NED']);self.ev0=np.array(p['fusion_velocity_error']);self.align_input=np.array(p['fusion_attitude_alignment']);self.dbg=np.array(p['sensor_gyro_bias'])-p['gyro_bias'];self.dba=np.array(p['sensor_accel_bias'])-p['accel_bias'];t=self.fusion_pub-self.delay;v=np.array(self.physical[t]['body_v']);self.error_live={'E':self.anchor.copy(),'ev':self.ev0.copy(),'ep':self.ep0.copy(),'last_v':v,'sample_us':t}
  if i.get('p14h_error_live'):
   x=i['p14h_error_live'];self.error_live={k:np.array(v) if k!='sample_us' else int(v) for k,v in x.items()}
  old=self.op.fuse
  def fuse(t,q,v,g,bg,ba):
   z=self.error_live;dt=(t-z['sample_us'])*1e-6
   if not 0<dt<=.032:raise ValueError('errorstate fusion-step assumption violated; branch/unmodelled')
   trueq=unit(mul(conjugate(self.align_input),q));truev=np.asarray(v)-self.ev0;trueg=self.op.add(g,-self.ep0);E=z['E'];qhat=mul(E,trueq);specific=(truev-z['last_v'])/dt-np.array([0,0,9.8]);drive=(R(E)-np.eye(3))@specific+R(qhat)@self.dba;rates=self.error_model['rates_per_s'];rv,av=coefficients(rates['v'],dt);rp,ap=coefficients(rates['p'],dt);rq,_=coefficients(rates['theta'],dt);driven=unit(mul(qexp(R(qhat)@self.dbg*dt),E));anchor=self.anchor if np.dot(driven,self.anchor)>=0 else -self.anchor;En=unit(rq*driven+(1-rq)*anchor);ev=rv*z['ev']+av*drive;ep=self.ep0+rp*(z['ep']-self.ep0)+ap*ev;self.error_live={'E':En,'ev':ev,'ep':ep,'last_v':truev.copy(),'sample_us':int(t)}
   return old(t,mul(En,trueq),truev+ev,self.op.add(trueg,ep),bg,ba)
  self.op.fuse=fuse
 def dump(self,control_sample):
  x=super().dump(control_sample)
  if self.error_live is not None:x['p14h_error_live']={k:v.tolist() if isinstance(v,np.ndarray) else v for k,v in self.error_live.items()}
  return x

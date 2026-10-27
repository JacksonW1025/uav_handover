"""Source LP-before-attitude producer queue, initial backlog separated fromfuture.
One nominal causal mode. No false all-future scheduler/EKF coverage claim.
"""
import numpy as np
from p14h.feedback import Observer as Base
from p14r.op import Op
from p14_motion.core import biquad,mul,LEVER
from p11.models import R
class Observer(Base):
 def __init__(self,i,library,extra_delay=0,producer_order='PRE'):
  super().__init__(i,library,extra_delay,producer_order);self.schedule=i.get('p14h_schedule_model')
  if not self.schedule:return
  self.lag=int(self.schedule['future_OP_lag_us_nominal']);self.att_delay=int(self.schedule.get('att_extra_delivery_us',0));assert self.lag in [0,4000,8000] and self.att_delay in [0,4000]
  if not i.get('observer_live'):
   self.lp_sample=int(i['LP_cache_sample_us']);self.att_sample=int(i['att_cache_sample_us']);q,v,g,_=self.op.outputs();pending=[]
   # Lastfusionblob is the actual known post-correction state before later
   # propagation operations. Its LPpayload is not current OP extrapolation.
   f=Op(library,dict(i['observer'],past_operations=[]));fq,fv,fg,_=f.outputs();fp=f.project(fg,self.par['LP_reference_geo']);f.close();due=int(i['sample_us'])+4000
   if self.fusion_pub>self.lp_sample:pending.append((due,'LP',np.r_[fp,fv].astype(float),self.fusion_pub))
   if self.t>self.att_sample:pending.append((due+self.att_delay,'att',q.astype(float),self.t))
   self.queue=pending+self.queue
 def step(self,control_sample,p,v,q,w):
  if not self.schedule:return super().step(control_sample,p,v,q,w)
  M=R(q);self.physical[int(control_sample)]={'p':p.copy(),'v':v.copy(),'q':q.copy(),'w':w.copy(),'body_p':p+M@LEVER,'body_v':v+M@np.cross(w,LEVER)};target=int(control_sample-self.lag)
  while self.t<target:
   self.t+=4000;x=self.physical[self.t];rawg=np.array(x['w'])+self.par['sensor_gyro_bias'];rawa=self.rawaccel(self.t);da=.5*(rawg+self.lastgyro)*.004;coning=np.cross(self.lastdelta,da)/12;dv=.5*(rawa+self.lastaccel)*.004;self.lastdelta=da;self.lastgyro=rawg;self.lastaccel=rawa;self.op.advance(self.t,da+coning,dv);fused=self.t-self.fusion_pub>=self.par['fusion_period_us']
   if fused:
    self.fusion_pub=self.t;d=self.physical[self.t-self.delay];qf=mul(np.array(self.par['fusion_attitude_alignment']),np.array(d['q']));vf=np.array(d['body_v'])+self.par['fusion_velocity_error'];gf=self.op.add(self.op.add(self.par['world_geo'],d['body_p']),self.par['fusion_position_error_NED']);self.op.fuse(self.t-self.delay,qf,vf,gf,self.par['gyro_bias'],self.par['accel_bias'])
   oq,ov,og,_=self.op.outputs();lp=self.op.project(og,self.par['LP_reference_geo'])
   # Actual source EKF2::Run publishes LP after update andattitude afterLP.
   if fused:self.queue.append((control_sample+self.extra,'LP',np.r_[lp,ov].astype(float),self.t))
   self.queue.append((control_sample+self.extra+self.att_delay,'att',oq.astype(float),self.t))
  for due,kind,value,sample in self.queue:
   if due>control_sample:continue
   if kind=='att':
    if sample<self.att_sample:raise ValueError('sameproducer attitude timestampregression requiresdifferentmode')
    self.q=value;self.att_sample=sample
   else:
    if sample<self.lp_sample:raise ValueError('sameproducer LP timestampregression requiresdifferentmode')
    self.p=value[:3];self.v=value[3:];self.lp_sample=sample
  self.queue=[x for x in self.queue if x[0]>control_sample];filtered,self.d1,self.d2=biquad(w+np.array(self.par['sensor_gyro_bias']),self.d1,self.d2);self.gyro=filtered-np.array(self.par['gyro_bias']);return self.p.copy(),self.v.copy(),self.q.copy(),self.gyro.copy()

"""Source OutputPredictor + source-shaped IMU integration, conditional fusion.
Source q/gyro/LP and physical states remain distinct. Future EKF fused-target
error is held initial state, an explicit approximation rather than oracle data.
"""
import numpy as np
from p14r.op import Op
from p14_motion.core import mul,LEVER,biquad
from p11.models import R

class Observer:
 def __init__(self,i,library,extra_delay=0,producer_order='PRE'):
  self.producer_order=producer_order;self.i=i;self.par=i['observer_parameters'];self.op=Op(library,i['observer']);self.t=int(i['observer']['latest_completed_update_sample_us']);self.fusion_pub=int(i['observer']['latest_fusion_publication_sample_us']);self.physical={x['sample_us']:x for x in i['physical_prefix']};self.lag=self.par['OP_lag_us'];self.delay=self.par['fusion_delay_us'];self.extra=int(round(extra_delay*1e6));self.q=np.array(i['attitude']);self.p=np.array(i['position']);self.v=np.array(i['velocity']);self.gyro=np.array(i['omega']);self.d1=np.array(i['gyro_delay1']);self.d2=np.array(i['gyro_delay2']);self.queue=[];self.lp_sample=int(i['sample_us']-((i['sample_us']-i['lp_phase_us'])%8000));self.att_sample=self.t
  assert self.lag>=0 and self.lag%4000==0
  # Initial raw sensor integrator state is from source-shaped physical prefix.
  x=self.physical[self.t];self.lastgyro=np.array(x['w'])+self.par['sensor_gyro_bias'];prev=self.physical[self.t-4000];self.lastdelta=.5*(self.lastgyro+np.array(prev['w'])+self.par['sensor_gyro_bias'])*.004;self.lastaccel=self.rawaccel(self.t)
  live=i.get('observer_live')
  if live:
   self.lastgyro=np.array(live['lastgyro']);self.lastdelta=np.array(live['lastdelta']);self.lastaccel=np.array(live['lastaccel']);self.lp_sample=live['lp_sample'];self.att_sample=live['att_sample'];self.queue=[(a,k,np.array(v),s) for a,k,v,s in live['queue']]
 def rawaccel(self,t):
  x=self.physical[t];y=self.physical[t-4000];return R(np.array(x['q'])).T@((np.array(x['body_v'])-y['body_v'])/.004-np.array([0,0,9.8]))+self.par['sensor_accel_bias']
 def step(self,control_sample,p,v,q,w):
  M=R(q);self.physical[int(control_sample)]={'p':p.copy(),'v':v.copy(),'q':q.copy(),'w':w.copy(),'body_p':p+M@LEVER,'body_v':v+M@np.cross(w,LEVER)};lag=0 if self.producer_order=='POST' else self.lag;target=int(control_sample-lag)
  while self.t<target:
   self.t+=4000;x=self.physical[self.t];rawg=np.array(x['w'])+self.par['sensor_gyro_bias'];rawa=self.rawaccel(self.t);da=.5*(rawg+self.lastgyro)*.004;coning=np.cross(self.lastdelta,da)/12;dv=.5*(rawa+self.lastaccel)*.004;self.lastdelta=da;self.lastgyro=rawg;self.lastaccel=rawa;self.op.advance(self.t,da+coning,dv)
   fused=self.t-self.fusion_pub>=self.par['fusion_period_us']
   if fused:
    self.fusion_pub=self.t;d=self.physical[self.t-self.delay];qf=mul(np.array(self.par['fusion_attitude_alignment']),np.array(d['q']));vf=np.array(d['body_v'])+self.par['fusion_velocity_error'];gf=self.op.add(self.op.add(self.par['world_geo'],d['body_p']),self.par['fusion_position_error_NED']);self.op.fuse(self.t-self.delay,qf,vf,gf,self.par['gyro_bias'],self.par['accel_bias'])
   oq,ov,og,corr=self.op.outputs();lp=self.op.project(og,self.par['LP_reference_geo']);self.queue.append((control_sample+self.extra,'att',oq.astype(float),self.t))
   if fused:self.queue.append((control_sample+self.extra,'LP',np.r_[lp,ov].astype(float),self.t))
  for due,kind,value,sample in self.queue:
   if due>control_sample:continue
   if kind=='att':self.q=value;self.att_sample=sample
   else:self.p=value[:3];self.v=value[3:];self.lp_sample=sample
  self.queue=[x for x in self.queue if x[0]>control_sample]
  filtered,self.d1,self.d2=biquad(w+np.array(self.par['sensor_gyro_bias']),self.d1,self.d2);self.gyro=filtered-np.array(self.par['gyro_bias'])
  return self.p.copy(),self.v.copy(),self.q.copy(),self.gyro.copy()
 def dump(self,control_sample):
  import base64
  return {'observer':{'fusion_base64':base64.b64encode(self.op.snapshot()).decode(),'past_operations':[],'latest_completed_update_sample_us':self.t,'latest_fusion_publication_sample_us':self.fusion_pub},'physical_prefix':[{'sample_us':int(t),**{k:np.asarray(v).tolist() for k,v in x.items() if k!='sample_us'}} for t,x in sorted(self.physical.items()) if t>=control_sample-400000],'observer_live':{'lastgyro':self.lastgyro.tolist(),'lastdelta':self.lastdelta.tolist(),'lastaccel':self.lastaccel.tolist(),'lp_sample':self.lp_sample,'att_sample':self.att_sample,'queue':[(int(a),k,v.tolist(),int(s)) for a,k,v,s in self.queue]}}
 def close(self):self.op.close()

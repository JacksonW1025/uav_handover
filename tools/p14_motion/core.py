"""Causal moving source nominal; no log paths or future measurements."""
import copy
import numpy as np
from p11.models import R,plant,reference,speeds,tilt
from p12.state import Controller,EventTarget
from p12.execution import step as filter_step
from p13.physical_model import source_step,turn,mass

DT=.004;LEVER=np.array([0.,0.,.00186913101803548])
def mul(q,r):
 w,x,y,z=q;a,b,c,d=r
 return np.array([w*a-x*b-y*c-z*d,w*b+x*a+y*d-z*c,w*c-x*d+y*a+z*b,w*d+x*c-y*b+z*a])
def conjugate(q):return q*np.array([1,-1,-1,-1])
def yaw(q):return np.arctan2(R(q)[1,0],R(q)[0,0])
def coeff():
 ohm=np.tan(np.pi*40/250);c=1+np.sqrt(2)*ohm+ohm*ohm
 return np.array([ohm*ohm/c,2*ohm*ohm/c,ohm*ohm/c,2*(ohm*ohm-1)/c,(1-np.sqrt(2)*ohm+ohm*ohm)/c])
def biquad(x,d1,d2):
 b0,b1,b2,a1,a2=coeff();d0=x-a1*d1-a2*d2
 return b0*d0+b1*d1+b2*d2,d0,d1
def physical(p,v,q,w,f,fn,phase):
 _,ve,qn,wn=source_step(p,v,q,w,f,fn,DT,phase=phase)
 M=R(q);N=R(qn);r=-LEVER;alpha=(wn-w)/DT;ac=(ve-v)/DT
 vb=v-M@np.cross(w,r);ab=ac-M@(np.cross(alpha,r)+np.cross(w,np.cross(w,r)))
 vbn=vb+DT*ab
 return p-M@r+DT*vbn+N@r,vbn+N@np.cross(wn,r),qn,wn

class Ctl(Controller):
 def __init__(self,i,plan):
  self.h=np.array(i['h']);self.previous=np.array(i['previous']);self.mean=np.array(i['history']);self.count=int(i['history_count']);self.index=int(i['call_index']);self.force_sync=2;self.last_sample=int(i['sample_us']);self.phase=int(plan['p12_phase']);self.pending=None
  if i['stale'] and np.linalg.norm(i['target_v'])>1e-5:raise ValueError('initial captured moving profile not recovered')
  self.target=EventTarget(bool(plan['p12_repair']));self.target.external_seen=bool(i['external_seen']);self.target.r=np.array(i['target_p']);self.target.s=np.array(i['target_v']);self.target.yaw=float(i['target_yaw']);self.target.stale=bool(i['stale']);self.target.last_read=i['last_read_us']

def forecast(doc,M,P,variant='source',limit=None,scenario=None):
 i=doc['initial'];plan=doc['plan'];p=np.array(i['physical_COM_p']);v=np.array(i['physical_COM_v']);q=np.array(i['physical_q']);w=np.array(i['physical_omega']);phase=np.array(i['rotor_phase'])
 f=np.array(i['rotor_filter']);pending=np.array(i['pending_command']);op=np.array(i['position']);ov=np.array(i['velocity']);lp=op.copy();lv=ov.copy();att=np.array(i['attitude']);gyro=np.array(i['omega'])
 # GPS/LP NED axes are independent of estimated attitude heading error.
 nav=np.array(i.get('navigation_rotation_NED',np.eye(3)),float)
 align=mul(att,conjugate(q));bp=nav@(p+R(q)@LEVER);bv=nav@(v+R(q)@np.cross(w,LEVER));origin=op-bp
 d1=np.array(i['gyro_delay1']);d2=np.array(i['gyro_delay2']);bias=np.array(i['gyro_output_bias']);ctl=Ctl(i,plan);last_send=i.get('last_send_profile_s',-1e30);table=np.asarray(plan['profile']['table']);rows=[];states=[];inputs=[];native=[];stop=None
 end=plan['horizon_profile_s'] if limit is None else limit;older=pending.copy()
 clockjump=int(np.ceil((plan['full_source_windows_profile_s'][0][0]+.2-i['profile_s'])/DT))
 for k in range(int(np.ceil((end-i['profile_s'])/DT))+1):
  t=i['profile_s']+k*DT;sample=i['sample_us']+k*4000;now=i['native_us']+k*4000+(4000 if scenario=='native_plateau' and k==clockjump else 0)
  native.append(now)
  if k:
   oldhat=mul(align,q);selected=older if scenario=='extra_command_delay' else pending;older=pending.copy();fn=filter_step(f,selected,DT)
   if variant=='empirical_same_observer':p,v,q,w,_=plant(p,v,q,w,f,M);phase+=-turn*fn/10*DT
   else:p,v,q,w=physical(p,v,q,w,f,fn,phase)
   f=fn;bn=nav@(p+R(q)@LEVER);vn=nav@(v+R(q)@np.cross(w,LEVER));rho=np.exp(-DT/.25)
   ovn=vn+rho*(ov-bv);op=bn+origin+rho*(op+DT*(ov+ovn)/2-bn-origin);ov=ovn;bv=vn
   gy,d1,d2=biquad(w,d1,d2);gyro=gy+bias if variant!='source_no_gyro_filter' else w+bias
   att=mul(align,q) if variant=='source_no_att_delay' else oldhat
   if (sample-i['lp_phase_us'])%8000==0:lp=op.copy();lv=ov.copy()
   msg=None;inside=any(a<=t<b for a,b in plan['windows_profile_s'])
   if 0<=t<plan['stream_end_profile_s'] and not inside and t-last_send>=plan['publish_period_s']-1e-10:
    msg=reference(t,plan['profile'],table);last_send=t
   ctl.target.repair=plan['p12_repair'] and sample>=plan.get('repair_not_before_sample_us',0)
   action,info=ctl.step(now,sample,lp,lv,att,gyro,msg,P)
   if action is not None:pending=speeds(action)
   xx=info.get('input',np.full(22,np.nan))
  else:xx=np.full(22,np.nan)
  rows.append(np.r_[t,op,ov,tilt(att),ctl.previous,ctl.h,ctl.target.r,ctl.target.s,ctl.target.stale,mul(align,q),gyro,lp,lv,att,p[2],v[2],f])
  states.append(np.r_[p,v,q,w,phase,d1,d2,gyro,op,ov,ctl.mean,ctl.count]);inputs.append(xx)
  if not np.isfinite(states[-1]).all():stop={'profile_s':t,'reason':'NUMERICAL_UNCERTAIN'};break
  if tilt(q)>80 or max(abs(w))>8 or np.linalg.norm(v)>8:
   stop={'profile_s':t,'reason':'PHYSICAL_MODEL_DOMAIN_EXIT'};break
 return {'trace':np.array(rows),'states':np.array(states),'inputs':np.array(inputs),'native_us':np.array(native),'stop':stop,'target_events':ctl.target.events,'variant':variant,'height_modelled':True,'physical_and_observer_separate':True,'retrospective':True,'future_measurements_used':False}

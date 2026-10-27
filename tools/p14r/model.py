"""P14R moving source model; inherits immutable verified geometry/gyro/history.
One new stateful publisher/transport layer. No log access in forecast.
"""
import numpy as np
from p14_motion.core import DT,LEVER,physical,mul,conjugate,coeff,biquad,Ctl
from p11.models import R,plant,reference,speeds,tilt
from p12.execution import step as filter_step
from p13.physical_model import turn
from p14r.delivery import Delivery,Word
from p14r.exact_observer import Observer
def forecast(doc,M,P,variant='source',limit=None,scenario=None,word=None,observer_library=None,checkpoint_times=()):
 i=doc['initial'];plan=doc['plan'];p=np.array(i['physical_COM_p']);v=np.array(i['physical_COM_v']);q=np.array(i['physical_q']);w=np.array(i['physical_omega']);phase=np.array(i['rotor_phase'])
 f=np.array(i['rotor_filter']);pending=np.array(i['pending_command']);op=np.array(i['position']);ov=np.array(i['velocity']);lp=op.copy();lv=ov.copy();att=np.array(i['attitude']);gyro=np.array(i['omega'])
 # GPS/LP NED axes are independent of estimated attitude heading error.
 nav=np.array(i.get('navigation_rotation_NED',np.eye(3)),float)
 align=mul(att,conjugate(q));bp=nav@(p+R(q)@LEVER);bv=nav@(v+R(q)@np.cross(w,LEVER));origin=op-bp
 estimated_q=att.copy();d1=np.array(i['gyro_delay1']);d2=np.array(i['gyro_delay2']);bias=np.array(i['gyro_output_bias']);ctl=Ctl(dict(i,stale=False) if i.get('controller_live') else i,plan);last_send=i.get('last_send_profile_s',-1e30);table=np.asarray(plan['profile']['table']);rows=[];states=[];inputs=[];native=[];stop=None
 checkpoints=[];D=float(i.get('physical_D0_m',0));LPD=float(i.get('LP_D0_m',0));tilt_failed=bool(i.get('LP_tilt_failed_past',False));live=i.get('controller_live')
 if live:
  ctl.pending=None if live['pending'] is None else (np.array(live['pending'][0]),np.array(live['pending'][1]),live['pending'][2])
  for key,value in live['target'].items():
   if key in ['r','s']:value=np.array(value)
   if key=='profile' and value is not None:value=(value[0],np.array(value[1]),value[2],np.array(value[3]))
   if key=='recovery' and value is not None:value=[value[0],np.array(value[1]),np.array(value[2])]
   setattr(ctl.target,key,value)
 end=plan['horizon_profile_s'] if limit is None else limit;older=np.array(i.get('last_consumed_command',pending))
 delivery=Delivery(doc,word or Word());observer=Observer(i,observer_library,(word or Word()).transport_s,(word or Word()).producer_order) if observer_library is not None else None
 if observer is not None:
  estimated_q,ov,og,_=observer.op.outputs();op=observer.op.project(og,observer.par['LP_reference_geo'])
 clockjump=int(np.ceil((plan['full_source_windows_profile_s'][0][0]+.2-i['profile_s'])/DT))
 for k in range(int(np.ceil((end-i['profile_s'])/DT))+1):
  t=i['profile_s']+k*DT;sample=i['sample_us']+k*4000;now=i['native_us']+k*4000+(4000 if scenario=='native_plateau' and k==clockjump else 0)
  native.append(now)
  if k:
   oldhat=mul(align,q);selected=older if scenario=='extra_command_delay' else pending;older=pending.copy();fn=filter_step(f,selected,DT)
   if variant=='empirical_same_observer':p,v,q,w,_=plant(p,v,q,w,f,M);phase+=-turn*fn/10*DT
   else:p,v,q,w=physical(p,v,q,w,f,fn,phase)
   f=fn
   if observer is None:
    bn=nav@(p+R(q)@LEVER);vn=nav@(v+R(q)@np.cross(w,LEVER));rho=np.exp(-DT/.25)
    ovn=vn+rho*(ov-bv);op=bn+origin+rho*(op+DT*(ov+ovn)/2-bn-origin);ov=ovn;bv=vn
    gy,d1,d2=biquad(w,d1,d2);gyro=gy+bias if variant!='source_no_gyro_filter' else w+bias
    att=mul(align,q) if variant=='source_no_att_delay' else oldhat
    if (sample-i['lp_phase_us'])%8000==0:lp=op.copy();lv=ov.copy()
   else:
    lp,lv,att,gyro=observer.step(sample,p,v,q,w);oq,ov,og,_=observer.op.outputs();op=observer.op.project(og,observer.par['LP_reference_geo']);estimated_q=oq.astype(float);d1=observer.d1.copy();d2=observer.d2.copy()
   msg=delivery.step(t)
   ctl.target.repair=plan['p12_repair'] and sample>=plan.get('repair_not_before_sample_us',0)
   action,info=ctl.step(now,sample,lp,lv,att,gyro,msg,P)
   if action is not None:pending=speeds(action)
   xx=info.get('input',np.full(22,np.nan))
  else:xx=np.full(22,np.nan)
  rows.append(np.r_[t,op,ov,tilt(att),ctl.previous,ctl.h,ctl.target.r,ctl.target.s,ctl.target.stale,estimated_q if observer is not None else mul(align,q),gyro,lp,lv,att,p[2],v[2],f])
  states.append(np.r_[p,v,q,w,phase,d1,d2,gyro,op,ov,ctl.mean,ctl.count]);inputs.append(xx)
  D=max(D,float(p[2]-i['physical_H0_NED_z']));LPD=max(LPD,float(lp[2]-i.get('LP_H0_NED_z',lp[2])));tilt_failed=tilt_failed or tilt(att)>45
  if k and any(t>=at-1e-10 and not any(c['requested_time']==at for c in checkpoints) for at in checkpoint_times):
   import copy
   ci=copy.deepcopy(i);ci.update(profile_s=t,sample_us=sample,native_us=now,physical_COM_p=p.tolist(),physical_COM_v=v.tolist(),physical_q=q.tolist(),physical_omega=w.tolist(),rotor_phase=phase.tolist(),rotor_filter=f.tolist(),pending_command=pending.tolist(),last_consumed_command=older.tolist(),position=lp.tolist(),velocity=lv.tolist(),attitude=att.tolist(),omega=gyro.tolist(),h=ctl.h.tolist(),previous=ctl.previous.tolist(),history=ctl.mean.tolist(),history_count=ctl.count,call_index=ctl.index,stale=ctl.target.stale,last_read_us=ctl.target.last_read,external_seen=ctl.target.external_seen,target_p=ctl.target.r.tolist(),target_v=ctl.target.s.tolist(),target_yaw=ctl.target.yaw,physical_D0_m=D,LP_D0_m=LPD,LP_tilt_failed_past=tilt_failed,gyro_delay1=d1.tolist(),gyro_delay2=d2.tolist(),delivery_live=delivery.dump(),publisher_unconsumed_past=None)
   def jsonable(x):
    if isinstance(x,np.ndarray):return x.tolist()
    if isinstance(x,(tuple,list)):return [jsonable(v) for v in x]
    if isinstance(x,dict):return {k:jsonable(v) for k,v in x.items()}
    return x
   ci['controller_live']={'pending':jsonable(ctl.pending),'target':jsonable(vars(ctl.target))}
   if observer is not None:ci.update(observer.dump(sample));ci['lp_phase_us']=observer.lp_sample%8000
   requested=next(at for at in checkpoint_times if t>=at-1e-10 and not any(c['requested_time']==at for c in checkpoints));checkpoints.append({'requested_time':requested,'actual_time':t,'initial':ci,'D_not_reset':True,'physical_height_failure_latch':D>1,'LP_task_failure_latch':(LPD>1 or tilt_failed) if 'LP_H0_NED_z' in i else 'UNKNOWN_LP_BASELINE','controller_mode':'NEURAL_ACTIVE','classic_integrators':'opaque inactive retained, no invented zero'})
  if not np.isfinite(states[-1]).all():stop={'profile_s':t,'reason':'NUMERICAL_UNCERTAIN'};break
  if tilt(q)>80 or max(abs(w))>8 or np.linalg.norm(v)>8:
   stop={'profile_s':t,'reason':'PHYSICAL_MODEL_DOMAIN_EXIT'};break
 if observer is not None:observer.close()
 return {'checkpoints':checkpoints,'trace':np.array(rows),'states':np.array(states),'inputs':np.array(inputs),'native_us':np.array(native),'stop':stop,'target_events':ctl.target.events,'variant':variant,'height_modelled':True,'physical_and_observer_separate':True,'retrospective':True,'future_measurements_used':False}

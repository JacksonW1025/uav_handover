"""One P13 source-physics candidate, development working copy; no future reads."""
import numpy as np
from scipy.spatial.transform import Rotation
from open_plant_v1 import source_step,S,B
from p11.models import assert_input,R as matrix,speeds,reference,tilt,features,qstep
from p12.state import Controller
from p12.execution import step as motor_step

def forecast(doc,model,P):
 assert_input(doc);ini=doc['initial'];plan=doc['plan'];dt=.004
 p=np.array(ini['physical_COM_p']);v=np.array(ini['physical_COM_v']);q=np.array(ini['physical_q']);w=np.array(ini['physical_omega']);offset=np.array(ini['COM_to_origin_body']);M0=matrix(q);origin0=p+M0@offset;originv0=v+M0@np.cross(w,offset)
 E=matrix(np.array(ini['attitude']))@M0.T;biasw=np.array(ini['omega'])-w
 def obs(p,v,q,w):
  M=matrix(q);op=p+M@offset;ov=v+M@np.cross(w,offset);cq=Rotation.from_matrix(E@M).as_quat()[[3,0,1,2]]
  return np.array(ini['position'])+(op-origin0),np.array(ini['velocity'])+(ov-originv0),cq,w+biasw
 ohm=np.tan(np.pi*40/250);den=1+np.sqrt(2)*ohm+ohm*ohm;b0=ohm*ohm/den;b1=2*b0;b2=b0;a1=2*(ohm*ohm-1)/den;a2=(1-np.sqrt(2)*ohm+ohm*ohm)/den
 z1=np.array(ini['omega'])/(1+a1+a2);z2=z1.copy()
 ep,ev,eq,ew=obs(p,v,q,w);lp=np.array(ini['position']);lv=np.array(ini['velocity']);att=np.array(ini['attitude']);ctl=Controller(ini,plan['p12_repair'],plan['p12_phase']);rotor=np.array(ini['rotor_filter']);pending=np.array(ini['pending_command']);t0=ini['profile_s'];sample=ini['sample_us'];native=ini['native_us'];lastsend=-1e30;table=np.asarray(plan['profile']['table']);rows=[];nt=[];stop=None
 for k in range(int(np.ceil((plan['horizon_profile_s']-t0)/dt))+1):
  t=t0+k*dt;st=sample+4000*k;now=native+4000*k;nt.append(now)
  if k:
   oldeq=eq.copy();rn=motor_step(rotor,pending,dt);op,ov,oq,ow=p.copy(),v.copy(),q.copy(),w.copy();p,v,_,_=source_step(p,v,q,w,rotor,rn);_,diff=features(rotor);w=ow+dt*(np.array(model['torque'])*diff-np.array(model['angular_drag'])*ow);q=qstep(oq,(ow+w)/2);rotor=rn;ep,ev,eq,ew=obs(p,v,q,w)
   if (st-ini['lp_phase_us'])%8000==0:lp=ep.copy();lv=ev.copy()
   att=oldeq
   inside=any(a<=t<b for a,b in plan['windows_profile_s']);msg=None
   if 0<=t<plan['stream_end_profile_s'] and not inside and t-lastsend>=plan['publish_period_s']-1e-10:msg=reference(t,plan['profile'],table);lastsend=t
   ctl.target.repair=plan['p12_repair'] and st>=plan.get('repair_not_before_sample_us',0)
   action,info=ctl.step(now,st,lp,lv,att,ew,msg,P)
   if action is not None:pending=speeds(action)
  rows.append(np.r_[t,ep,ev,tilt(eq),ctl.previous,ctl.h,ctl.target.r,ctl.target.s,ctl.target.stale,eq,ew,lp,lv,att,p,v,q,w,rotor])
  if not np.isfinite(rows[-1]).all():stop={'profile_s':t,'reason':'NUMERICAL_UNCERTAIN'};break
  if tilt(eq)>45 or max(abs(w))>8 or np.linalg.norm(ep[:2])>10 or -ep[2]>8:stop={'profile_s':t,'reason':'PREDICTED_ENVELOPE'};break
 return {'trace':np.array(rows),'native_us':np.array(nt),'stop':stop,'target_events':ctl.target.events,'kind':'M5','status':'SOURCE_PHYSICS_INITIAL_CACHE_OFFSET_CANDIDATE','height_modelled':True,'certified_actual_coverage':False,'scope':'source force/axis drag/mass/geometry/servo; averaged rotor transverse inertia; finite-step angular approximation; fixed initial estimator frame/bias, no future filter fitting'}

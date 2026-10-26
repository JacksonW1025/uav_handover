"""P13 candidate: source vertical COM/axis drag, inherited M4 horizontal/angular closure.
The inherited closure models controller-level attitude/rate; it is NOT promoted
into an exact physical angular model. The separate source step audit covers it.
"""
import numpy as np
from p11.models import assert_input,plant,tilt,speeds,reference,R
from p12.state import Controller
from p12.execution import step as motor_step
from open_plant_v1 import pos,mass

def forecast(doc,model,P):
 assert_input(doc);ini=doc['initial'];plan=doc['plan'];dt=.004
 p=np.array(ini['position']);v=np.array(ini['velocity']);q=np.array(ini['attitude']);omega=np.array(ini['omega']);lp=p.copy();lv=v.copy();att=q.copy();ctl=Controller(ini,plan['p12_repair'],plan['p12_phase']);rotor=np.array(ini['rotor_filter']);pending=np.array(ini['pending_command']);comz=ini['physical_COM_p'][2];comvz=ini['physical_COM_v'][2];offset=np.array(ini['COM_to_origin_body']);z_bias=p[2]-(comz+R(q)@offset)[2] if False else p[2]-comz-(R(q)@offset)[2];v_bias=v[2]-comvz-(R(q)@np.cross(omega,offset))[2];t0=ini['profile_s'];sample=ini['sample_us'];native=ini['native_us'];last_send=-1e30;table=np.asarray(plan['profile']['table']);rows=[];nt=[];stop=None
 for k in range(int(np.ceil((plan['horizon_profile_s']-t0)/dt))+1):
  t=t0+k*dt;st=sample+4000*k;now=native+4000*k;nt.append(now)
  if k:
   oldq=q.copy();M=R(q);axis=M[:,2];vel=np.r_[v[:2],comvz];linkv=vel+np.cross(omega,pos)@M.T;perp=linkv-np.outer(linkv@axis,axis);drag=(-abs(rotor)[:,None]*8.06428e-5*perp).sum(axis=0);az=9.8-axis[2]*8.54858e-6*np.sum(rotor**2)/mass+drag[2]/mass;comvz+=dt*az;comz+=dt*comvz
   p,v,q,omega,_=plant(p,v,q,omega,rotor,model);p[2]=comz+(R(q)@offset)[2]+z_bias;v[2]=comvz+(R(q)@np.cross(omega,offset))[2]+v_bias;rotor=motor_step(rotor,pending,dt)
   if (st-ini['lp_phase_us'])%8000==0:lp=p.copy();lv=v.copy()
   att=oldq;inside=any(a<=t<b for a,b in plan['windows_profile_s']);msg=None
   if 0<=t<plan['stream_end_profile_s'] and not inside and t-last_send>=plan['publish_period_s']-1e-10:msg=reference(t,plan['profile'],table);last_send=t
   ctl.target.repair=plan['p12_repair'] and st>=plan.get('repair_not_before_sample_us',0);action,info=ctl.step(now,st,lp,lv,att,omega,msg,P)
   if action is not None:pending=speeds(action)
  rows.append(np.r_[t,p,v,tilt(q),ctl.previous,ctl.h,ctl.target.r,ctl.target.s,ctl.target.stale,q,omega,lp,lv,att,comz,comvz,rotor])
  if not np.isfinite(rows[-1]).all():stop={'profile_s':t,'reason':'NUMERICAL_UNCERTAIN'};break
  if tilt(q)>45 or max(abs(omega))>8 or np.linalg.norm(p[:2])>10 or -p[2]>8:stop={'profile_s':t,'reason':'PREDICTED_ENVELOPE'};break
 return {'trace':np.array(rows),'native_us':np.array(nt),'stop':stop,'target_events':ctl.target.events,'kind':'M5','status':'SOURCE_VERTICAL_COM_WITH_INHERITED_M4_CLOSURES','height_modelled':True,'certified_actual_coverage':False,'scope':'source gravity/thrust/axis drag, direct past COM H/W and origin velocity geometry; inherited empirical M4 horizontal/angular and nominal cache/schedule; initial LP-physical vertical offsets held, no future resets or fitting'}

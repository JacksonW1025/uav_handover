"""ONE retrospective candidate M14 and fixed geometry-only control G.
Only sanitized initial state/plan and fixed weights/coefficients enter forecast.
Vertical observer is a causal complementary APPROXIMATION, not reconstructed EKF.
"""
import numpy as np
from p11.models import assert_input,plant,tilt,speeds,reference,R
from p12.state import Controller
from p12.execution import step as motor_step
from p13.physical_model import pos,mass

BODY_LEVER=np.array([0.,0.,.00186913101803548])

def body_point(z,w,q,omega):
 return z+(R(q)@BODY_LEVER)[2], w+(R(q)@np.cross(omega,BODY_LEVER))[2]

def observer_step(z,w,body_z,body_w,previous_body_w,origin,dt=.004,tau=.25):
 # Integrate predicted body velocity increments, then relax velocity tracking
 # error and position tracking error. No future sensor/EKF correction supplied.
 rho=np.exp(-dt/tau)
 wn=body_w+rho*(w-previous_body_w)
 zn=body_z+origin+rho*(z+dt*(w+wn)/2-body_z-origin)
 return zn,wn

def forecast(doc,model,P,kind='M14'):
 if kind not in ['M14','G']:raise ValueError(kind)
 assert_input(doc);ini=doc['initial'];plan=doc['plan'];dt=.004
 p=np.array(ini['position']);v=np.array(ini['velocity']);q=np.array(ini['attitude']);omega=np.array(ini['omega'])
 lp=p.copy();lv=v.copy();att=q.copy();ctl=Controller(ini,plan['p12_repair'],plan['p12_phase'])
 rotor=np.array(ini['rotor_filter']);pending=np.array(ini['pending_command']);comz=ini['physical_COM_p'][2];comvz=ini['physical_COM_v'][2]
 # Actual physical initial orientation belongs to its own time/frame; do not
 # silently use LP attitude for the initial physical body-point map.
 bz0,bw0=body_point(comz,comvz,np.array(ini['physical_q']),np.array(ini['physical_omega']))
 origin=p[2]-bz0;vb=v[2]-bw0;last_body_w=bw0
 t0=ini['profile_s'];sample=ini['sample_us'];native=ini['native_us'];last_send=-1e30
 table=np.asarray(plan['profile']['table']);rows=[];nt=[];stop=None
 for k in range(int(np.ceil((plan['horizon_profile_s']-t0)/dt))+1):
  t=t0+k*dt;st=sample+4000*k;now=native+4000*k;nt.append(now)
  if k:
   oldq=q.copy();M=R(q);axis=M[:,2];vel=np.r_[v[:2],comvz]
   linkv=vel+np.cross(omega,pos)@M.T;perp=linkv-np.outer(linkv@axis,axis)
   drag=(-abs(rotor)[:,None]*8.06428e-5*perp).sum(axis=0)
   az=9.8-axis[2]*8.54858e-6*np.sum(rotor**2)/mass+drag[2]/mass
   comvz+=dt*az;comz+=dt*comvz
   oldz,oldv=p[2],v[2]
   p,v,q,omega,_=plant(p,v,q,omega,rotor,model)
   bz,bw=body_point(comz,comvz,q,omega)
   if kind=='G':p[2]=bz+origin;v[2]=bw+vb
   else:p[2],v[2]=observer_step(oldz,oldv,bz,bw,last_body_w,origin)
   last_body_w=bw;rotor=motor_step(rotor,pending,dt)
   if (st-ini['lp_phase_us'])%8000==0:lp=p.copy();lv=v.copy()
   att=oldq;inside=any(a<=t<b for a,b in plan['windows_profile_s']);msg=None
   if 0<=t<plan['stream_end_profile_s'] and not inside and t-last_send>=plan['publish_period_s']-1e-10:
    msg=reference(t,plan['profile'],table);last_send=t
   ctl.target.repair=plan['p12_repair'] and st>=plan.get('repair_not_before_sample_us',0)
   action,info=ctl.step(now,st,lp,lv,att,omega,msg,P)
   if action is not None:pending=speeds(action)
  rows.append(np.r_[t,p,v,tilt(q),ctl.previous,ctl.h,ctl.target.r,ctl.target.s,ctl.target.stale,q,omega,lp,lv,att,comz,comvz,rotor])
  if not np.isfinite(rows[-1]).all():stop={'profile_s':t,'reason':'NUMERICAL_UNCERTAIN'};break
  if tilt(q)>45 or max(abs(omega))>8 or np.linalg.norm(p[:2])>10 or -p[2]>8:
   stop={'profile_s':t,'reason':'PREDICTED_ENVELOPE'};break
 return {'trace':np.array(rows),'native_us':np.array(nt),'stop':stop,'target_events':ctl.target.events,'kind':kind,
  'height_modelled':True,'retrospective':True,'certified_actual_coverage':False,
  'scope':'body-point source geometry; causal approximate vertical observer M14 or constant-offset G; inherited M4 angular/horizontal; nominal future clocks; no future injection'}

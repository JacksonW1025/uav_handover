"""Offline float64 transcription of frozen P11 M2 and RAPTOR policy.
No simulator, Thor access, fitting, or network access in this module.
Reverse autograd is the discrete adjoint of the unrolled equations.
"""
from pathlib import Path
import json
import numpy as np
import torch
torch.set_default_dtype(torch.float64)
torch.set_num_threads(1)
ROOT=Path(__file__).resolve().parent
BASE=ROOT/'upstream/data/p11-20261025-formal'
P={k:torch.tensor(v) for k,v in dict(np.load(BASE/'models/policy.npz')).items()}
M=json.loads((BASE/'models/models.json').read_text())['M2']
DT=.004
def T(x):return torch.as_tensor(x,dtype=torch.float64)
def R(q):
 w,x,y,z=q
 return torch.stack([1-2*y*y-2*z*z,2*x*y-2*w*z,2*x*z+2*w*y,2*x*y+2*w*z,1-2*x*x-2*z*z,2*y*z-2*w*x,2*x*z-2*w*y,2*y*z+2*w*x,1-2*x*x-2*y*y]).reshape(3,3)
def mul(a,b):
 w,x,y,z=a;v,p,q,r=b
 return torch.stack([w*v-x*p-y*q-z*r,w*p+x*v+y*r-z*q,w*q-x*r+y*v+z*p,w*r+x*q-y*p+z*v])
def inputs(p,v,q,w,r,s,yaw):
 c=torch.cos(yaw);z=torch.sin(yaw);zero=T(0.);one=T(1.)
 frame=torch.stack([c,z,zero,z,-c,zero,zero,zero,-one]).reshape(3,3)
 qr=q*T([1,1,-1,-1]);qc=torch.stack([torch.cos(yaw/2),zero,zero,torch.sin(yaw/2)])
 return torch.cat([(frame@(p-r)).clamp(-.5,.5),R(mul(qc,qr)).flatten(),(frame@(v-s)).clamp(-1,1),w*T([1,-1,-1])])
def net(h,x):
 e=torch.relu(P['W0']@x+P['b0']);gi=P['Wi']@e+P['bi'];gh=P['Wh']@h+P['bh']
 r=torch.sigmoid(gi[:16]+gh[:16]);z=torch.sigmoid(gi[16:32]+gh[16:32]);n=torch.tanh(gi[32:]+r*gh[32:]);hh=(1-z)*n+z*h
 return hh,(P['W2']@hh+P['b2']).clamp(-1,1)
def speeds(a):return 150+425*(a[[0,2,3,1]]+1)
def motor(rot,command):return command+(rot-command)*torch.exp(-DT/torch.where(command>rot,.0125,.025))
def acceleration(v,q,w,rot):
 u=rot*rot/1e6
 diff=torch.stack([-u[0]+u[1]+u[2]-u[3],u[0]-u[1]+u[2]-u[3],u[0]+u[1]-u[2]-u[3]])
 return T([0,0,9.80665])-R(q)[:,2]*M['thrust']*u.sum()-T(M['drag'])*v,T(M['torque'])*diff-T(M['angular_drag'])*w
def plant(p,v,q,w,rot,bias):
 a,dw=acceleration(v,q,w,rot);a=a+bias[:3];dw=dw+bias[3:]
 vv=v+DT*a;pp=p+DT*(v+vv)/2;ww=w+DT*dw
 a,b,c,d=q;x,y,z=(w+ww)/2
 dq=.5*torch.stack([-b*x-c*y-d*z,a*x+c*z-d*y,a*y+d*x-b*z,a*z+b*y-c*x]);qq=q+DT*dq;qq=qq/torch.linalg.vector_norm(qq)
 return pp,vv,qq,ww
def tilt(q):return torch.acos(R(q)[2,2].clamp(-1+1e-12,1-1e-12))*180/np.pi
def yaw(q):return torch.atan2(2*(q[1]*q[2]+q[0]*q[3]),1-2*(q[2]**2+q[3]**2))
def load_drop(rep,variant):
 path=BASE/f'F4-r{rep}-{variant}'
 d=dict(np.load(path/'packed/measurement.npz'))
 doc=json.loads((path/'packed/prediction-input.json').read_text())
 edges=np.flatnonzero((d['stale'][1:] == 1)&(d['stale'][:-1]==0))+1
 i=int(next(k for k in edges if d['profile_s'][k]>12))
 return d,doc,i
def rotor_at(d,i):
 rot=speeds(T(d['action'][max(0,i-1000)]))
 for k in range(max(0,i-1000),i):rot=motor(rot,speeds(T(d['action'][k])))
 return rot
def drop(rep=1,variant='AB',alpha=None,bias=None,horizon=1.8,offset=0.,capture_log=False):
 d,doc,i=load_drop(rep,variant);plan=doc['plan'];profile=plan['profile'];tab=np.array(profile['table'])
 alpha=T(0. if variant=='AB' else 1.) if alpha is None else alpha
 bias=T(np.zeros(6)) if bias is None else bias
 p,v,q,w=[T(d[k][i]) for k in ['position','velocity','attitude','omega']]
 lp=p;lv=v;att=q;h=T(d['h_before'][i]);hist=T(d['input'][i,18:]);previous=T(d['previous'][i]);rot=rotor_at(d,i)
 # Exact observed entry snapshot; future sensor/controller schedule is nominal.
 t0=float(d['profile_s'][i]);native=int(d['sample_us'][i]);commit0=bool(d['committed'][i]);lp_phase=int(d['lp_sample'][i])%8000
 cp=p;cv=v;cy=yaw(q);capt=0.;stale=True;last_send=t0-.204;last_read=t0-.204
 r=cp;s=T([0.,0.,0.]);target_yaw=cy
 rows=[];captures=[]
 for k in range(round(horizon/DT)+1):
  t=t0+k*DT;st=native+k*4000
  if k:
   oldq=q;p,v,q,w=plant(p,v,q,w,rot,bias);rot=motor(rot,speeds(previous));att=oldq
   if st%8000==lp_phase:lp=p;lv=v
   inside=any(a+offset<=t<b+offset for a,b in plan['windows_profile_s'])
   send=not inside and t<plan['stream_end_profile_s'] and t-last_send>=.02-1e-10
   if send:
    j=min(len(tab)-1,max(0,int(np.floor((t-profile['table_t0_s'])/DT+1e-8))))
    r=T(tab[j,:3]);s=T(tab[j,3:6]);target_yaw=T(profile['yaw']);last_send=t;last_read=t
   new_stale=t-last_read>.2000001
   if new_stale and not stale:cp=lp;cv=lv;cy=yaw(att);capt=k*DT
   stale=new_stale
  if stale:
   elapsed=k*DT-capt;speed=torch.linalg.vector_norm(cv[:2]);direction=cv[:2]/speed.clamp_min(1e-12);tau=torch.minimum(T(elapsed),speed/2.)
   rr=cp[:2]+alpha*direction*(speed*tau-tau*tau)
   ss=alpha*direction*torch.relu(speed-2*elapsed)
   r=torch.cat([rr,cp[2:]]);s=torch.cat([ss,T([0.])]);target_yaw=cy
  xx=inputs(lp,lv,att,w,r,s,target_yaw)
  if k:hist=(hist+previous)/2 if (commit0==(k%2==0)) else previous
  hh,action=net(h,torch.cat([xx,hist]));commit=(commit0==(k%2==0))
  if commit:h=hh
  previous=action
  rows.append(torch.cat([p,v,q,w,action,tilt(q).reshape(1)]))
  if capture_log:captures.append((t,stale,float(alpha.detach()),r.detach().numpy(),s.detach().numpy()))
 out=torch.stack(rows);end=i+len(rows)
 measured=np.column_stack([d['position'][i:end],d['velocity'][i:end],d['attitude'][i:end],d['omega'][i:end],d['action'][i:end],np.degrees(np.arccos(np.clip(1-2*np.sum(d['attitude'][i:end,1:3]**2,axis=1),-1,1)))])
 # Fixed 1.8s local window: peak tilt and altitude loss are separate objectives.
 J=torch.stack([out[:,-1].max(),(out[:,2]-out[0,2]).max()])
 actual=np.array([measured[:,-1].max(),np.max(measured[:,2]-measured[0,2])])
 return J,actual,out,measured,dict(case=f'F4-r{rep}-{variant}',start_index=i,profile_start=t0,initial_speed=float(torch.linalg.vector_norm(T(d['velocity'][i,:2]))),horizon=horizon,captures=captures)

from pathlib import Path
import copy,sys,json,numpy as np
ROOT=Path(__file__).resolve().parent
OLD=ROOT.parent/'model-search-20261028'
sys.path.insert(0,str(OLD))
import h2_preflight as reference
from p12.state import Controller
from p11.state import f32
from p11.models import speeds,tilt
from p12.execution import step as motor_step
DT=.004;G=9.80665

def rotation(q):
    w,x,y,z=q
    return np.array([[1-2*(y*y+z*z),2*(x*y-w*z),2*(x*z+w*y)],
                     [2*(x*y+w*z),1-2*(x*x+z*z),2*(y*z-w*x)],
                     [2*(x*z-w*y),2*(y*z+w*x),1-2*(x*x+y*y)]])

def plant(p,v,q,w,rot,model):
    u=rot**2/1e6
    torque=np.array([-u[0]+u[1]+u[2]-u[3],u[0]-u[1]+u[2]-u[3],u[0]+u[1]-u[2]-u[3]])
    acc=np.array([0.,0.,G])-model['thrust']*u.sum()*rotation(q)[:,2]-np.array(model['drag'])*v
    ww=w+DT*(np.array(model['torque'])*torque-np.array(model['angular_drag'])*w)
    om=.5*(w+ww);q0=q[0];qv=q[1:]
    dq=.5*np.r_[-qv@om,q0*om+np.cross(qv,om)]
    qq=q+DT*dq;qq/=np.linalg.norm(qq)
    vv=v+DT*acc;pp=p+.5*DT*(v+vv)
    return pp,vv,qq,ww,acc

class HeldTarget:
    def __init__(self,target):
        self.__dict__=copy.deepcopy(target.__dict__)
    def step(self,now,sample,p,v,q,message=None,activation=False):
        if message is not None:
            self.r=f32(message[0]);self.s=f32(message[1]);self.yaw=float(np.float32(message[2]));self.last_read=int(now)
        self.stale=self.last_read is None or int(now)-self.last_read>200000
        return self.r.copy(),self.s.copy(),self.yaw,self.stale

def sanitize(r):
    return {k:copy.deepcopy(r[k]) for k in ['id','family','arm','block','branch','gap_s','phase','initial']}

def forecast(inp,model,variant='full',capture=False):
    # No outcome fields are accepted by the prediction API.
    assert set(inp)==set(['id','family','arm','block','branch','gap_s','phase','initial'])
    init=inp['initial'];doc=reference.DOCS[inp['family']];profile=doc['plan']['profile'];table=np.array(profile['table']);yaw=profile['yaw']
    t0=init['profile_s'];sample0=init['sample_us'];native0=init['native_us'];state=lambda key:np.array(init[key],float)
    p=state('position');v=state('velocity');q=state('attitude');q/=np.linalg.norm(q);w=state('omega');lp=p.copy();lv=v.copy();aq=q.copy()
    ctl=Controller(init,inp['branch']=='REPAIR',inp['phase'])
    if variant.startswith('hold_target'):ctl.target=HeldTarget(ctl.target)
    f=state('rotor_filter');pending=state('pending_command');lp_phase=init['lp_phase_us'];H0=-p[2];D=0.
    Bstart=13.615+inp['gap_s'];Bend=Bstart+.36;end=doc['plan']['horizon_profile_s'];streamend=doc['plan']['stream_end_profile_s']
    trace=[];branches=[];stale=True;stop=None;lastsend=-1e30;has_B=inp['branch'] in ['B','AB','REPAIR'];has_A=inp['branch'] in ['A','AB','REPAIR'];seam=None;seam_done=False
    donor=None
    if variant in ['no_carry','hold_target_no_carry','no_neural_carry','no_physical_carry']:
        nominal=copy.deepcopy(inp);nominal['branch']='B'
        donor=forecast(nominal,model,'hold_target' if variant.startswith('hold_target') else 'full',True)[2]
        assert donor is not None
    for k in range(int(np.ceil((end-t0)/DT))+1):
        t=t0+k*DT;sample=sample0+4000*k;native=native0+4000*k
        if k and not seam_done and t>=Bstart:
            seam_done=True
            if donor is not None:
                if variant in ['no_carry','hold_target_no_carry','no_physical_carry']:
                    p,v,q,w,lp,lv,aq,f,pending=[x.copy() for x in donor['physical']]
                if variant in ['no_carry','hold_target_no_carry']:
                    ctl=copy.deepcopy(donor['controller']);lastsend=donor['lastsend'];stale=donor['stale']
                if variant=='no_neural_carry':
                    for key in ['h','previous','mean','count']:setattr(ctl,key,copy.deepcopy(getattr(donor['controller'],key)))
            seam=dict(k=k,t=t,state_time=t-DT,physical=[x.copy() for x in [p,v,q,w,lp,lv,aq,f,pending]],controller=copy.deepcopy(ctl),lastsend=lastsend,stale=stale)
            if capture:return None,None,seam
        if k:
            oldq=q.copy();p,v,q,w,_=plant(p,v,q,w,f,model);f=motor_step(f,pending,DT)
            if sample%8000==lp_phase:lp=p.copy();lv=v.copy()
            aq=oldq;message=None
            if 0<=t<streamend and not ((has_A and 13.255<=t<13.615) or (has_B and Bstart<=t<Bend)) and t-lastsend>=.02-1e-10:
                j=min(len(table)-1,max(0,int(np.floor((t-profile['table_t0_s'])/DT+1e-8))));message=(table[j,:3],table[j,3:],yaw);lastsend=t
            action,info=ctl.step(native,sample,lp,lv,aq,w,message,reference.P)
            if action is not None:pending=speeds(action)
            if ctl.target.stale!=stale:branches.append(dict(t=t,stale=bool(ctl.target.stale)));stale=ctl.target.stale
        L=lp[2]+H0;D=max(D,L);th=tilt(aq);trace.append([t,L,D,lv[2],th,*lp,*lv])
        if not np.isfinite(np.r_[p,v,q,w]).all() or np.linalg.norm(v)>15 or max(abs(w))>15 or th>85:
            stop='DOMAIN_EXIT';break
    z=np.array(trace);scope=z[:,0]>=doc['plan']['common_first_gap_profile_s'];baseline=float(np.interp(doc['plan']['common_first_gap_profile_s'],z[:,0],z[:,7]));D=max(0.,float(z[scope,7].max()-baseline))
    return dict(id=inp['id'],family=inp['family'],arm=inp['arm'],block=inp['block'],prediction=D,predicted_tilt=float(z[scope,4].max()),stop=stop,branches=branches,simulated_until=float(z[-1,0]),seam_time=None if seam is None else seam['t']),z,seam

def vec(m):return np.r_[m['thrust'],m['drag'],m['torque'],m['angular_drag']]
def model(x):return dict(kind='M2',thrust=float(x[0]),drag=x[1:4].tolist(),torque=x[4:7].tolist(),angular_drag=x[7:10].tolist(),execution_state='4 asymmetric rotor states tau_up.0125/down.025')

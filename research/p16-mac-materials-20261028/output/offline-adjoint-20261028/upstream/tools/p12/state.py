"""P12 target branch and explicit call/commit state; no log access."""
import numpy as np
from p11.state import Target
from p11.observe import inputs,network
from p12.execution import step as motor_step


class EventTarget(Target):
    def __init__(self,repair=False,decel=2.):
        super().__init__(0,decel,0.);self.repair=repair;self.external_seen=False

    def step(self,now,sample,p,v,q,message=None,activation=False):
        if activation:self.external_seen=False
        self.mode=2 if self.repair and self.external_seen and not activation else 0
        result=super().step(now,sample,p,v,q,message,activation)
        if message is not None:self.external_seen=True
        return result


class Controller:
    def __init__(self,initial,repair=False,phase=0):
        self.h=np.array(initial['h']);self.previous=np.array(initial['previous'])
        self.mean=np.array(initial['history']);self.count=int(initial['history_count'])
        self.index=int(initial['call_index']);self.force_sync=int(initial['force_sync'])
        if self.force_sync!=2:raise ValueError('only validated source force_sync=2 admitted')
        self.last_sample=int(initial['sample_us']);self.phase=phase;self.pending=None
        self.target=EventTarget(repair);self.target.external_seen=bool(initial['external_seen'])
        self.target.r=np.array(initial['target_p']);self.target.s=np.array(initial['target_v'])
        self.target.yaw=float(initial['target_yaw']);self.target.stale=bool(initial['stale'])
        self.target.last_read=initial['last_read_us']
        if np.linalg.norm(initial['target_v'])>1e-5:raise ValueError('initial moving profile not supported; do not zero it')

    def step(self,native,sample,p,v,q,omega,message,P,ablation=None):
        commit=self.index%self.force_sync==0
        if message is not None:self.pending=message
        allowed=self.phase==0 or (self.phase==1 and commit) or (self.phase==2 and not commit)
        delivered=self.pending if allowed else None
        if delivered is not None:self.pending=None
        # True target update/guard precedes duplicate rejection.
        r,s,yaw,stale=self.target.step(native,sample,p,v,q,delivered)
        if sample<=self.last_sample:return None,{'rejected':True,'stale':stale}
        self.last_sample=sample
        self.mean=(self.mean*self.count+self.previous)/(self.count+1)
        x=np.r_[inputs(p,v,q,omega,r,s,yaw),self.mean]
        if ablation=='no_history':
            self.h[:]=0;x[18:]=0
        h,raw,a=network(P,self.h,x)
        if commit:self.h=h
        self.count=0 if commit else self.count+1;self.index+=1;self.previous=a
        return a,{'rejected':False,'commit':commit,'stale':stale,'target_p':r,'target_v':s,'input':x}

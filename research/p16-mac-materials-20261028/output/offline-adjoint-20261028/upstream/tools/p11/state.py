#!/usr/bin/env python3
"""Causal target/capture/recovery state. No log access in Target.step().

Equations are independently transcribed from TargetProfile/RecoveryTarget.hpp;
P11 checks every observed target and strict stale transition on development data.
"""
import argparse
import json
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from p9_model import sha, write


def f32(x):return np.asarray(x,dtype=np.float32).astype(float)


def yaw_of(q):
    q=np.asarray(q,dtype=np.float32)
    return float(np.arctan2(np.float32(2)*(q[1]*q[2]+q[0]*q[3]),np.float32(1)-np.float32(2)*(q[2]*q[2]+q[3]*q[3])))


class Target:
    def __init__(self,mode=0,decel=2.,recovery=0.):
        self.mode=mode;self.decel=float(np.float32(decel));self.rate=float(np.float32(recovery))
        self.last_read=None;self.stale=True;self.armed=False;self.profile=None;self.recovery=None
        self.r=None;self.s=None;self.yaw=None;self.events=[]

    def step(self,now,sample,p,v,q,message=None,activation=False):
        p=f32(p);v=f32(v);was=self.stale
        if activation:self.last_read=None
        if message is not None:
            self.r=f32(message[0]);self.s=f32(message[1]);self.yaw=float(np.float32(message[2]));self.last_read=int(now)
        stale=self.last_read is None or int(now)-self.last_read>200000
        capture=stale and (not was or activation or self.r is None)
        if capture:
            self.r=p.copy();self.s=np.zeros(3);self.yaw=yaw_of(q);self.profile=None
            if self.mode==2 or self.mode==1 and activation:
                speed=float(np.hypot(v[0],v[1]));direction=v[:2]/speed if speed>0 else np.zeros(2)
                self.profile=(sample,p.copy(),speed,direction)
            self.events.append({'sample_us':int(sample),'kind':'CAPTURE','activation':activation})
        if self.profile is not None:
            if not stale:self.profile=None
            else:
                start,pos,speed,direction=self.profile;t=max(0.,(int(sample)-start)*1e-6);tau=min(t,speed/self.decel)
                self.r=pos.copy();self.r[:2]=f32(pos[:2]+direction*(speed*tau-.5*self.decel*tau*tau))
                self.s=np.r_[f32(direction*max(0.,speed-self.decel*t)),0.]
        # Native transition BEFORE observe/apply. New timeout ends ongoing recovery.
        if stale:
            if activation:self.armed=False
            elif not was:self.armed=True
            if self.recovery is not None:self.events.append({'sample_us':int(sample),'kind':'END_STALE'})
            self.recovery=None
        elif was and self.armed:
            self.armed=False
            if self.rate>0:
                self.recovery=[int(sample),p[:2].copy(),v[:2].copy()]
                self.events.append({'sample_us':int(sample),'kind':'START'})
        r=self.r.copy();s=self.s.copy()
        if self.recovery is not None:
            last,pr,vr=self.recovery;dt=min(.05,max(0.,(int(sample)-last)*1e-6))
            acc=2.25*(self.r[:2]-pr)+3*(self.s[:2]-vr);norm=np.linalg.norm(acc)
            if norm>self.rate:acc*=self.rate/norm
            vr=vr+acc*dt;pr=pr+vr*dt;self.recovery=[int(sample),pr,vr]
            if np.linalg.norm(self.r[:2]-pr)<.02 and np.linalg.norm(self.s[:2]-vr)<.02:
                self.recovery=None;self.events.append({'sample_us':int(sample),'kind':'END_CONVERGED'})
            else:r[:2]=f32(pr);s[:2]=f32(vr)
        self.stale=stale
        return r,s,self.yaw,stale


def validate(sync,config,out):
    out.mkdir(parents=True,exist_ok=False);d=dict(np.load(sync));cfg=json.loads(config.read_text())
    t=cfg['p2_treatment_parameters'];state=Target(t['rtgt'],t['rtdec'],t['rrec']);pred=[];max_r=0.;max_s=0.;max_yaw=0.;wrong_stale=0
    for i in range(len(d['sample_us'])):
        message=(d['external_p'][i],d['external_v'][i],d['external_yaw'][i]) if d['read_valid'][i] else None
        r,s,y,stale=state.step(int(d['native_us'][i]),int(d['sample_us'][i]),d['position'][i],d['velocity'][i],d['attitude'][i],message,activation=i==0)
        max_r=max(max_r,float(np.max(np.abs(r-d['target_p'][i]))));max_s=max(max_s,float(np.max(np.abs(s-d['target_v'][i]))))
        max_yaw=max(max_yaw,abs(float(np.arctan2(np.sin(y-d['target_yaw'][i]),np.cos(y-d['target_yaw'][i])))))
        wrong_stale+=stale!=bool(d['stale'][i]);pred.append(np.r_[r,s,y])
    result={'schema':'p11-target-replay-1','rows':len(pred),'max_position_m':max_r,'max_velocity_m_s':max_s,'max_yaw_rad':max_yaw,
        'stale_mismatch':int(wrong_stale),'events':state.events,'tolerance':1e-5,
        'inputs':'actual exogenous observed p/v/q and actual valid raw messages/read times; capture/recovery evolve independently; known-input replay',
        'status':'PASS' if max(max_r,max_s,max_yaw)<1e-5 and wrong_stale==0 else 'FAIL',
        'hashes':{str(sync):sha(sync),str(config):sha(config),'TargetProfile.hpp':sha(ROOT/'research/state/TargetProfile.hpp'),
                  'RecoveryTarget.hpp':sha(ROOT/'research/state/RecoveryTarget.hpp')}}
    np.savez_compressed(out/'targets.npz',target=np.array(pred));write(out/'target-replay.json',result);print(json.dumps(result,ensure_ascii=False));return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('sync',type=Path);p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=validate(a.sync,a.config,a.output);raise SystemExit(0 if r['status']=='PASS' else 1)

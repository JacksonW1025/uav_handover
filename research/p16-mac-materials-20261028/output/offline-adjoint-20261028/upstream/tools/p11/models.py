#!/usr/bin/env python3
"""P11 prediction core. forecast takes a sanitized initial state, plan, and frozen model.
No log names, paths, observations, targets, actual event times or termination enter forecast.
"""
import numpy as np
from p11.state import Target
from p11.observe import inputs, network, rotation

G=9.80665
DT=.004
REMAP=[0,2,3,1]


def R(q):return rotation(q).reshape(3,3)


def qstep(q,omega,dt=DT):
    w,x,y,z=q;u,v,t=omega
    dq=.5*np.array([-x*u-y*v-z*t,w*u+y*t-z*v,w*v+z*u-x*t,w*t+x*v-y*u])
    q=q+dt*dq
    return q/np.linalg.norm(q)


def tilt(q):return float(np.degrees(np.arccos(np.clip(R(q)[2,2],-1,1))))


def speeds(a):return 150.+850.*((np.asarray(a)[REMAP]+1.)/2.)


def motor_step(rot,command,dt=DT):
    tau=np.where(command>rot,.0125,.025)
    return command+(rot-command)*np.exp(-dt/tau)


def features(rot):
    u=rot*rot/1e6
    return u.sum(),np.array([-u[0]+u[1]+u[2]-u[3],u[0]-u[1]+u[2]-u[3],u[0]+u[1]-u[2]-u[3]])


def plant(p,v,q,omega,rot,model):
    collective,diff=features(rot)
    acc=np.array([0.,0.,G])-R(q)[:,2]*model['thrust']*collective-np.array(model['drag'])*v
    angular=np.array(model['torque'])*diff-np.array(model['angular_drag'])*omega
    vv=v+DT*acc;pp=p+DT*(v+vv)/2
    ww=omega+DT*angular;qq=qstep(q,(omega+ww)/2)
    return pp,vv,qq,ww,acc


def reference(t,profile,table=None):
    # The ORIGINAL source p1_profile is sampled before experiments and serialized
    # into a 4ms known PLAN table, never made from actual future messages.
    if table is None:table=np.asarray(profile['table'])
    j=min(len(table)-1,max(0,int(np.floor((t-profile['table_t0_s'])/DT+1e-8))))
    return table[j,:3],table[j,3:6],float(profile['yaw'])


def assert_input(doc):
    allowed={'schema','identity','initial','plan','model_sha256','policy_sha256'}
    if set(doc)!=allowed:raise ValueError('unexpected prediction input keys')
    forbidden=['actual','measured','future','truth','termination','ulog','telemetry','events.jsonl']
    def walk(x):
        if isinstance(x,dict):
            for k,v in x.items():
                if any(f in k.lower() for f in forbidden):raise ValueError('future/log key forbidden '+k)
                walk(v)
        elif isinstance(x,list):
            for v in x:walk(v)
    walk(doc)
    if np.asarray(doc['initial']['h']).shape!=(16,):raise ValueError('initial GRU dimension')
    if np.asarray(doc['initial']['previous']).shape!=(4,):raise ValueError('initial action dimension')
    table=np.asarray(doc['plan']['profile']['table'])
    if table.ndim!=2 or table.shape[1]!=6 or not np.all(np.isfinite(table)):
        raise ValueError('reference plan table shape/finite')


def forecast(doc,model,P):
    assert_input(doc)
    init=doc['initial'];plan=doc['plan'];kind=model['kind']
    reference_table=np.asarray(plan['profile']['table'])
    p=np.array(init['position']);v=np.array(init['velocity']);q=np.array(init['attitude']);omega=np.array(init['omega'])
    lp=p.copy();lv=v.copy();att=q.copy();h=np.array(init['h']);previous=np.array(init['previous'])
    history=np.array(init['history']);count=int(init['history_count']);rot=speeds(previous);pending=rot.copy()
    target=Target(plan['treatment']['rtgt'],plan['treatment']['rtdec'],plan['treatment']['rrec'])
    target.r=np.array(init['target_p']);target.s=np.array(init['target_v']);target.yaw=init['target_yaw']
    target.stale=bool(init['stale']);target.last_read=init['last_read_us']
    # No active RTGT/recovery remains at the fixed 5s warmup endpoint. This is
    # an admission condition independently checked by the input packer.
    t0=float(init['profile_s']);sample=int(init['sample_us']);native=int(init['native_us'])
    lp_phase=int(init['lp_phase_us']);commit_phase=int(init['commit_phase_us']);last_send=-1e30
    yaw0=float(plan['profile']['yaw']);c=np.cos(yaw0);s=np.sin(yaw0);B=np.array([[c,s],[s,-c]])
    qgeo=-G*R(q)[:2,2]/R(q)[2,2];qproxy=B@qgeo
    e=B@(p[:2]-target.r[:2]);d=B@(v[:2]-target.s[:2]);queue=[np.r_[np.clip(e,-.5,.5),np.clip(d,-1,1)] for _ in range(22)]
    rows=[];stop=None
    n=int(np.ceil((plan['horizon_profile_s']-t0)/DT))+1
    for k in range(n):
        t=t0+k*DT;now=native+k*4000;st=sample+k*4000
        if k==0:
            rows.append(np.r_[t,p,v,tilt(q),previous,h,target.r,target.s,target.stale,q,omega,lp,lv,att])
            continue
        if kind!='M0':
            effective=rot if kind=='M2' else pending
            oldq=q.copy();p,v,q,omega,acc=plant(p,v,q,omega,effective,model)
            if kind=='M2':rot=motor_step(rot,pending)
            if (st-lp_phase)%8000==0:lp=p.copy();lv=v.copy()
            att=oldq
        inside=any(a<=t<b for a,b in plan['windows_profile_s'])
        message=None
        if 0.<=t<plan['stream_end_profile_s'] and not inside and (t-last_send>=plan['publish_period_s']-1e-10 or last_send<-1e20):
            message=reference(t,plan['profile'],reference_table);last_send=t
        r,sv,yaw,stale=target.step(now,st,lp,lv,att,message)
        if kind=='M0':
            e=B@(p[:2]-r[:2]);d=B@(v[:2]-sv[:2]);old=queue.pop(0)
            u=-np.array(model['kp'])*old[:2]-np.array(model['kv'])*old[2:]
            nxt=np.exp(-DT/model['tau'])*qproxy+(1-np.exp(-DT/model['tau']))*u
            vv=v.copy();vv[:2]+=DT*B.T@(qproxy+nxt)/2;pp=p.copy();pp[:2]+=DT*(v[:2]+vv[:2])/2
            queue.append(np.r_[np.clip(e,-.5,.5),np.clip(d,-1,1)]);qproxy=nxt;p=pp;v=vv;lp=p.copy();lv=v.copy()
            angle=float(np.degrees(np.arctan(np.linalg.norm(qproxy)/G)));action=np.full(4,np.nan)
        else:
            xx=inputs(lp,lv,att,omega,r,sv,yaw)
            history=(history*count+previous)/(count+1) if count else previous.copy()
            hh,raw,action=network(P,h,np.r_[xx,history])
            commit=(st-commit_phase)%8000==0
            if commit:h=hh
            count=0 if commit else count+1;previous=action
            command=speeds(action)
            pending=command
            angle=tilt(q)
        rows.append(np.r_[t,p,v,angle,action,h if kind!='M0' else np.full(16,np.nan),r,sv,stale,
            q if kind!='M0' else np.full(4,np.nan),omega if kind!='M0' else np.full(3,np.nan),lp,lv,
            att if kind!='M0' else np.full(4,np.nan)])
        if not np.all(np.isfinite(np.r_[p,v,q,omega])):
            stop={'profile_s':t,'reason':'NUMERICAL_UNCERTAIN'};break
        if angle>45 or np.max(np.abs(omega))>8 or np.linalg.norm(p[:2])>10 or -p[2]>8:
            stop={'profile_s':t,'reason':'PREDICTED_ENVELOPE','angle_deg':angle};break
    return {'trace':np.array(rows),'stop':stop,'target_events':target.events,'kind':kind,
            'initialization_only':True,'future_log_access':False,'height_modelled':kind!='M0'}

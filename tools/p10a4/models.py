"""Three bounded A4 model definitions, common native observation interface."""
import json
from pathlib import Path
import numpy as np
from data import ROOT

H=.004


def rot(x,yaw):
    x=np.asarray(x);c,s=np.cos(yaw),np.sin(yaw)
    return np.stack([c*x[...,0]+s*x[...,1],s*x[...,0]-c*x[...,1]],axis=-1)


def baseline():
    b=json.loads((ROOT/'data/p9-20261024-freeze/model.json').read_text())
    return {'name':'M0-A3-4ms','kp':b['kp'],'kv':b['kv'],'tau':b['tau_s'],'delay_steps':22,
        'plant':'q_trapezoid','yaw_transport':'fixed_origin','parameters':6,'state_dim':6,
        'provenance':'P9 fitted at20ms, predicted8ms, reused4ms by A3; no claim of parameter invariance'}


def valid_steps(a,d,start):
    good=np.asarray(a['valid'],bool).copy();good&=a['cap_valid']
    bad=np.r_[0,np.cumsum(~good)]
    k=np.arange(d,len(good)-1)
    mask=(a['t'][k]>=start)&(bad[k+2]-bad[k-d]==0)
    for off in range(d+1):mask&=(a['t'][k+1-off]-a['t'][k-off]==4000)
    return k[mask]


def predict_rows(a,m,k):
    if m.get('sensor_clocks'):
        qn=q_at(a,m,k,a['t'][k+1]-a['att_age_us'][k+1])
        lt=a['t']-a['lp_age_us'];advance=lt[k+1]-lt[k]
        if not np.isin(advance,[0,8000]).all():raise ValueError('unsupported LP clock mode')
        q0=q_at(a,m,k,lt[k]);q1=q_at(a,m,k,lt[k]+4000);q2=q_at(a,m,k,lt[k]+8000)
        if m['plant']=='q_trapezoid':
            v1=a['v'][k]+H/2*(q0+q1);p1=a['p'][k]+H/2*(a['v'][k]+v1)
            vv=v1+H/2*(q1+q2);pp=p1+H/2*(v1+vv);an=None
        else:
            aa,b,g=m['acc_ar'];aa1=aa*a['a'][k]+b*q0+g*a['v'][k]
            vv=a['v'][k]+.008/2*(a['a'][k]+aa1);pp=a['p'][k]+.008/2*(a['v'][k]+vv)
            an=np.where((advance>0)[:,None],aa1,a['a'][k])
        return np.where((advance>0)[:,None],pp,a['p'][k]),np.where((advance>0)[:,None],vv,a['v'][k]),qn,an
    d=m['delay_steps'];j=k-d;rho=np.exp(-H/m['tau'])
    if m['yaw_transport']=='fixed_origin':
        ep=rot(a['p'][j]-a['rp'][j],a['frame_yaw0'][j]);dv=rot(a['v'][j]-a['rv'][j],a['frame_yaw0'][j]);yaw=a['frame_yaw0'][k]
    else:ep=a['ep'][j];dv=a['dv'][j];yaw=a['yaw'][j]
    u=-np.array(m['kp'])*np.clip(ep,-.5,.5)-np.array(m['kv'])*np.clip(dv,-1,1)
    qn=rho*a['q'][k]+(1-rho)*rot(u,yaw)
    if m['plant']=='q_trapezoid':
        vn=a['v'][k]+H/2*(a['q'][k]+qn);pn=a['p'][k]+H/2*(a['v'][k]+vn);an=None
    else:
        alpha,beta,gamma=m['acc_ar'];an=alpha*a['a'][k]+beta*a['q'][k]+gamma*a['v'][k]
        vn=a['v'][k]+H/2*(a['a'][k]+an);pn=a['p'][k]+H/2*(a['v'][k]+vn)
    return pn,vn,qn,an


def q_features(a,k,tau,delay,target=None):
    att=a['t']-a['att_age_us'];target=att[k+1] if target is None else np.asarray(target)
    n=((target-att[k])//4000).astype(int);rho=np.exp(-H/tau)
    if np.any(n>4):raise ValueError('unsupported attitude clock horizon')
    feat=np.zeros((len(k),2,4))
    for l in range(max(0,int(n.max()))):
        active=n>l;tt=att[k]+l*4000-delay*4000
        j=np.minimum(k,np.maximum(0,np.searchsorted(a['t'],tt,side='right')-1))
        c,s=np.cos(a['yaw'][j]),np.sin(a['yaw'][j]);ep=np.clip(a['ep'][j],-.5,.5);dv=np.clip(a['dv'][j],-1,1)
        f=np.stack([np.c_[-c*ep[:,0],-s*ep[:,0]],np.c_[-s*ep[:,1],c*ep[:,1]],
                    np.c_[-c*dv[:,0],-s*dv[:,0]],np.c_[-s*dv[:,1],c*dv[:,1]]],axis=-1)
        feat+=f*((1-rho)*rho**np.maximum(n-l-1,0)*active)[:,None,None]
    return rho**np.maximum(n,0),feat


def q_at(a,m,k,target):
    att=a['t']-a['att_age_us'];target=np.asarray(target);past=target<=att[k]
    hi=np.minimum(k,np.maximum(0,np.searchsorted(att,target,side='left')))
    lo=np.minimum(k,np.maximum(0,np.searchsorted(att,target,side='right')-1))
    den=att[hi]-att[lo];f=np.divide(target-att[lo],den,out=np.zeros(len(k),float),where=den!=0)
    observed=a['q'][lo]+np.clip(f,0,1)[:,None]*(a['q'][hi]-a['q'][lo])
    power,features=q_features(a,k,m['tau'],m['delay_steps'],target)
    coeff=np.array([m['kp'][0],m['kp'][1],m['kv'][0],m['kv'][1]])
    predicted=power[:,None]*a['q'][k]+np.einsum('nai,i->na',features,coeff)
    return np.where(past[:,None],observed,predicted)


def physical_P():
    f=json.loads((ROOT/'data/p10-20261024-a2/construction-reviewed/certificate.json').read_text())['P_integer']
    l=json.loads((ROOT/'data/p10-20261025-a3/source-08/matrix-candidate.json').read_text())['P_integer']
    return np.array(f,float)[:3,:3]/1e10,np.array(l,float)[:3,:3]/1e10


def residuals(a,m,k):
    pn,vn,qn,an=predict_rows(a,m,k)
    w=np.stack([a['p'][k+1]-pn,a['v'][k+1]-vn,a['q'][k+1]-qn],axis=1) # N x p/v/q x NED2
    wf=rot(w,a['frame_yaw0'][k,None]);pf,pl=physical_P()
    pnorm=np.sqrt(np.maximum(0,np.einsum('ni,ij,nj->n',wf[:,:,0],pf,wf[:,:,0])+np.einsum('ni,ij,nj->n',wf[:,:,1],pl,wf[:,:,1])))
    # Auxiliary capture states: actual logged constrained reset, then exact hold.
    newcap=a['cap_sample'][k+1]!=a['cap_sample'][k]
    cp=np.where(newcap[:,None],a['p'][k+1],a['cap_p'][k]);cv=np.where(newcap[:,None],a['v'][k+1],a['cap_v'][k])
    aux=np.c_[a['cap_p'][k+1]-cp,a['cap_v'][k+1]-cv]
    complete=np.sqrt(pnorm**2+np.sum(aux**2,axis=1))
    return w,complete,aux,None if an is None else a['a'][k+1]-an


def rollout(a,m,start,length):
    if m.get('sensor_clocks'):return clock_rollout(a,m,start,length)
    end=min(len(a['t'])-1,start+length);d=m['delay_steps'];rho=np.exp(-H/m['tau'])
    p=a['p'][start].copy();v=a['v'][start].copy();q=a['q'][start].copy();acc=a['a'][start].copy()
    fixed=m['yaw_transport']=='fixed_origin';all_yaw=a['frame_yaw0'] if fixed else a['yaw']
    all_e=rot(a['p']-a['rp'],all_yaw);all_d=rot(a['v']-a['rv'],all_yaw)
    eh=[np.clip(x,-.5,.5) for x in all_e[max(0,start-d):start]]
    dh=[np.clip(x,-1,1) for x in all_d[max(0,start-d):start]]
    yh=list(a['yaw'][max(0,start-d):start]);out=[]
    for k in range(start,end+1):
        out.append(np.r_[p,v,q]);ep=rot(p-a['rp'][k],all_yaw[k]);dv=rot(v-a['rv'][k],all_yaw[k])
        eh.append(np.clip(ep,-.5,.5));dh.append(np.clip(dv,-1,1));yh.append(a['yaw'][k])
        ix=max(0,len(eh)-d-1);u=-np.array(m['kp'])*eh[ix]-np.array(m['kv'])*dh[ix]
        theta=all_yaw[k] if fixed else yh[ix]
        qn=rho*q+(1-rho)*rot(u,theta)
        if m['plant']=='q_trapezoid':vn=v+H/2*(q+qn)
        else:
            aa,b,g=m['acc_ar'];an=aa*acc+b*q+g*v;vn=v+H/2*(acc+an);acc=an
        p=p+H/2*(v+vn);v=vn;q=qn
    return np.asarray(out)


def clock_rollout(a,m,start,length):
    end=min(len(a['t'])-1,start+length);att=a['t']-a['att_age_us'];lp=a['t']-a['lp_age_us'];rho=np.exp(-H/m['tau'])
    p=a['p'][start].copy();v=a['v'][start].copy();acc=a['a'][start].copy()
    ep=[np.clip(x,-.5,.5) for x in a['ep'][:start]];dv=[np.clip(x,-1,1) for x in a['dv'][:start]]
    cache={int(att[i]):a['q'][i].copy() for i in range(max(0,start-40),start+1)}
    def qt(tt,current):
        tt=int(tt)
        if tt in cache:return cache[tt]
        keys=sorted(cache);lo=max((t for t in keys if t<=tt),default=keys[0]);hi=min((t for t in keys if t>=tt),default=None)
        if hi is not None:
            cache[tt]=cache[lo].copy() if hi==lo else cache[lo]+(tt-lo)/(hi-lo)*(cache[hi]-cache[lo]);return cache[tt]
        t=lo;q=cache[t].copy()
        while t<tt:
            j=min(current,max(0,int(np.searchsorted(a['t'],t-m['delay_steps']*4000,side='right'))-1))
            u=-np.array(m['kp'])*ep[j]-np.array(m['kv'])*dv[j]
            q=rho*q+(1-rho)*rot(u,a['yaw'][j]);t+=4000;cache[t]=q.copy()
        return q
    out=[]
    for k in range(start,end+1):
        q=qt(att[k],max(start,k-1));out.append(np.r_[p,v,q])
        ep.append(np.clip(rot(p-a['rp'][k],a['yaw'][k]),-.5,.5));dv.append(np.clip(rot(v-a['rv'][k],a['yaw'][k]),-1,1))
        if k==end:break
        if lp[k+1]>lp[k]:
            if m['plant']=='q_trapezoid':
                for t in range(int(lp[k]),int(lp[k+1]),4000):
                    q0,q1=qt(t,k),qt(t+4000,k);vn=v+H/2*(q0+q1);p=p+H/2*(v+vn);v=vn
            else:
                aa,b,g=m['acc_ar'];an=aa*acc+b*qt(lp[k],k)+g*v
                vn=v+.004*(acc+an);p=p+.004*(v+vn);v=vn;acc=an
        qt(att[k+1],k)
    return np.asarray(out)

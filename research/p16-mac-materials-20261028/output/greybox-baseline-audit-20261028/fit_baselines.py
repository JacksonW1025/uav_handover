from pathlib import Path
import json,hashlib,time,numpy as np
from scipy.optimize import lsq_linear,least_squares
from core import ROOT,OLD,rotation,model,vec,G,DT

def datasets():
    original=json.loads((OLD/'h2_strict_singles.json').read_text());data=[];manifest=[]
    for r in original['training']:
        p=OLD/'upstream/data/p11-20261025-formal'/r['id']/'packed/measurement.npz'
        sha=hashlib.sha256(p.read_bytes()).hexdigest();assert sha==r['sha256'];assert r['id'].split('-')[-1] in ['NORMAL','A','B']
        d=dict(np.load(p));d['id']=r['id'];data.append(d);manifest.append(dict(id=r['id'],sha256=sha))
    return data,manifest,original['model']

def rotors(d):
    command=150+425*(d['action'][:,[0,2,3,1]]+1);f=np.empty_like(command);f[0]=command[0]
    for k in range(1,len(f)):
        u=command[max(0,k-2)];tau=np.where(u>f[k-1],.0125,.025);f[k]=u+(f[k-1]-u)*np.exp(-DT/tau)
    return f

def fit_ee(ds):
    X=[];Y=[];WX=[];WY=[]
    for d in ds:
        f=rotors(d);u=f*f/1e6;collective=u.sum(axis=1);tau=u@np.array([[-1,1,1],[1,-1,1],[1,1,-1],[-1,-1,-1]])
        st=d['sample_us'].astype(np.int64);lp=d['lp_sample'].astype(np.int64)
        for k in np.flatnonzero(np.diff(lp)>0)+1:
            a=np.searchsorted(st,lp[k-1],side='left');b=np.searchsorted(st,lp[k],side='right')
            if a<1 or b>len(st) or b<=a:continue
            bz=rotation(d['attitude'][k-1])[:,2];force=-bz*collective[a:b].mean()
            mat=np.zeros((3,4));mat[:,0]=force;mat[:,1:]=-np.diag(d['velocity'][k-1]);X.append(mat)
            Y.append((d['velocity'][k]-d['velocity'][k-1])/((lp[k]-lp[k-1])/1e6)-[0,0,G])
        good=np.flatnonzero(np.diff(st)==4000)+1
        WX.append(np.stack([tau[good-1],-d['omega'][good-1]],axis=-1));WY.append((d['omega'][good]-d['omega'][good-1])/DT)
    X=np.concatenate(X);Y=np.concatenate(Y);WX=np.concatenate(WX);WY=np.concatenate(WY)
    p=lsq_linear(X,Y,bounds=([0]*4,[20,5,5,5]),tol=1e-12,max_iter=1000).x
    om=np.array([lsq_linear(WX[:,a],WY[:,a],bounds=([-1000,0],[1000,20]),tol=1e-12,max_iter=1000).x for a in range(3)])
    return model(np.r_[p,om[:,0],om[:,1]])

def windows(ds):
    packs=[]
    for d in ds:
        f=rotors(d);st=d['sample_us'].astype(np.int64);lp=d['lp_sample'].astype(np.int64)
        eligible=(np.flatnonzero(np.diff(lp)>0)+1)[::16];eligible=eligible[eligible+16<len(st)]
        eligible=eligible[st[eligible+16]-st[eligible]==64000]
        # Same sensor-state channel as the existing identification; no truth/COM.
        packs.append(dict(v=d['velocity'][eligible],w=d['omega'][eligible],q=d['attitude'][eligible],
            f=np.array([f[i:i+16] for i in eligible]),yv=d['velocity'][eligible+16],yw=d['omega'][eligible+16],id=d['id'],n=len(eligible)))
    return {k:np.concatenate([p[k] for p in packs]) for k in ['v','w','q','f','yv','yw']},[{k:p[k] for k in ['id','n']} for p in packs]

def response(x,wins):
    v=wins['v'].copy();w=wins['w'].copy();q=wins['q'].copy();q/=np.linalg.norm(q,axis=1)[:,None]
    for j in range(16):
        u=wins['f'][:,j]**2/1e6
        diff=u@np.array([[-1,1,1],[1,-1,1],[1,1,-1],[-1,-1,-1]])
        a,b,c,d=q.T;bz=np.stack([2*(b*d+a*c),2*(c*d-a*b),1-2*(b*b+c*c)],axis=1)
        v+=DT*(np.array([0.,0.,G])-x[0]*u.sum(axis=1)[:,None]*bz-x[1:4]*v)
        wn=w+DT*(x[4:7]*diff-x[7:10]*w);om=(w+wn)/2
        dq=.5*np.column_stack([-np.sum(q[:,1:]*om,axis=1),q[:,0,None]*om+np.cross(q[:,1:],om)])
        q+=DT*dq;q/=np.linalg.norm(q,axis=1)[:,None];w=wn
    return np.column_stack([(v-wins['yv'])/.1,(w-wins['yw'])/.2]).ravel()

def main():
    t=time.perf_counter();ds,manifest,old=datasets();ee=fit_ee(ds);wins,count=windows(ds);x0=vec(ee)
    lower=np.r_[np.zeros(4),[-1000]*3,np.zeros(3)];upper=np.r_[[20,5,5,5],[1000]*3,[20]*3]
    sol=least_squares(response,np.maximum(lower+1e-10,np.minimum(upper-1e-10,x0)),args=(wins,),bounds=(lower,upper),x_scale='jac',max_nfev=80,ftol=1e-9,xtol=1e-9,gtol=1e-8)
    out=dict(training=manifest,equation_error=ee,output_error=model(sol.x),original_parameter_max_abs=float(np.max(abs(vec(ee)-vec(old)))),
      oe_fit=dict(window_s=.064,windows=count,total_windows=len(wins['v']),initial_normalized_mse=float(np.mean(response(x0,wins)**2)),final_normalized_mse=float(np.mean(sol.fun**2)),nfev=sol.nfev,status=int(sol.status),success=bool(sol.success),message=sol.message),elapsed_s=time.perf_counter()-t)
    (ROOT/'models.json').write_text(json.dumps(out,indent=2));print(json.dumps({k:v for k,v in out.items() if k!='training'},indent=2),flush=True)
if __name__=='__main__':main()

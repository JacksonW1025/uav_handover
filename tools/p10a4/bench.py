"""Frozen A3 whole source case and A4 counterfactual repair declarations."""
import gzip,json
import sys
import numpy as np
from data import ROOT,sha
from models import rot,physical_P

N=49
def load():
    base=ROOT/'data/p10-20261025-a3/source-08'
    source_manifest=json.loads((base/'manifest.json').read_text())
    for name,digest in source_manifest['files'].items():assert sha(base/name)==digest,'A3_SOURCE_ARTIFACT_CHANGED'
    for path,digest in source_manifest['source_sha256'].items():assert sha(ROOT/path)==digest,'A3_SOURCE_DEPENDENCY_CHANGED'
    startup=json.loads((base/'startup-observation.json').read_text());cfg=json.loads((ROOT/'config/p10_a4.json').read_text())
    rows=[json.loads(l) for l in gzip.open(base/'trace.jsonl.gz','rt')]
    yaw=startup['origin_event']['yaw_rad'];origin=np.array(startup['origin_event']['origin_ned_m'][:2]);rr=[];vv=[];latest=None
    sys.path.insert(0,str(ROOT/'tools/p10a3'))
    from source import runner
    runner_object,_=runner(startup)
    motion=np.array(runner_object.pcfg['motion_axis_ned'][:2])
    intent=np.array([rot(motion*runner_object.p1_profile(r['profile_us']/1e6)[0],yaw) for r in rows])
    for row in rows:
        if row['input'][2]:latest=row['input'][10:14]
        rr.append(rot(np.array([latest[0],latest[2]])-origin,yaw));vv.append(rot([latest[1],latest[3]],yaw))
    p=np.array(startup['relative_position_flu']);v=np.array(startup['velocity_flu']);q=np.array(startup['q_flu'])
    center=np.zeros((2,N));center[:,0]=p;center[:,1]=v;center[:,2]=q
    center[:,3:47:2]=(p-rr[0])[:,None];center[:,4:47:2]=(v-vv[0])[:,None]
    generators=np.zeros((2,N,2));generators[1,0,0]=.01;generators[1,2,1]=.1;generators[1,3:47:2,0]=.01
    frozen=json.loads((ROOT/'data/p9-20261024-freeze/model.json').read_text())
    assert frozen['kp']==[8.790378768672879,9.221169165107131] and frozen['kv']==[5.453065498984149,5.868822102037157]
    return {'rows':rows,'r':np.array(rr),'s':np.array(vv),'intent':intent,'center':center,'G':generators,'yaw':yaw,'origin':origin,
        'axis':rot(json.loads((base/'source-config.json').read_text())['profile']['motion_axis_ned'][:2],yaw),'config':cfg,
        'kp':np.array([8.790378768672879,9.221169165107131]),'kv':np.array([5.453065498984149,5.868822102037157]),'P':physical_P()}


def coefficients(us,stale,cap_us,resume_us,case):
    t=max(0.,(us-cap_us)/1e6);T=case['brake_s'];alpha=case['alpha'];z=min(t,T)
    cp=np.array([1.,alpha*(z-z*z/(2*T))]);cv=np.array([0.,alpha*max(0.,1-t/T)])
    if stale:return cp,cv,0.
    if cap_us<0 or not case['resume_s'] or us-resume_us>=case['resume_s']*1e6:return np.zeros(2),np.zeros(2),1.
    u=max(0.,(us-resume_us)/1e6/case['resume_s']);beta=3*u*u-2*u*u*u
    return (1-beta)*cp,(1-beta)*cv,beta


def transition(kp,kv,rho,cp,cv,sigmas):
    A=np.zeros((N,N));A[0,0]=A[1,1]=1.;A[0,1]=.004
    z=np.zeros(N);z[2]=rho;z[45:47]=-(1-rho)*np.array([kp,kv])
    A[2]=z;A[1]+=.002*(np.eye(N)[2]+z);A[0]+=.000004*(np.eye(N)[2]+z)
    A[3,0]=sigmas[0];A[3,47:49]=-sigmas[0]*cp
    A[4,1]=sigmas[1];A[4,47:49]=-sigmas[1]*cv
    for i in range(5,47):A[i,i-2]=1.
    A[47,47]=A[48,48]=1.
    return A


def cov_map(A,S):
    # Shift rows are exact permutations; only seven rows need arithmetic.
    idx=np.r_[0,1,2,0,1,np.arange(3,45),47,48]
    special=np.array([0,1,2,3,4,47,48]);X=S[idx,:].copy();X[special]=A[special]@S
    Y=X[:,idx].copy();Y[:,special]=X@A[special].T
    return (Y+Y.T)/2

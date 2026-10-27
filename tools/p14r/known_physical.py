"""Finite observer mechanism contrasts, FUTURE ACTUAL inputs diagnostic only."""
import sys,json,time
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p14.common import write
from p14r.exact_observer import Observer
from p14r.observer import read,CORE
from p13.physics import read as phread,BODY,rot
from p13.physical_model import S,B
from p14_motion.core import LEVER
from p14_motion.analyze import angles
from p14.evaluate import stats,crossing
from p12c.features import load

def main():
 out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);results=[]
 write(out/'before-compute.json',{'variants':['future physical only','physical+actual IMU','physical+actual fusion','physical+actual IMU+fusion','physical+actual IMU+fusion+actual cache word'],'interpretation':'input substitutions locate sensitivity/implementation, not additive causal attribution or autonomous scores','limits':'protocol-v1, no time alignment fit','scope':'three valid passive records; d01 remains quarantine'})
 for number in ['d02','d03','d04','d05','d06']:
  target=next((R/'data/p14r-20261027/runs').glob('p14r-'+number+'-*'));run=target/'run';version='source-inputs-v4' if number in ['d05','d06'] else 'source-inputs-v3';doc=json.load(open(R/'data/p14r-20261027'/version/number/'input.json'));i=doc['initial'];body,_=phread(run/'gz-motor/physics-p13-body.bin',BODY,b'P13BODY1');body=body[(body['phase']==1)&(body['valid']==63)];Q=S@rot(body['base_q'])@B;quat=Rotation.from_matrix(Q).as_quat()[:,[3,0,1,2]];w=np.einsum('nji,nj->ni',Q,body['base_omega']@S.T);p=body['com_p']@S.T;v=body['com_v']@S.T;lookup={int(t):k for k,t in enumerate(body['sim_ns']//1000)};core,_=read(run/'gz-motor/observer-core.bin',CORE,b'P14RCORE',True);calc={int(r['sample_us']):r for r in core[core['kind']==1]};fusion={int(r['sample_us']):r for r in core[core['kind']==3]};d=load(run,target/'analysis-v1');indices=np.flatnonzero(d['sample_us']>i['sample_us']);cmap={int(d['sample_us'][j]):j for j in indices}
  for useIMU,useFusion,actualCache in [(False,False,False),(True,False,False),(False,True,False),(True,True,False),(True,True,True)]:
   obs=Observer(i,R/'data/p14r-20261027/offline-build-v2/libop.bin');advance,fuse=obs.op.advance,obs.op.fuse;cache={};current_sample=[obs.t]
   if actualCache:obs.lag=0
   def remember(sample):
    qq,vv,gg,_=obs.op.outputs();cache[int(sample)]=(qq.copy(),obs.op.project(gg,obs.par['LP_reference_geo']),vv.copy())
   remember(obs.t)
   if useIMU:
    def inject_IMU(t,da,dv,dt=.004):
     r=calc[t];advance(t,r['data'][64:67],r['data'][67:70],float(r['data'][70]));current_sample[0]=t;remember(t)
    obs.op.advance=inject_IMU
   if useFusion:
    def inject_fusion(t,q,v,geo,bg,ba):
     r=fusion[t];fuse(t,r['data'][64:68],r['data'][68:71],r['geo'][3:6],r['data'][74:77],r['data'][77:80]);remember(current_sample[0])
    obs.op.fuse=inject_fusion
   samples=[];values=[]
   for sample in range(i['sample_us']+4000,min(max(cmap),max(lookup))+1,4000):
    j=lookup[sample];lp,lv,q,g=obs.step(sample,p[j],v[j],quat[j],w[j])
    if sample in cmap:
     k=cmap[sample]
     if actualCache:
      at=int(d['att_sample'][k]);lt=int(d['lp_sample'][k])
      if at not in cache or lt not in cache:continue
      q=cache[at][0];lp=cache[lt][1];lv=cache[lt][2]
     samples.append(k);values.append(np.r_[lp,lv,q,g])
   obs.close();ii=np.array(samples);a=np.array(values);t=d['t'][ii];errs={'LP_p_m':np.linalg.norm(a[:,:3]-d['position'][ii],axis=1),'LP_v_m_s':np.linalg.norm(a[:,3:6]-d['velocity'][ii],axis=1),'att_deg':angles(a[:,6:10],d['attitude'][ii]),'gyro_rad_s':np.linalg.norm(a[:,10:13]-d['omega'][ii],axis=1)}
   stages={'p5s':[i['profile_s'],i['profile_s']+.5],'2s':[i['profile_s'],i['profile_s']+2],'all':[i['profile_s'],t[-1]]};row={'case':number,'actual_physical':True,'actual_future_IMU':useIMU,'actual_future_fusion':useFusion,'actual_future_cache_word':actualCache,'rows':len(t),'errors':{name:{key:stats(val[(t>=a)&(t<=b)]) for key,val in errs.items()} for name,(a,b) in stages.items()},'first':{key:crossing(t,val,L) for (key,val),L in zip(errs.items(),[.1,.15,2.5,.1])},'source_order':'source-model fixed fusion/LP cadence; actual source timestamps supplied only by explicit injection; actual controller read scheduling not reset'};write(out/number/(f'imu{int(useIMU)}-fusion{int(useFusion)}-cache{int(actualCache)}.json'),row);np.savez_compressed(out/number/(f'imu{int(useIMU)}-fusion{int(useFusion)}-cache{int(actualCache)}.npz'),t=t,values=a,**errs);results.append(row)
 write(out/'summary.json',results)
if __name__=='__main__':main()

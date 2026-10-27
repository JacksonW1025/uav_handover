"""All completed passive records: absolute-time process errors, no time fitting."""
import sys,json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p14.common import write
from p12c.features import load
from p13.physics import read,BODY,rot
from p13.physical_model import S,B
from p14_motion.analyze import angles,episodes
from p14.evaluate import stats,crossing
LIMITS={'p':.1,'v':.15,'SO3':2.5,'w':.1,'LP':.1,'LPv':.15,'att':2.5,'gyro':.1,'input':.1,'h':.5,'action':.1}
def main():
 pred,out=map(Path,sys.argv[1:]);out.mkdir(parents=True,exist_ok=False);rows=[]
 for folder in sorted(x for x in (pred/'predictions').iterdir() if x.is_dir()):
  number=folder.name;run=next((R/'data/p14r-20261027/runs').glob('p14r-'+number+'-*'));d=load(run/'run',run/'analysis-v1');v='source-inputs-v4' if number in ['d05','d06'] else 'source-inputs-v3';doc=json.load(open(R/'data/p14r-20261027'/v/number/'input.json'));start=doc['initial']['profile_s'];a,b=doc['plan']['full_source_windows_profile_s'][:2]
  body,_=read(run/'run/gz-motor/physics-p13-body.bin',BODY,b'P13BODY1');body=body[(body['phase']==1)&(body['valid']==63)];ix=np.flatnonzero(d['t']>=start);t=d['t'][ix];j=np.searchsorted(body['wall_ns'],d['run_wall_ns'][ix],side='right')-1;real=body[j];Q=S@rot(real['base_q'])@B;pq=Rotation.from_matrix(Q).as_quat()[:,[3,0,1,2]];pw=np.einsum('nji,nj->ni',Q,real['base_omega']@S.T)
  for file in sorted(folder.glob('*.npz')):
   z=np.load(file);tr=z['trace'];st=z['states'];pt=tr[:,0];valid=t<=pt[-1];tt=t[valid];ii=ix[valid]
   def ip(x):return np.column_stack([np.interp(tt,pt,x[:,k]) for k in range(x.shape[1])])
   sq=ip(st[:,6:10]);sq/=np.linalg.norm(sq,axis=1)[:,None];aq=ip(tr[:,48:52]);aq/=np.linalg.norm(aq,axis=1)[:,None];inp=ip(z['inputs']);good=np.isfinite(inp).all(axis=1)
   e={'p':np.linalg.norm(ip(st[:,:3])-real['com_p'][valid]@S.T,axis=1),'v':np.linalg.norm(ip(st[:,3:6])-real['com_v'][valid]@S.T,axis=1),'SO3':angles(sq,pq[valid]),'w':np.linalg.norm(ip(st[:,10:13])-pw[valid],axis=1),'LP':np.linalg.norm(ip(tr[:,42:45])-d['position'][ii],axis=1),'LPv':np.linalg.norm(ip(tr[:,45:48])-d['velocity'][ii],axis=1),'att':angles(aq,d['attitude'][ii]),'gyro':np.linalg.norm(ip(tr[:,39:42])-d['omega'][ii],axis=1),'input':np.linalg.norm(inp-d['input'][ii],axis=1),'h':np.linalg.norm(ip(tr[:,12:28])-d['h_after'][ii],axis=1),'action':np.linalg.norm(ip(tr[:,8:12])-d['action'][ii],axis=1)}
   windows={'p5s':[start,start+.5],'2s':[start,start+2],'hold':[a[0]+.2,a[1]],'resume_p5':[a[1],a[1]+.5],'resume_2':[a[1],a[1]+2],'all':[start,min(tt[-1],doc['plan']['horizon_profile_s'])]}
   report={'case':number,'model':file.stem,'stop':json.load(open(file.with_suffix('.json')))['stop'],'first':{k:crossing(tt[good],v[good],LIMITS[k]) for k,v in e.items()},'windows':{name:{'absolute_window':w,'errors':{k:stats(v[(tt>=w[0])&(tt<=w[1])&good]) for k,v in e.items()}} for name,w in windows.items()},'exposure':'passive diagnostic, autonomous future inputs forbidden; all retrospective','initial_state_preserved':True}
   report['clipping']={}
   for side,x,tx in [('actual',d['input'][ii],tt),('prediction',z['inputs'],pt)]:
    report['clipping'][side]={'position_axes':[episodes(tx,np.abs(x[:,k])>=.5-1e-6) for k in range(3)],'velocity_axes':[episodes(tx,np.abs(x[:,12+k])>=1-1e-6) for k in range(3)]}
   write(out/number/(file.stem+'.json'),report);rows.append(report)
 write(out/'summary.json',rows)
if __name__=='__main__':main()

"""Development-only source plant diagnostic. Known future command, no state resets."""
import json,sys,xml.etree.ElementTree as X
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p13.physics import read,BODY,ROTOR,rot
from p11.models import plant as M4plant,R as matrix,qstep,tilt
from p9_model import write
S=np.array([[0.,1.,0.],[1.,0.,0.],[0.,0.,-1.]])
B=np.diag([1.,-1.,-1.]);mass=2.0643076923076924
pos=np.array([[.174,.174,-.06],[-.174,-.174,-.06],[.174,-.174,-.06],[-.174,.174,-.06]])-np.array([0,0,-.00186913101803548]);turn=np.array([1,1,-1,-1]);Ir=2.649858234714004e-5
I=np.diag([.02166666666666667,.02166666666666667,.04])
for p in pos:I+=.016076923076923075*(np.dot(p,p)*np.eye(3)-np.outer(p,p))+np.diag([(3.8464910483993325e-7+2.6115851691700804e-5)/2]*2+[Ir])
I+=2.*(.00186913101803548**2)*np.diag([1,1,0])

def source_step(p,v,q,w,rotor,next_rotor,dt=.004):
 M=matrix(q);axis=M[:,2];link_v=v+np.cross(w,pos)@M.T
 drag=-abs(rotor)[:,None]*8.06428e-5*(link_v-np.outer(link_v@axis,axis))
 T=8.54858e-6*rotor**2;forces=-T[:,None]*axis+drag;force=forces.sum(axis=0)
 torques=np.cross(pos,forces@M).sum(axis=0);torques[2]+=np.dot(turn,T)*.016
 torques+=(-abs(rotor)[:,None]*1e-6*(link_v-np.outer(link_v@axis,axis))).sum(axis=0)@M
 # FRD spin angular momentum has the opposite sign to FLU motor turn.
 spin=np.array([0,0,-Ir*np.dot(turn,rotor)/10]);spin_rate=np.array([0,0,-Ir*np.dot(turn,next_rotor-rotor)/(10*dt)])
 dw=np.linalg.solve(I,torques-spin_rate-np.cross(w,I@w+spin))
 vv=v+dt*(np.array([0,0,9.8])+force/mass);pp=p+dt*vv;ww=w+dt*dw;qq=qstep(q,ww,dt)
 return pp,vv,qq,ww

def main(target,out):
 out.mkdir(parents=True,exist_ok=False);run=target/'run';b,_=read(run/'gz-motor/physics-p13-body.bin',BODY,b'P13BODY1');post=b[b['phase']==1];pre=b[b['phase']==0]
 ev=[json.loads(s) for s in (run/'p11-sends.jsonl').read_text().splitlines()];epoch=round(next(x['stream_t0_monotonic_s'] for x in ev if x['stream_t0_monotonic_s'] is not None)*1e9)
 doc=json.load(open(target/'analysis-v1/packed/prediction-input.json'));end=epoch+doc['plan']['nominal_horizon_profile_s']*1e9
 use=(pre['wall_ns']>=epoch)&(pre['wall_ns']<=end)&(pre['valid']==63);pre=pre[use];post=post[use];t=(pre['wall_ns'].astype(np.int64)-epoch)/1e9
 ro=[];rn=[]
 for k in range(4):
  x,_=read(run/f'gz-motor/physics-p13-rotor-{k}.bin',ROTOR,b'P13ROTR1');j=np.searchsorted(x['step'],pre['step']);ro.append(abs(x['joint'][j]*10));rn.append(x['filter_after'][j])
 ro=np.array(ro).T;rn=np.array(rn).T
 truth_q=Rotation.from_matrix(S@rot(post['base_q'])@B).as_quat()[:,[3,0,1,2]]
 initq=Rotation.from_matrix(S@rot(pre['base_q'][:1])[0]@B).as_quat()[[3,0,1,2]];init=(S@pre['com_p'][0],S@pre['com_v'][0],initq,B@matrix(initq).T@S@pre['base_omega'][0])
 # Correct world angular vector mapping: body_FRD=M_NED_FRD^T*S*omega_ENU.
 init=(*init[:3],matrix(initq).T@S@pre['base_omega'][0])
 old=json.load(open(R/'data/p12-cont-20261026-freeze/models/models.json'))['M2'];results={};arrays={'profile_s':t,'COM_position':post['com_p']@S.T,'COM_velocity':post['com_v']@S.T,'body_q':truth_q}
 for name in ['M4_physical_initial_known_rotor','source_physics_candidate_known_rotor']:
  p,v,q,w=[np.array(a).copy() for a in init];values=[];stop=None
  for k in range(len(t)):
   if name.startswith('M4'):p,v,q,w,_=M4plant(p,v,q,w,ro[k],old)
   else:p,v,q,w=source_step(p,v,q,w,ro[k],rn[k])
   values.append(np.r_[p,v,q,w,tilt(q)])
   if not np.isfinite(values[-1]).all() or tilt(q)>50 or max(abs(w))>8 or np.linalg.norm(v)>8:
    stop={'row':k,'profile_s':float(t[k]),'tilt_deg':tilt(q),'omega':w.tolist(),'reason':'declared finite diagnostic domain exit, no long-tail interpretation'};break
  values=np.array(values);n=len(values);truthp=post['com_p'][:n]@S.T;truthv=post['com_v'][:n]@S.T;theta=np.array([tilt(q0) for q0 in truth_q[:n]])
  results[name]={'rows':n,'stop':stop,'full':n==len(t),'max_position_error_m':float(np.linalg.norm(values[:,:3]-truthp,axis=1).max()),'max_velocity_error_m_s':float(np.linalg.norm(values[:,3:6]-truthv,axis=1).max()),'max_tilt_error_deg':float(abs(values[:,-1]-theta).max()),'H_end_error_m':float(-values[-1,2]+truthp[-1,2])};arrays[name]=values
 # One-step only independent reset from each real PRE state, explicitly diagnostic.
 errs=[]
 for k in range(len(t)):
  Q=Rotation.from_matrix(S@rot(pre['base_q'][k:k+1])[0]@B).as_quat()[[3,0,1,2]];p,v,q,w=source_step(S@pre['com_p'][k],S@pre['com_v'][k],Q,matrix(Q).T@S@pre['base_omega'][k],ro[k],rn[k]);errs.append(np.r_[p-S@post['com_p'][k],v-S@post['com_v'][k],tilt(q)-tilt(truth_q[k])])
 errs=np.array(errs);report={'schema':'p13-source-open-plant-1','case':target.name,'one_step_reset_diagnostic':{'position_max_m':float(np.linalg.norm(errs[:,:3],axis=1).max()),'velocity_max_m_s':float(np.linalg.norm(errs[:,3:6],axis=1).max()),'tilt_max_deg':float(abs(errs[:,-1]).max())},'open_replays':results,'source_inertia':I.tolist(),'future_known_rotor_input':True,'not_autonomous':True,'no_fit':True,'limitations':['rotor transverse inertia averaged, true anisotropy rotates','ideal rigid geometry; observed joint translation residual retained separately','actual future joint filter input supplied, no controller prediction']};write(out/'diagnostic.json',report);np.savez_compressed(out/'arrays.npz',**arrays);print(json.dumps(report))
if __name__=='__main__':main(Path(sys.argv[1]),Path(sys.argv[2]))

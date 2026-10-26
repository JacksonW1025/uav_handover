"""Post-freeze SOURCE RELATION audit, not a new candidate/forecast score.
FreeJoint6.13.2 source integration is independently accounted for. Only numerical
relation tests with actual command/state inputs, or known-future-command open
replay, are performed; frozen M3/M4/M5 and formal experiment are unchanged.
"""
import json,sys,math
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p13.physical_model import source_step,S,B,matrix
from p13.physics import read,BODY,ROTOR,rot
from p12.execution import step as filter_step
from p11.models import tilt
from p9_model import write,sha
rBC=np.array([0,0,-.00186913101803548])
def discrete(p,v,q,w,rotor,rotor_next,phase,dt=.004):
 # Angular kernel is the frozen source kernel; no fitted coefficients.
 _,euclid_v,qn,wn=source_step(p,v,q,w,rotor,rotor_next,dt,phase=phase)
 M=matrix(q);N=matrix(qn);alpha=(wn-w)/dt;ac=(euclid_v-v)/dt
 vb=v-M@np.cross(w,rBC);abase=ac-M@(np.cross(alpha,rBC)+np.cross(w,np.cross(w,rBC)))
 vbn=vb+dt*abase;vn=vbn+N@np.cross(wn,rBC)
 pn=p-M@rBC+dt*vbn+N@rBC
 return pn,vn,qn,wn

def audit(target,out,open_replay=True):
 out.mkdir(parents=True,exist_ok=False);run=target/'run';b,_=read(run/'gz-motor/physics-p13-body.bin',BODY,b'P13BODY1');pre=b[b['phase']==0];post=b[b['phase']==1];ev=[json.loads(s) for s in (run/'p11-sends.jsonl').read_text().splitlines()];epoch=round(next(s['stream_t0_monotonic_s'] for s in ev if s['stream_t0_monotonic_s'] is not None)*1e9);doc=json.load(open(target/'analysis-v1/packed/prediction-input.json'));m=json.load(open(target/'analysis-v1/measured/measurement.json'));end=doc['plan']['nominal_horizon_profile_s']
 if m.get('failure'):end=min(end,(m['failure']['monotonic_ns']-epoch)/1e9)
 use=(pre['wall_ns']>=epoch)&(pre['wall_ns']<=epoch+end*1e9)&(pre['valid']==63)&(post['valid']==63);pre=pre[use];post=post[use];t=(pre['wall_ns'].astype(np.int64)-epoch)/1e9;rotors=[]
 for k in range(4):
  x,_=read(run/f'gz-motor/physics-p13-rotor-{k}.bin',ROTOR,b'P13ROTR1');j=np.searchsorted(x['step'],pre['step']);assert np.array_equal(x['step'][j],pre['step']);rotors.append(x[j])
 Q=S@rot(pre['base_q'])@B;N=S@rot(post['base_q'])@B;qu=Rotation.from_matrix(Q).as_quat()[:,[3,0,1,2]];qn=Rotation.from_matrix(N).as_quat()[:,[3,0,1,2]];p=pre['com_p']@S.T;v=pre['com_v']@S.T;w=np.einsum('nji,nj->ni',Q,pre['base_omega']@S.T);truthp=post['com_p']@S.T;truthv=post['com_v']@S.T;truthw=np.einsum('nji,nj->ni',N,post['base_omega']@S.T)
 phi=[]
 for x in rotors:
  rel=np.transpose(Q,(0,2,1))@(S@rot(x['q'])@B);phi.append(np.arctan2(rel[:,1,0],rel[:,0,0]))
 phi=np.array(phi).T;rs=np.array([abs(x['joint']*10) for x in rotors]).T;commands=np.array([x['command'] for x in rotors]).T;filters=np.array([x['filter_before'] for x in rotors]).T
 errors=[]
 for j in range(len(t)):
  rn=filter_step(filters[j],commands[j],.004);pp,vv,qq,ww=discrete(p[j],v[j],qu[j],w[j],rs[j],rn,phi[j].copy());qe=(Rotation.from_quat(qq[[1,2,3,0]]).inv()*Rotation.from_quat(qn[j,[1,2,3,0]])).magnitude();errors.append(np.r_[pp-truthp[j],vv-truthv[j],ww-truthw[j],np.degrees(qe)])
 errors=np.array(errors);one={'rows':len(t),'COM_position_max_m':float(np.linalg.norm(errors[:,:3],axis=1).max()),'COM_velocity_max_m_s':float(np.linalg.norm(errors[:,3:6],axis=1).max()),'body_omega_max_rad_s':float(np.max(abs(errors[:,6:9]))),'body_SO3_max_deg':float(np.max(abs(errors[:,9]))),'scope':'each actual PRE physical state and selected command supplied; no autonomous claim'}
 opened=None;openarr=[]
 if open_replay:
  pc,vc,qc,wc=p[0].copy(),v[0].copy(),qu[0].copy(),w[0].copy();ph=phi[0].copy();f=filters[0].copy();current=rs[0].copy();stop=None
  for j in range(len(t)):
   nxt=filter_step(f,commands[j],.004);pc,vc,qc,wc=discrete(pc,vc,qc,wc,current,nxt,ph);f=nxt;current=nxt;openarr.append(np.r_[pc,vc,qc,wc,tilt(qc)])
   if not np.isfinite(openarr[-1]).all() or tilt(qc)>80 or max(abs(wc))>8 or np.linalg.norm(vc)>8:
    stop={'profile_s':float(t[j]),'row':j,'reason':'frozen finite working-domain exit; no long-tail mechanism inference'};break
  aa=np.array(openarr);n=len(aa);angles=np.degrees(np.arccos(np.clip(N[:n,2,2],-1,1)));opened={'rows':n,'total_recorded_rows':len(t),'full':n==len(t),'stop':stop,'COM_position_max_m':float(np.linalg.norm(aa[:,:3]-truthp[:n],axis=1).max()),'COM_velocity_max_m_s':float(np.linalg.norm(aa[:,3:6]-truthv[:n],axis=1).max()),'tilt_error_max_deg':float(abs(aa[:,-1]-angles).max()),'scope':'initial physical state once, future actually selected commands ONLY; own carried filter/rotorphase/body dynamics. No future pose/omega/filter resets. Diagnostic, not blind flight forecast.'}
 report={'schema':'p13-source-discrete-relation-audit-1','case':target.name,'raw_body_sha256':sha(run/'gz-motor/physics-p13-body.bin'),'one_step':one,'known_command_open':opened,'not_new_main_candidate':True,'frozen_M3_M4_M5_unchanged':True,'formal_prediction_scores_unchanged':True,'source_provenance':{'upstream_version':'DART6.13.2 FreeJoint::integrateVelocities and integratePositions','url':'https://raw.githubusercontent.com/dartsim/dart/v6.13.2/dart/dynamics/FreeJoint.cpp','source_relationship':'linear classical-acceleration update, translated pose, rotation of stored velocities; COM rBC geometry retained','installed_binary':'Ubuntu6.13.2+ds actual snapshot, source reading is not a rebuilt binary certificate'},'future_certificate':False,'remaining':'future SERVO/FP/joint geometry domain and EKF/cache feedback; observed residuals not hard future bounds'}
 write(out/'audit.json',report);np.savez_compressed(out/'arrays.npz',profile_s=t,one_step_errors=errors,known_command_open=np.array(openarr),COM_p_post=truthp,COM_v_post=truthv,body_q_post=qn)
 print(target.name,one,opened,flush=True);return report
if __name__=='__main__':
 out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);rows=[]
 for p in sorted((R/'data/p13-20261026-development').iterdir()):rows.append(audit(p,out/p.name,open_replay=p.name.startswith(('dev01','dev02','dev03','dev04'))))
 write(out/'summary.json',{'schema':'p13-source-discrete-audit-all-development-1','records':rows,'new_SITL':0,'not_an_autonomous_model_or_new_candidate':True})

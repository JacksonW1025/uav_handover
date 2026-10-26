"""Input-replacement diagnostics under recorded commands, never autonomous scores."""
import sys,json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
R=Path(__file__).resolve().parents[2];sys.path[:0]=[str(R/'tools'),str(Path(__file__).parent)]
from source_discrete_kernel_v1 import discrete,S,B,matrix
from p13.physics import read,BODY,ROTOR,rot
from p12.execution import step as filter_step
from p11.models import tilt
from p9_model import write,sha

def first(t,x,threshold):
 q=np.flatnonzero(x>threshold);return None if not len(q) else float(t[q[0]])
def run(target,out):
 out.mkdir(parents=True,exist_ok=False);r=target/'run';b,_=read(r/'gz-motor/physics-p13-body.bin',BODY,b'P13BODY1');pre=b[b['phase']==0];post=b[b['phase']==1];ev=[json.loads(x) for x in (r/'p11-sends.jsonl').read_text().splitlines()];epoch=round(next(x['stream_t0_monotonic_s'] for x in ev if x['stream_t0_monotonic_s'] is not None)*1e9);doc=json.load(open(target/'analysis-v1/packed/prediction-input.json'));end=doc['plan']['nominal_horizon_profile_s'];use=(pre['wall_ns']>=epoch)&(pre['wall_ns']<=epoch+end*1e9)&(pre['valid']==63)&(post['valid']==63);pre=pre[use];post=post[use];t=(pre['wall_ns'].astype(np.int64)-epoch)/1e9;Q=S@rot(pre['base_q'])@B;N=S@rot(post['base_q'])@B;qr=Rotation.from_matrix(Q).as_quat()[:,[3,0,1,2]];qc=Rotation.from_matrix(N).as_quat()[:,[3,0,1,2]];pp=pre['com_p']@S.T;vv=pre['com_v']@S.T;ww=np.einsum('nji,nj->ni',Q,pre['base_omega']@S.T);truthp=post['com_p']@S.T;truthv=post['com_v']@S.T;ro=[];rn=[];commands=[];phi=[];f0=[]
 for k in range(4):
  x,_=read(r/f'gz-motor/physics-p13-rotor-{k}.bin',ROTOR,b'P13ROTR1');j=np.searchsorted(x['step'],pre['step']);assert (j+1<len(x)).all() and np.array_equal(x['step'][j+1],pre['step']+1)
  ro.append(abs(x['joint'][j]*10));rn.append(abs(x['joint'][j+1]*10));commands.append(x['command'][j]);f0.append(float(x['filter_before'][j[0]]));rel=np.transpose(Q,(0,2,1))@(S@rot(x['q'][j])@B);phi.append(np.arctan2(rel[:,1,0],rel[:,0,0]))
 ro=np.array(ro).T;rn=np.array(rn).T;commands=np.array(commands).T;phi=np.array(phi).T;angles=np.degrees(np.arccos(np.clip(N[:,2,2],-1,1)));arrays={'profile_s':t,'COM_p_post':truthp,'COM_v_post':truthv,'body_q_post':qc};results={}
 variants=['known_commands_only','actual_joint_current_and_next','actual_rotor_phase','actual_joint_and_rotor_phase','actual_COM_velocity_each_pre','actual_body_pose_each_pre']
 for name in variants:
  p,v,q,w=pp[0].copy(),vv[0].copy(),qr[0].copy(),ww[0].copy();phase=phi[0].copy();f=np.array(f0);jnow=ro[0].copy();vals=[];stop=None
  for i in range(len(t)):
   nxt=filter_step(f,commands[i],.004)
   if name in ['actual_joint_current_and_next','actual_joint_and_rotor_phase']:jnow=ro[i];nxt=rn[i]
   if name in ['actual_rotor_phase','actual_joint_and_rotor_phase']:phase=phi[i].copy()
   if name=='actual_COM_velocity_each_pre':v=vv[i].copy()
   if name=='actual_body_pose_each_pre':q=qr[i].copy()
   p,v,q,w=discrete(p,v,q,w,jnow,nxt,phase);f=nxt;jnow=nxt;vals.append(np.r_[p,v,q,w,tilt(q)])
   if not np.isfinite(vals[-1]).all() or tilt(q)>80 or max(abs(w))>8 or np.linalg.norm(v)>8:stop={'row':i,'profile_s':float(t[i]),'reason':'finite domain exit'};break
  a=np.array(vals);n=len(a);pe=np.linalg.norm(a[:,:3]-truthp[:n],axis=1);ve=np.linalg.norm(a[:,3:6]-truthv[:n],axis=1);ae=abs(a[:,-1]-angles[:n]);results[name]={'rows':n,'full':n==len(t),'stop':stop,'first_position_error_over_point2m_s':first(t[:n],pe,.2),'first_tilt_error_over5deg_s':first(t[:n],ae,5),'max_position_m':float(max(pe)),'max_velocity_m_s':float(max(ve)),'max_tilt_deg':float(max(ae)),'future_replaced_inputs':name,'resets_after_initial':'COM velocity every step' if name=='actual_COM_velocity_each_pre' else ('body attitude every step' if name=='actual_body_pose_each_pre' else 'none of body state')};arrays[name]=a
 common=min(x['rows'] for x in results.values());preA=doc['plan']['common_first_gap_profile_s'];cm=(t[:common]<preA)
 for name,x in results.items():a=arrays[name][:common];x['same_common_preA_rows']=int(cm.sum());x['same_common_preA_tilt_max_error_deg']=float(max(abs(a[cm,-1]-angles[:common][cm])));x['same_common_preA_position_error_m']=float(max(np.linalg.norm(a[cm,:3]-truthp[:common][cm],axis=1)))
 write(out/'diagnostic.json',{'schema':'p13-controlled-source-kernel-replays-1','case':target.name,'source_kernel_sha256':sha(Path(__file__).parent/'source_discrete_kernel_v1.py'),'variants':results,'same_common_rows':common,'meaning':'future actual input/state substitutions localize open replay error under fixed recorded commands; not a full flight causal intervention, not M5/heldout score, and no formal model update','raw_body_sha256':sha(r/'gz-motor/physics-p13-body.bin'),'new_SITL':0});np.savez_compressed(out/'arrays.npz',**arrays);print(target.name,[(n,x['stop'],x['same_common_preA_position_error_m']) for n,x in results.items()],flush=True)
if __name__=='__main__':
 out=Path(sys.argv[1]);out.mkdir(exist_ok=False)
 for name in ['dev01-F2-NORMAL','dev03-F4-AB']:run(R/'data/p13-20261026-development'/name,out/name)

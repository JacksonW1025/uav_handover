"""Same physical step source balance, independent after-the-fact diagnostic only."""
import json,sys
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p13.physics import read,BODY,ROTOR,rot
from p9_model import write

def main(target,out):
 out.mkdir(parents=True,exist_ok=False);run=target/'run';a=target/'analysis-v1';doc=json.load(open(a/'packed/prediction-input.json'))
 ev=[json.loads(x) for x in (run/'p11-sends.jsonl').read_text().splitlines()];epoch=round(next(x['stream_t0_monotonic_s'] for x in ev if x['stream_t0_monotonic_s'] is not None)*1e9)
 b,h=read(run/'gz-motor/physics-p13-body.bin',BODY,b'P13BODY1');pre=b[b['phase']==0];post=b[b['phase']==1];ok=(pre['valid']==63)&(post['valid']==63)&(pre['wall_ns']>=epoch)&(pre['wall_ns']<=epoch+doc['plan']['nominal_horizon_profile_s']*1e9);pre=pre[ok];post=post[ok];dt=pre['dt_ns']/1e9;t=(pre['wall_ns'].astype(np.int64)-epoch)/1e9
 force=np.zeros((len(pre),3));torque=np.zeros_like(force);rotors=[]
 for k in range(4):
  x,_=read(run/f'gz-motor/physics-p13-rotor-{k}.bin',ROTOR,b'P13ROTR1');j=np.searchsorted(x['step'],pre['step']);assert np.array_equal(x['step'][j],pre['step']);x=x[j];rotors.append(x)
  f=rot(x['q'])[:,:,2]*x['thrust'][:,None]+x['drag'];force+=f;torque+=np.cross(x['p']-pre['com_p'],f)+x['parent_torque']
 predicted=force/pre['mass'][:,None]+np.array([0,0,-9.8]);dv=(post['com_v']-pre['com_v'])/dt[:,None];error=dv-predicted
 pp=pre['com_p']+post['com_v']*dt[:,None];pe=post['com_p']-pp
 first=doc['plan']['common_first_gap_profile_s'];bounds=[('all',-1,1e9),('pre_A',0,first),('A_and_tail',first,1e9)];summary=[]
 for name,lo,hi in bounds:
  ii=(t>=lo)&(t<hi)
  if ii.any():summary.append({'segment':name,'rows':int(ii.sum()),'acceleration_error_max_m_s2':float(np.linalg.norm(error[ii],axis=1).max()),'vertical_error_max_m_s2':float(abs(error[ii,2]).max()),'acceleration_error_rms_m_s2':float(np.sqrt(np.mean(error[ii]**2))),'position_semiimplicit_residual_max_m':float(np.linalg.norm(pe[ii],axis=1).max())})
 # External torque and angular momentum include individual rotor spin and inertia.
 Ibase=np.diag([.02166666666666667,.02166666666666667,.04000000000000001]);Ir=np.diag([3.8464910483993325e-7,2.6115851691700804e-5,2.649858234714004e-5]);M=rot(pre['base_q']);H=np.einsum('nij,jk,nlk,nl->ni',M,Ibase,M,pre['base_omega'])
 for k,x in enumerate(rotors):
  Q=rot(x['q']);H+=np.einsum('nij,jk,nlk,nl->ni',Q,Ir,Q,x['omega'])+np.cross(x['p']-pre['com_p'],pre['link_mass'][:,k+1,None]*(x['v']-pre['com_v']))
 H+=np.cross(pre['base_p']-pre['com_p'],pre['link_mass'][:,0,None]*(pre['base_v']-pre['com_v']))
 consecutive=np.diff(pre['step'])==1;Herror=np.diff(H,axis=0)/dt[:-1,None]-torque[:-1];he=Herror[consecutive]
 report={'schema':'p13-source-balance-diagnostic-1','case':target.name,'physical_step_rows':len(pre),'same_step_force':'actual source-computed thrust rotated by actual link q plus direct drag; gravity -9.8 ENU source','results':summary,'angular_momentum_torque_residual_max_Nm':float(np.linalg.norm(he,axis=1).max()),'angular_scope':'finite-step forward differencing of aggregate angular momentum including anisotropic spinning rotors; not assumed exact Euler update','future_actual_inputs':True,'autonomous':False,'future_bound':False,'new_starts':0}
 write(out/'diagnostic.json',report);np.savez_compressed(out/'arrays.npz',profile_s=t,com_pre_p=pre['com_p'],com_post_p=post['com_p'],com_pre_v=pre['com_v'],com_post_v=post['com_v'],force=force,torque=torque,acceleration_measured=dv,acceleration_source=predicted,error=error,angular_momentum=H,Herror=Herror)
 print(json.dumps(report))
if __name__=='__main__':main(Path(sys.argv[1]),Path(sys.argv[2]))

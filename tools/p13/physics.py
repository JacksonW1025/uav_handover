"""P13 direct physical records, explicit phase/validity; no missing-state zero fill."""
import json,sys,struct
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p9_model import write,sha
from p12.execution import DTYPE as EXEC
HEAD=struct.Struct('<8s7Q')
BODY=np.dtype([(k,'<u8') for k in ['step','sim_ns','dt_ns','wall_ns','phase','valid']]+[(k,'<f8',s) for k,s in [('origin_p',3),('origin_q',4),('base_p',3),('base_q',4),('base_v',3),('base_omega',3),('com_p',3),('com_v',3)]]+[('mass','<f8'),('link_com_p','<f8',(5,3)),('link_com_v','<f8',(5,3)),('link_mass','<f8',5)])
ROTOR=np.dtype([(k,'<u8') for k in ['step','sim_ns','dt_ns','wall_ns','sample_us','valid']]+[(k,'<f8') for k in ['command','filter_before','filter_after','joint','thrust']]+[(k,'<f8',s) for k,s in [('p',3),('q',4),('v',3),('omega',3),('axis',3),('wind',3),('drag',3),('parent_torque',3)]])
assert BODY.itemsize==544 and ROTOR.itemsize==288

def read(path,dtype,magic):
 with path.open('rb') as f:head=f.read(HEAD.size)
 if len(head)!=HEAD.size:raise ValueError('short header '+str(path))
 h=dict(zip(['magic','version','bytes','capacity','count','dropped','errors','complete'],HEAD.unpack(head)))
 if h['magic']!=magic or h['version']!=1 or h['bytes']!=dtype.itemsize:raise ValueError('schema '+str(path))
 h['magic']=h['magic'].decode();a=np.fromfile(path,dtype,offset=HEAD.size)
 if len(a)!=h['count'] or path.stat().st_size!=HEAD.size+h['count']*dtype.itemsize:raise ValueError('truncated physical buffer '+str(path))
 return a,h

def rot(q):
 w,x,y,z=q.T
 return np.stack([1-2*(y*y+z*z),2*(x*y-w*z),2*(x*z+w*y),2*(x*y+w*z),1-2*(x*x+z*z),2*(y*z-w*x),2*(x*z-w*y),2*(y*z+w*x),1-2*(x*x+y*y)],axis=-1).reshape(-1,3,3)

def analyze(run,out,task_start_ns=None,task_end_ns=None):
 out.mkdir(parents=True,exist_ok=False);b,h=read(run/'gz-motor/physics-p13-body.bin',BODY,b'P13BODY1');headers=[h]
 # Raw first records before Physics has populated requested components remain invalid.
 post=b[b['phase']==1];pre=b[b['phase']==0]
 if task_start_ns is None:
  ev=[json.loads(s) for s in (run/'p11-sends.jsonl').read_text().splitlines()];task_start_ns=round(next(s['stream_t0_monotonic_s'] for s in ev if s['stream_t0_monotonic_s'] is not None)*1e9)
 if task_end_ns is None:task_end_ns=int(post['wall_ns'][-1])
 task=post[(post['wall_ns']>=task_start_ns)&(post['wall_ns']<=task_end_ns)]
 gates={'headers':True,'task_state_present':len(task)>0,'body_full_task_valid':bool(len(task) and np.all(task['valid']==63)),'body_unique_phases':bool(len(pre)==len(post) and np.array_equal(pre['step'],post['step']) and np.all(np.diff(post['step'])==1)),'physics_dt':bool(np.all(post['dt_ns']==4000000)),'post_to_next_pre':True}
 metrics={};valid=task[task['valid']==63];M=rot(valid['base_q']);r=np.array([0,0,.00186913101803548]);offset=np.einsum('nij,j->ni',M,r)
 def maxnorm(x):return float(np.linalg.norm(x,axis=-1).max()) if len(x) else None
 metrics['COM_base_position_error_m']=maxnorm(valid['com_p']-valid['base_p']-offset)
 metrics['COM_base_velocity_error_m_s']=maxnorm(valid['com_v']-valid['base_v']-np.cross(valid['base_omega'],offset))
 metrics['COM_origin_distance_m_range']=[float(x) for x in [np.linalg.norm(valid['com_p']-valid['origin_p'],axis=1).min(),np.linalg.norm(valid['com_p']-valid['origin_p'],axis=1).max()]] if len(valid) else []
 # Preserve the failed ideal-rigid hypothesis; direct aggregate COM must include
 # actual joint translation/velocity residual, not assume perfect rigid joints.
 ideal_ok=metrics['COM_base_position_error_m'] is not None and metrics['COM_base_position_error_m']<=1e-8 and metrics['COM_base_velocity_error_m_s']<=1e-7
 centers=np.array([[0,0,0],[.174,-.174,.06],[-.174,.174,.06],[.174,.174,.06],[-.174,-.174,.06]])
 lever=np.einsum('nij,kj->nki',M,centers)
 delta_p=valid['link_com_p']-valid['base_p'][:,None,:]-lever
 delta_v=valid['link_com_v']-valid['base_v'][:,None,:]-np.cross(valid['base_omega'][:,None,:],lever)
 dp=np.sum(valid['link_mass'][:,:,None]*delta_p,axis=1)/valid['mass'][:,None]
 dv=np.sum(valid['link_mass'][:,:,None]*delta_v,axis=1)/valid['mass'][:,None]
 metrics['joint_mass_weighted_position_residual_m']=maxnorm(dp)
 metrics['joint_mass_weighted_velocity_residual_m_s']=maxnorm(dv)
 metrics['COM_full_geometry_position_error_m']=maxnorm(valid['com_p']-valid['base_p']-offset-dp)
 metrics['COM_full_geometry_velocity_error_m_s']=maxnorm(valid['com_v']-valid['base_v']-np.cross(valid['base_omega'],offset)-dv)
 gates['COM_geometry']=metrics['COM_full_geometry_position_error_m'] is not None and metrics['COM_full_geometry_position_error_m']<=1e-8 and metrics['COM_full_geometry_velocity_error_m_s']<=1e-7
 expected_mass=np.array([2.,.016076923076923075,.016076923076923075,.016076923076923075,.016076923076923075])
 gates['source_link_mass']=bool(len(valid) and np.max(abs(valid['link_mass']-expected_mass))<=1e-14)

 j=np.searchsorted(pre['step'],post['step'][:-1]+1);use=(j<len(pre));j=j[use];pp=post[:-1][use];ok=(pp['valid']==63)&(pre['valid'][j]==63);err=maxnorm(pre['com_p'][j[ok]]-pp['com_p'][ok]);metrics['post_next_pre_COM_position_error_m']=err;gates['post_to_next_pre']=err is not None and err<=1e-10
 if len(valid)>1:
  dt=np.diff(valid['sim_ns']).astype(float)/1e9;res=np.diff(valid['com_p'],axis=0)-valid['com_v'][1:]*dt[:,None];metrics['COM_semiimplicit_position_step_residual_m']=maxnorm(res);gates['integration_check']=metrics['COM_semiimplicit_position_step_residual_m']<=.001
 rotor_summaries=[]
 for k in range(4):
  a,hh=read(run/f'gz-motor/physics-p13-rotor-{k}.bin',ROTOR,b'P13ROTR1');headers.append(hh);e=np.fromfile(run/f'gz-motor/execution-p12-{k}.bin',EXEC);rt=a[(a['wall_ns']>=task_start_ns)&(a['wall_ns']<=task_end_ns)]
  j=np.searchsorted(e['sim_us'],a['sim_ns']//1000);match=(j<len(e));gates[f'motor{k}_same_step']=bool(match.all() and np.array_equal(e['sim_us'][j],a['sim_ns']//1000))
  if not match.all():raise ValueError('execution step missing')
  er=max(float(abs(a[n]-e[m][j]).max()) for n,m in [('command','command'),('filter_before','filter_before'),('filter_after','filter_after'),('joint','joint'),('thrust','thrust')]);gates[f'motor{k}_execution']=er<=1e-12;gates[f'motor{k}_valid']=bool(len(rt) and np.all(rt['valid']==3) and np.all(np.diff(rt['step'])==1))
  vrel=rt['v']-rt['wind'];projection=vrel-np.sum(vrel*rt['axis'],axis=1)[:,None]*rt['axis'];drag=-np.abs(rt['joint']*10)[:,None]*8.06428e-5*projection
  de=maxnorm(drag-rt['drag']);gates[f'motor{k}_drag_source']=de is not None and de<=1e-12
  rotor_summaries.append({'motor':k,'rows':len(a),'same_step_execution_max_error':er,'drag_formula_error_N':de,'sha256':sha(run/f'gz-motor/physics-p13-rotor-{k}.bin')})
 gates['headers']=all(x['complete']==1 and x['dropped']==x['errors']==0 for x in headers)
 report={'schema':'p13-physics-acceptance-3','ideal_rigid_geometry_preserved':{'status':'PASS' if ideal_ok else 'FAIL','thresholds_unchanged':[1e-8,1e-7],'scope':'ideal fixed-offset assumption only; full measured COM includes actual joint translation/velocity residual; no future bound inferred'},'status':'PASS' if all(gates.values()) else 'FAIL','gates':gates,'metrics':metrics,'headers':headers,'rotors':rotor_summaries,'body_sha256':sha(run/'gz-motor/physics-p13-body.bin'),'task_interval_host_ns':[task_start_ns,task_end_ns],'units':'ENU/world,FLU body; p_COM and v_COM mass-weighted direct link inertial poses/velocities; PreUpdate0 force step, PostUpdate1 integrated state; not callback finite difference','certificate':'numerical/interface verification, no continuous-domain invariance proof'}
 write(out/'physics.json',report);np.savez_compressed(out/'body.npz',**{n:b[n] for n in b.dtype.names});return report
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('run',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=analyze(a.run,a.output);print(r['status'],r['metrics']);raise SystemExit(0 if r['status']=='PASS' else 1)

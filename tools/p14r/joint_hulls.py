"""Explicit finite-support membership witnesses, rotor phase retained.
An observed-support outer hull is not a proof that its interior is reachable.
"""
import sys,json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p14.common import write,sha
from p11.models import speeds

def main():
 out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);base=R/'data/p14r-20261027/B-joint-support-v1';rows=[json.load(open(p)) for p in sorted(base.glob('*/initial.json'))];groups=[]
 fields=[('physical_COM_p',.1),('physical_COM_v',.15),('physical_omega',.1),('position',.1),('velocity',.15),('omega',.1),('h',.5),('previous',.1),('history',.1),('rotor_filter',10.),('pending_command',10.),('rotor_phase',.1),('gyro_delay1',.1),('gyro_delay2',.1),('gyro_output_bias',.01),('target_p',.1),('target_v',.15),('physical_H0_NED_z',.1),('physical_D0_m',.1)]
 for row in rows:
  i=row['initial'];i['last_consumed_command']=i['pending_command'];i['pending_command']=np.asarray(speeds(np.array(i['previous'])),np.float32).astype(float).tolist()
 for family in ['F2','F4']:
  rr=[r for r in rows if r['family']==family]
  for cls in sorted(set(tuple(r['class']) for r in rr)):
   points=[r for r in rr if tuple(r['class'])==cls];center=points[0]['initial'];X=[];scales=np.concatenate([np.full(np.size(center[k]),scale) for k,scale in fields]+[np.full(6,np.radians(2.5))]);names=[f'{key}:{k}' for key,_ in fields for k in range(np.size(center[key]))]+[f'{key}-SO3:{k}' for key in ['physical','estimated'] for k in range(3)]
   for row in points:
    i=row['initial'];parts=[]
    for key,_ in fields:
     d=np.atleast_1d(i[key])-np.atleast_1d(center[key]);parts.append((d+np.pi)%(2*np.pi)-np.pi if key=='rotor_phase' else d)
    for key in ['physical_q','attitude']:
     a=Rotation.from_quat(np.array(center[key])[[1,2,3,0]]);b=Rotation.from_quat(np.array(i[key])[[1,2,3,0]]);parts.append((a.inv()*b).as_rotvec())
    X.append(np.concatenate(parts))
   X=np.array(X);U,s,V=np.linalg.svd((X/scales).T,full_matrices=False);rank=min(8,len(s));basis=U[:,:rank]*scales[:,None];coordinate=(X/scales)@U[:,:rank];amp=np.max(abs(coordinate),axis=0);residual=X-coordinate@basis.T;tail=np.max(abs(residual),axis=0)+2e-13;G=np.column_stack([basis*amp,np.diag(tail)]);epsilon=np.divide(coordinate,amp,out=np.zeros_like(coordinate),where=amp>0);eta=residual/tail;witness=np.column_stack([epsilon,eta]);error=np.max(abs(witness@G.T-X));bound=np.max(abs(witness));assert error<1e-10 and bound<=1+1e-12
   name=family+'-'+str(len(groups));np.savez_compressed(out/(name+'.npz'),X=X,G=G,witness=witness);groups.append({'name':name,'family':family,'class':cls,'ids':[p['id'] for p in points],'source_center':points[0]['id'],'names':names,'rank':rank,'witness_max_abs':float(bound),'reconstruction_max_abs':float(error),'rotor_phase_projection_included':True,'pending_vs_consumed_separate':True,'old_runtime_OP_fields':'not available; no OP hull invented','future_reachability':'not asserted; finite observed support witnesses only','joint_outer':'8 shared scaled directions plus explicit residual diagonals; interior can contain unreachable combinations'})
 write(out/'summary.json',{'groups':groups,'support_count':len(rows),'all_observed_membership_witnessed':True,'max_error':max(g['reconstruction_max_abs'] for g in groups),'source':sha(Path(__file__)),'selection':'all66pre-event inventory; propagation restricted to earlier12/family plan, no outcome selection'})
if __name__=='__main__':main()

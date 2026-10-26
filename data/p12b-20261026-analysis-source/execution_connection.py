#!/usr/bin/env python3
"""Independent finite-record chain join by causal host order, never by matching values."""
from pathlib import Path
import numpy as np,json,sys
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p12b.solver import read,S,V
from p12.execution import DTYPE
from p9_model import write,sha

def main(run,out):
 run=run.resolve()
 if out.exists():raise FileExistsError(out)
 paths=[]
 for p in (run/'gz-motor').glob('dart-solver-*.bin'):
  if any(t==3 for t,*_ in read(p)):paths.append(p)
 if len(paths)!=1:raise RuntimeError('one physics World trace required')
 p=paths[0];before={};rows=[]
 for typ,step,wall,sim,raw in read(p):
  if typ==1:
   v=S.unpack(raw);name=v[7].split(b'\0')[0].decode()
   if name.startswith('rotor_'):before[(step,v[1])]={'step':step,'world_before_us':sim,'pre_wall_ns':wall,'joint':v[1],'name':name,'command':float(v[16]),'free_velocity':float(v[22]),'dt':v[8]}
  elif typ==3:
   v=V.unpack(raw);b=before.get((step,v[0]))
   if b:rows.append(dict(b,post_wall_ns=wall,post_velocity=v[2]))
 result={};arrays={}
 for i,direction in enumerate([1,1,-1,-1]):
  points=[r for r in rows if r['name']==f'rotor_{i}_joint'];e=np.fromfile(run/f'gz-motor/execution-p12-{i}.bin',DTYPE)
  wall=np.array([r['pre_wall_ns'] for r in points],dtype=np.int64);j=np.searchsorted(e['end_ns'],wall,side='left')-1
  valid=(j>=0)&(j+1<len(e));points=[r for r,v in zip(points,valid) if v];j=j[valid];a=e[j];n=e[j+1]
  command=np.array([r['command'] for r in points]);post=np.array([r['post_velocity'] for r in points]);prewall=np.array([r['pre_wall_ns'] for r in points],dtype=np.int64);postwall=np.array([r['post_wall_ns'] for r in points],dtype=np.int64)
  same_order=(a['end_ns']<prewall)&(n['consume_ns']>postwall)
  command_error=command-direction*a['filter_after']/a['slowdown'];next_error=n['joint']-post
  expected=direction*np.sign(a['scaled_joint'])*a['motor_constant']*a['scaled_joint']**2;thrust_error=a['thrust']-expected
  world=np.array([r['world_before_us'] for r in points],dtype=np.int64);offset=a['sim_us'].astype(np.int64)-world
  result[str(i)]={'pairs':len(j),'strict_source_order_pairs':int(same_order.sum()),'motor_sim_minus_World_pre_us':sorted(np.unique(offset).tolist()),'command_from_filter_after_max_rad_s':float(abs(command_error).max()),'next_preupdate_joint_from_postWorld_max_rad_s':float(abs(next_error).max()),'signed_thrust_source_formula_max_N':float(abs(thrust_error).max()),'free_velocity_minus_preupdate_joint_max_rad_s':float(max(abs(np.array([r['free_velocity'] for r in points])-a['joint']))),'alignment':'last completed motor trace before getInformation, next motor trace after World post bracket; no value or outcome based pairing','outside_bracket':int((~same_order).sum())}
  arrays[f'motor{i}']=np.column_stack([a['sim_us'],world,prewall,postwall,command_error,next_error,thrust_error])
 out.mkdir(parents=True,exist_ok=False);np.savez_compressed(out/'connections.npz',**arrays)
 status='PASS' if all(r['outside_bracket']==0 and r['command_from_filter_after_max_rad_s']<1e-9 and r['next_preupdate_joint_from_postWorld_max_rad_s']<1e-9 and r['signed_thrust_source_formula_max_N']<1e-9 for r in result.values()) else 'FAIL'
 write(out/'connections.json',{'schema':'p12b-execution-full-connection-1','status':status,'run':str(run),'motors':result,'DART_trace_sha256':sha(p),'scope':'known-record consumed/filter/joint/solver/next-force numerical connection, not future coverage or whole-body wrench/height proof'})
 print(json.dumps({'status':status,'motors':result},indent=2))
if __name__=='__main__':main(Path(sys.argv[1]),Path(sys.argv[2]))

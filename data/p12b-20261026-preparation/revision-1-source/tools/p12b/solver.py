#!/usr/bin/env python3
"""DART passive trace audit: eta from independent pre-solver matrix, never from e_j."""
import argparse,json,struct,sys
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p9_model import sha,write
H=struct.Struct('<4I3Q');S=struct.Struct('<7Q96s2d6B54d');V=struct.Struct('<Q96s6dQd');L=struct.Struct('<2Q6i')
def read(path):
 with path.open('rb') as f:
  while True:
   h=f.read(H.size)
   if not h:return
   if len(h)!=H.size:raise RuntimeError('trailing partial header')
   magic,typ,size,version,step,wall,sim=H.unpack(h)
   if magic!=0x42323150 or version not in [1,2] or size<H.size:raise RuntimeError('solver trace protocol')
   raw=f.read(size-H.size)
   if len(raw)!=size-H.size:raise RuntimeError('trailing partial record')
   yield typ,step,wall,sim,raw

def analyze(path,out,unit=False):
 if out.exists():raise FileExistsError(out)
 servo={};pending={};world=[];matrices=[];other_rows=0;counts={};joints=set();fails=[];seeds=[];types={};group_rows={}
 for typ,step,wall,sim,raw in read(path):
  counts[typ]=counts.get(typ,0)+1
  if typ==1:
   row=S.unpack(raw);constraint,joint,bptr,dim,dof,mode,limits_enforced,name,dt,cfm=row[:10];active=np.asarray(row[10:16],bool);a=np.asarray(row[16:]).reshape(9,6)
   name=name.split(b'\0')[0].decode();joints.add(name)
   if dim!=int(active[:dof].sum()):raise RuntimeError('servo dimension/active mismatch')
   servo.setdefault(step,[]).append({'joint':joint,'name':name,'bptr':bptr,'dim':dim,'dof':dof,'mode':mode,'limits_enforced':limits_enforced,'dt':dt,'cfm':cfm,'active':active,'a':a})
  elif typ==2:
   solver,bptr,n,stride,nub,kind,ok,early=L.unpack(raw[:L.size]);off=L.size
   def take(count,dtype='<f8'):
    nonlocal off
    a=np.frombuffer(raw,dtype=dtype,count=count,offset=off).copy();off+=a.nbytes;return a
   A=take(n*stride).reshape(n,stride)[:,:n];b=take(n);lo=take(n);hi=take(n);x=take(n);findex=take(n,'<i4')
   if off!=len(raw):raise RuntimeError('solver frame length')
   eta=A@x-b;maps=[]
   for s in servo.get(step,[]):
    distance=s['bptr']-bptr
    if distance<0 or distance%8 or distance//8+s['dim']>n:continue
    start=distance//8
    for ordinal,dofindex in enumerate(np.flatnonzero(s['active'][:s['dof']])):
     i=start+ordinal;cfm=s['cfm'];D=A[i,i]/(1+cfm);correction=cfm*D*x[i];command,free,flo,fhi,vlo,vhi,position,plo,phi=s['a'][:,dofindex]
     desired=float(np.clip(np.clip(command,vlo,vhi),(plo-position)/s['dt'],(phi-position)/s['dt']));limit_offset=desired-command
     maps.append({'step':step,'sim_us':sim,'joint':s['joint'],'name':s['name'],'dof':int(dofindex),'solver_kind':kind,'solver_success':bool(ok),'row':i,'n':n,'dt':s['dt'],'cfm':cfm,'mode':s['mode'],'command':float(command),'free':float(free),'b':float(b[i]),'lambda':float(x[i]),'lower_impulse':float(lo[i]),'upper_impulse':float(hi[i]),'force_limits':[float(flo),float(fhi)],'velocity_limits':[float(vlo),float(vhi)],'finite_impulse_limits':bool(np.isfinite(lo[i]) and np.isfinite(hi[i])),'D':float(D),'cfm_D_lambda':float(correction),'eta_matrix':float(eta[i]),'predicted_joint_error':float(eta[i]-correction+limit_offset),'limit_offset':float(limit_offset),'limits_enforced':bool(s['limits_enforced']),'position':float(position),'position_limits':[float(plo),float(phi)],'near_bound':bool(x[i]<=lo[i]+1e-9 or x[i]>=hi[i]-1e-9),'b_source_error':float(b[i]-(desired-free)),'limit_source_error':float(max(abs(lo[i]-flo*s['dt']) if np.isfinite(lo[i]) else 0,abs(hi[i]-fhi*s['dt']) if np.isfinite(hi[i]) else 0))})
   other_rows+=n-len(maps);matrices.append({'step':step,'n':n,'mapped_servo_rows':len(maps),'other_constraint_rows':n-len(maps),'kind':kind,'success':bool(ok),'symmetry_error':float(abs(A-A.T).max()),'interior_equation_residual_max':float(abs(eta[(x>lo+1e-9)&(x<hi-1e-9)]).max(initial=0))})
   for m in maps:pending[(step,m['joint'],m['dof'])]=m
  elif typ==6:
   seeds.append(struct.unpack('<Q',raw)[0])
  elif typ==4:
   offset,dim,name=struct.unpack('<QQ96s',raw);name=name.split(b'\0')[0].decode();types[name]=types.get(name,0)+1;group_rows.setdefault(step,[]).append((offset,dim,name))
  elif typ==3:
   row=V.unpack(raw);joint,name=row[:2];v=row[2:8];dof=row[8]
   for i in range(dof):
    p=pending.get((step,joint,i))
    if p:
     p={**p,'post_velocity_direct':v[i],'post_error_direct':v[i]-p['command'],'identity_error':(v[i]-p['command'])-p['predicted_joint_error'],'time_after_direct':row[9]};world.append(p)
  else:raise RuntimeError('unknown solver frame')
 for m in world:
  if abs(m['b_source_error'])>1e-9 or abs(m['limit_source_error'])>1e-9 or abs(m['identity_error'])>1e-7:fails.append(m)
 status='PASS' if not fails and (unit or len(world)>0) else 'FAIL'
 # Infinity is explicitly retained as a string, not misrepresented as a finite bound.
 def safe(x):
  if isinstance(x,float) and not np.isfinite(x):return 'Infinity' if x>0 else '-Infinity' if x<0 else 'NaN'
  if isinstance(x,dict):return {k:safe(v) for k,v in x.items()}
  if isinstance(x,list):return [safe(v) for v in x]
  return x
 out.mkdir(parents=True,exist_ok=False)
 # Full row arrays stay local; no decimation. Small examples/counters enter Git.
 if world:
  keys=[k for k,v in world[0].items() if isinstance(v,(float,int,bool))];np.savez_compressed(out/'solver-rows.npz',**{k:np.array([r[k] for r in world]) for k in keys},name=np.array([r['name'] for r in world]))
 report={'schema':'p12b-solver-audit-1','status':status,'raw_sha256':sha(path),'raw_bytes':path.stat().st_size,'frame_counts':counts,'actual_rng_seed_set_calls':seeds,'constraint_type_counts':types,'servo_post_rows':len(world),'joint_names':sorted(joints),'solver_systems':len(matrices),'other_constraint_rows':other_rows,'systems_with_other_constraints':sum(r['other_constraint_rows']>0 for r in matrices),'secondary_solver_systems':sum(r['kind']==2 for r in matrices),'unsaturated_rows':sum(not r['near_bound'] for r in world),'command_clipping_rows':sum(abs(r['limit_offset'])>0 for r in world),'near_bound_rows':sum(r['near_bound'] for r in world),'max_independent_identity_error_rad_s':max((abs(r['identity_error']) for r in world),default=None),'max_eta_matrix_interior':max((abs(r['eta_matrix']) for r in world if not r['near_bound']),default=None),'finite_impulse_limit_rows':sum(r['finite_impulse_limits'] for r in world),'examples':world[:4],'failure_examples':fails[:8],'maximum_interior_matrix_equation_residual':max((r['interior_equation_residual_max'] for r in matrices),default=None),'constraint_path':'installed automatic JointConstraint SERVO/limit path, not ServoMotorConstraint assumption','variable_provenance':{'direct':'pre-solver A,b,limits/findex; solved x(lambda); pre-free and post-World joint velocities; command/dt/CFM/actuator mode','source_reconstructed':'D=Aii/(1+CFM); eta=A_original*x-b_original; full coupling retained','defined_from_ej':'NONE; eta never obtained from post velocity error','future_hard_bounds':'NOT_PROVEN; infinite force limits provide no finite impulse bound'},'scope':'finite numerical connection audit, not a future hard-domain theorem','unit':unit}
 write(out/'solver-audit.json',safe(report));print(json.dumps({'status':status,'servo_post_rows':len(world),'systems':len(matrices),'max_identity_error':report['max_independent_identity_error_rad_s']}));return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('trace',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--unit',action='store_true');a=p.parse_args();raise SystemExit(analyze(a.trace,a.output,a.unit)['status']!='PASS')

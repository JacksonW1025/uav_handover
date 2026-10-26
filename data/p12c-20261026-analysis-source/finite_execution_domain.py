#!/usr/bin/env python3
"""Finite airborne servo domain: source geometry/kinetic structure, then old matrix audit.
No new physics hook, no future empirical hard bound and no SITL launch.
"""
from pathlib import Path
from fractions import Fraction as F
import json,sys,math,hashlib,struct,xml.etree.ElementTree as X
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p12b.solver import read,S,L

def source_domain():
 p=R/'uav_lab/.local/checkouts/px4-raptor/Tools/simulation/gz/models/x500_base/model.sdf';m=X.parse(p).getroot().find('model');links={l.attrib['name']:l for l in m.findall('link')};base=links['base_link'];rotors=[links[f'rotor_{i}'] for i in range(4)];I=[F(l.findtext('inertial/inertia/izz')) for l in rotors];assert len(set(I))==1;Ezz=F(base.findtext('inertial/inertia/izz'));model_pose=[F(x) for x in m.findtext('pose').split()];collision=[]
 for name,l in links.items():
  pose=[F(x) for x in l.findtext('pose','0 0 0 0 0 0').split()];pos=[float(model_pose[i]+pose[i]) for i in range(3)]
  for c in l.findall('collision'):
   cp=[float(x) for x in c.findtext('pose','0 0 0 0 0 0').split()];g=c.find('geometry');box=g.find('box')
   if box is None:raise RuntimeError('unhandled collision shape, no no-contact claim')
   size=[float(x) for x in box.findtext('size').split()];bound=np.linalg.norm(pos)+np.linalg.norm(cp[:3])+np.linalg.norm(size)/2
   collision.append({'link':name,'collision':c.attrib['name'],'origin_radius_upper_m':float(bound),'method':'triangle + rotated box circumsphere; conservative for all orientations and rotor angles'})
 for l in rotors:
  mass=F(l.findtext('inertial/mass'));pose=[F(x) for x in l.findtext('pose').split()];Ezz+=mass*(pose[0]**2+pose[1]**2)
 kappa=1/Ezz;alpha=1/I[0];c=F('0.000000001');cmd=F(100);free=F(110);bnorm=2*(cmd+free);impulse=bnorm/(alpha*(1+c));Dmax=alpha+kappa;error=10*c*Dmax*impulse
 return {'source':str(p.relative_to(R)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'rotor_Izz_kg_m2_exact':str(I[0]),'yaw_free_effective_inertia_exact':str(Ezz),'kappa_inverse_inertia':float(kappa),'A_servo_ideal':'I_r^-1 I4 + kappa 11T; add c*diag(A) to CFM diagonal','alpha_lower':float(alpha),'condition_number_upper':float((alpha+4*kappa)/alpha),'collision_geometry':collision,'max_collision_radius_m':max(x['origin_radius_upper_m'] for x in collision),'finite_working_domain':{'time':'task0 through nominal full poststream, <=36s; takeoff/landing outside certificate claim but logs retained','world_model_origin_H_m':[.7,8.],'tilt_deg_max':50,'body_velocity_norm_m_s_max':8,'body_omega_component_rad_s_max':8,'rotor_relative_angle_abs_rad_max':1000000,'scaled_joint_and_free_speed_abs_rad_s_max':1100,'filter_and_consumed_command_rad_s':[0,1000],'dt_physics_s':.004,'LP_att_cache_age_s_max':.024,'clock':'sample/native actual words, including native plateau allowed; no constant4ms controller map','constraint_modes':'no ground/self contact conditional on geometric height domain and one-vehicle plane world; SERVO, no finite force/velocity limits; position ±1e16 inactive in rotor angle domain','unknown_invariance':'future free/body/cache/height membership and floating solver error NOT_PROVEN; full target records must be checked without removing unfavorable failures'},'uniform_source_conditional_bounds':{'CFM':float(c),'free_joint_rad_s_max':float(free),'command_joint_rad_s_max':float(cmd),'b_l2_rad_s_max':float(bnorm),'lambda_l2_N_m_s_max_exact_arithmetic':float(impulse),'joint_scaled_error_l2_rad_s_CFMonly':float(error),'with_independent_solver_eta':'add 10*(1+c*Dmax/alpha)*||eta||_2 conservatively using ||lambda||<=(||b||+||eta||)/alpha; future eta bound NOT_PROVEN','scope':'finite-domain real mass/constraint algebra, not empirical max or full FP/closed-loop certificate','infinite_force_limits':'not used as impulse bound; positive inertia and bounded b supply conditional bound'}}

def audit(path,source):
 Ir=float(F(source['rotor_Izz_kg_m2_exact']));k=source['kappa_inverse_inertia'];servo=[];last=None;rows=[]
 for typ,step,wall,sim,raw in read(path):
  if step!=last:servo=[];last=step
  if typ==1:
   s=S.unpack(raw);servo.append(s)
  if typ!=2:continue
  solver,bptr,n,stride,nub,kind,ok,early=L.unpack(raw[:L.size]);offset=L.size;A=np.frombuffer(raw,'<f8',n*stride,offset).reshape(n,stride)[:,:n];offset+=n*stride*8;b=np.frombuffer(raw,'<f8',n,offset);offset+=n*8*3;lam=np.frombuffer(raw,'<f8',n,offset)
  mapped=[]
  for s in servo:
   delta=s[2]-bptr
   if delta>=0 and delta%8==0 and delta//8+s[3]<=n:mapped.append((delta//8,s))
  if n!=4 or len(mapped)!=4 or any(s[3]!=1 or s[4]!=1 for _,s in mapped):continue
  ideal=np.eye(4)/Ir+k*np.ones((4,4));cfms=np.zeros(4)
  for i,s in mapped:cfms[i]=s[9];ideal[i,i]*=(1+s[9])
  eta=A@lam-b;rows.append([step,sim,n,kind,bool(ok),float(abs(A-ideal).max()),np.linalg.eigvalsh((A+A.T)/2)[0],np.linalg.norm(b),np.linalg.norm(lam),np.linalg.norm(eta),float(abs(A-A.T).max()),float(cfms.max())])
 return np.asarray(rows)

def main(out):
 if out.exists():raise FileExistsError(out)
 out.mkdir(parents=True);s=source_domain();assert s['max_collision_radius_m'] < s['finite_working_domain']['world_model_origin_H_m'][0];reports=[]
 for auditp in sorted((R/'data/p12b-20261026-preparation-v2/solver-recheck').glob('*/solver-audit.json')):
  meta=json.load(open(auditp));run=R/'data/p12b-20261026-development-v2'/auditp.parent.name/'run';paths=[p for p in (run/'gz-motor').glob('dart-solver-*.bin') if p.stat().st_size==meta['raw_bytes']];assert len(paths)==1;arr=audit(paths[0],s);np.savez_compressed(out/(auditp.parent.name+'.npz'),rows=arr);reports.append({'id':auditp.parent.name,'old_already_seen':True,'raw_sha256':meta['raw_sha256'],'servo_only_systems':len(arr),'max_source_matrix_error':float(arr[:,5].max()) if len(arr) else None,'min_A_eigenvalue_observed':float(arr[:,6].min()) if len(arr) else None,'max_b_norm_observed':float(arr[:,7].max()) if len(arr) else None,'max_lambda_norm_observed':float(arr[:,8].max()) if len(arr) else None,'max_eta_norm_observed':float(arr[:,9].max()) if len(arr) else None,'mode_scope':'posthoc servo-only matrix reconstruction; contact/coupled systems excluded from THIS theorem, remain raw and original full solver audit; target-domain no-contact must be separately geometry-checked'})
 (out/'domain-and-audit.json').write_text(json.dumps({'schema':'p12c-finite-servo-domain-1','source_domain':s,'historical_matrix_audit':reports,'certification':'source-conditioned real matrix bound plus posthoc numeric consistency only; future floating/closed-loop domain NOT_PROVEN; not a new model or formal prediction','new_SITL_starts':0,'A4':'NOT_PROVEN_EXCLUDED'},indent=2)+'\n');print('FINITE_DOMAIN_SOURCE',s['max_collision_radius_m'],s['uniform_source_conditional_bounds']);print('MATRIX_AUDIT',[(x['id'],x['servo_only_systems'],x['max_source_matrix_error']) for x in reports])
if __name__=='__main__':main(Path(sys.argv[1]))

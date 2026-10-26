#!/usr/bin/env python3
"""Conditional event-height map; never fit constants to formal outcomes."""
from fractions import Fraction as F
import json,math,sys,hashlib,xml.etree.ElementTree as X
from pathlib import Path
R=Path(__file__).resolve().parents[2]

def advance(loss,down,maxloss,duration,acc_down,position_defect=F(0),velocity_jump=F(0)):
 # Continuous flow with an explicit end-of-mode velocity jump. DART discrete
 # integration defects must be separately supplied/proved; not silently zero.
 T=F(duration);a=F(acc_down);V=F(down);L=F(loss);candidates=[L,L+V*T+a*T*T/2]
 if a and 0 < -V/a < T:candidates.append(L-V*V/(2*a))
 newloss=L+V*T+a*T*T/2+F(position_defect)
 return newloss,V+a*T+F(velocity_jump),max(F(maxloss),*candidates,newloss)

def profile(modes):
 L=V=M=F(0);rows=[]
 for name,T,a in modes:
  L,V,M=advance(L,V,M,T,a);rows.append({'mode':name,'duration_s':float(T),'acc_down_m_s2':float(a),'loss_m':float(L),'down_velocity_m_s':float(V),'historical_max_loss_m':float(M),'current_margin_m':float(1-L),'history_margin_m':float(1-M),'ever_height_failed':M>1})
 return rows

def example():
 # Exact rational example of a missing absolute-margin/residual-velocity premise.
 # Source interruption duration and g=.55 match the historical F4 plan; thrust
 # levels are a declared mechanical envelope, not a neural reachability claim.
 g=F('9.8');T=F('.36');recovery=F('.8');between=F('.55');ad=g/4;au=ad*T/recovery
 single=profile([('low_thrust',T,ad),('recovery',recovery,-au),('post_hold',F('1'),F(0))])
 combined=profile([('A_low',T,ad),('partial_A_recovery_before_B',between,-au),('B_low',T,ad),('B_recovery',recovery,-au),('post_hold',F('1'),F(0))])
 assert single[-1]['historical_max_loss_m']<1 and combined[-1]['historical_max_loss_m']>1
 return {'same_tilt_peak_deg':17,'gravity_exact':str(g),'deceleration_down_exact':str(ad),'recovery_up_exact':str(au),'single':single,'AB':combined,'meaning':'counterexample to tilt-peak-only or reset-height-at-event inference in declared thrust/kinematic envelope, not a proven reachable NN/Gazebo trajectory; filter transients, integration and closed-loop domains must be bounded before claiming physical system coverage'}

def material():
 p=R/'uav_lab/.local/checkouts/px4-raptor/Tools/simulation/gz/models/x500_base/model.sdf';root=X.parse(p).getroot().find('model');mass=F(0);rz=F(0);links=[]
 for link in root.findall('link'):
  m=F(link.findtext('inertial/mass'));pose=link.findtext('pose','0 0 0 0 0 0').split();z=F(pose[2]);mass+=m;rz+=m*z;links.append({'name':link.attrib['name'],'mass':str(m),'z_base_m':str(z)})
 return {'source':str(p.relative_to(R)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'links':links,'total_mass_exact':str(mass),'total_mass_kg':float(mass),'COM_offset_base_z_exact':str(rz/mass),'COM_offset_base_z_m':float(rz/mass),'condition':'rotor revolute axes pass through their inertial centers; no unlisted links or payload; model origin is not reset at capture'}

def constraint(mass,remaining,down,T,theta_deg,joint_error,drag_force,geometry_and_integration_budget):
 # Source T_z >= cos(theta) * k * sum(max(f_i-Ej_i,0)^2).
 Amax=2*(remaining-down*T-geometry_and_integration_budget)/(T*T)
 required_total_thrust=max(0,mass*(9.8-Amax)+drag_force)/math.cos(math.radians(theta_deg))
 fmin=joint_error+math.sqrt(required_total_thrust/(4*8.54858e-6))
 return {'remaining_margin_m':remaining,'initial_down_m_s':down,'whole_segment_T_s':T,'theta_upper_deg':theta_deg,'assumed_joint_abs_error_rad_s':joint_error,'assumed_other_force_down_N':drag_force,'assumed_geometry_and_integration_budget_m':geometry_and_integration_budget,'permitted_down_acc_m_s2':Amax,'required_total_thrust_N':required_total_thrust,'sufficient_each_filter_floor_rad_s':fmin,'configured_command_ceiling_rad_s':1000,'algebraic_feasibility_below_command_ceiling':fmin<1000,'assumption_validation':'NOT_ESTABLISHED_FOR_ACTUAL_FUTURE; illustrative independent domain, not fitted or used to relabel experiments'}

def main(out):
 if out.exists():raise FileExistsError(out)
 m=material();e=example();c=constraint(m['total_mass_kg'],.5,.2,1.16,45,1.,4*1000*8.06428e-5*2,.075)
 result={'schema':'p12b-conditional-event-margin-map-1','no_formal_fit':True,'source_material':m,'GZ_gravity_m_s2':9.8,'unchanged_M3_M4_gravity_m_s2':9.80665,'gravity_scope':'physical world SDF uses9.8; original frozen predictor9.80665 unchanged, no refit','world_height_reference':'truth model origin, not COM; resolved merge frame adds0.24m, COM offset from model origin0.241869131m','geometry_budget_scope':'example .075 includes conservative model-origin/COM geometry rotation span up to45deg plus an assumed .004 integration budget, not verified future coverage','whole_segment_constraint_example':c,'tilt_only_counterexample':e,'height_composition':'L_out=L_in+V_in*T+integral_0^T (T-s)*a_down(s)ds+integration_defect; V_out=V_in+integral a_down + velocity_jumps; D_out=max(D_in,sup L_prefix); NEVER reset L or D at capture/resume','future_theory':'conditional event relation, not complete verified NN/solver/body/cache domain or A4 exclusion','network_history':'mode-dependent H/X/action and previous/mean/count update must propagate with same target/cache/clock word; action box2 is conservative, not an experiment rejection','A4':'NOT_PROVEN_EXCLUDED'}
 out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2)+'\n');print('CONDITIONAL_MARGIN_MAP',c['sufficient_each_filter_floor_rad_s'],'single/ABmax',e['single'][-1]['historical_max_loss_m'],e['AB'][-1]['historical_max_loss_m'])
if __name__=='__main__':main(Path(sys.argv[1]))

"""Exact rational CONDITIONAL sufficient recovery map, not a flight certificate."""
from fractions import Fraction as F
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p14.common import write

def map_prefix(L,W,D,ar,n,h=F(1,250),ep=F(3,10**6)):
 l=[L+j*h*W-ar*h*h*j*(j+1)/2+j*ep for j in range(n+1)]
 return {'L_upper':l[-1],'D_upper':max([D]+l),'W_upper':W-n*h*ar,'max_at_step':max(range(n+1),key=l.__getitem__)}

def calculate():
 m=F(13418,6500) # exact SDF combined mass 2.0643076923076923
 k=F('0.00000854858');cd=F('0.0000806428');g=F('9.8')
 # Source bounds, NOT observed maxima: filter >=871, scaled joint error<=1,
 # Ω<=1001, Vrel<=2, cos(theta)>=.93. Entire interval conditions required.
 force=4*k*870**2*F(93,100)-4*cd*1001*2
 ar=force/m-g
 assert ar>1
 rows=[]
 for T in [F(55,100),F(12,10),F(2)]:
  n=int(T*250);x=map_prefix(F(3,10),F(8,10),F(4,10),F(1),n)
  rows.append({'T_requested_s':str(T),'physical_full_steps':n,'covered_T_s':str(F(n,250)),**{k:str(v) for k,v in x.items()},'LP_margin_if_E_LP_02':str(1-x['D_upper']-F(2,100)),'uncovered_partial_s':str(T-F(n,250))})
 return {'schema':'p14-conditional-height-exact-1','conditions':{'filter_all_rotors_all_steps_min':871,'commands_min':871,'actual_scaled_joint_minus_filter_abs_max_assumed':1,'filter_initial_min':871,'wind':0,'no_external_up_or_down_contact':True,'cos_theta_min':'.93','Vrel_max_m_s':2,'joint_max_rad_s':1001,'LP_body_COM_error_assumed_m':'.02','initial_L':'.3','initial_D':'.4','initial_W':'.8','position_defect_per_step_assumed_m':'.000003'},
  'force_derived_up_acceleration_lower_exact':str(ar),'conservative_ar':1,'nonempty_algebraic_filter_command_range':[871,1000],
  'prefix_maps':rows,'stop_time_bound_s':'.8','no_reset_L_D_W':True,
  'direction':'sufficient safety at all covered physical samples under the entire stated domain; not necessary loss, not actual reachability or full B event certificate',
  'continuous_between_samples':'not certified without extra intersample geometry/integration budget; .55s has .002s uncovered partial interval',
  'remaining':['prove actual controller maintains filter>=871 and theta cone for whole segment','solver/geometry/FP and LP error bounds not yet certified','B and final tail require their own conditioned maps; do not reset D'],
  'rational_cos_bound':'theta<=pi/9: cos>=1-(22/63)^2/2 >.93, exact Taylor inequality',
  'future_hard_actual_certificate':False}

if __name__=='__main__':write(Path(sys.argv[1]),calculate())

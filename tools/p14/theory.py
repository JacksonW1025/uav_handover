"""One predeclared correlated finite-feedback attempt and source obligations."""
import json,sys,math
from pathlib import Path
from fractions import Fraction as F
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p14.affine import Context,cat,network,filter_step
from p14.common import write,sha
from p13.physical_model import mass

def attempt(P,radius,box=False):
 C=Context(box);z=C.variable([-3.],radius);cap=z;v=C.variable([.1],radius)
 # Speed-matched horizontal capture: shared initial position and velocity.
 px=C.variable([0.],radius);pc=px;vx=C.variable([1.8],radius);vc=vx
 h=C.variable(np.zeros(16),radius);previous=C.variable(np.full(4,.45),radius);mean=previous;count=0
 f=C.variable(np.full(4,770.),radius);pending=f;lpz=z;lpv=v;lpx=px;lpvx=vx
 rows=[]
 for k in range(1,17):
  # Source vertical projection conditioned on fixed level attitude, no wind,
  # zero joint residual, exact COM/body coincidence, nominal dt and no contact.
  # These are explicit nonempty model conditions, NOT actual-domain membership.
  total=(f*f).linear(np.ones((1,4)));acc=9.8-total*(8.54858e-6/mass)
  v=v+.004*acc;z=z+.004*v;px=px+.004*vx;f=filter_step(f,pending)
  if k%2==0:lpz=z;lpv=v;lpx=px;lpvx=vx
  t=.004*k;r=pc+t*vc-.5*2*t*t;sv=vc-2*t
  mean=(count/(count+1))*mean+(1/(count+1))*previous
  # FLU rotation identity and zero angular input; speed remains positive.
  x=cat((lpx-r).clip(.5),C.constant([0.]),(cap-lpz).clip(.5),C.constant(np.eye(3).reshape(-1)),(lpvx-sv).clip(1.),C.constant([0.]),(-lpv).clip(1.),C.constant([0.,0.,0.]),mean)
  hh,action=network(P,h,x)
  if k%2==0:h=hh;count=0
  else:count+=1
  previous=action;pending=150+425*(action[[0,2,3,1]]+1)
  if k in [1,2,4,8,16]:
   al,au=action.bounds();zl,zu=z.bounds();vl,vu=v.bounds()
   lb,ub=(z-cap).bounds()
   rows.append({'calls':k,'T_s':t,'action_radius_max':float(action.radius().max()),'action_interval_width_max':float((au-al).max()),'vertical_velocity_interval':[float(vl[0]),float(vu[0])],'COM_L_interval':[float(lb[0]),float(ub[0])],'height_radius_m':float(z.radius()[0]),'generators':C.n,'informative_action_width_lt_2':bool(max(au-al)<2)})
  if not np.isfinite(z.c).all() or not np.isfinite(z.g).all():return {'radius':radius,'box':box,'rows':rows,'numerical_failure_call':k}
 return {'radius':radius,'box':box,'rows':rows,'numerical_failure_call':None}

def source_budget():
 Ir=F('0.00002649858234714004');kap=F('22.7821780951');c=F(1,10**9);alpha=1/Ir;D=alpha+kap;d=alpha+c*D
 # Bounded matrix perturbation: Neumann sufficient, no observed maxima.
 delta=F(1,1000000);B=F('408.47650626');eta=F(1,1000)
 lam=(B+2*eta)/(d-delta)
 ej=10*(eta+c*D*lam+delta*lam)
 return {'hypotheses':{'four_SERVO_only':True,'no_desired_clipping':True,'delta_A_operator_norm_assumed':str(delta),'eta_inf_assumed':str(eta),'rhs_L2_bound':str(B)},'d_lower':float(d),'matrix_perturbation_ratio':float(delta/d),'lambda_L2_bound':float(lam),'scaled_joint_error_inf_bound':float(ej),'Ej1_self_consistency':bool(ej<1),'exact_fraction_scaled_bound':str(ej),
  'certified_here':'rational implication and inverse/Neumann margin, not installed solver global FP/mode bound',
  'remaining':['certify actual floating A perturbation and independent eta over future source domain','prove no contact/other constraints and bounded body/free states','include finite arithmetic of filter and joint/body geometry']}

def a4():
 p=ROOT/'data/p10-20261025-a4/contract-counterexample-final/counterexample.json';x=json.load(open(p));w=[F(t) for t in x['per_step_w_p_v_q']];h=F(1,250)
 # If BOTH actual and nominal p/v used a common trapezoid integrator, their
 # additive innovations must satisfy wp=h*wv/2 (when acceleration/q residual
 # enters v before p). The old vector violates this relation.
 mismatch=w[0]-h*w[1]/2
 return {'original_sha256':sha(p),'w_p_v_q':list(map(float,w)),'trapezoid_position_velocity_defect':float(mismatch),'nonzero_exact_defect':str(mismatch),
  'conditional_exclusion':'excluded ONLY by the hypothetical common trapezoidal p/v innovation contract wp=h*wv/2, zero integration/measurement defect',
  'actual_exclusion':'NOT_PROVEN_EXCLUDED','why':'real A4 residual is LP/held-estimator minus a proxy, not two identical trapezoid physical states. Cache holds, EKF correction and native words can contribute position innovation. Need a certified joint measurement/dynamics defect bound smaller than this mismatch while including every real record, including native plateaus. No sampled absence is exclusion.'}

def main():
 out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);P=dict(np.load(ROOT/'data/p13-20261026-freeze/models/policy.npz'));results=[]
 for r in [1e-6,.001]:
  for box in [False,True]:
   x=attempt(P,r,box);results.append(x);print('FINITE_JOINT',r,box,x['rows'][-1] if x['rows'] else x,flush=True)
 write(out/'joint-attempt.json',{'schema':'p14-shared-generator-finite-feedback-1','results':results,'predeclared_steps':[1,2,4,8,16],
  'real_math':'product affine remainder bounded by rx*ry; analytic sigmoid second derivative <=.1, tanh <=1; exact ReLU secant-strip; same generators propagated through mean/count/GRU/output/filter/vertical force and capture',
  'roundoff_scope':'IEEE dot/add/multiply gamma_n plus 1e-14 libm hypothesis; not an independently verified interval libm or DART FP certificate',
  'conditions':'level fixed attitude, zero angular input, 1D positive speed1.8 capture/decel2, vertical source force/COM, nominal sample/cache phase, exact joint-to-filter relation/no drag/contact. A nonempty mathematical reduced feedback model, not an invariant subset of Gazebo flight',
  'first_missing_actual_connection':'angular state and estimator/cache dynamics, source solver/FP/joint residual; conditioning fixed attitude does not prove full controller can hold it',
  'not_sampling_Jacobians':True,'actual_record_coverage':False,'not_full_event_safety':True,'no_post_result_search':True})
 write(out/'servo-budget.json',source_budget());write(out/'A4-compatibility.json',a4())
if __name__=='__main__':main()

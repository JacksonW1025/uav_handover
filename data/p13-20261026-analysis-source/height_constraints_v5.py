"""Conditional source-actuator all-prefix height constraints, not a risk scorer.

All numeric budgets are antecedents. No observed maximum is substituted into a
future residual bound. mpmath interval arithmetic encloses the finite sums.
"""
import json,sys,math
from pathlib import Path
import mpmath as mp
mp.iv.dps=45
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p9_model import write
iv=mp.iv

def low(x):return math.nextafter(float(x.a),-math.inf)
def high(x):return math.nextafter(float(x.b),math.inf)
def interval(x):return iv.mpf(x) if isinstance(x,float) else iv.mpf(str(x))

def motor_necessary_reserve(W0,filters,T=.4,Vrel=12,Ej=1,epsilon_p=0.,first_command=None,a_discrete_extra=0.):
 dt=iv.mpf(1)/250;alpha=iv.exp(-dt/(iv.mpf(1)/80));mass=iv.mpf('2.0643076923076924');k=iv.mpf('0.00000854858');cd=iv.mpf('0.0000806428');g=iv.mpf('9.8');state=[interval(v) for v in filters];w=interval(W0);L=iv.mpf(0);rows=[];best=0.;bestrow=None
 for j in range(int(math.floor(T/.004+1e-12))):
  # Force precedes filter update, and even the best future controller is limited.
  om=[x+interval(Ej) for x in state];up=(sum(k*x*x for x in om)+sum(cd*x*interval(Vrel) for x in om))/mass-g+interval(a_discrete_extra)
  w=w-up*dt;L=L+w*dt-interval(epsilon_p);lo=low(L)
  rows.append({'physics_prefix_steps':j+1,'time_s':(j+1)*.004,'filter_upper_rad_s':[high(x) for x in state],'upward_acceleration_upper_m_s2':high(up),'down_velocity_lower_m_s':low(w),'COM_additional_loss_lower_m':lo})
  if lo>best:best=lo;bestrow=j+1
  command=[1000]*4 if j or first_command is None else first_command
  state=[interval(c)+(x-interval(c))*alpha for x,c in zip(state,command)]
 return {'schema':'p13-source-motor-necessary-reserve-5','inputs':{'W0_m_s':W0,'filters_rad_s':filters,'horizon_s':T,'represented_complete_physics_steps':int(math.floor(T/.004+1e-12)),'horizon_scope':'complete discrete physics prefixes within T; partial last step and continuous intersample extrema require separate budgets','Vrel_bound_m_s':Vrel,'joint_filter_and_filter_numeric_error_bound_rad_s':Ej,'position_residual_bound_per_step_m':epsilon_p,'source_discrete_upward_acceleration_extra_budget_m_s2':a_discrete_extra,'first_selected_command':first_command},'necessary_additional_COM_margin_lower_m':best,'critical_prefix_steps':bestrow,'prefixes':rows,'meaning':'any source-airborne trajectory satisfying antecedent bounds requires at least this COM reserve, regardless NN/event/native-clock word. Passing this necessary test is not safety.','antecedents':['true physical initial COM W/filter and joint relation','same physical dt and force-before-filter ordering','commands<=1000; upper filter exponential source map incl declared numeric error through Ej','actual scaled joint<=ideal maximal filter+Ej at all steps; Ej includes solver AND floating filter propagation discrepancies, no empirical bound inferred','relative air-link speed<=Vrel; no contact/other upward external force','FreeJoint COM velocity extra acceleration <=a_discrete_extra and position discrepancy<=epsilon_p; source nominal geometric budgets can be derived analytically; additional FP/joint budgets unproved, no sample maxima used'],'interval_numerics':'mpmath interval arithmetic45digits for exp/rational finite sums; interval theorem is for stated real-source/error-budget model, not certification of C++ libm or DART finite arithmetic'}

def sufficient_recovery(L0,D0,W0,T,ar):
 if ar<=0:raise ValueError('certified whole-interval ar must be positive')
 s=min(T,max(0,W0/ar));peak=max(0,W0*s-.5*ar*s*s);end=L0+W0*T-.5*ar*T*T
 return {'L_end_upper_m':end,'W_end_upper_m_s':W0-ar*T,'D_upper_m':max(D0,L0+peak),'whole_interval_additional_loss_upper_m':peak,'time_to_nonpositive_W_upper_s':max(0,W0/ar),'assumption':'actual net upward acceleration>=ar over entire hold/resume/recovery segment; not same as RTDEC, not established by sampled success','source_sufficient_not_necessary':True}

def required_joint_floor(ar,theta_deg,Vrel,Omega_max=1000):
 mass=2.0643076923076924;k=8.54858e-6;cd=8.06428e-5;theta=math.radians(theta_deg);drag=4*cd*Omega_max*Vrel*math.sin(theta)
 return math.sqrt((mass*(9.8+ar)+drag)/(4*k*math.cos(theta)))

if __name__=='__main__':
 out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);scenarios=[]
 for W in [.2,.5,.98,1.4]:
  for speed in [700,750,850]:
   env=json.load(open(R/'data/p13-20261026-theory/source-envelope-v1/envelope.json'));r=motor_necessary_reserve(W,[speed]*4,epsilon_p=env['COM_semimplicit_position_geometry_remainder_upper_m_per_step'],a_discrete_extra=env['COM_discrete_upward_acceleration_extra_upper_m_s2']);name=f'W{W}-filter{speed}';write(out/(name+'.json'),r);scenarios.append({'case':name,'W0':W,'filter':speed,'necessary_COM_margin_lower_m':r['necessary_additional_COM_margin_lower_m'],'prefix_s':r['critical_prefix_steps']*.004 if r['critical_prefix_steps'] else 0})
 floors=[{'ar_m_s2':a,'theta_max_deg':th,'Vrel_bound_m_s':2,'necessary_joint_floor_for_sufficient_ar_rad_s':required_joint_floor(a,th,2),'filter_floor_if_Ej1_rad_s':required_joint_floor(a,th,2)+1,'future_conditions_certified':False} for a in [.5,1.,2.] for th in [15,20,30]]
 recovery=[{'T_s':T,**sufficient_recovery(.4,.5,.98,T,1)} for T in [.55,1.2,2.]]
 # Distinguish irreversible historic failure from recovered current altitude.
 counter={'same_current_L_and_W':{'L':.1,'W':0},'different_past_D':[.8,1.2],'second_history_already_failed_even_if_H_recovered':True,'same_tilt_peak_can_have_different_integrated_descent':'acceleration/timing/history determine integral, peak angle alone insufficient'}
 write(out/'summary.json',{'schema':'p13-height-constraint-results-5','source_constants_only':True,'formal_results_used_for_budgets':False,'necessary_scenarios':scenarios,'sufficient_joint_floor_conditions':floors,'conditional_Aresume_to_B_examples':recovery,'counterexample':counter,'status':'COMPUTABLE_CONDITIONAL_SOURCE_RELATIONS; NO_COMPLETE_NEURAL_EKF_SOLVER_CERTIFICATE','joint_filter_error_Ej1':'candidate antecedent only, no empirical maximum promoted','COM_to_LP_extension':'DeltaL_LP=DeltaL_COM+DeltaG_COM_to_PX4body-Deltae_EKF_cache. Use sourcebase/body/IMUoffset and~.001869COMlever, notautomaticallynamedGazeboorigin.241869. Namedoriginphysicaldiagnostic remainsseparate. Futuregeometry/estimator/cachebudgetsrequired; noactualLPcertificate.','A4':'NOT_PROVEN_EXCLUDED'})
 print('NECESSARY',[(s['case'],round(s['necessary_COM_margin_lower_m'],5)) for s in scenarios]);print('FLOOR1_20',required_joint_floor(1,20,2))

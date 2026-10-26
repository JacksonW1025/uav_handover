#!/usr/bin/env python3
"""Exact source-parameter servo inverse and all-prefix height composition; no fitted bounds."""
from fractions import Fraction as F
from pathlib import Path
import json,sys,math,importlib.util
R=Path(__file__).resolve().parents[2]
sp=importlib.util.spec_from_file_location('domain',Path(__file__).with_name('finite_execution_domain.py'));domain=importlib.util.module_from_spec(sp);sp.loader.exec_module(domain)

def flow(L,W,D,T,a):
 L,W,D,T,a=map(F,[L,W,D,T,a]);v=[L,L+W*T+a*T*T/2]
 if a and 0<-W/a<T:v.append(L-W*W/(2*a))
 return L+W*T+a*T*T/2,W+a*T,max(D,*v)

def recovery_requirement(W,guaranteed_up_a):
 W=F(W);a=F(guaranteed_up_a)
 if W<=0:return F(0),F(0)
 if a<=0:raise ValueError('no guaranteed stopping/recovery bound')
 return W/a,W*W/(2*a)

def main(out):
 if out.exists():raise FileExistsError(out)
 d=domain.source_domain();Ir=F(d['rotor_Izz_kg_m2_exact']);kap=F(1)/F(d['yaw_free_effective_inertia_exact']);c=F('1e-9');alpha=1/Ir;D=alpha+kap;diagonal=alpha+c*D;beta=kap/(diagonal*(diagonal+4*kap));assert kap/diagonal-beta*diagonal-4*kap*beta==0
 gamma=c*D/diagonal;state=(F(0),F(0),F(0));rows=[]
 modes=[('A_pre_timeout',F('.2'),F('2.45')),('A_capture',F(0),F(0)),('A_hold',F('.16'),F('2.45')),('A_resume',F(0),F(0)),('A_recovery_until_B',F('.55'),F('-1.1025')),('B_pre_timeout',F('.2'),F('2.45')),('B_capture',F(0),F(0)),('B_hold',F('.16'),F('2.45')),('B_resume',F(0),F(0)),('B_recovery',F('.8'),F('-1.1025')),('full_tail',F(1),F(0))]
 for name,T,a in modes:
  state=flow(*state,T,a);L,W,H=state;rows.append({'mode':name,'T_s':float(T),'a_down_m_s2':float(a),'L_m':float(L),'W_down_m_s':float(W),'D_m':float(H),'ever_height_failed':H>1,'not_reset_at_capture_resume':True})
 tstop,loss=recovery_requirement(F('.98'),F(1));mass=d['source_domain']['mass'] if 'source_domain' in d else 2.0643076923076924;drag=4*1000*8.06428e-5*2;fmin=1+math.sqrt((mass*(9.8+1)+drag)/(math.cos(math.radians(20))*4*8.54858e-6));doc={'schema':'p12c-source-servo-and-height-maps-1','servo_exact_real_arithmetic':{'A':'d I4 + kappa11T, d=1/Ir+c*(1/Ir+kappa)','inverse':'A^-1 = I4/d - kappa11T/[d(d+4kappa)]','inverse_identity_exact_rational':True,'global_domain_increment':'||delta_lambda||2 <= ||delta_b||2/d; ||delta(vpost-u)||2 <= gamma*(||delta_u||2+||delta_vfree||2), same fixed noncontact SERVO mode; numeric eta/DeltaA terms separate','gamma':float(gamma),'CFM_scaled_uniform_error_bound_rad_s':d['uniform_source_conditional_bounds']['joint_scaled_error_l2_rad_s_CFMonly'],'floating_numeric_error':'NOT_CERTIFIED_FOR_ALL_FUTURE; posthoc verification alone not future bound','state_domain':d['finite_working_domain']},'height_flow':'L+=W*T+integral(T-s)*a_down(s)ds+integration/geometry; W+=integral a_down; D=max(D,sup all L prefixes); physical capture/resume has no L/W reset','source_incremental_acceleration':'|delta_a_down| <= Tbar/m*||delta_n|| + 2*k*OmegaBar/m*sum|delta_Omega_i| + E_drag/m; E_drag <= cd*(Vbar*sum|delta_Omega| + OmegaBar*sum||delta_v_link|| +2*N*OmegaBar*Vbar*||delta_n||); v_link=v_origin+R(omega cross r_i)-wind. Physical time/cache and numerical defects must be separate.','capture_history':'reference capture jointly copies p/v, hidden/previous/mean/count updates follow actual output/GRU mode word; cannot replace by independent free reference or assume isolatedGRU contraction','whole_hold_nonclipping_condition':'given capture input errors Ep0/Ev0 and actual a_body-a_ref sup Ares, Ev(t)<=Ev0+t*Ares and Ep(t)<=Ep0+t*Ev0+.5*t^2*Ares. Require ALL hold prefixes below original per-axis clip1m/s/.5m; resume adds actual planned external-reference jump bound; does NOT itself ensure tilt/height safety.','B_before_sufficient_condition':'D_B<=1 and L_B+max_{0<=s<=T_B}(W_B*s+.5*a_bar*s^2)+geometry/integration_budget<=1; check endpoints AND interior vertex, no reset; conditions require actual remaining event/tail duration and source force/attitude domains','recovery_example':{'initial_down_m_s':.98,'guaranteed_up_acc_m_s2':1,'stop_time_upper_s':float(tstop),'sufficient_height_reserve_m':float(loss),'floor_for_each_filter_rad_s':fmin,'conditions':'theta<=20deg, Ej<=1rad/s, link relative airspeed<=2m/s, Omega<=1000rad/s, source mass/thrust/drag constants, whole recovery duration; NOT proven maintained by actual NN or actual cache/physics','not_necessary_minimum':'reserve is sufficient under guaranteed minimum up-acc, not a proven necessary bound; max available acceleration would give necessary stopping-distance bound'},'counterexample_full_segment':rows,'counterexample_scope':'same17deg tilt peak declared mechanical/kinematic envelope, exact rational heights; no proven NN/Gazebo reachability, no A4 exclusion','first_missing_for_actual_whole_sequence':['future DeltaA/eta and source-domain invariance for installed FP solver','physical COM initial W/sample-time set: pose callback stamps arrival hrt and differentiates with clipped dt, discards original pose physical time','body angular/drag/EKF/cache feedback domain over entire sequence; mode durations from allowed dual-clock words, not constant4ms controller map'],'actual_record_certificate':'NOT_PROVEN','new_model_or_fit':False,'new_SITL':0,'A4':'NOT_PROVEN_EXCLUDED'};out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(doc,indent=2)+'\n');print('MAPS',float(gamma),float(loss),fmin,'lastD',rows[-1]['D_m'])
if __name__=='__main__':main(Path(sys.argv[1]))

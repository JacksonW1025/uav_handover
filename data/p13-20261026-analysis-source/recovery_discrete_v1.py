"""Conditional source-discrete recovery and all recorded-prefix margin map.
No actual future solver/cache/NN reachability is inferred from these examples.
"""
import sys,json,math
from fractions import Fraction as F
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'));from p9_model import write

def bound(L0,D0,W0,ar,T,ep=0,h=.004):
 L0,D0,W0,ar,T,ep,h=map(lambda x:F(str(x)),[L0,D0,W0,ar,T,ep,h]);N=int(T//h)
 if ar<=0:raise ValueError('ar must be a certified whole-segment positive effective upward acceleration bound')
 # W_j<=W0-j h ar; L_j<=L0+j h W0-ar h² j(j+1)/2+j ep.
 q=lambda j:L0+j*h*W0-ar*h*h*j*(j+1)/2+j*ep
 jstar=(h*W0+ep)/(ar*h*h)-F(1,2);js={0,N,max(0,min(N,math.floor(jstar))),max(0,min(N,math.ceil(jstar)))};peak=max(q(j) for j in js);critical=max(js,key=q)
 return {'represented_steps':N,'represented_duration_s':float(N*h),'W_end_upper_m_s':float(W0-N*h*ar),'L_end_upper_m':float(q(N)),'D_upper_m':float(max(D0,peak)),'critical_prefix_step':critical,'whole_recorded_prefix_additional_loss_upper_m':float(max(F(0),peak-L0)),'required_recorded_COM_margin_m':float(max(F(0),peak-L0)),'first_step_nonpositive_W':max(0,math.ceil(W0/(h*ar))),'assumptions':'each step W_next<=W-ar*h and L_next<=L+h*W_next+ep, same task0 baseline across capture/resume. ar includes force/attitude/solver/coordinate/numeric velocity budgets; ep covers position/joint/FP discrepancy. Conditions must hold whole segment. No continuous intersample invariant claim.'}

def selftest():
 checks=[]
 for W in [-.4,0,.2,.98,1.4]:
  for T in [.55,1.2,2.]:
   for ep in [0,.000003]:
    b=bound(.4,.5,W,1,T,ep);h=F(1,250);w=F(str(W));l=F('.4');d=F('.5')
    for j in range(b['represented_steps']):w-=h;l+=h*w+F(str(ep));d=max(d,l)
    assert abs(float(l)-b['L_end_upper_m'])<1e-14 and abs(float(w)-b['W_end_upper_m_s'])<1e-14 and abs(float(d)-b['D_upper_m'])<1e-14
    checks.append({'W':W,'T':T,'ep':ep,'exact_fraction_recurrence':'PASS'})
 return checks
if __name__=='__main__':
 out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);env=json.load(open(R/'data/p13-20261026-theory/source-envelope-v1/envelope.json'));ep=env['COM_semimplicit_position_geometry_remainder_upper_m_per_step'];rows=[{'planned_interval_s':T,**bound(.4,.5,.98,1,T,ep)} for T in [.55,1.2,2.]];tests=selftest();write(out/'map.json',{'schema':'p13-conditional-discrete-recovery-1','rows':rows,'source_geometric_ep_candidate':ep,'example_ar1_is_not_frozen_RTDEC2_or_certified_actual_NN_acceleration':True,'actual_additional_FP_and_joint_geometry_budget_missing':True,'continuous_recovery_formula_scope':'smooth ideal model separately; this map retains source-discrete position error explicitly','tests':tests,'formal_fit':False,'A4':'NOT_PROVEN_EXCLUDED','new_SITL':0});print('DISCRETE MAP',rows,'tests',len(tests))

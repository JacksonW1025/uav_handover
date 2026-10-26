#!/usr/bin/env python3
"""Future-input height balance diagnostic, never autonomous prediction or fitting."""
import json,sys,math
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p12c.features import load
from p12.execution import DTYPE
from p11.score import so3

def ctheta(q):return 1-2*(q[:,1]**2+q[:,2]**2)
def integrate(t,a,H0,W0):
 dt=np.diff(t);w=np.empty(len(t));h=np.empty(len(t));w[0]=W0;h[0]=H0
 for i in range(1,len(t)):
  avg=(a[i-1]+a[i])/2;h[i]=h[i-1]-w[i-1]*dt[i-1]-avg*dt[i-1]**2/2;w[i]=w[i-1]+avg*dt[i-1]
 return h,w

def diagnostic(parent,out):
 if out.exists():raise FileExistsError(out)
 out.mkdir(parents=True);a=parent/'analysis';run=parent/'run';d=load(run,a);plan=json.load(open(a/'packed/prediction-input.json'))['plan'];t=d['t'];end=plan['nominal_horizon_profile_s'];meas=json.load(open(a/'measured/measurement.json'));epoch=float(d['run_wall_ns'][0]-t[0]*1e9)
 if meas.get('failure'):end=min(end,(meas['failure']['monotonic_ns']-epoch)/1e9)
 sel=(t>=0)&(t<=end);t=t[sel];idx=np.flatnonzero(sel);mass=2.0643076923076924;r=.24186913101803548;Hz=-d['truth_pv'][sel,2];lpH=-d['position'][sel,2];qc=d['attitude'][sel];qt=d['truth_q'][sel];Hcom=Hz+r*ctheta(qt)
 # Raw force phase precedes filter update. Match last completed trace causally,
 # not value matching; exact full actuator streams stay local.
 thrust=[]
 for m in range(4):
  e=np.fromfile(run/f'gz-motor/execution-p12-{m}.bin',DTYPE);j=np.searchsorted(e['end_ns'],d['run_wall_ns'][sel],side='right')-1;assert (j>=0).all();thrust.append(e['thrust'][j])
 thrust=np.array(thrust).sum(axis=0);acf_truth=9.8-ctheta(qt)*thrust/mass;acf_cache=9.8-ctheta(qc)*thrust/mass
 # Finite difference estimates are held callback outputs, not direct physical W.
 Wmodel_fd=d['truth_pv'][sel,5];Wlp=d['velocity'][sel,2];geom_derivative=np.gradient(r*ctheta(qt),t);Wcom_fd=Wmodel_fd-geom_derivative
 result=[];arrays={'profile_s':t,'observed_H_model':Hz,'observed_H_COM_geometry':Hcom,'observed_H_LP':lpH,'observed_W_model_callback_difference':Wmodel_fd,'observed_W_LP':Wlp,'COM_geometry_derivative_estimate':geom_derivative,'source_vertical_acc_truth_attitude':acf_truth,'source_vertical_acc_controller_cache':acf_cache}
 for name,acc,W0 in [('truth_attitude_callback_W',acf_truth,float(Wcom_fd[0])),('cached_attitude_callback_W',acf_cache,float(Wcom_fd[0])),('truth_attitude_LP_W',acf_truth,float(Wlp[0]-geom_derivative[0]))]:
  H,W=integrate(t,acc,float(Hcom[0]),W0);Hmodel=H-r*ctheta(qt);arrays[name+'_H_model']=Hmodel;arrays[name+'_W_COM']=W;segments=[]
  for label,lo,hi in [('pre_A',0,plan['common_first_gap_profile_s']),('A_to_B',plan['common_first_gap_profile_s'],plan['full_source_windows_profile_s'][1][0]),('after_B',plan['full_source_windows_profile_s'][1][0],end)]:
   use=(t>=lo)&(t<=hi)
   if use.any():segments.append({'segment':label,'rows':int(use.sum()),'H_abs_error_max_m':float(abs(Hmodel[use]-Hz[use]).max()),'H_signed_end_error_m':float((Hmodel-Hz)[np.flatnonzero(use)[-1]])})
  result.append({'name':name,'initial_W_COM_estimate':W0,'segments':segments,'replacement':'actual future consumed-force trace and named attitude stream; one initial H/W only; no state resets after task0','limitations':'missing aerodynamic/other vertical force, discrete integration and asynchronous callback/force stages; initial W is finite-difference/LP estimate, not exact physical COM velocity; not causally attributed to solver or scored as forecast'})
 arrays['truth_cache_SO3_deg']=so3(qt,qc);np.savez_compressed(out/'full-arrays.npz',**arrays)
 b=plan['full_source_windows_profile_s'][1][0];j=max(0,int(np.searchsorted(t,b,side='right')-1));doc={'schema':'p12c-height-process-known-input-diagnostic-1','old_or_preparation_case':parent.name,'results':result,'B_before_at_common_absolute_time':{'profile_s':float(t[j]),'truth_H_model_m':float(Hz[j]),'LP_H_m':float(lpH[j]),'truth_LP_height_difference_m':float(Hz[j]-lpH[j]),'truth_callback_W_m_s':float(Wmodel_fd[j]),'LP_W_m_s':float(Wlp[j]),'COM_geometry_velocity_term_fd_m_s':float(geom_derivative[j]),'truth_cache_SO3_deg':float(arrays['truth_cache_SO3_deg'][j])},'H_geometry':'H_COM=H_model+ez R r; W_model=W_COM+ez R(omega_cross_r); FD geometry derivative is noisy/held estimate, not direct omega truth','scope':'diagnostic known future inputs, no fit/new candidate/forecast improvement; all prefixes retained, no height or D reset','gravity':9.8,'frozen_model_gravity_unchanged':9.80665,'new_SITL_starts':0};(out/'diagnostic.json').write_text(json.dumps(doc,indent=2)+'\n');print(parent.name,'B',doc['B_before_at_common_absolute_time'])
if __name__=='__main__':diagnostic(Path(sys.argv[1]),Path(sys.argv[2]))

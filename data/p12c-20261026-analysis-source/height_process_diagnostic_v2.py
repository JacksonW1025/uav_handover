#!/usr/bin/env python3
"""Physical-step aligned controlled height diagnostic; actual future inputs, not forecast."""
import json,sys
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p12c.features import load
from p12.execution import DTYPE
from p3_memory import rotation

def main(parent,out):
 if out.exists():raise FileExistsError(out)
 out.mkdir(parents=True);a=parent/'analysis';d=load(parent/'run',a);plan=json.load(open(a/'packed/prediction-input.json'))['plan'];m=json.load(open(a/'measured/measurement.json'));t=d['t'];epoch=float(d['run_wall_ns'][0]-t[0]*1e9);end=plan['nominal_horizon_profile_s']
 if m.get('failure'):end=min(end,(m['failure']['monotonic_ns']-epoch)/1e9)
 idx=np.flatnonzero((t>=0)&(t<=end));t=t[idx];sample=d['sample_us'][idx];physical=(sample.astype(np.float64)-sample[0])/1e6;dt=np.diff(physical);assert np.all(dt>0);H=-d['truth_pv'][idx,2];qt=d['truth_q'][idx];qc=d['attitude'][idx];omega=d['omega'][idx];vel=d['truth_pv'][idx,3:6];r=.24186913101803548;mass=2.0643076923076924;ct=lambda q:1-2*(q[:,1]**2+q[:,2]**2);geom=r*ct(qt);Hc=H+geom;geomdot=np.gradient(geom,physical);Wfd=d['truth_pv'][idx,5];Wlp=d['velocity'][idx,2];forces=[];speeds=[];alignment=[]
 for motor in range(4):
  e=np.fromfile(parent/f'run/gz-motor/execution-p12-{motor}.bin',DTYPE);j=np.searchsorted(e['sim_us'],sample)
  assert (j<len(e)).all() and np.array_equal(e['sim_us'][j],sample)
  forces.append(e['thrust'][j]);speeds.append(e['scaled_joint'][j]);alignment.append({'motor':motor,'all_destination_sample_exact':True,'period':'force in row sim_us advances World pre(sim_us-4000) to post(sim_us), under checked4ms nominal World; held pose timestamps remain arrival-native, not physics sample stamps'})
 T=np.asarray(forces).sum(axis=0);speeds=np.asarray(speeds);arrays={'profile_s':t,'physics_relative_s':physical,'H_model_observed':H,'W_model_callback_difference':Wfd,'W_LP':Wlp,'geometry_derivative_fd':geomdot};reports=[]
 # NED/FRD rotor center vectors from named origin; gyro is cache, not direct world omega.
 pos=np.array([[.174,-.174,-.3],[-.174,.174,-.3],[.174,.174,-.3],[-.174,-.174,-.3]]) # direction only affects drag diagnostic; norm/order source checked below
 import xml.etree.ElementTree as X
 model=X.parse(R/'uav_lab/.local/checkouts/px4-raptor/Tools/simulation/gz/models/x500_base/model.sdf').getroot().find('model')
 for motor in range(4):
  p0=np.array([float(x) for x in next(x for x in model.findall('link') if x.attrib['name']==f'rotor_{motor}').findtext('pose').split()[:3]]);p0[2]+=.24;pos[motor]=p0*np.array([1,-1,-1])
 for label,q,with_drag,initial in [('truth_pose_force',qt,False,'callback'),('cached_attitude_force',qc,False,'callback'),('truth_pose_approx_drag',qt,True,'callback'),('truth_pose_approx_drag_LP_initial',qt,True,'LP')]:
  acc=np.zeros(len(t));drag=np.zeros(len(t));
  for k in range(1,len(t)):
   M=rotation(q[k-1]).reshape(3,3);axis=M[:,2]
   if with_drag:
    F=np.zeros(3)
    for motor in range(4):
     vr=vel[k-1]+M@np.cross(omega[k-1],pos[motor]);perp=vr-np.dot(vr,axis)*axis;F-=abs(speeds[motor,k])*8.06428e-5*perp
    drag[k]=F[2]/mass
   acc[k]=9.8-M[2,2]*T[k]/mass+drag[k]
  for mode in ['continuous_constant_acc','semiimplicit_position']:
   hc=np.empty(len(t));wc=np.empty(len(t));hc[0]=Hc[0];wc[0]=(Wfd[0] if initial=='callback' else Wlp[0])-geomdot[0]
   for k in range(1,len(t)):
    wc[k]=wc[k-1]+acc[k]*dt[k-1];hc[k]=hc[k-1]-(wc[k] if mode=='semiimplicit_position' else (wc[k]+wc[k-1])/2)*dt[k-1]
   hm=hc-geom;name=label+'_'+mode;arrays[name+'_H_model']=hm;arrays[name+'_W_COM']=wc;segments=[]
   for seg,lo,hi in [('pre_A',0,plan['common_first_gap_profile_s']),('A_resume_to_B',plan['common_first_gap_profile_s'],plan['full_source_windows_profile_s'][1][0]),('B_and_full_tail',plan['full_source_windows_profile_s'][1][0],end)]:
    use=(t>=lo)&(t<=hi)
    if use.any():segments.append({'segment':seg,'rows':int(use.sum()),'H_error_max_m':float(abs(hm[use]-H[use]).max()),'H_signed_end_error_m':float((hm-H)[np.flatnonzero(use)[-1]])})
   reports.append({'variant':name,'segments':segments,'initial_COM_W_estimate':float(wc[0]),'controlled_replacements':{'actual_future_T':True,'attitude_stream':label.split('_force')[0],'approx_drag_from_actual_future_held_v_and_cached_gyro':with_drag,'initial_W_source':initial,'after_initial_state_reset':False},'scope':'diagnostic conditional balance, no new candidate or fitting, not autonomous score; force/IMU destination physics-step alignment exact, pose physical sample time lost at native-stamped callback; drag is reconstructed approximation not direct vector, numerical integration not certified'})
 np.savez_compressed(out/'full-arrays.npz',**arrays);(out/'diagnostic.json').write_text(json.dumps({'schema':'p12c-height-process-diagnostic-2','case':parent.name,'alignment':alignment,'results':reports,'W_truth_source':'poseInfoCallback finite difference of poses divided by clipped native-arrival dt[.001,.1]s; not direct physical velocity; pose physical header time not retained','geometry':'H_COM=H_model+rR33; W_COM=W_model-d(rR33)/dt, includes source/timing uncertainty','future_certificate':False,'autonomous_prediction':False,'new_SITL_starts':0},indent=2)+'\n');print(parent.name,[(x['variant'],x['segments'][-1]['H_error_max_m']) for x in reports])
if __name__=='__main__':main(Path(sys.argv[1]),Path(sys.argv[2]))

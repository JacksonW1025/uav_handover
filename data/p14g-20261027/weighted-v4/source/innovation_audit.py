"""Future-actual fusion residuals ONLY to falsify assumptions on scoring side.
No fit/update of the autonomous candidate, no empirical max made a future bound.
"""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from scipy.spatial.transform import Rotation
from p14g.common import *
from p14r.observer import read,FUSION
from p14r.op import Op
from p13.physics import read as pread,BODY,rot
from p13.physical_model import S,B as BODYB
from p14_motion.core import LEVER,mul,conjugate
from p14g.observer import qexp

def main():
 out=Path(sys.argv[1]);register(out,'actualfuture scoring-only check of held/fading residual budget conditions, no parameter updates');limit(20);rows=[];bud=protocol()['C']['parameter_boxes']['small']
 for n,c in cases().items():
  d=json.load(open(B/'inputs-v1'/n/'input.json'));i=d['initial'];cut=i['observer']['cutoff_wall_ns'];m=i['p14g_innovation'];run=R/c['raw_run'];f,_=read(run/'gz-motor/observer-fusion.bin',FUSION,b'P14RFUS1',True);f=f[(f['core']['kind']==4)&(f['core']['wall_ns']>cut)];body,_=pread(run/'gz-motor/physics-p13-body.bin',BODY,b'P13BODY1');body=body[(body['phase']==1)&(body['valid']==63)];lookup={int(x['sim_ns']//1000):x for x in body};op=Op(OLD/'offline-build-v2/libop.bin',i['observer']);series={'held':[],'fading':[]}
  for row in f:
   r=row['core'];st=int(r['sample_us']);t=i['profile_s']+(int(r['ids'][0])-i['sample_us'])*1e-6
   if t>d['plan']['horizon_profile_s']:break
   if st not in lookup:continue
   x=lookup[st];M=S@rot(x['base_q'][None,:])[0]@BODYB;q=Rotation.from_matrix(M).as_quat()[[3,0,1,2]];w=M.T@S@x['base_omega'];p=S@x['com_p']+M@LEVER;v=S@x['com_v']+M@np.cross(w,LEVER);align=mul(r['data'][64:68],conjugate(q));ev=r['data'][68:71]-v;ep=op.sub(r['geo'][3:6],op.add(i['observer_parameters']['world_geo'],p));dt=max(0,(st-m['past_delayed_sample_us'])*1e-6);amp=m['tau_s']*(1-np.exp(-dt/m['tau_s']))
   for mode in series:
    a=np.array(i['observer_parameters']['fusion_attitude_alignment']);vv=np.array(i['observer_parameters']['fusion_velocity_error']);pp=np.array(i['observer_parameters']['fusion_position_error_NED'])
    if mode=='fading':a=mul(qexp(amp*np.array(m['rates']['theta'])),a);vv+=amp*np.array(m['rates']['velocity']);pp+=amp*np.array(m['rates']['position'])
    e=mul(align,conjugate(a));theta=Rotation.from_quat(e[[1,2,3,0]]).as_rotvec();error=[float(max(abs(theta))),float(max(abs(ev-vv))),float(max(abs(ep-pp)))];over=any(x>r for x,r in zip(error,[bud['theta_rad'],bud['velocity_m_s'],bud['position_m']]));series[mode].append({'t':t,'max_component_theta_v_p':error,'outside_small_innovation_box':over})
  summary={}
  for mode,z in series.items():summary[mode]={'rows':len(z),'first_outside':next((r for r in z if r['outside_small_innovation_box']),None),'fraction_inside':float(np.mean([not r['outside_small_innovation_box'] for r in z])) if z else None,'empirical_max_not_bound':np.max([r['max_component_theta_v_p'] for r in z],axis=0).tolist() if z else None}
  write(out/(n+'.json'),series);rows.append({'id':n,'models':summary});op.close()
 write(out/'summary.json',{'rows':rows,'future_input_role':'diagnostic assumption check only; no predictor refit or relabeling','interpretation':'smallconditional budgets mayfail actualrecords; source OP correction/integrals do not certify external EKFinnovation. A failing budget invalidates actualcoverage claims, nottheinternalconditional real-map algebra.'})
if __name__=='__main__':main()

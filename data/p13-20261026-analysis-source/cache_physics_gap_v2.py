from analysis_paths_v1 import analysis_dir
"""Actual cache/physical gap and frozen M5 offset/kinematic diagnostics only."""
import sys,json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p13.physics import read,BODY,rot
from p13.physical_model import S,B
from p11.models import R as matrix
from p12c.features import load
from p9_model import write,sha

def stat(v):
 a=np.asarray(v);return {'min':float(a.min()),'max':float(a.max()),'RMS':float(np.sqrt(np.mean(a*a)))}
def create(target,out):
 out.mkdir(parents=True,exist_ok=False);a=analysis_dir(target);d=load(target/'run',a);doc=json.load(open(a/'packed-physical/prediction-input.json'));ini=doc['initial'];end=min(json.load(open(a/'measured/measurement.json'))['observed_profile_end_s'],doc['plan']['nominal_horizon_profile_s']);ix=np.flatnonzero((d['t']>=0)&(d['t']<=end));b,_=read(target/'run/gz-motor/physics-p13-body.bin',BODY,b'P13BODY1');b=b[b['phase']==1];j=np.searchsorted(b['wall_ns'],d['run_wall_ns'][ix],side='right')-1;assert np.all(j>=0);p=b[j];originv=p['base_v']+np.cross(p['base_omega'],p['origin_p']-p['base_p']);dz=d['position'][ix,2]+p['origin_p'][:,2];dv=d['velocity'][ix,2]+originv[:,2];bodyR=S@rot(p['base_q'])@B;obsR=np.array([matrix(q) for q in d['attitude'][ix]]);rel=obsR@np.transpose(bodyR,(0,2,1));yaw=Rotation.from_matrix(rel).as_euler('xyz')[:,2];ang=np.linalg.norm(Rotation.from_matrix(rel).as_rotvec(),axis=1);wb=np.einsum('nji,nj->ni',bodyR,p['base_omega']@S.T);dw=np.linalg.norm(d['omega'][ix]-wb,axis=1);hostage=(d['run_wall_ns'][ix].astype(np.int64)-p['wall_ns'].astype(np.int64))/1000;sourceage=d['sample_us'][ix].astype(np.int64)-(p['sim_ns']//1000).astype(np.int64)
 offset=np.array(ini['COM_to_origin_body']);zb=ini['position'][2]-ini['physical_COM_p'][2]-(matrix(ini['attitude'])@offset)[2];vb=ini['velocity'][2]-ini['physical_COM_v'][2]-(matrix(ini['attitude'])@np.cross(ini['omega'],offset))[2];tr=np.load(a/'prediction/M5.npz')['trace'];kin=np.diff(tr[:,3])/np.diff(tr[:,0])-tr[1:,6]
 report={'schema':'p13-cache-physical-gap-1','id':target.name,'rows':len(ix),'physical_latest_past_host_age_us':stat(hostage),'source_sample_minus_physics_sample_us':stat(sourceage),'LP_z_minus_direct_origin_NED_z_m':stat(dz),'LP_z_bias_drift_from_first_m':stat(dz-dz[0]),'LP_W_minus_direct_origin_W_m_s':stat(dv),'LP_W_bias_drift_from_first_m_s':stat(dv-dv[0]),'LPatt_minus_direct_physical_SO3_deg':stat(np.degrees(ang)),'yaw_offset_deg':stat(np.degrees(yaw)),'gyro_filtered_vs_direct_body_omega_l2_rad_s':stat(dw),'M5_fixed_initial_z_bias_m':zb,'M5_fixed_initial_v_bias_m_s':vb,'M5_predicted_plant_finite_difference_minus_reported_W_m_s':stat(kin),'interpretation':'actual cache/physical states retain independent times, source transport and filtering; differences do not equal observer error at identical physical instant. M5 holds independent initial z/v offsets constant; nonzero finite-difference residual includes its fixed velocity offset and rotation geometry. This diagnoses model structure, not solver causality or corrected heldout performance.','new_parameters_or_refit':False,'raw_body_sha256':sha(target/'run/gz-motor/physics-p13-body.bin')}
 write(out/'gap.json',report);np.savez_compressed(out/'gaps.npz',t=d['t'][ix],LP_z_minus_origin_z=dz,LP_W_minus_origin_W=dv,yaw_offset_deg=np.degrees(yaw),gyro_difference_l2=dw,physical_host_age_us=hostage,source_physical_age_us=sourceage);return report
if __name__=='__main__':create(Path(sys.argv[1]),Path(sys.argv[2]))

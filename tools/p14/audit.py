"""Historic evidence inventory, original score audit, direct point/time checks."""
import sys,json,datetime
from pathlib import Path
import numpy as np
from pyulog import ULog
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p14.common import records,write,sha,OUT
from p13.physics import read,BODY,rot
from p13.physical_model import S,B
from p12c.features import load
from p11.models import R as matrix,tilt

def first(t,e,limit):
 j=np.flatnonzero(e>limit)
 return None if not len(j) else float(t[j[0]])

def main():
 out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);inputs={};rows=[]
 for doc in sorted((ROOT/'docs').glob('THOR_P1[123]*')):
  if doc.is_file():inputs[str(doc.relative_to(ROOT))]=sha(doc)
 for p in [ROOT/'docs/THOR_P10_A4_PROOF.md',ROOT/'docs/THOR_P10_A4_REPORT.md',ROOT/'config/p13-formal.json',ROOT/'data/p13-20261026-preparation/attempts.jsonl']:
  inputs[str(p.relative_to(ROOT))]=sha(p)
 for r in records():
  a=r['analysis'];run=r['target']/'run';doc=json.load(open(r['packed']/'prediction-input.json'));d=load(run,a)
  end=min(doc['plan']['nominal_horizon_profile_s'],json.load(open(r['measured']))['observed_profile_end_s'])
  use=(d['t']>=0)&(d['t']<=end);ii=np.flatnonzero(use);t=d['t'][use]
  b,h=read(run/'gz-motor/physics-p13-body.bin',BODY,b'P13BODY1');post=b[b['phase']==1];pre=b[b['phase']==0]
  j=np.searchsorted(post['wall_ns'],d['run_wall_ns'][ii],side='right')-1;assert np.all(j>=0);p=post[j]
  Q=S@rot(p['base_q'])@B;w=np.einsum('nji,nj->ni',Q,p['base_omega']@S.T)
  rigid_r=np.array([0.,0.,.00186913101803548]);pc=p['com_p']@S.T;vc=p['com_v']@S.T
  predicted_base=pc+np.einsum('nij,j->ni',Q,rigid_r)
  predicted_bv=vc+np.einsum('nij,nj->ni',Q,np.cross(w,rigid_r))
  # Residual is independently read base data, not set to zero by rigid map.
  ep=(p['base_p']@S.T)-predicted_base;ev=(p['base_v']@S.T)-predicted_bv
  dz=d['position'][ii,2]+p['base_p'][:,2];dv=d['velocity'][ii,2]+p['base_v'][:,2]
  relative=np.array([matrix(q) for q in d['attitude'][ii]])@np.transpose(Q,(0,2,1))
  angle=np.degrees(np.arccos(np.clip((np.trace(relative,axis1=1,axis2=2)-1)/2,-1,1)))
  u=ULog(str(run/'flight.ulg'));topics={x.name:x for x in u.data_list if x.multi_id==0}
  params={k:u.initial_parameters.get(k) for k in ['EKF2_TAU_POS','EKF2_TAU_VEL','EKF2_IMU_POS_X','EKF2_IMU_POS_Y','EKF2_IMU_POS_Z']}
  assert params['EKF2_TAU_POS']==.25 and params['EKF2_TAU_VEL']==.25
  selected=['sensor_combined','vehicle_imu','sensor_baro','sensor_gps','vehicle_magnetometer','estimator_states','estimator_odometry','vehicle_local_position','vehicle_attitude']
  raw=[run/'flight.ulg',run/'gz-motor/physics-p13-body.bin']+list((run/'gz-motor').glob('physics-p13-rotor-*.bin'))+[r['packed']/'prediction-input.json',a/'observation/synchronized.npz',a/'native/history.npz']
  raw+=list(r['prediction'].glob('*.npz'));raw+=[r['prediction']/'prediction.json']
  for f in raw:inputs[str(f.relative_to(ROOT))]=sha(f)
  stats=lambda v:{'min':float(np.min(v)),'max':float(np.max(v)),'RMSE':float(np.sqrt(np.mean(v*v)))}
  row={'id':r['id'],'group':r['group'],'rows':len(t),'end_s':end,'raw_available':True,'physical_header':h,
   'parameters':params,'source_point_map_joint_residual':{'position_max_m':float(np.max(np.linalg.norm(ep,axis=1))),'velocity_max_m_s':float(np.max(np.linalg.norm(ev,axis=1)))},
   'LP_minus_body_z_m':stats(dz),'LP_bias_z_drift_m':stats(dz-dz[0]),'LP_minus_body_W_m_s':stats(dv),'LP_bias_W_drift_m_s':stats(dv-dv[0]),'LP_vs_physical_SO3_deg':stats(angle),
   'first_obvious_cache_physical':{'velocity15cm_s':first(t,abs(dv-dv[0]),.15),'position10cm':first(t,abs(dz-dz[0]),.1),'SO3_2p5deg':first(t,angle,2.5)},
   'native_platform_edges':int(np.sum(np.diff(d['native_us'])==0)),
   'Post_next_Pre':{k:float(np.max(abs(post[k][:-1]-pre[k][1:]))) for k in ['com_p','com_v','base_q','base_omega']},
   'time_relation':bool(np.array_equal(pre['sim_ns'][1:]-post['sim_ns'][:-1],pre['dt_ns'][1:])),
   'sensor_topics':{k:{'rows':len(topics[k].data['timestamp']),'fields':list(topics[k].data)} if k in topics else None for k in selected},
   'complete_EKF_reconstruction':'NOT_IDENTIFIED: full cross covariance, ring buffers, fusion/reset state, output predictor tracking integrators and exact scheduling not snapshot; available raw IMU/baro/GPS/mag and estimator_states support conditioned replay, not autonomous future corrections'}
  write(out/r['id']/'state-time.json',row);rows.append({k:v for k,v in row.items() if k!='sensor_topics'})
  print('POINT_AUDIT',r['id'],flush=True)
 old=[]
 for p in sorted((ROOT/'data/p11-20261026-analysis').glob('*/score/score.json')):
  s=json.load(open(p));id=p.parent.parent.name;raw=ROOT/'data/p11-20261025-formal'/id/'run/flight.ulg';cfg=json.load(open(raw.parent/'config.json'))
  old.append({'id':id,'split':cfg['p11']['model_split'],'raw_available':raw.exists(),'raw_sha256':sha(raw),'score_sha256':sha(p),'M2':{k:s['models']['M2'][k] for k in ['risk_comparison','task_risk_comparison','peak_abs_error_deg','full_prediction','observed_censored']}})
 write(out/'p11-score-chain.json',old)
 inputs.update({str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'data').glob('p1*/attempts.jsonl')})
 for p in (ROOT/'data').glob('p1*-*preparation*/attempts.jsonl'):inputs[str(p.relative_to(ROOT))]=sha(p)
 write(out/'input-hashes.json',inputs);write(out/'summary.json',{'schema':'p14-inventory-1','rows':rows,'P11_raw_audited':len(old),'new_SITL':0,'originals_read_only':True})
if __name__=='__main__':main()

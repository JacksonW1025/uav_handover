"""Predicted original P0 joint recovery, using sealed trajectories only."""
import sys,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'));from recovery import recovery
from p9_model import write,sha

def create(target,out):
 out.mkdir(parents=True,exist_ok=False);a=target/'analysis-v1';doc=json.load(open(a/'packed-physical/prediction-input.json'));ini=doc['initial'];plan=doc['plan'];cfg=json.load(open(target/'run/config.json'))['joint_recovery'];obs=json.load(open(a/'measured/measurement.json'));meta=json.load(open(a/'prediction/prediction.json'));res={}
 for n,m in meta['models'].items():
  tr=np.load(a/f'prediction/{n}.npz')['trace'];ts=ini['sample_us']+np.arange(len(tr),dtype=np.int64)*4000;end=min(float(plan['nominal_horizon_profile_s']),float(tr[-1,0]));end_sample=int(ini['sample_us']+round((end-ini['profile_s'])*1e6));caps=[v for v in m['target_events'] if v['kind']=='CAPTURE' and ini['profile_s']+(v['sample_us']-ini['sample_us'])/1e6>=plan['stream_end_profile_s']];r={'status':'NOT_REACHED_BY_PREDICTION','source':'model final poststream capture, not actual future capture'}
  if caps:
   cap=int(caps[0]['sample_us']);idx=np.r_[True,((ts[1:]-ini['lp_phase_us'])%8000==0)];loc={'timestamp':ts[idx],**{k:tr[idx,j] for k,j in zip(['x','y','z','vx','vy','vz'],range(42,48))}};angular={'timestamp':ts,**{f'xyz[{j}]':tr[:,39+j] for j in range(3)}};tgt={'timestamp':ts,**{f'position[{j}]':tr[:,28+j] for j in range(3)}};rr=recovery(loc,angular,cfg,cap,end_sample,tgt)['joint_recovery'];r={'status':rr['status'],'time_after_predicted_final_capture_s':rr['time_s'],'predicted_final_capture_profile_s':ini['profile_s']+(cap-ini['sample_us'])/1e6,'recovery_result':rr,'predicted_source_clock':'sample physical grid, nominal independent native schedule retained; P13 nominal clocks coincide'}
  actual=obs['joint_recovery_after_final_capture'];r['observed_original_recovery']=actual;r['time_error_s']=r.get('time_after_predicted_final_capture_s')-actual['from_final_capture_s'] if r.get('status')=='SETTLED' and actual['status']=='SETTLED' and actual['from_final_capture_s'] is not None else None;res[n]=r
 write(out/'recovery-prediction.json',{'schema':'p13-recovery-prediction-1','id':target.name,'models':res,'scope':'original P0 .2m/.1m_s/.1rad_s continuous2s and20ms gap rule; nominal task terminal fixed before results, each model own predicted capture/target. Actual capture/recovery used only comparison. No truncation-to-success or future resets.','scores_unchanged':True,'source_sha256':sha(Path(__file__)),'new_SITL':0});return res
if __name__=='__main__':create(Path(sys.argv[1]),Path(sys.argv[2]))

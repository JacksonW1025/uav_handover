"""Retrospective point/physical/observer/cropping diagnostics, no parameter fit."""
import sys,json
from pathlib import Path
import numpy as np
from pyulog import ULog
from scipy.spatial.transform import Rotation
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'data/p13-20261026-analysis-source')]
from p14.common import write,sha,records
from p12c.features import load
from p12.score import score
from p14.evaluate import stages,stats,crossing
from p13.physics import read,BODY,rot
from p13.physical_model import S,B
from p11.models import R,tilt
from p14_motion.core import biquad,coeff
from source_discrete_kernel_v1 import audit as source_audit

def angles(q,r):
 return np.degrees(np.linalg.norm((Rotation.from_quat(q[:,[1,2,3,0]]).inv()*Rotation.from_quat(r[:,[1,2,3,0]])).as_rotvec(),axis=1))
def first(t,e,L):return crossing(t,np.asarray(e),L)
def episodes(t,flag):
 out=[];start=None
 for j,on in enumerate(flag):
  if on and start is None:start=j
  if start is not None and (not on or j==len(flag)-1):
   last=j-1 if not on else j;out.append({'enter_s':float(t[start]),'last_sample_s':float(t[last]),'duration_lower_s':float(t[last]-t[start]),'duration_upper_s':float(t[last]-t[start]+.004)});start=None
 return out

def main():
 out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);base=ROOT/'data/p14-motion-20261027';index=json.load(open(base/'inputs-v2/index.json'));rr={r['id']:r for r in records()};rows=[]
 for rec in index:
  id=rec['id'];r=rr[id];d=load(r['target']/'run',r['analysis']);doc=json.load(open(base/'inputs-v2'/id/'task-input.json'));end=min(doc['plan']['nominal_horizon_profile_s'],json.load(open(r['measured']))['observed_profile_end_s']);pred=base/'point-v1/predictions'/id
  sc=score(pred,r['packed'],r['measured'],out/id/'score');bo,_=read(r['target']/'run/gz-motor/physics-p13-body.bin',BODY,b'P13BODY1');bo=bo[bo['phase']==1];ix=np.flatnonzero((d['t']>=0)&(d['t']<=end));t=d['t'][ix];j=np.searchsorted(bo['wall_ns'],d['run_wall_ns'][ix],side='right')-1;real=bo[j];physQ=S@rot(real['base_q'])@B;pq=Rotation.from_matrix(physQ).as_quat()[:,[3,0,1,2]];pw=np.einsum('nji,nj->ni',physQ,real['base_omega']@S.T);window,ev=stages(d,doc['plan'],id,end);models={}
  for variant in sc['models']:
   z=np.load(pred/(variant+'.npz'));st=z['states'];tr=z['trace'];pt=tr[:,0];valid=t<=pt[-1];tt=t[valid];ii=ix[valid]
   interp=lambda x:np.column_stack([np.interp(tt,pt,x[:,k]) for k in range(x.shape[1])])
   sp=interp(st[:,:3]);sv=interp(st[:,3:6]);sq=interp(st[:,6:10]);sq/=np.linalg.norm(sq,axis=1)[:,None];sw=interp(st[:,10:13]);oq=interp(tr[:,48:52]);oq/=np.linalg.norm(oq,axis=1)[:,None]
   inp=interp(z['inputs']);realin=d['input'][ii];hidden=interp(tr[:,12:28]);action=interp(tr[:,8:12]);gyro=interp(tr[:,39:42]);lp=interp(tr[:,42:45]);lv=interp(tr[:,45:48])
   errs={'physical_p_m':np.linalg.norm(sp-real['com_p'][valid]@S.T,axis=1),'physical_v_m_s':np.linalg.norm(sv-real['com_v'][valid]@S.T,axis=1),'physical_SO3_deg':angles(sq,pq[valid]),'physical_omega_rad_s':np.linalg.norm(sw-pw[valid],axis=1),'LP_p_m':np.linalg.norm(lp-d['position'][ii],axis=1),'LP_v_m_s':np.linalg.norm(lv-d['velocity'][ii],axis=1),'att_cache_SO3_deg':angles(oq,d['attitude'][ii]),'gyro_cache_rad_s':np.linalg.norm(gyro-d['omega'][ii],axis=1),'input_l2':np.linalg.norm(inp-realin,axis=1),'h_l2':np.linalg.norm(hidden-d['h_after'][ii],axis=1),'action_l2':np.linalg.norm(action-d['action'][ii],axis=1)}
   lims={'physical_p_m':.1,'physical_v_m_s':.15,'physical_SO3_deg':2.5,'physical_omega_rad_s':.1,'LP_p_m':.1,'LP_v_m_s':.15,'att_cache_SO3_deg':2.5,'gyro_cache_rad_s':.1,'input_l2':.1,'h_l2':.5,'action_l2':.1}
   # First row inputs are intentionally undefined; start at first finite row.
   good=np.all(np.isfinite(inp),axis=1);summ={k:stats(v[good]) for k,v in errs.items()};fst={k:first(tt[good],v[good],lims[k]) for k,v in errs.items()}
   source_alignment={'profile_offset_range_s':[float(min(pt[0]-doc['initial']['profile_s'],0)),0.],'note':'same absolute task time, no optimized shift; physical latestPast and cache age distinct'}
   stage={k:{'window':w,'errors':{e:stats(v[(tt>=w[0])&(tt<w[1])&good]) for e,v in errs.items()}} for k,w in window.items()}
   models[variant]={'errors':summ,'first':fst,'stages':stage,'score':sc['models'][variant],'alignment':source_alignment}
  # Source physical audit with actual future selected commands; separate output.
  a=source_audit(r['target'],out/id/'known-command-source',open_replay=True)
  arrays=np.load(out/id/'known-command-source/arrays.npz');op=arrays['known_command_open'];ot=arrays['profile_s'][:len(op)];n=len(op)
  oe={'p_m':np.linalg.norm(op[:,:3]-arrays['COM_p_post'][:n],axis=1),'v_m_s':np.linalg.norm(op[:,3:6]-arrays['COM_v_post'][:n],axis=1),'SO3_deg':angles(op[:,6:10],arrays['body_q_post'][:n])}
  a['first_obvious']={k:first(ot,v,L) for (k,v),L in zip(oe.items(),[.1,.15,2.5])}
  gyro_report=gyro_diagnostic(r['target']/'run',d)
  row={'id':id,'models':models,'known_command':a,'raw_gyro_reconstruction':gyro_report,'actual_stage_events':ev,'score_interpretation':'all retrospective,4 fixed cases; source gyro/raw future inputs only in diagnostic below, not autonomous predictions'}
  write(out/id/'analysis.json',row);rows.append(row);print('ANALYZED_FIXED',id,flush=True)
 write(out/'summary.json',rows)

def gyro_diagnostic(run,d):
 u=ULog(str(run/'flight.ulg'),['sensor_gyro','estimator_sensor_bias','research_angular_velocity']);topics={x.name:x.data for x in u.data_list if x.multi_id==0};raw=topics['sensor_gyro'];g=np.column_stack([raw[k] for k in ['x','y','z']]);b0,b1,b2,a1,a2=coeff();d1=g[0]/(1+a1+a2);d2=d1.copy();vals=[]
 for x in g:y,d1,d2=biquad(x,d1,d2);vals.append(y.copy())
 vals=np.array(vals);bias=topics.get('estimator_sensor_bias');correct=np.zeros_like(vals)
 if bias is not None:
  jj=np.searchsorted(bias['timestamp'],raw['timestamp'],side='right')-1;v=jj>=0;correct[v]=np.column_stack([bias[f'gyro_bias[{k}]'][jj[v]] for k in range(3)])
 off=np.array([u.initial_parameters.get('CAL_GYRO0_'+a+'OFF',0.) for a in ['X','Y','Z']]);scale=np.array([u.initial_parameters.get('CAL_GYRO0_'+a+'SCALE',1.) for a in ['X','Y','Z']]);vals=(vals-off)*scale-correct;unfiltered=(g-off)*scale-correct
 jj=np.searchsorted(raw['timestamp_sample'],d['sample_us']);ok=(jj<len(raw['timestamp_sample']));ii=np.flatnonzero(ok);jj=jj[ok];hit=raw['timestamp_sample'][jj]==d['sample_us'][ii];ii=ii[hit];jj=jj[hit]
 use=d['t'][ii]>=0;ii=ii[use];jj=jj[use];e=np.linalg.norm(vals[jj]-d['omega'][ii],axis=1);eu=np.linalg.norm(unfiltered[jj]-d['omega'][ii],axis=1)
 return {'rows':len(e),'filtered_error_rad_s':stats(e),'unfiltered_error_rad_s':stats(eu),'future_diagnostic_inputs':'raw sensor gyro and currently logged estimated bias, exact sample ID. No future pose injection. Startup biquadsteady seed; no unlogged reset/device-selection reconstruction certified.','source_filter':'two-pole250Hz40Hz; DNF_EN0/NFfreq0; FFT_ENalone does not activate dynamicnotch','calibration':'board/device rotation assumed sourceparams recorded; actual matching diagnosed, not complete EKF replay'}

if __name__=='__main__':main()

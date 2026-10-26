"""All three target-frame axes over full actual hold; no clipping/censor omission."""
import sys,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p12c.features import load
from p9_model import write,sha

def create(target,event_json,out):
 out.mkdir(parents=True,exist_ok=False);d=load(target/'run',target/'analysis-v1');events=json.load(open(event_json));rows=[]
 for e in events['events']:
  if e.get('status')!='CAPTURE_REACHED':rows.append({'event':e['label'],'status':e['status']});continue
  start=e['capture_profile_s'];end=e.get('resume_profile_s',events['valid_end_s']);caprow=next(x for x in events['rows'] if x['label']==e['label']+'_capture');capsample=int(caprow['witness']['sample_us']);j=int(np.searchsorted(d['sample_us'],capsample));assert j<len(d['sample_us']) and int(d['sample_us'][j])==capsample;resrow=next(x for x in events['rows'] if x['label']==e['label']+'_resume');stopidx=int(np.searchsorted(d['sample_us'],int(resrow['sample_us']))) if resrow.get('status')=='OBSERVED' else len(d['t']);use=(np.arange(len(d['t']))>=j)&(np.arange(len(d['t']))<stopidx)&(d['t']<=events['valid_end_s']);ep=d['position'][use]-d['target_p'][use];ev=d['velocity'][use]-d['target_v'][use];yaw=d['target_yaw'][use];c=np.cos(yaw);s=np.sin(yaw);P=np.c_[c*ep[:,0]+s*ep[:,1],s*ep[:,0]-c*ep[:,1],-ep[:,2]];V=np.c_[c*ev[:,0]+s*ev[:,1],s*ev[:,0]-c*ev[:,1],-ev[:,2]]
  capture={'sample_us':int(d['sample_us'][j]),'position_error_NED_m':(d['position'][j]-d['target_p'][j]).tolist(),'velocity_error_NED_m_s':(d['velocity'][j]-d['target_v'][j]).tolist(),'clipped_policy_position':d['input'][j,:3].tolist(),'clipped_policy_velocity':d['input'][j,12:15].tolist(),'h':d['h_before'][j].tolist(),'previous':d['previous'][j].tolist(),'mean':d['mean'][j].tolist(),'count':int(d['count'][j])}
  r={'event':e['label'],'status':'FULL_HOLD' if e.get('resume_status')=='READ_AND_FRESH_CONFIRMED' else 'CENSORED_HOLD_PREFIX','interval_s':[start,end],'rows':int(use.sum()),'position_raw_max_axis_m':np.max(abs(P),axis=0).tolist() if len(P) else None,'velocity_raw_max_axis_m_s':np.max(abs(V),axis=0).tolist() if len(V) else None,'position_clip_rows_all3':int(np.sum(np.max(abs(P),axis=1)>.5)) if len(P) else None,'velocity_clip_rows_all3':int(np.sum(np.max(abs(V),axis=1)>1)) if len(V) else None,'capture_sample_included':capsample,'capture_call_included':bool(use[j]),'resume_read_call_excluded':True,'capture':capture,'resume_state':next((x for x in events['rows'] if x['label']==e['label']+'_resume'),None)};rows.append(r)
 write(out/'hold-axes.json',{'schema':'p13-hold-all-axes-2','case':target.name,'rows':rows,'axis':'target-yaw frame XYZ; source capture sample inclusive to actual resume read sample exclusive. Host capture bracket is not a row-selection cutoff; full hold or explicitly censored prefix','thresholds':'original position .5m/velocity1m/s per axis, no changes','actual_raw_ulog_sha256':sha(target/'run/flight.ulg'),'no_flight_causal_intervention':True});return rows
if __name__=='__main__':create(Path(sys.argv[1]),Path(sys.argv[2]),Path(sys.argv[3]))

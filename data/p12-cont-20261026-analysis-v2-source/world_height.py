"""Source-checked GZBridge world-height conversion, separate from frozen LP task labels."""
import numpy as np

def world_height(z,t,sample,truth_sample,first,nominal,censored):
 z=np.asarray(z);t=np.asarray(t);i0=max(0,int(np.searchsorted(t,0,side='right')-1));mask=(t>=first)&(t<=nominal)&np.isfinite(z)
 if not np.isfinite(z[i0]) or not mask.any():return {'status':'UNKNOWN_MISSING_BASELINE_OR_WINDOW'}
 return {'status':'MEASURED','task_start_m':float(-z[i0]),'min_height_m':float(-z[mask].max()),'max_loss_from_task_start_m':float(max(0,z[mask].max()-z[i0])),'held_truth_max_sample_age_us':int(np.max(np.asarray(sample)[mask].astype(np.int64)-np.asarray(truth_sample)[mask].astype(np.int64))),'complete':not censored,'scope':'H=-truth NED z, source GZBridge ENU->NED; common task-start baseline, no capture/resume reset; held callback age retained','model_absolute_world_coverage':'NOT_CERTIFIED; frozen M4 plant state is estimator NED proxy, origin/bias dynamics unclosed'}

def self_test():
 t=np.array([-.1,0.,1.,2.]);z=np.array([-3.,-3.,-2.5,-3.2]);s=np.arange(4)*4000
 r=world_height(z,t,s,s,0.,2.,False)
 assert r['task_start_m']==3. and r['min_height_m']==2.5 and r['max_loss_from_task_start_m']==.5
 assert world_height(z,t,s,s,0.,2.,True)['complete'] is False
 assert world_height(z,t,s,s,3.,4.,False)['status'].startswith('UNKNOWN')
 # A climb alone must never be reported as positive loss.
 assert world_height(np.array([-3.,-3.,-3.2,-3.5]),t,s,s,0.,2.,False)['max_loss_from_task_start_m']==0.
 return {'status':'PASS','checks':4,'conversion':'H=-z_NED','new_SITL_starts':0}
if __name__=='__main__':
 import json;print(json.dumps(self_test()))

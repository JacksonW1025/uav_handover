"""Reconstruct predicted history from sealed predicted actions, not future states.
Diagnostic exact sample-ID matching records original profile-time discrepancy;
no count normalization, response shift, classification or model changes.
"""
import sys,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'));from p12c.features import load
from p9_model import write,sha

def create(target,out):
 out.mkdir(parents=True,exist_ok=False);a=target/'analysis-v1';doc=json.load(open(a/'packed-physical/prediction-input.json'));ini=doc['initial'];d=load(target/'run',a);meta=json.load(open(a/'prediction/prediction.json'));B=doc['plan']['full_source_windows_profile_s'][1][0];end=json.load(open(a/'measured/measurement.json'))['observed_profile_end_s'];results={};arrays={}
 for name in meta['models']:
  tr=np.load(a/f'prediction/{name}.npz')['trace'];n=len(tr);mean=np.array(ini['history']);count=ini['history_count'];index=ini['call_index'];mb=np.empty((n,4));ma=np.empty((n,4));cb=np.empty(n,int);ca=np.empty(n,int);mb[0]=ma[0]=mean;cb[0]=ca[0]=count
  for k in range(1,n):
   mb[k]=mean;cb[k]=count;mean=(mean*count+tr[k-1,8:12])/(count+1);commit=index%ini['force_sync']==0;count=0 if commit else count+1;index+=1;ma[k]=mean;ca[k]=count
  delta=d['sample_us'].astype(np.int64)-int(ini['sample_us']);ix=np.flatnonzero((delta>0)&(delta%4000==0)&(delta//4000<n)&(d['t']>=0)&(d['t']<=min(end,doc['plan']['nominal_horizon_profile_s'])));j=(delta[ix]//4000).astype(int);meanerr=np.linalg.norm(mb[j]-d['mean'][ix],axis=1);preverr=np.linalg.norm(tr[j-1,8:12]-d['previous'][ix],axis=1);herr=np.linalg.norm(tr[j-1,12:28]-d['h_before'][ix],axis=1);countdiff=cb[j]-d['count'][ix];timeerr=d['t'][ix]-tr[j,0];bm=np.flatnonzero(d['t'][ix]<B);last=int(bm[-1]) if len(bm) and end>=B else None
  results[name]={'matched_source_sample_calls':len(ix),'original_profile_time_difference_s_range':[float(min(timeerr)),float(max(timeerr))],'count_before_difference_counts':{str(int(k)):int(v) for k,v in zip(*np.unique(countdiff,return_counts=True))},'mean_before_error_l2_max':float(max(meanerr)),'previous_before_error_l2_max':float(max(preverr)),'hidden_before_error_l2_max':float(max(herr)),'B_before':{'status':'NOT_REACHED' if end<B else ('UNKNOWN_MODEL_PREFIX' if last is None or d['t'][ix[last]]<B-.008 else 'COVERED'),'actual_profile_s':None if last is None else float(d['t'][ix[last]]),'predicted_profile_s':None if last is None else float(tr[j[last],0]),'mean_error_l2':None if last is None else float(meanerr[last]),'previous_before_error_l2':None if last is None else float(preverr[last]),'hidden_before_error_l2':None if last is None else float(herr[last]),'count_before_difference':None if last is None else int(countdiff[last])}}
  arrays[name+'_mean_before']=mb;arrays[name+'_mean_after']=ma;arrays[name+'_count_before']=cb;arrays[name+'_count_after']=ca
 write(out/'history-prediction.json',{'schema':'p13-predicted-history-1','id':target.name,'models':results,'reconstruction':'initial after-call mean/count/index from sealed past-only input; before-call mean/count retained; convex update uses previous predicted action then count resets only commit. No future measured hidden/action/history supplied to predictor. Actual histories only score.','alignment':'exact absolute sample identity from ini.sample_us+4000*k, not count renaming or trajectory/response alignment; raw time discrepancy included, original v2 unshifted score unchanged','source_sha256':sha(Path(__file__)),'new_SITL':0});np.savez_compressed(out/'predicted-history.npz',**arrays)
if __name__=='__main__':create(Path(sys.argv[1]),Path(sys.argv[2]))

from analysis_paths_v1 import analysis_dir
"""Threshold witness intervals with canonical A-window LP baseline, no time shift."""
import json,sys
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'));sys.path.insert(0,str(Path(__file__).parent))
from p11.models import tilt
from record_review_v3 import crossing
from p9_model import write,sha

def create(target,out):
 out.mkdir(parents=True,exist_ok=False);a=analysis_dir(target);pack=a/'packed-physical';doc=json.load(open(pack/'prediction-input.json'));d=np.load(pack/'measurement.npz');meta=json.load(open(a/'prediction/prediction.json'));meas=json.load(open(a/'measured/measurement.json'));scores=json.load(open(a/'score/score.json'));tt=d['profile_s'];lo=doc['plan']['common_first_gap_profile_s'];hi=doc['plan']['horizon_profile_s'];use=(tt>=lo)&(tt<=hi);obs0=np.interp(lo,tt,d['position'][:,2]);oa=np.array([tilt(q) for q in d['attitude']]);obs={'tilt':crossing(tt[use],oa[use],45),'height':crossing(tt[use],d['position'][use,2]-obs0,1)};rows=[]
 for name,info in meta['models'].items():
  tr=np.load(a/f'prediction/{name}.npz')['trace'];pt=tr[:,0];good=np.isfinite(tr).all(axis=1)
  if info.get('stop',{}):
   if info['stop']['reason']=='NUMERICAL_UNCERTAIN':good &=pt<info['stop']['profile_s']
  bad=np.flatnonzero(~good);tr=tr[:int(bad[0])] if len(bad) else tr;pt=tr[:,0];mask=(pt>=lo)&(pt<=hi);z0=np.interp(lo,pt,tr[:,3]);pr={'tilt':crossing(pt[mask],tr[mask,7],45),'height':crossing(pt[mask],tr[mask,3]-z0,1)}
  for component in ['tilt','height']:
   p,o=pr[component],obs[component];err=None
   if p and o:err=[p['last_nonwitness_or_first_time_s']-o['first_sampled_witness_s'],p['first_sampled_witness_s']-o['last_nonwitness_or_first_time_s']]
   rows.append({'model':name,'component':component,'forward_prediction_first_witness':p,'observed_first_witness':o,'predicted_minus_observed_first_time_error_interval_s':err,'prediction_complete':scores['models'][name]['full_prediction'],'observation_complete':not meas['censored'],'canonical_scoped_classification':scores['models'][name]['risk']['comparisons'][component],'no_observed_witness_is_safe_only_if_complete':True,'no_predicted_witness_is_safe_only_if_complete':True})
 write(out/'crossing.json',{'schema':'p13-first-crossing-1','id':target.name,'rows':rows,'scope':'forward sealed model entire nominal horizon and recorded observation prefix, physical sampled brackets only; canonical v2 scoped-to-observation classification unchanged','height_baseline':'common planned first A-window LP baseline, never reset at B/capture/resume; extra physical task0 baseline separate','continuous_intersample_certificate':False,'source_sha256':sha(Path(__file__))})
if __name__=='__main__':create(Path(sys.argv[1]),Path(sys.argv[2]))

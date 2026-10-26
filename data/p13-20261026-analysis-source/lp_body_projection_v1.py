"""Posthoc correction of output point mapping ONLY on frozen M5 trajectories.
No feedback reforecast, model tuning, reclassification or new main candidate.
"""
import sys,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'));from p11.models import R as matrix
from p12c.features import load
from p9_model import write
out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);rows=[]
for tar in sorted((R/'data/p13-20261026-development').iterdir()):
 a=tar/'analysis-v1';pr=a/'prediction';pack=a/'packed-physical'
 if not pr.exists():pr=R/'data/p13-20261026-development-predictions-v1'/tar.name/'prediction';pack=pr.parent/'packed'
 doc=json.load(open(pack/'prediction-input.json'));i=doc['initial'];t=np.load(pr/'M5.npz')['trace'];r=np.array([0,0,.00186913101803548]);bz=i['position'][2]-i['physical_COM_p'][2]-(matrix(i['attitude'])@r)[2];bv=i['velocity'][2]-i['physical_COM_v'][2]-(matrix(i['attitude'])@np.cross(i['omega'],r))[2];lpz=i['position'][2];lpv=i['velocity'][2];z=[];v=[]
 for k,row in enumerate(t):
  if k and (i['sample_us']+k*4000-i['lp_phase_us'])%8000==0:lpz=row[52]+(matrix(row[35:39])@r)[2]+bz;lpv=row[53]+(matrix(row[35:39])@np.cross(row[39:42],r))[2]+bv
  z.append(lpz);v.append(lpv)
 d=load(tar/'run',a);ix=np.flatnonzero((d['t']>=0)&(d['t']<=min(t[-1,0],doc['plan']['nominal_horizon_profile_s'])));tt=d['t'][ix]
 def er(pred,truth):e=np.interp(tt,t[:,0],pred)-truth;return {'RMSE':float(np.sqrt(np.mean(e*e))),'max_abs':float(max(abs(e)))}
 rows.append({'id':tar.name,'LP_H_original':er(t[:,44],d['position'][ix,2]),'LP_H_body_point_projection_only':er(z,d['position'][ix,2]),'LP_W_original':er(t[:,47],d['velocity'][ix,2]),'LP_W_body_point_projection_only':er(v,d['velocity'][ix,2]),'source_body_lever_m':r.tolist(),'new_biases_from_initial_information_only':[bz,bv]})
write(out/'diagnostic.json',{'schema':'p13-M5-output-body-point-component-correction-1','records':rows,'scope':'development-only fixed frozenM5physical trajectories/actions/h. Replace .241869 named-model lever by source base/body-to-COM .001869 lever in output reporting, same8ms LP holding rule and past-only initial z/v offsets. Feedback originally used oldmap, so this is NOT an autonomous corrected candidate or heldout improvement; frozenM5andallformal scores unchanged.','new_model_candidates':0,'future_true_states_supplied_to_forecast':False,'new_SITL':0});print('BODY_COMPONENT_DIAGNOSTIC',len(rows))

"""Independent finite-response validation, branch changes never smoothed away."""
import sys,json,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from p14h.common import *

def main():
 out=register(sys.argv[1],'H1 finiteforward checks of localresponse directions, steps andbranch crossings; no futureactual');limit(30);base=B/'offline-v2';jobs=json.load(open(base/'jobs.json'));rows=[];groups={}
 for j,job in enumerate(jobs):
  p=base/f'{j:03d}/result/result.json'
  if not p.exists():continue
  x=json.load(open(p));groups.setdefault((job['case'],job['axis']),{})[job['delta_s']]=(j,x)
 def signature(x):return tuple((b['read'],b['refresh'],b['capture'],b['resume'],b['commit'],b['duplicate']) for b in x['branches'])
 def features(x):
  xx=next((m for m in x['metrics'] if m['gap']==0 and m['window_s']==.5 and m['status']=='FULL'),None)
  return None if xx is None else np.r_[xx['first_action'],xx['peak_tilt_deg'],xx['LP_D_m'],xx['COM_D_m'],xx['last_W']]
 scales=np.r_[[.02]*4,2.5,.1,.1,.15]
 for (name,axis),points in groups.items():
  if axis=='base':continue
  # Separate within-cell derivative on negative andpositive sides. Independent
  # ±1ms samples are validation; derivative uses±.25/.75 around±.5ms only.
  for side in [-1,1]:
   ks=[side*t for t in [.00025,.0005,.00075,.001]]
   if not all(t in points for t in ks):continue
   A=points[ks[0]][1];C=points[ks[1]][1];D=points[ks[2]][1];E=points[ks[3]][1];f=[features(x) for x in [A,C,D,E]]
   if any(x is None for x in f):continue
   same=signature(A)==signature(C)==signature(D)==signature(E);der=(f[2]-f[0])/(ks[2]-ks[0]);pred=f[1]+(ks[3]-ks[1])*der;err=pred-f[3]
   rows.append({'case':name,'axis':axis,'side':side,'same_complete_discrete_branch':same,'derivative_step_s':.00025,'validation_delta_s':ks[3],'normalized_response_error':(err/scales).tolist(),'response_L2_scaled':float(np.linalg.norm((f[3]-f[1])/scales)),'prediction_error_L2_scaled':float(np.linalg.norm(err/scales)),'direction_dot':float(np.dot(pred-f[1],f[3]-f[1])),'scope':'source model finiteforward test only, nominalLP/physical separate, no physicalcausalclaim'})
  if axis=='release' and all(t in points for t in [-.00075,-.0005,-.00025,.001]):
   A,C,D,E=[points[t][1] for t in [-.00075,-.0005,-.00025,.001]];f=[features(x) for x in [A,C,D,E]]
   if any(x is None for x in f):continue
   der=(f[2]-f[0])/.0005;pred=f[1]+.0015*der
   rr=[points[t][1] for t in [.00025,.0005,.00075]];ff=[features(x) for x in rr];right=ff[1]+.0005*(ff[2]-ff[0])/.0005
   rows.append({'case':name,'axis':axis,'cross_boundary':signature(C)!=signature(E),'continuous_extrapolation_L2_scaled_error':float(np.linalg.norm((pred-f[3])/scales)),'branch_aware_L2_scaled_error':float(np.linalg.norm((right-f[3])/scales)),'right_training_points_s':[.00025,.0005,.00075],'validation_point_s':.001,'right_training_and_validation_same_branch':all(signature(x)==signature(E) for x in rr),'actual_model_jump_L2_scaled':float(np.linalg.norm((f[3]-f[1])/scales)),'branch_aware_prediction':'right-cell .25/.75ms derivative around .5ms predicts heldout1ms; no use ofvalidation point inprediction, no saltationclaim','first_different_call':next((j+1 for j,(a,b) in enumerate(zip(signature(C),signature(E))) if a!=b),None),'features':['action4','cachedtiltpeak','LPD','COMD','downW']})
 write(out/'result.json',{'attempts':len(jobs),'available_results':sum(len(v) for v in groups.values()),'rows':rows,'future_actual_used':False,'predictions_are_conditional_source_model':True,'no_fixed_during_crossing_smooth_derivative_claim':True});print('OFFLINE_RESPONSE_AUDITED',len(rows))
if __name__=='__main__':main()

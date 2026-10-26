import json,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,'tools')
from p11.models import tilt
from p9_model import write
root=Path('data/p11-20261025-formal');out=Path('data/p11-20261026-analysis');plan=json.loads(Path('config/p11.json').read_text());records=[]
for row in plan['rows']:
 case=root/row['id']
 if not (case/'result.json').exists():continue
 d=dict(np.load(case/'packed/measurement.npz'));t=d['profile_s'];angle=np.array([tilt(q) for q in d['attitude']]);doc=json.loads((case/'packed/prediction-input.json').read_text());pred=case/'prediction'
 if not pred.exists():pred=out/row['id']/'prediction'
 for model in ['M0','M1','M2']:
  tr=np.load(pred/(model+'.npz'))['trace']
  for j,(a,b) in enumerate(doc['plan']['windows_profile_s']):
   selected=(t>=a)&(t<a+.5);unsafe=np.flatnonzero(selected&(angle>45.))
   if not len(unsafe):continue
   actual=float(t[unsafe[0]]);pred_unsafe=np.flatnonzero((tr[:,0]>=a)&(tr[:,0]<a+.5)&(tr[:,7]>45.));pt=float(tr[pred_unsafe[0],0]) if len(pred_unsafe) else None
   value=float(np.interp(actual,tr[:,0],tr[:,7]));records.append({'id':row['id'],'split':row['split'],'model':model,'event_index':j,'actual_first_unsafe_profile_s':actual,'predicted_first_unsafe_within_window_s':pt,'prediction_at_actual_first_unsafe_deg':value,'observed_at_first_unsafe_deg':float(angle[unsafe[0]]),'predicted_onset_minus_actual_ms':(pt-actual)*1000 if pt is not None else None,'safe_prediction_at_actual_first_unsafe':bool(value<=45),'interpretation':'post-hoc time-resolved/onset diagnostic; original frozen window-maximum classification remains unchanged; phase/clock uncertainty must be applied before a deterministic deadline assertion'})
write(out/'event-onset-audit.json',{'schema':'p11-event-onset-audit-1','records':records,'not_model_refit':True,'original_scoring_unchanged':True})
for model in ['M0','M1','M2']:
 for split in ['development','heldout']:
  rs=[r for r in records if r['model']==model and r['split']==split];print(model,split,'unsafe windows',len(rs),'safe_at_actual_onset',sum(r['safe_prediction_at_actual_first_unsafe'] for r in rs),'lags_ms',[r['predicted_onset_minus_actual_ms'] for r in rs])

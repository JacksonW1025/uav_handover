from pathlib import Path
import json,numpy as np
ROOT=Path(__file__).resolve().parent
for stem,tracefile in [('h2_preflight_results','h2_preflight_traces'),('h2_strict_singles','h2_strict_singles_traces'),('h2_strict_normal_only','h2_strict_normal_only_traces')]:
 p=ROOT/(stem+'.json');backup=ROOT/(stem+'_prestream_accounting.json')
 if not backup.exists():backup.write_bytes(p.read_bytes())
 d=json.loads(backup.read_text());tr=np.load(ROOT/(tracefile+'.npz'))
 for r in d['results']:
  z=tr[r['id']];t=z[:,0];mask=t>=13.255;base=float(np.interp(13.255,t,z[:,7]));r['prediction']=max(0.,float(z[mask,7].max()-base));r['predicted_failure']=r['prediction']>1;r['predicted_tilt']=float(z[mask,4].max());r['predicted_height_baseline_profile_s']=13.255;r['predicted_height_baseline_LP_z']=base
 complete=[r for r in d['results'] if not r['actual_censored']];pos=[r for r in d['results'] if r['actual']>1];neg=[r for r in complete if r['actual']<=1]
 d['summary']['height_MAE']=float(np.mean([abs(r['prediction']-r['actual']) for r in complete]));d['summary']['tilt_MAE']=float(np.mean([abs(r['predicted_tilt']-r['actual_tilt']) for r in complete]));d['summary']['height_FN']=sum(r['prediction']<=1 for r in pos);d['summary']['height_FP']=sum(r['prediction']>1 for r in neg)
 for k in ['complete_mae','complete_rmse','height_false_negatives','height_false_positives']:d['summary'].pop(k,None)
 d['accounting_revision']='Score height from predicted LP z at original common first-event time13.255, matching the archived task metric. Raw traces unchanged; column7 is LP z. Earlier pre-stream-origin scores preserved separately.'
 p.write_text(json.dumps(d,indent=2));print(stem,d['summary'])

"""Independent P14R scoring adapter; original P12/P13 scores unchanged.
Three-valued scoring v2, actual control LP cache for height. Raw source OP
current output remains separately available in the prediction arrays.
"""
import sys,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p14.common import write,sha
from p12.score import score

def main():
 pred,out=map(Path,sys.argv[1:]);out.mkdir(parents=True,exist_ok=False);rows=[]
 write(out/'before-compute.json',{'scope':'all5valid new records x9conditional comparisons, independent flight denominator5, shared8words not extra flights','scorer':'unchanged tools/p12/score.py v2','adapter':'derived scoring trace columns1:7 copy actual predicted controller LP cache columns42:48; source current OP output preserved in original. Exclude first physical-domain/numerical stopping row; earlier witnesses remain. Frozen LP common-first-gap baseline unchanged; task0 COM/LP L/D separate event diagnostics.','primary_word':'PRE-phase0.0-jointdelay0.0','other_words':'timing sensitivity, no unique branch attribution or automatic safety union','exposure':'retrospective diagnostics; d05/d06 structure sealed before start, no outcome-independent prospective claim','source':sha(Path(__file__))})
 for folder in sorted(x for x in (pred/'predictions').iterdir() if x.is_dir()):
  n=folder.name;run=next((R/'data/p14r-20261027/runs').glob('p14r-'+n+'-*'));adapt=out/n/'scoring-input';adapt.mkdir(parents=True);meta={'models':{},'raw_source':str(folder),'all_comparisons_retrospective':True}
  for p in sorted(folder.glob('*.npz')):
   z=dict(np.load(p));info=json.load(open(p.with_suffix('.json')));trace=z['trace'].copy();trace[:,1:7]=trace[:,42:48];stop=info.get('stop');excluded=0
   if stop and len(trace):
    keep=trace[:,0]<stop['profile_s'];excluded=int(sum(~keep));trace=trace[keep]
   np.savez_compressed(adapt/p.name,trace=trace);meta['models'][p.stem]={'stop':stop,'height_modelled':True,'compute_s':info['elapsed_s'],'excluded_invalid_domain_rows':excluded,'raw_prediction_sha256':sha(p)}
  write(adapt/'prediction.json',meta);s=score(adapt,run/'analysis-v1/packed',run/'analysis-v1/measured/measurement.json',out/n/'score');rows.append({'id':n,'models':s['models']})
 summaries={}
 for model in rows[0]['models']:
  summaries[model]={}
  for part in ['tilt','height','task']:
   comparisons=[r['models'][model]['risk']['comparisons'][part] for r in rows];truth=[r['models'][model]['risk']['observed'][part] for r in rows];prediction=[r['models'][model]['risk']['predicted'][part] for r in rows];summaries[model][part]={'flights':len(rows),'actual_failures':truth.count('FAILURE'),'actual_success':truth.count('SUCCESS'),'actual_unknown':truth.count('UNKNOWN'),'danger_miss':comparisons.count('DANGER_MISS'),'false_alarm':comparisons.count('FALSE_ALARM'),'agreement':comparisons.count('AGREEMENT'),'prediction_unknown':prediction.count('UNKNOWN'),'classification_eligible':sum(r['models'][model]['risk']['classification_eligible'][part] for r in rows),'full_trajectory_eligible':sum(r['models'][model]['risk']['full_trajectory_eligible'][part] for r in rows),'classifications':dict(zip([r['id'] for r in rows],comparisons))}
 write(out/'summary.json',{'summaries':summaries,'records':rows,'independent_units':5,'models_or_windows_not_independent':True,'separate_domains':'source physical finite-domain stop does not imply observed censoring; missing/witness/truncation correctv2 rules retained'})
if __name__=='__main__':main()

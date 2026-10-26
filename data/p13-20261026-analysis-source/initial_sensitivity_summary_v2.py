"""All three frozen models, recomputed from existing sensitivity predictions only."""
import sys,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'));from p9_model import write,sha
src=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=False);rows=[]
for case in sorted(p for p in src.iterdir() if p.is_dir()):
 for name in ['M3','M4','M5']:
  nom=np.load(case/f'nominal/prediction/{name}.npz')['trace']
  for variant in sorted(p for p in case.iterdir() if p.is_dir()):
   a=np.load(variant/f'prediction/{name}.npz')['trace'];stop=min(nom[-1,0],a[-1,0]);mask=nom[:,0]<=stop;t=nom[mask,0]
   rows.append({'id':case.name,'model':name,'variant':variant.name,'common_end_profile_s':float(stop),'maximum_tilt_change_deg':float(np.max(abs(np.interp(t,a[:,0],a[:,7])-nom[mask,7]))),'maximum_LP_H_change_m':float(np.max(abs(np.interp(t,a[:,0],a[:,44])-nom[mask,44]))),'status':'fixed-model initial-uncertainty diagnostic, not flight causal intervention, no score adjustment or fitting'})
write(out/'summary.json',{'schema':'p13-initial-sensitivity-2','rows':rows,'earlier_M5_only_summary_sha256':sha(src/'summary.json'),'new_predictions':0,'SITL':0,'all_M3_M4_M5_predictions_retained':True})

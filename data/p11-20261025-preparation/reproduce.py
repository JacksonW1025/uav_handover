import sys,json
from pathlib import Path
import numpy as np
sys.path.insert(0,'tools')
from p11.isolated import predict
from p11.score import score
from p9_model import write
root=Path('data/p11-20261025-formal');analysis=Path('data/p11-20261026-analysis');out=Path('data/p11-20261026-reproduction');out.mkdir(exist_ok=False);reports=[]
for identity in ['F1-r1-AB','F4-r1-AB','ANCHOR-D-09-r1-ORIGINAL']:
 case=root/identity;dest=out/identity;dest.mkdir();predict(case/'packed',root/'models',dest/'prediction');score(dest/'prediction',case/'packed',case/'measured/measurement.json',dest/'score')
 original=case/'prediction'
 if not original.exists():original=analysis/identity/'prediction'
 for name in ['M0','M1','M2']:
  a=np.load(original/(name+'.npz'))['trace'];b=np.load(dest/'prediction'/(name+'.npz'))['trace'];reports.append({'id':identity,'model':name,'trace_exact_equal_including_NaN':bool(np.array_equal(a,b,equal_nan=True)),'max_finite_abs_difference':float(np.max(abs(a[np.isfinite(a)]-b[np.isfinite(a)])))})
write(out/'reproduction.json',{'schema':'p11-isolated-reproduction-1','status':'PASS' if all(x['trace_exact_equal_including_NaN'] for x in reports) else 'FAIL','cases':reports,'no_SITL':True,'no_models_refitted':True,'scope':'full69 scoring generated from sealed models once; these3 representative initial/plan inputs independently rerun with future data physically hidden; runtime metrics may differ'})
print('reproduction',all(x['trace_exact_equal_including_NaN'] for x in reports))

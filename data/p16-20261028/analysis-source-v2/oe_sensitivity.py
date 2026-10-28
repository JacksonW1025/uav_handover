"""Predeclared alternate ordinaryOE coefficients, diagnostic only. No selection update."""
import sys,json,time,numpy as np
from pathlib import Path
sys.path.insert(0,'tools')
from p16.greybox import forecast
from p16.common import B,write,sha,now
out=Path(sys.argv[1]);out.mkdir(exist_ok=False,parents=True);model=json.load(open(B/'frozen/model-parameters.json'))['OE_sensitivity_only'];records={};trace={};st=time.perf_counter();cpu=time.process_time()
for path in sorted((B/'frozen/model-inputs').glob('*.json')):
 x=json.load(open(path));r,z=forecast(x,model);records[x['id']]=r;trace[x['id']]=z
np.savez_compressed(out/'traces.npz',**trace);write(out/'predictions.json',records);write(out/'receipt.json',dict(time=now(),CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-st,parameter_sha256=sha(B/'frozen/model-parameters.json'),future_actual_inputs=False,used_for_selection=False,primary_remains='strictEE',cases=len(records)))

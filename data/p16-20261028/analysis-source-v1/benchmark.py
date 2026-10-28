"""Reproduce frozen autonomous inputs; no new data fitting or SITL."""
import sys,time,json,resource
from pathlib import Path
sys.path.insert(0,'tools')
from p16.greybox import forecast
from p16.common import B,write,now,sha
out=Path(sys.argv[1]);out.mkdir(exist_ok=False,parents=True);records=[]
for path in sorted((B/'frozen/model-inputs').glob('*.json')):
 x=json.load(open(path));st=time.perf_counter();cpu=time.process_time();r,tr=forecast(x);records.append(dict(input=str(path),sha256=sha(path),CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-st,peak_tilt=r['peak_tilt'],peak_loss=r['peak_loss'],future_actual_inputs=r['future_actual_inputs']))
prior=json.load(open(B/'frozen/initial-predictions.json'));checks={Path(x['input']).stem:max(abs(x['peak_tilt']-prior[Path(x['input']).stem]['peak_tilt']),abs(x['peak_loss']-prior[Path(x['input']).stem]['peak_loss'])) for x in records};assert max(checks.values())==0
write(out/'result.json',dict(time=now(),records=records,reproduction_max_delta=checks,CPU_s=sum(x['CPU_s'] for x in records),wall_s=sum(x['wall_s'] for x in records),scope='measured repeatedcomputation of originalpast+plan inputs, original predictionwall unmeasured, no maintruth access, not futuredata update'))
print('FROZEN_FORECASTS_REPRODUCED',len(records),flush=True)

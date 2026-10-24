"""160 raw, no-flight remeasurements; exact frozen serialization comparison."""
import json,time,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(HERE));sys.path.insert(0,str(ROOT/'tools'))
from measurement_v2 import analyze
from p9_model import sha,write
start=time.monotonic();rows=[]
for batch in ['data/p9-20261024-formal','data/p9-20261024-continuation-v1-formal']:
 for r in json.loads((ROOT/batch/'results.json').read_text())['runs']:
  if not r.get('p9'):continue
  run=ROOT/r['directory'];a=analyze(run);expected=run/'p9-metrics.json'
  exact=(json.dumps(a['measurement'],indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode()==expected.read_bytes()
  rows.append({'id':r['id'],'kind':a['kind'],'exact_bytes':exact,'saved_sha256':sha(expected),'raw_sha256':sha(run/'flight.ulg')})
  print('COMPAT',len(rows),r['id'],exact,flush=True)
  if a['kind']!='ORIGINAL_COMPATIBLE' or not exact:raise RuntimeError('compatibility differs '+r['id'])
assert len(rows)==160
write(HERE/'compatibility-160.json',{'status':'PASS','n':160,'elapsed_s':time.monotonic()-start,'rows':rows,'new_SITL_starts':0,'original_files_rewritten':False,'adapter_sha256':sha(HERE/'measurement_v2.py'),'frozen_metric_sha256':sha(ROOT/'tools/p9_metrics.py')})

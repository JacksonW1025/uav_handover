"""Read-only raw161 compatibility, original P7 replay and v3 admission. No flight."""
import json,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(HERE));sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(ROOT/'data/p9-20261024-continuation-v2-preparation'))
from measurement_v2 import analyze
from opportunity_v3 import assess,decide
from p9_model import sha,write
import p7_metrics
start=time.monotonic();rows=[]
for epoch in ['data/p9-20261024-formal','data/p9-20261024-continuation-v1-formal','data/p9-20261024-continuation-v2-formal']:
 for r in json.loads((ROOT/epoch/'results.json').read_text())['runs']:
  if not r.get('infrastructure_ok') or not r.get('p9'):continue
  run=ROOT/r['directory'];a=analyze(run);p7=p7_metrics.analyze(run);original=json.loads((run/'p7-metrics.json').read_text());op=assess(run);gate=decide(r,a,op,p7)
  identical=(json.dumps(a['measurement'],indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode()==(run/'p9-metrics.json').read_bytes()
  assert identical and original==p7 and gate['evidence_admissible'] and not gate['exception_not_reached'],r['id']
  rows.append({'id':r['id'],'exact_original_p9_bytes':identical,'p7_raw_identical':True,'opportunity':op['state'],'v3_admissible':True,'original_p9_sha256':sha(run/'p9-metrics.json'),'raw_sha256':sha(run/'flight.ulg')});print('COMPAT',len(rows),r['id'],flush=True)
assert len(rows)==161
negative=[]
for rid,base in [('C-CZ15-g0.1-reference-P9-Z','data/p9-20261024-formal'),('D-07-P9-Z','data/p9-20261024-continuation-v1-formal'),('D-07-P9-R','data/p9-20261024-continuation-v2-formal')]:
 run=ROOT/base/rid/'run';a=analyze(run);op=assess(run)
 negative.append({'id':rid,'measurement_kind':a['kind'],'opportunity':op['state'],'posthoc_only':True,'not_added_to161_or_future9':True})
write(HERE/'compatibility-161.json',{'status':'PASS','n':161,'elapsed_s':time.monotonic()-start,'rows':rows,'negative_cases':negative,'source_hashes':{p.name:sha(p) for p in [HERE/'opportunity_v3.py',HERE/'run_v3.py',Path(__file__).resolve()]},'new_SITL_starts':0,'old_files_rewritten':False})

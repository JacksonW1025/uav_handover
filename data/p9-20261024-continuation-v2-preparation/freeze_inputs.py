"""Create v2 immutable manifest after all no-flight gates; no flight launch."""
from pathlib import Path
import json,sys,hashlib,subprocess
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'tools'))
from p9_model import write,sha
freeze=ROOT/'data/p9-20261024-continuation-v2-freeze'
comp=json.loads((HERE/'compatibility-160.json').read_text());assert comp['status']=='PASS' and comp['n']==160 and comp['adapter_sha256']==sha(HERE/'measurement_v2.py')
assert '24 passed' in (HERE/'unit-tests.log').read_text()
for p in HERE.glob('*.py'):compile(p.read_text(),str(p),'exec')
old=ROOT/'data/p9-20261024-continuation-v1-freeze';m=json.loads((old/'manifest.json').read_text());files=dict(m['files'])
for k,h in files.items():assert sha(ROOT/k)==h,k
new=list(p for p in HERE.iterdir() if p.is_file())+[ROOT/'docs/THOR_P9_CONTINUATION_V2_PLAN.md']+[freeze/n for n in ['plan.json','model.json','prior-ledger.jsonl']]
for p in new:files[str(p.relative_to(ROOT))]=sha(p)
write(freeze/'manifest.json',{'version':'p9-execution-measurement-continuation-v2','created_at':datetime.now(timezone.utc).isoformat(),'files':files,'original_freeze_commit':'6a0292e4d7259f9396d5dad08486eb9e2a743427','previous_freeze_commit':'95f424bafd040214dd834fb2737d29986c54913a','previous_manifest_sha256':sha(old/'manifest.json'),'sealed_searches_sha256':sha(ROOT/'data/p9-20261024-formal/searches-sealed-before-reference.json'),'new_trials':11,'formal_prior_starts':162,'formal_total_cap':173,'development_starts':10,'old102_missing':True,'old162_postflight_diagnostic_only':True,'no_model_refit':True})
print(json.dumps({'frozen_files':len(files),'manifest_sha256':sha(freeze/'manifest.json'),'plan_sha256':sha(freeze/'plan.json'),'adapter_sha256':sha(HERE/'measurement_v2.py'),'model_sha256':sha(freeze/'model.json')}))

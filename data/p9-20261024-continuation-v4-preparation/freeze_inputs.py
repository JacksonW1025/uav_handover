from pathlib import Path
from datetime import datetime,timezone
import json,sys
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'tools'))
from p9_model import write,sha
assert '58 passed' in (HERE/'no-flight-tests-final.log').read_text()
eq=json.loads((HERE/'execution-equivalence.json').read_text());assert eq['status']=='PASS' and all(eq['same_functions_after_epoch_label_normalization'].values()) and sha(HERE/'run_v4.py')==eq['new_runner_sha256']
f=ROOT/'data/p9-20261024-continuation-v4-freeze';assert (ROOT/'data/p9-20261024-preparation/attempts.jsonl').read_bytes()==(f/'prior-ledger.jsonl').read_bytes()
old=ROOT/'data/p9-20261024-continuation-v3-freeze';files=dict(json.loads((old/'manifest.json').read_text())['files'])
for p,h in files.items():assert sha(ROOT/p)==h,p
for p in [x for x in HERE.iterdir() if x.is_file()]+[ROOT/'docs/THOR_P9_EXECUTION_V4_PLAN.md',old/'manifest.json']+[f/n for n in ['plan.json','model.json','prior-ledger.jsonl']]:files[str(p.relative_to(ROOT))]=sha(p)
write(f/'manifest.json',{'version':'p9-execution-continuation-v4-only','created_at':datetime.now(timezone.utc).isoformat(),'files':files,'previous_freeze_commit':'4fb828d898fc6501fd3232a6b310968a73f31958','v2_freeze_commit':'0050ecee60af8f0640df6c105c560cd3536d169f','v1_freeze_commit':'95f424bafd040214dd834fb2737d29986c54913a','original_freeze_commit':'6a0292e4d7259f9396d5dad08486eb9e2a743427','sealed_searches_sha256':sha(ROOT/'data/p9-20261024-formal/searches-sealed-before-reference.json'),'formal_before':169,'new_trials':4,'formal_cap':173,'development':10,'169_remains_rejected':True,'no_measurement_or_admission_rule_change':True})
print(json.dumps({'files':len(files),'manifest_sha256':sha(f/'manifest.json'),'plan_sha256':sha(f/'plan.json')}))

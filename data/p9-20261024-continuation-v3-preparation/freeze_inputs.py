"""Freeze tested v3 nine-row version; never launches anything."""
from pathlib import Path
from datetime import datetime,timezone
import sys,json
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'tools'))
from p9_model import write,sha
f=ROOT/'data/p9-20261024-continuation-v3-freeze';comp=json.loads((HERE/'compatibility-161.json').read_text());assert comp['status']=='PASS' and comp['n']==161
for name,h in comp['source_hashes'].items():assert sha(HERE/name)==h,name
assert '62 passed' in (HERE/'test-v3-release-final.log').read_text()
assert (ROOT/'data/p9-20261024-preparation/attempts.jsonl').read_bytes()==(f/'prior-ledger.jsonl').read_bytes()
old=ROOT/'data/p9-20261024-continuation-v2-freeze';files=dict(json.loads((old/'manifest.json').read_text())['files'])
for k,h in files.items():assert sha(ROOT/k)==h,k
items=[p for p in HERE.iterdir() if p.is_file()]+[ROOT/'docs/THOR_P9_CONTINUATION_V3_PLAN.md']+[f/n for n in ['model.json','plan.json','prior-ledger.jsonl']]+[ROOT/d/'manifest.json' for d in ['data/p9-20261024-freeze','data/p9-20261024-continuation-v1-freeze','data/p9-20261024-continuation-v2-freeze']]
for p in items:files[str(p.relative_to(ROOT))]=sha(p)
write(f/'manifest.json',{'version':'p9-continuation-v3-opportunity','created_at':datetime.now(timezone.utc).isoformat(),'files':files,'original_freeze_commit':'6a0292e4d7259f9396d5dad08486eb9e2a743427','v1_freeze_commit':'95f424bafd040214dd834fb2737d29986c54913a','previous_freeze_commit':'0050ecee60af8f0640df6c105c560cd3536d169f','sealed_searches_sha256':sha(ROOT/'data/p9-20261024-formal/searches-sealed-before-reference.json'),'new_trials':9,'formal_prior_starts':164,'formal_total_cap':173,'development_starts':10,'old102_missing':True,'old162_posthoc_only':True,'old164_posthoc_only':True,'no_refit_or_repair_selection':True})
print(json.dumps({'files':len(files),'manifest_sha256':sha(f/'manifest.json'),'plan_sha256':sha(f/'plan.json'),'opportunity_sha256':sha(HERE/'opportunity_v3.py')}))

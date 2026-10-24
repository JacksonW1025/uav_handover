"""Prepare exactly11 untouched original rows; no flight or model fitting."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p9_model import write,sha
from p9_campaign import validate_row
prep=Path(__file__).resolve().parent;freeze=ROOT/'data/p9-20261024-continuation-v2-freeze';freeze.mkdir(exist_ok=False)
old=ROOT/'data/p9-20261024-freeze';plan=json.loads((old/'plan.json').read_text());cfg=json.loads((ROOT/'config/p9.json').read_text())
ledger=(ROOT/'data/p9-20261024-preparation/attempts.jsonl').read_bytes();events=[json.loads(x) for x in ledger.decode().splitlines()];started={x['id'] for x in events if x['event']=='START_INTENT'}
runs=[r for r in plan['runs'] if r['id'] not in started];assert len(runs)==11 and all(r['stage']=='D' for r in runs)
assert runs[0]['id']=='D-07-P9-C' and runs[-1]['id']=='D-09-P9-CR'
for r in runs:validate_row(plan,cfg,r)
write(freeze/'plan.json',{'version':'p9-execution-measurement-continuation-v2','runs':runs,'search_slots':[],'search_candidates':[],'global_formal_cap':173,'original_formal_starts':162,'new_start_cap':11,'development_starts':10,'new_development_cap':0,'no_retry_ids':['C-CZ15-g0.1-reference-P9-Z','D-07-P9-Z'],'original_plan_sha256':sha(old/'plan.json'),'information_policy':'no fit/search/repair selection changes, original seeds/order/cases/treatments/thresholds fixed; old162 remains postflight diagnostic, old102 missing; new measurements version-tagged'})
(freeze/'model.json').write_bytes((old/'model.json').read_bytes());(freeze/'prior-ledger.jsonl').write_bytes(ledger)
write(prep/'remaining-validation.json',{'n':len(runs),'all_original_rows':True,'generation_domain_and_runner_budget':'PASS original validate_row and original frozen slot equality','first':runs[0]['id'],'last':runs[-1]['id'],'original_model_sha256':sha(freeze/'model.json'),'predictions':'must equal original frozen precomputed forecast before every start'})
print('Prepared exactly11 original never-started D rows')

#!/usr/bin/env python3
"""Independent final ledger, frozen identity, denominator and preservation checks; no SITL."""
import json,hashlib,subprocess,sys,collections
from pathlib import Path
R=Path(__file__).resolve().parents[2];D=R/'data/p12-cont-20261026-delivery-v2'
def read(p):return json.loads((R/p).read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
checks={}
manifest=read('data/p12-cont-20261026-freeze/manifest.json')
checks['all_frozen_files_unchanged']=all(sha(R/p)==h for p,h in manifest['files'].items())
checks['frozen_tools_research_config_unchanged']=subprocess.check_output(['git','diff','--name-only','68dfb73b','--','tools','research','config'],cwd=R)==b''
rows=[json.loads(s) for s in (R/'data/p12-cont-20261026-preparation/attempts.jsonl').read_text().splitlines()];starts=[r for r in rows if r['event']=='START_INTENT'];prep=[r for r in starts if r['budget_class']=='development'];formal=[r for r in starts if r['budget_class']=='formal'];old=[json.loads(s) for s in (R/'data/p12-20261026-preparation/attempts.jsonl').read_text().splitlines() if json.loads(s)['event']=='START_INTENT']
checks['caps_unique_starts_and_contiguous_ordinals']=len(old)==9 and len(prep)==12 and len(formal)==27 and len({r['id'] for r in starts})==39 and [r['ordinal'] for r in formal]==list(range(1,28))
plan=read('config/p12-cont.json')['rows'];ledger=read('data/p12-cont-20261026-delivery-v2/startup-exclusion-ledger.json');counts=dict(collections.Counter(r['status'] for r in ledger))
checks['exact_all_assignment_statuses']=counts=={'VALID_FINISHED':25,'INVALID_INFRASTRUCTURE_INTERRUPTED':1,'REJECTED_FROZEN_AUDIT':1,'NOT_STARTED':21} and len(ledger)==len(plan)==48
byid={r['id']:r for r in plan};checks['all_start_input_hashes_match_freeze']=all(r['input_sha256']==byid[r['id']]['config_sha256'] for r in formal)
cases=read('data/p12-cont-20261026-delivery-v2/cases.json');denoms=read('data/p12-cont-20261026-delivery-v2/prediction-denominators.json')
checks['valid_cases_native_execution_target_score']=len(cases)==25 and all(read(f'data/p12-cont-20261026-formal/{i}/analysis/native/native-audit.json')['status']=='PASS' and read(f'data/p12-cont-20261026-formal/{i}/analysis/execution/execution.json')['status']=='PASS' and read(f'data/p12-cont-20261026-formal/{i}/analysis/score/score.json')['schema']=='p12-scoring-2' for i in cases)
checks['classification_and_full_peak_denominators']=sum(x['flight_samples'] for x in denoms.values())==175 and sum(x['full_peak_denominator'] for x in denoms.values())==167 and all(sum(x['risk_labels']['task_risk_comparison'].values())==25 for x in denoms.values())
checks['tilt_danger_miss_not_hidden_by_task_OR']=denoms['M4']['risk_labels']['risk_comparison']['DANGER_MISS']==1 and denoms['M4']['risk_labels']['task_risk_comparison']=={'AGREEMENT':25}
checks['new_audit_failure_not_reclassified']=read('data/p12-cont-20261026-formal/b3-ph2-NORMAL1/analysis/native/native-audit.json')['status']=='FAIL' and not (R/'data/p12-cont-20261026-formal/b3-ph2-NORMAL1/result.json').exists()
checks['no_pending_output_started']=all(not (R/'data/p12-cont-20261026-formal'/r['id']).exists() for r in ledger if r['status']=='NOT_STARTED')
sup=read('data/p12-cont-20261026-delivery-v2/final-supplement.json');repair=[c for c in sup['planned_event_captures'] if c['branch']=='REPAIR'];checks['real_planned_repair_mode2']=len(repair)==10 and all(c['mode']==2 and c['horizontal_velocity_input_error_m_s']==0 for c in repair)
checks['history_checks_pass']=all(read('data/p12-cont-20261026-delivery-v2/all-raw-derived-history-manifest.json')['original_ledgers_unchanged'].values())
checks['reproduction']=read('data/p12-cont-20261026-reproduction-final/reproduction.json')['status']=='PASS'
result={'schema':'p12-cont-final-audit-1','checks':checks,'status':'PASS' if all(checks.values()) else 'FAIL','status_counts':counts,'starts':{'old':9,'preparation':12,'formal':27,'cumulative':48},'scope':'offline evidence consistency only; does not override frozen audit stop or certify full feedback','new_SITL_starts':0}
output=D/'final-audit.json'
if output.exists():raise FileExistsError(output)
output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));sys.exit(not all(checks.values()))

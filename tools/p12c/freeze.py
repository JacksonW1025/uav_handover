#!/usr/bin/env python3
"""Seal engineering/design release, unchanged models and actual runtime before holdout."""
import json,sys,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p9_model import sha,write
import p2_batch
PREP=ROOT/'data/p12-cont-20261026-preparation';OUT=ROOT/'data/p12-cont-20261026-freeze'
def main():
 if OUT.exists():raise FileExistsError(OUT)
 old=[json.loads(x) for x in (ROOT/'data/p12-20261026-preparation/attempts.jsonl').read_text().splitlines()];items=[json.loads(x) for x in (PREP/'attempts.jsonl').read_text().splitlines()]
 if len([x for x in old if x['event']=='START_INTENT'])!=9:raise RuntimeError('old count changed')
 starts=[x for x in items if x['event']=='START_INTENT']
 if len(starts)>12 or any(x['budget_class']!='development' for x in starts):raise RuntimeError('preparation caps/splits')
 if any(x['event'] in ['STOP','EXCEPTION'] for x in items):raise RuntimeError('critical preparation error')
 ids=['window-09-single','window-11-AB-repair-intermediate','window-12-AB-native']
 gates={n:json.loads((PREP/('gate-'+n+'-final.json')).read_text()) for n in ids}
 if not all(g['engineering_status']=='PASS' for g in gates.values()):raise RuntimeError('observation/engineering failed')
 if len(starts)!=12:raise RuntimeError('unexplained starts')
 recovery=json.loads((PREP/'disconnect-recovery/recovery.json').read_text())
 if not recovery['candidate_unchanged']:raise RuntimeError('unexplained interrupted identity')
 acceptance={'schema':'p12-cont-acceptance-1','engineering_experimental_status':'PASS','interrupted_preparation_id':'window-10-single-repair','legacy_protocol_diagnosis':'pre-event-repair-diagnosis.json; old repair7 excluded from final protocol acceptance','preparation_starts':len(starts),'old_starts':9,'formal_starts':0,'gates':{n:g['engineering_status'] for n,g in gates.items()},'design':'blocked randomized; no strict same-initial-state claim; no post-treatment filtering','common_rule':'fixed world reference/native ack2s/30ms; T0 activation, repair only post-activation capture','comparability_status':'ACCEPTED_RANDOMIZED_DESIGN_WITH_RECORDED_INITIAL_UNCERTAINTY','strict_pairs':0,'actual_gate_classes':'read-native vs read-intermediate validated; capture relation reported as outcome','score_schema':'p12-scoring-2','runtime':'actual regular-file binary/plugin/weights copies with hash; no symlink snapshot','capacity':{'available_bytes':shutil.disk_usage(ROOT).free,'per_start_bound_bytes':400000000,'reserve_bytes':10000000000,'analysis_build_bytes':12000000000,'required_for48_bytes':41200000000},'theory_gate':{'status':'FULL_FEEDBACK_NOT_PROVEN','experimental_stop':False,'source_relations':'capture, entire decel reference, switched filter, conditional servo-LCP connection; M4 explicit repair sample-window','first_gap':'future impulse/residual admissible domain and body/EKF/cache feedback','A4':'NOT_PROVEN_EXCLUDED'},'catchup':'NOT_VALIDATED_CANCELLED; no assigned catchup flights','permission':'user expressly authorizes formal after gates/freeze push/remote readback; no general reconfirmation'}
 if acceptance['capacity']['available_bytes']<acceptance['capacity']['required_for48_bytes']:raise RuntimeError('capacity insufficient')
 write(PREP/'acceptance.json',acceptance);OUT.mkdir();models=OUT/'models';models.mkdir()
 source=ROOT/'data/p11-20261025-formal/models'
 for n in ['models.json','policy.npz','fit.json']:shutil.copy2(source/n,models/n)
 write(models/'seal.json',{'schema':'p12-cont-model-seal-1','model_sha256':sha(models/'models.json'),'policy_arrays_sha256':sha(models/'policy.npz'),'fit_sha256':sha(models/'fit.json'),'M2':'unchanged frozen P11 numeric model and semantics','M3':'unchanged P12 source baseline','M4':'same numeric plant with explicit repair sample-window; direct initial/history/filter interface; no fitting','new_fit':False,'seen_material':'P11 oldP12 and all12 continuation preparation; all48 continuation formal heldout for these sealed parameters','sealed_before_formal_starts':True,'formal_starts':0})
 write(OUT/'candidate.json',p2_batch.identity())
 paths=[ROOT/'config/p12-cont.json',*sorted((ROOT/'config/p12-cont-cases').glob('*.json')),PREP/'acceptance.json',PREP/'repeat-protocol.json',PREP/'experimental-protocol.json',PREP/'frozen-experimental-protocol.json',PREP/'window-protocol.json',PREP/'effect-scale-provenance.json',PREP/'pre-event-repair-diagnosis.json',PREP/'disconnect-recovery/recovery.json',PREP/'repeatability.json',PREP/'f4-repeatability.json',PREP/'execution-chain.json',PREP/'runtime-snapshot-window.json',PREP/'build-config-snapshot.json',ROOT/'docs/THOR_P12_CONT_PLAN.md',ROOT/'docs/THOR_P12_CONT_EXECUTION.md',*models.glob('*')]
 runtime=json.loads((PREP/'runtime-snapshot-window.json').read_text())
 for r in runtime['files']:
  if sha(ROOT/r['snapshot'])!=r['sha256'] or sha(ROOT/r['source'])!=r['sha256']:raise RuntimeError('runtime copy/source mismatch')
  paths.extend([ROOT/r['snapshot'],ROOT/r['source']])
 for entry in json.loads((PREP/'build-config-snapshot.json').read_text())['files']:
  paths.append(ROOT/entry['snapshot'])
 for n in ids:paths.append(PREP/('gate-'+n+'-final.json'))
 def label(p):
  try:return str(p.relative_to(ROOT))
  except ValueError:return str(p)
 write(OUT/'manifest.json',{'schema':'p12-cont-freeze-1','files':{label(p):sha(p) for p in paths},'old_count':9,'new_preparation':len(starts),'formal_count':0,'budget_cap':{'preparation':12,'formal':48,'new_total':60,'cumulative':69},'model_parameters_sealed':True,'theory_and_experiment_gates_separate':True,'randomization_before_formal':True})
 print('SEALED',sha(OUT/'manifest.json'),'files',len(paths))
if __name__=='__main__':main()

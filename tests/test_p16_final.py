"""Published P16 evidence cross-checks; reads small receipts, never starts flight."""
import json
from pathlib import Path
B=Path(__file__).resolve().parents[1]/'data/p16-20261028'
def read(p):return json.load(open(B/p))

def test_fixed_quality_independent_scorers_agree():
 a=read('analysis-v2-results/delivery.json');b=read('main-score-results-v1/result.json')
 for name in ['A_grid','A_cheap','G','R']:
  ms=a['methods'][name];computed=next((x['query'] for i,x in enumerate(ms['series']) if all(z['quality']['same_quality'] for z in ms['series'][i:])),None)
  assert computed==ms['first_persistent_joint_quality']==b['methods'][name]['first_persistent_joint_quality']
 assert a['comparisons']['G_vs_A_cheap']['query_saving']==2
 assert a['comparisons']['R_vs_G']['query_saving']==0

def test_actual_process_boots_not_virtual_queries():
 p=read('process-evidence-v1.json');s=[json.loads(x) for x in (B/'attempts.jsonl').read_text().splitlines()];starts=[x for x in s if x['event']=='START_INTENT']
 assert len(starts)==len({x['id'] for x in starts})==p['actual_PX4_starts']==p['actual_Gazebo_starts']==32
 assert {x['id'] for x in starts}=={x['id'] for x in p['rows']}
 assert all(x['seed']==x['real_gazebo_seed_argument'] and x['PX4_exit']==0 for x in p['rows'])
 assert {k:sum(x['stage']==k for x in starts) for k in ['development','main','replication']}==dict(development=2,main=24,replication=6)
 assert read('final-audit-v1/audit.json')['unresolved']==[]

def test_cached_policy_still_pays_query_and_unknown_costs_remain():
 d=read('analysis-v2-results/delivery.json');g=d['methods']['G']['series'];r=d['methods']['R']['series']
 assert all(a['query_wall_s']==b['query_wall_s'] and b['query_wall_s']>0 for a,b in zip(g[1:],r[1:]))
 assert all(not read(f'policies/R/queries/q{i:02d}/reveal-cost.json')['new_physical_START'] for i in range(1,9))
 assert d['costs']['initial_forecast_wall_s'] is None
 assert d['costs']['unknown_costs']
 assert r[-1]['R_extra_historical_calibration_CPU_s']>53
 assert g[-1]['R_extra_historical_calibration_CPU_s']==0
 assert read('cost-inventory-results-v4/inventory.json')['policy_scores_changed'] is False

def test_joint_accuracy_does_not_hide_axis_miss_and_censoring():
 d=read('analysis-v2-results/delivery.json');q=d['methods']['G']['series'][6]['quality']['components']
 assert q['task']['correct']==24 and q['task']['danger_as_safe']==0
 assert q['tilt']['danger_as_safe']==1
 assert q['height']['truth_unknown']==5 and q['height']['prediction_unknown']==4
 s=d['seed2_quality']['G'];assert s['same_quality'] is None
 assert s['components']['task']['correct']==6
 assert s['components']['tilt']['danger_as_safe']==1
 assert s['components']['height']['prediction_unknown']==2

def test_reuse_empty_acceptance_is_not_accuracy_evidence():
 d=read('analysis-v2-results/delivery.json');scope=read('reuse-scope-audit-v1.json');supp=read('analysis-supplement-results-v1/supplement.json')
 assert d['reuse']['accepted']==0 and supp['reuse']['max_observed_class_size']==0
 assert scope['raw_repeated_records']>scope['matching_suffix_repeated_records']>scope['unique_matching_suffix_pairs']==5
 assert len(read('actual-pair-diagnostic-results-v1/pairs.json')['records'])==14
 assert supp['common_final_unqueried']['G']['initial_on_same_unqueried']['components']['task']['correct']==16
 assert supp['common_final_unqueried']['G']['updated_on_same_unqueried']['components']['task']['correct']==16

def test_posthoc_task_baseline_not_substituted_for_frozen_primary():
 a=read('analysis-v2-results/A_grid-maps.json');b=read('task-only-grid-sensitivity-results-v1/result.json')
 assert read('analysis-v2-results/delivery.json')['methods']['A_grid']['first_persistent_joint_quality']==13
 assert b['first_persistent']==9 and 'retrospective' in b['scope']
 assert [x['selected']['id'] for x in a[1:]]==[x['selected']['id'] for x in b['maps'][:-1]]
 assert b['new_START']==0

def test_ablation_alias_repair_all_affected_maps_keeps_scores():
 receipt=read('analysis-v3-log-repair/receipt.json');assert receipt['maps_verified']==18
 assert receipt['predictions_and_scores_changed'] is False
 assert len(receipt['rows'])==5 and all(x['corrected_changed'] and not x['old_changed'] for x in receipt['rows'])
 for name in ['drop_state_timing','drop_L_D_prefixTilt']:
  old=read(f'analysis-v2-results/ablation-{name}.json');new=read(f'analysis-v3-log-repair/ablation-{name}.json')
  assert [(x['prediction'],x['quality']) for x in old]==[(x['prediction'],x['quality']) for x in new]

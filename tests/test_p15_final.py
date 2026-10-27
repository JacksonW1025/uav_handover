"""Independent final acceptance: mixed qualification, immutable scoring, reuse."""
import json,sys,importlib.util
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[1];B=R/'data/p15-20261027'
def read(p):return json.load(open(B/p))
def test_all_starts_counted_once_and_terminal():
 rr=[json.loads(l) for l in (B/'attempts.jsonl').read_text().splitlines()];ss=[r for r in rr if r['event']=='START_INTENT'];assert len(ss)==len({r['id'] for r in ss})==42
 from collections import Counter
 assert dict(Counter(r['budget_class'] for r in ss))==dict(development=6,search=32,map=4)
 for s in ss:assert any(r['event'] in ['FINISH','REVIEW_RESOLVED'] and r.get('id')==s['id'] for r in rr)
def test_scoped_missing_physics_does_not_become_full_pass():
 r=read('runs/p15-e-b2-M2-t3-F4-B/analysis-v2/result.json');assert r['qualified_controller_task'] and r['physical_record_status']=='INVALID_EMPTY_BUFFER';assert r['status']!='PASS'
 d=read('delivery-v2/method-total-costs.json')['M2'];assert d['qualified_task']==8 and d['full_platform_PASS']==7 and d['physical_invalid']==1
 assert read('evaluation-LP-only-v2/p15-e-b2-M2-t3-F4-B/summary.json')['future_inputs_used'] is False

def test_original_aux_tail_failure_retained():
 a=read('runs/p15-e-b2-M1-t3-F4-B/analysis-v1/result.json');b=read('runs/p15-e-b2-M1-t3-F4-B/analysis-v2/result.json');assert a['status']=='NOT_PASSED';assert b['status']=='PASS_SCORED_TASK_PREFIX_AUX_TAIL_UNKNOWN'
def test_component_denominators_do_not_hide_height_misses():
 d=read('delivery-v4/machine.json')['classification'];assert d['height']['nominal_miss']==d['height']['actual_FAIL']==3;assert d['height']['actual_UNKNOWN']==8
 for v in d.values():assert v['actual_FAIL']+v['actual_SUCCESS']+v['actual_UNKNOWN']==32
 assert d['tilt']['nominal_miss']==1 and d['tilt']['nominal_false_alarm']==2

def test_map_update_not_promoted_to_selection_gain():
 d=read('delivery-v4/map-update-effects.json');assert len(d)==4 and not any(x['selection_changed'] for x in d)
 for x in d:
  planned=read('runs/'+x['id']+'/run/p15-selection-input.json')['context']['A_start']+.3+1.8
  assert x['actual_controller_Bpre']['profile_s']<planned and x['updated_model_Bpre']['t']<planned and x['no_update_model_Bpre']['t']<planned
 for x in d[2:]:assert x['Bpre_comparison']['W']['updated_abs_error']>x['Bpre_comparison']['W']['no_update_abs_error']

def test_policy_support_limit_not_erased():
 d=read('controlled-support-audit-v2.json');assert not d['same_conditional_candidate_support_all4'];assert d['strict_same_pool_and_prefix_information_groups']==['M1','M2','M3'];assert read('delivery-v4/machine.json')['strict_comparison'].startswith('M1/M2/M3')

def test_same_model_reuse_preserves_clock_history_D():
 old=read('offline-reuse-v1/result.json');new=read('model-clock-reuse-v2/result.json');assert new['status']=='PASS' and len(new['rows'])==6
 for r in new['rows']:assert r['same_rows'] and r['trajectory_max_abs']<1e-10 and r['D_not_reset']
 assert new['K6_anchor_plus_reuse_CPU_s']<new['K6_full_recompute_CPU_s']

def test_crossing_keeps_first_prefix_bracket():
 spec=importlib.util.spec_from_file_location('supplement',B/'final-analysis-v4-source/supplement.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 assert m.crossing([0,.004,.008],[.8,1.1,.9],1)==[0.,.004]
 assert m.crossing([0,.004],[.8,1.],1) is None

def test_all36_taps_bitidentical_no_future_scoring_input():
 ids=[r['id'] for r in read('delivery-v2/physical-component-v1/all-starts.json') if r['budget_class']!='development']
 for rid in ids:
  q=read('taps/'+rid+'/result.json');assert q['core_bit_identical'] and q['future_inputs'] is False
  x=read('extra-metrics/'+rid+'/result.json')['Bpre'];assert x is not None and x['strictly_before_B']

def test_cost_contract_late_and_scope_explicit():
 q=read('delivery-v2/cost-allocation-audit.json');assert q['rule_registered_after_two_START'] and q['unviewed_labels_independent_audit'].startswith('UNAVAILABLE');assert 'not chronological' in q['curve_kind']

def test_final_history_and_source_content_no_drift():
 q=read('final-retention-v2/result.json');assert q['status']=='PASS' and q['historical_files_checked']==101618 and not q['historical_changed'] and not q['frozen_source_drift'];assert q['all_PX4_zero'] and q['raw_unique_inode_bytes']>0

def test_map_edge_is_explicit_conditional_point_not_joint_certificate():
 q=read('delivery-v4/map-edge.json');assert 'NO_CERTIFIED_JOINT_TUBE' in q['status'];assert 'not physicalCOM' in q['model'];s=q['output']['successor'];assert all(k in s for k in ['h','previous','mean','count','filter','read_pending','D','prefix_failure_latch']);assert q['output']['reusable_clock_origin']['sample_us']>0

def test_host_end_state_is_actual_host_observation():
 q=read('final-host-state-v1/result.json');assert 'actual host' in q['source'] and q['no_owned_experiment_processes'] and q['matching_processes']==[]

import json,sys,copy
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'tools'))
from p15.state import parse
from p15.model import rank,rollout
from p15.prepare import config
from run_experiment import p5_profile,Experiment
from types import SimpleNamespace

def recorded():
 log=R/'data/p14h-20261027/runs/p14h-d01-F4-A-before-s142710201/run/logs/commands.log'
 for l in log.read_text().splitlines():
  d=json.loads(l)
  if 'TOPIC: research_p11' in d['output']:return parse(d['output'])
 raise AssertionError('missing fixture')

def test_parse_complete_row():
 s=recorded();assert len(s['gru_after'])==16 and len(s['policy_input'])==22;assert s['timestamp_sample']>0

def test_missing_field_not_zero():
 import pytest
 with pytest.raises((AssertionError,ValueError)):parse('timestamp: 1')

def test_prefix_common_reference_unchanged():
 cfgs=[config('F2',dict(prefix=p,budget_class='development',method='M3',seed=1)) for p in ['NORMAL','A','B','AB']];tables=[]
 for c in cfgs:
  s=c['p5']['conditions']['p11-case'];p=p5_profile(c['p5'],s);ns=SimpleNamespace(cfg={'p1_speed_m_s':s['speed_m_s']},pcfg=p);tables.append([Experiment.p1_profile(ns,float(t)) for t in np.arange(0,30,.02)])
 assert tables[0]==tables[1]==tables[2]==tables[3]

def test_equal_information_random_and_magnitude():
 s=recorded();s.update(LP_W_m_s=.2,tilt_deg=5);pool=[dict(id='a',G=1.2,D=.24,prefix='AB'),dict(id='b',G=1.8,D=.38,prefix='AB')];ctx=dict(D_LP=.1)
 for method in ['M0','M1','M2']:
  a=rank(s,pool,ctx,{},None,method,np.random.default_rng(4));assert set(x['candidate']['id'] for x in a['rows'])=={'a','b'};assert a['not_safety_classification']

def test_selection_ignores_future_keys():
 s=recorded();s.update(LP_W_m_s=.2,tilt_deg=5);p=[dict(id='a',G=1.2,D=.24,prefix='AB')];a=rank(s,p,{'D_LP':0},{},None,'M2',np.random.default_rng(1));s['actual_future_risk']='FAIL';s['truth_B']=999;b=rank(s,p,{'D_LP':0},{},None,'M2',np.random.default_rng(1));assert a['rows']==b['rows']

def test_historical_frozen_no_change():
 assert json.load(open(R/'data/p15-20261027/baseline.json'))['HEAD']=='82ac9fa476a73a61b5dd31619921ec5e6de68856'

def test_local_update_is_mode_dynamics_and_bounded():
 from p15.update import local
 p={'full_prefix':[[1.,.1,.1,.2,3],[1.2,.2,.2,.3,4]]};s={'profile_s':1.2,'LP_W_m_s':1.3,'position':[0,0,-2.8]};u=local(p,s,{'A_start':.5,'A_duration':.3,'H0_LP':3.});assert u['vertical_acceleration_residual']==.5 and u['no_history_or_D_reset'];assert u['not_future_hard_bound']

def test_quota_code_materialized_before_formal():
 p=R/'data/p15-20261027/development-stage3/plan.json';d=json.load(open(p));assert [r['prefix'] for r in d['rows']]==['B','AB','AB'];assert d['rows'][-1]['decision_phase']=='postA'

def test_reserve_direction_and_failure_not_erased():
 from p15.map import reserve
 assert reserve(-1,2)==0 and reserve(2,2)==1
 import pytest
 with pytest.raises(ValueError):reserve(1,0)

def test_live_query_budget_and_phase_guards_are_explicit():
 source=(R/'tools/p15/state.py').read_text();assert "timeout=.1" in source
 source=(R/'tools/p15/runner.py').read_text();assert 'preA selection completed after A' in source and 'decision information phase violation' in source and 'self.p15_failed or' in source

def test_pending_review_blocks_queue():
 source=(R/'tools/p15/campaign.py').read_text();assert "['FINISH','REVIEW_RESOLVED']" in source

def test_complete_successor_composition_is_preserved():
 d=json.load(open(R/'data/p15-20261027/theory-check-v2/composition.json'));assert d['status']=='PASS' and d['max_abs']<1e-10;assert d['full_history_D_publisher_pending_retained']

def test_projection_common_A_does_not_erase_failure():
 source=(R/'tools/p15/model.py').read_text();assert 'prefix_failure_latch=failed' in source and 'whole_prefix_score_v1' in source and 'B_new_D_m' in source

def test_map_update_has_independent_past_provenance():
 source=(R/'tools/p15/runner.py').read_text();assert 'p15-inherited-update.json' in source and 'source_role' in source

def test_formal_methods_have_equal_information_schedule_and_budgets():
 d=json.load(open(R/'data/p15-20261027/search-freeze-v2/plan.json'));assert len(d['rows'])==32
 for block in [1,2]:
  ref=None
  for method in ['M0','M1','M2','M3']:
   rr=[r for r in d['rows'] if r['block']==block and r['method']==method];assert len(rr)==4
   schedule=sorted((r['trial'],r['family'],r['decision_phase']) for r in rr)
   if ref is None:ref=schedule
   else:assert ref==schedule
   if method!='M0':assert sorted(r['prefix'] for r in rr)==['AB','AB','B','B']
   for r in rr:assert not r['prestart_prediction']['future_new_data_used']

def test_map_validation_uses_distinct_seeds_and_past_source():
 d=json.load(open(R/'data/p15-20261027/map-freeze-v2/plan.json'));rr=d['rows'];assert len(rr)==4 and len(set(r['seed'] for r in rr))==4
 assert rr[0]['map_loop'] and rr[1]['map_loop'];assert 'p15-m01-F2' in rr[2]['local_update_path'] and 'p15-m02-F4' in rr[3]['local_update_path']

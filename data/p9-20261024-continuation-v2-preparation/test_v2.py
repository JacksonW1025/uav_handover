import copy,json,sys
from pathlib import Path
import pytest
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parents[1]/'tools'))
import measurement_v2 as m
from run_v2 import claim_continuation
ROOT=HERE.parents[1]

def ev():
 return dict(safety_abort=True,closed_count=0,first_gap_started=True,explicit_windows=True,phase_matches=True,captures=[1204000],receptions=[990000,1000000],later_reception=False,delay_bounds=[200000,216000],capture_parameters_match=True,profile_start=0,ownership_end=1400000,expected_first_gap=1010000,state_continuity=True)

@pytest.mark.parametrize('field,value',[('safety_abort',False),('closed_count',1),('first_gap_started',False),('explicit_windows',False),('phase_matches',False),('captures',[]),('captures',[1204000,1210000]),('receptions',[]),('later_reception',True),('capture_parameters_match',False),('state_continuity',False),('ownership_end',1100000),('expected_first_gap',2000000),('delay_bounds',[205000,216000])])
def test_missing_or_inconsistent_evidence_abstains(field,value):
 e=ev();e[field]=value;assert m.validate_open_evidence(e)[0] is None

def test_supported_anchor_and_boundaries():
 assert m.validate_open_evidence(ev())==(1000000,None)
 for d in [200000,216000]:
  e=ev();e['captures']=[1000000+d];assert m.validate_open_evidence(e)[0]==1000000

def test_compatible_path_returns_same_dict_including_later_open(monkeypatch,tmp_path):
 old={'clock_origin_native_us':1.,'clock_origin_spread_us':1.,'max_tilt_deg':1.,'max_altitude_loss_m':1.,'max_lag_m':1.,'max_horizontal_distance_m':1.,'integrated_abs_lag_m_s':1.,'status':'MEASURED','open_gap':True,'recoveries':[{'index':0,'vehicle_catch_up_10s_s':None}],'complete_window':False}
 monkeypatch.setattr(m.p9_metrics,'analyze',lambda p:old)
 a=m.analyze(tmp_path);assert a['kind']=='ORIGINAL_COMPATIBLE' and a['measurement'] is old

def test_non_anchor_error_never_infers_success(monkeypatch,tmp_path):
 def bad(p):raise ValueError('insufficient cruise setpoints for fixed-window native-clock origin')
 monkeypatch.setattr(m.p9_metrics,'analyze',bad)
 a=m.analyze(tmp_path);assert a['kind']=='UNMEASURABLE' and a['measurement'] is None

def test_missing_topic_structured_NA(monkeypatch,tmp_path):
 def bad(p):raise KeyError('vehicle_attitude')
 monkeypatch.setattr(m.p9_metrics,'analyze',bad)
 assert m.analyze(tmp_path)['kind']=='UNMEASURABLE'

def test_real162_is_separate_censored_not_recovery():
 a=m.analyze(ROOT/'data/p9-20261024-continuation-v1-formal/D-07-P9-Z/run')
 assert a['kind']=='OPEN_GAP_CENSORED',a
 v=a['measurement'];assert v['censored'] and not v['complete_window'] and v['recoveries']==[]
 assert v['final_task_cost_outcome']=='UNOBSERVED_FINAL_RESUME'
 assert v['max_tilt_deg']==pytest.approx(47.14847183227539)
 assert a['known_outcomes']['altitude_failure'] is None
 assert not (ROOT/'data/p9-20261024-continuation-v1-formal/D-07-P9-Z/run/p9-metrics.json').exists()

def test_real102_cannot_be_recovered():
 a=m.analyze(ROOT/'data/p9-20261024-formal/C-CZ15-g0.1-reference-P9-Z/run')
 assert a['kind']=='UNMEASURABLE' and a['measurement'] is None

def intents(n):
 return [{'event':'START_INTENT','budget_class':'development','id':'dev'+str(i)} for i in range(10)]+[{'event':'START_INTENT','budget_class':'formal','id':'old'+str(i)} for i in range(n)]

def test_cap174_and_known_ids_rejected():
 rows=json.loads((ROOT/'data/p9-20261024-continuation-v2-freeze/plan.json').read_text())['runs'];row=rows[0]
 with pytest.raises(RuntimeError):claim_continuation(intents(173),row)
 for rid in ['C-CZ15-g0.1-reference-P9-Z','D-07-P9-Z',row['id']]:
  x=intents(162);x[-1]['id']=rid
  with pytest.raises(RuntimeError,match='already attempted'):claim_continuation(x,dict(row,id=rid))
 assert claim_continuation(intents(162),row)==163
 with pytest.raises(RuntimeError,match='unplanned'):claim_continuation(intents(162),{'id':'not-in-plan'})

def test_remaining11_are_original_unchanged_order():
 old=json.loads((ROOT/'data/p9-20261024-freeze/plan.json').read_text())['runs']
 ledger=[json.loads(x) for x in (ROOT/'data/p9-20261024-preparation/attempts.jsonl').read_text().splitlines()]
 started={x['id'] for x in ledger if x['event']=='START_INTENT'}
 new=json.loads((ROOT/'data/p9-20261024-continuation-v2-freeze/plan.json').read_text())['runs']
 assert new==[r for r in old if r['id'] not in started] and len(new)==11

def test_missing_samples_never_create_recovery():
 import numpy as np
 t=np.array([0.,.01,.02,.6,.61,.62]);z=np.zeros(len(t))
 assert m.p9_metrics.catch_up(t,z,z,0) is None
 t=np.arange(0.,11.,.01)
 assert m.p9_metrics.catch_up(t,np.ones(len(t)),np.zeros(len(t)),0) is None

def test_thresholds_remain_original_and_missing_future_is_unknown(monkeypatch,tmp_path):
 old={'clock_origin_native_us':1.,'clock_origin_spread_us':1.,'max_altitude_loss_m':1.,'max_lag_m':1.,'max_horizontal_distance_m':1.,'integrated_abs_lag_m_s':1.,'status':'MEASURED','max_tilt_deg':45.,'tilt_ge_45_failure':True,'task_failure':False,'task_outcome':'CENSORED','complete_window':False}
 monkeypatch.setattr(m.p9_metrics,'analyze',lambda p:old)
 assert m.analyze(tmp_path)['measurement']==old

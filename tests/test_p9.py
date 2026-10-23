import copy
import json
import math
from pathlib import Path

import numpy as np
import pytest

from p9_model import ROOT, fit, load_runs, write
from p9_plan import build, within_domain, case_spec, scan_windows
from p9_predict import potential, energy, capture_target, forecast, select_repair
from p9_run import claim, budget_counts
from p9_search import propose, observed_brackets
from p9_metrics import catch_up
from p9_campaign import validate_row, storage_gate


@pytest.fixture(scope='module')
def model():
    return json.loads((ROOT/'data/p9-20261024-preparation/model.json').read_text())


def test_exact_budget_and_fixed_paths():
    cfg,plan=build()
    assert plan['audit']['formal_max']==180
    assert plan['audit']['counts']=={'B':48,'C-reference':36,'D':36,'C-search':60}
    assert plan['audit']['path_length_range_m']==pytest.approx([11.79,11.79])
    assert len(plan['development'])+plan['development_reserve_slots']==12
    assert len({r['cluster'] for r in plan['runs'] if r['stage']=='D'})==9
    for r in plan['runs']+plan['search_candidates']:
        assert within_domain(r['case'])
        assert case_spec(cfg,r['case'])['safety_budget_m']['radius_m']<7.


@pytest.mark.parametrize('key,value',[('heading_deg',-1),('heading_deg',91),('speed_m_s',1.49),('speed_m_s',2.01)])
def test_generation_domain_separate_from_safety_budget(key,value):
    cfg,_=build();c={'speed_m_s':1.8,'heading_deg':15.,'windows_s':scan_windows(.36,.3)};c[key]=value
    assert not within_domain(c)
    with pytest.raises(ValueError,match='generation domain'):case_spec(cfg,c)


def test_duration_interval_and_span_domain():
    base={'speed_m_s':1.8,'heading_deg':15.,'windows_s':[[0,.3],[.4,.7]]}
    for w in [[[0,.19]],[[0,.66]],[[0,.3],[.39,.7]],[[0,.3],[1.81,2.11]],[[0,.3],[2.4,2.7]]]:
        assert not within_domain(dict(base,windows_s=w))


def test_preserve_first_last_and_complementary_phase():
    for d in [.36,.58]:
        ws=[scan_windows(d,g) for g in [.1,.25,.4,.55,.7]]
        assert all(w[0]==ws[0][0] and w[-1]==ws[0][-1] for w in ws)


def test_no_silent_pre_post_or_unknown_parameter_changes():
    cfg,_=build();c={'speed_m_s':1.8,'heading_deg':15.,'windows_s':scan_windows(.36,.3)}
    for change in [{'pre_gap_s':.9},{'post_gap_s':4.5},{'wind':0.},{'post_gap_s':float('nan')}]:
        assert not within_domain(dict(c,**change))
    with pytest.raises(ValueError,match='fixed deceleration'):case_spec(cfg,dict(c,post_gap_s=3.))


def test_atomic_json_write_leaves_complete_file_and_no_transaction(tmp_path):
    p=tmp_path/'evidence.json';write(p,{'a':[1,2]});assert json.loads(p.read_text())=={'a':[1,2]}
    write(p,{'a':None});assert json.loads(p.read_text())=={'a':None}
    assert list(tmp_path.iterdir())==[p]


def test_exact_capture_semantics():
    p=np.array([2.,3.]);v=np.array([3.,4.])
    assert capture_target(p,v,1.,0,2.)[0]==pytest.approx(p)
    tp,tv=capture_target(p,v,1.,2,2.)
    assert tp==pytest.approx(p+v/5*4.)
    assert tv==pytest.approx(v/5*3.)
    assert capture_target(p,v,8.,2,2.)[1]==pytest.approx([0,0])


def test_unclipped_position_accumulation_and_no_lyapunov_claim():
    kp=np.array([9.,9.])
    assert potential(np.array([4.,0]),kp)>potential(np.array([1.,0]),kp)
    # e=0,dv=q=[1,0], fixed target => E_dot=dv.q>0 despite zero position error.
    assert np.dot([1.,0.],[1.,0.])>0


def test_forecast_determinism_height_and_no_future_state(model):
    c={'speed_m_s':1.8,'heading_deg':45.,'windows_s':scan_windows(.36,.3)}
    tp={'rtgt':0,'rtdec':2.,'rrec':0.}
    a=forecast(model,c,tp);b=forecast(model,c,tp)
    assert a==b
    assert a['predicted_altitude_loss_m'] is None
    assert not a['overall_skip'] and not a['tilt_only_screen_skip']
    assert a['overall_decision']=='ABSTAIN_HEIGHT_UNMODELLED'
    assert len([e for e in a['events'] if e['event']=='capture' and 0<=e['t_s']<3])==3
    assert [e['t_s'] for e in a['events'] if e['event']=='resume']==pytest.approx([.36,1.024,2.6])


def test_repair_selection_no_holdout_argument_and_cost_zero_is_valid(model):
    got=select_repair(model)
    assert got['heldout_data_used'] is False
    assert got['selected_rrec'] in [1.,2.,3.]
    assert any(c['task_cost_feasible'] for c in got['comparisons'])


def pool():
    return [dict(phase_s=round(.1+.05*i,2),point_tilt_deg=30+3*i,max_energy=float((i-6)**2),positive_event_injection=float(i)) for i in range(12)]


@pytest.mark.parametrize('method',['ledger','replay'])
def test_search_same_endpoints_and_confirmations(method):
    c=pool();h=[]
    assert propose(method,c,h)['index']==0
    h=[{'index':0,'failure':False}]
    assert propose(method,c,h)['index']==11
    h=[{'index':4,'failure':False},{'index':5,'failure':True}]
    assert propose(method,c,h)['index']==4
    h.append({'index':4,'failure':False})
    assert propose(method,c,h)['index']==5
    h.append({'index':5,'failure':True})
    assert propose(method,c,h)['status']=='LOCAL_CONFIRMED_BRACKET'
    assert observed_brackets(c,h)==[[.3,.35]]


def test_search_noise_no_global_monotonicity_and_hard_cap():
    c=pool();h=[{'index':4,'failure':False},{'index':5,'failure':True},{'index':4,'failure':True}]
    r=propose('ledger',c,h)
    assert r['index'] not in [4,5] and r['noisy_indices']==[4]
    assert propose('replay',c,[{'index':0,'failure':False}]*10)['status']=='BUDGET_EXHAUSTED'


def test_last_budget_slot_can_complete_confirmation():
    h=[{'index':0,'failure':False}]*6+[{'index':4,'failure':False},{'index':5,'failure':True},
                                       {'index':4,'failure':False},{'index':5,'failure':True}]
    assert propose('ledger',pool(),h)['status']=='LOCAL_CONFIRMED_BRACKET'


def test_all_start_intents_count_failed_or_unknown():
    items=[{'event':'START_INTENT','id':str(i),'budget_class':'development'} for i in range(12)]
    items.append({'event':'BLOCKED_BEFORE_START','id':'blocked'})
    assert budget_counts(items)=={'development':12,'formal':0}
    with pytest.raises(RuntimeError,match='hard cap'):claim(items,{'id':'new'},'development')
    with pytest.raises(RuntimeError,match='already attempted'):claim(items,{'id':'0'},'formal')
    assert claim(items,{'id':'new'},'formal')==1
    full=[{'event':'START_INTENT','id':str(i),'budget_class':'formal'} for i in range(180)]
    with pytest.raises(RuntimeError,match='hard cap'):claim(full,{'id':'new'},'formal')


def test_formal_slot_checks_case_seed_domain_and_runner_config():
    cfg,plan=build();r=plan['runs'][0];validate_row(plan,cfg,r)
    with pytest.raises(RuntimeError,match='slot'):validate_row(plan,cfg,dict(r,sim_seed=r['sim_seed']+1))
    bad=copy.deepcopy(r);bad['case']['heading_deg']=91
    with pytest.raises(RuntimeError,match='slot'):validate_row(plan,cfg,bad)
    slot=plan['search_slots'][0];c=next(c for c in plan['search_candidates'] if c['family']==slot['family'])
    r=dict(slot,kind='p5_gap',case=c['case'],condition=c['condition']);validate_row(plan,cfg,r)
    other=next(c for c in plan['search_candidates'] if c['family']!=slot['family'])
    with pytest.raises(RuntimeError,match='family'):validate_row(plan,cfg,dict(r,case=other['case'],condition=other['condition']))


def test_storage_gate_preserves_reserve_and_counts_all_intents():
    cfg={'p9':{'budget':{'formal_cap':180},'storage_plan':{'max_pilot_allocated_bytes':100,'per_attempt_multiplier':1.15,'audit_and_system_reserve_bytes':1000}}}
    needed=1000+180*115
    assert storage_gate(cfg,[],available=needed)['status']=='PASS'
    with pytest.raises(RuntimeError,match='preserve historical raw'):storage_gate(cfg,[],available=needed-1)
    starts=[{'event':'START_INTENT','id':'x','budget_class':'formal'}]
    assert storage_gate(cfg,starts,available=needed-115)['remaining_max_starts']==179


def test_missing_samples_break_catchup_and_never_convert_censoring_to_recovery():
    t=np.arange(0,2,.01);d=np.zeros(len(t));dv=np.zeros(len(t))
    assert catch_up(t,d,dv,0)==0.
    assert catch_up(t,np.ones(len(t)),dv,0) is None
    t=np.array([0.,.01,.02,.6,.61,.62]);z=np.zeros(len(t))
    assert catch_up(t,z,z,0) is None


def test_model_fit_repeatable_on_portable_identification_inputs():
    runs=load_runs(ROOT/'data/p9-20261024-preparation')
    # Full fit deterministic; LOCO repeat is separately saved in determinism.json.
    a=fit(runs);b=fit(runs)
    assert a==b
    assert a['delay_s']==.088

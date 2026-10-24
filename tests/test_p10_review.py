"""Offline source-application regression tests, independent of A2 constructor."""
import ast
import copy
import importlib.util
import json
from fractions import Fraction as F
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('p10review', ROOT/'tools/p10review/verify.py')
v = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(v)


def proposal():
    return {'include_reposition': True, 'publisher_phase_us': -2000,
            'first_grid_us': -5000000, 'EP': str(v.EP), 'EV': str(v.EV),
            'w_P_budget': '1/10000000', 'A2_prepopulated_slots': 22,
            'source_initialization_relation_proved': False}


def test_exact_tail_counterexample_survives_original_float_envelopes():
    c, _ = v.first_held_counterexample()
    assert F(c['delta_position_m']) == F(1, 10**6)
    assert F(c['source_velocity_m_s']) == -F(1, 1000)
    assert F(c['position_excess_after_source_EP_and_A2_EP_m']) > 0
    assert F(c['velocity_excess_after_source_EV_and_A2_EV_m_s']) > 0
    assert F(c['binary32_position_discrepancy_m']) > v.EP
    assert F(c['binary32_velocity_discrepancy_m_s']) > v.EV
    assert v.refuse_changed_application(proposal()).startswith('REJECT')


@pytest.mark.parametrize('key,value', [
    ('include_reposition', False), ('publisher_phase_us', 0),
    ('first_grid_us', -4996000), ('EP', '1/1000'), ('EV', '1/100'),
    ('w_P_budget', '1/10'), ('A2_prepopulated_slots', 0),
    ('source_initialization_relation_proved', True),
])
def test_no_silent_budget_clock_warmup_or_initialization_rescue(key, value):
    p = proposal();p[key] = value
    with pytest.raises(ValueError, match='UNREVIEWED'):
        v.refuse_changed_application(p)


@pytest.mark.parametrize('key,value', [
    ('gate', 'PASSED'), ('actual_complete_source_sequence_certified', True),
    ('B_C_D_authorized', True), ('new_SITL_starts', 1),
    ('manual_proxy_theorem_retained_with_its_assumptions', False),
])
def test_canonical_gate_refuses_misleading_scope(key, value):
    d = v.declaration();d[key] = value
    with pytest.raises(ValueError, match='GATE_OR_SCOPE'):
        v.require_declaration(d)


def test_empty_startup_and_prefilled_history_are_distinct():
    j = v.initialization_gap()
    assert j['P9_prediction']['initial_queue'] == 'empty'
    assert j['P9_prediction']['full_delay_intervals'] == 11
    assert j['A2_proxy']['new_model'] and not j['A2_proxy']['exact_resampling_of_P9']
    assert j['native']['source_to_proxy_step_simulation'] == 'UNPROVEN'


def test_source_correspondence_keeps_order_and_unclosed_relations():
    s = v.source_correspondence()
    assert len(s['checked_relations']) == 4 and len(s['unclosed']) == 4
    assert s['source_guard_times_conditional'] == [204000, 520000, 11704000]
    c = v.gates_and_coverage()
    assert c['overall_gate'] == 'NOT_PASSED'
    assert c['coverage'][0]['location_us'] == -5000000
    assert c['coverage'][0]['cause'] == 'REFERENCE_PRECONDITION_FALSE'


def test_reproducible_audit_and_refuse_output_overwrite(tmp_path):
    gate = ROOT/'config/p10_a_gate.json'
    v.run(tmp_path/'first', gate);v.run(tmp_path/'second', gate)
    for p in (tmp_path/'first').iterdir():
        assert p.read_bytes() == (tmp_path/'second'/p.name).read_bytes()
    with pytest.raises(FileExistsError):
        v.run(tmp_path/'first', gate)


def test_pure_source_oracle_does_not_import_or_execute_runner():
    cls, functions = v.extract_runner_profiles()
    assert set(functions) == {'profile_cfg', 'reposition', 'p1_profile'}
    assert set(n for n in vars(cls) if not n.startswith('__')) == set(functions)
    tree = ast.parse((ROOT/'tools/p10review/verify.py').read_text())
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            assert not {'subprocess', 'rclpy', 'os'}.intersection(x.name for x in n.names)
        if isinstance(n, ast.ImportFrom):
            assert n.module not in {'run_experiment', 'p10r2.construct', 'p10r2.verify'}

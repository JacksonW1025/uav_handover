"""Offline proof rejection tests: deliberately tampered claims must fail."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('p10_verify', ROOT/'tools/p10/verify.py')
verify = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify)
CERT = ROOT/'data/p10-20261024-a/construction/certificate.json'


def test_frozen_local_certificate():
    result = verify.verify(CERT)
    assert result['P10_A_operational_gate'] == 'NOT_PASSED'
    assert result['witness']['prefixes_checked'] == 251
    assert result['domain']['height'] == 'UNMODELLED_OVERALL_ABSTAIN'
    assert 'discrete' in result['proof_scope']
    assert 'excludes continuous/discrete' in result['quantization_residual_scope']
    assert all(not j['complete_sequence_repair_guarantee'] for j in result['jump_constraints'])


@pytest.mark.parametrize('mutation', ['negative_P', 'reset_queue', 'deleted_resume',
                                    'scale_change', 'model_substitution', 'zero_radius'])
def test_reject_tampered_certificate(tmp_path, mutation):
    doc = copy.deepcopy(json.loads(CERT.read_text()))
    if mutation == 'negative_P':
        doc['axes'][0]['P_integer'][0][0] = -1
    elif mutation == 'reset_queue':
        doc['axes'][0]['center_integer'][6][3:] = [0]*22
    elif mutation == 'deleted_resume':
        # Continue the captured deceleration target instead of the external
        # resume. At 40 ms this would leave e=.0016 and dv=.08.
        doc['axes'][0]['center_integer'][5][:2] = [1600000000, 80000000000]
    elif mutation == 'scale_change':
        doc['state_scale'] = 10**9
    elif mutation == 'model_substitution':
        doc['model_sha256'] = '0'*64
    else:
        doc['initial_P_radius'] = '0'
    path = tmp_path/'tampered.json'
    path.write_text(json.dumps(doc))
    with pytest.raises((AssertionError, ValueError)):
        verify.verify(path)


def test_no_experiment_imports_or_launches():
    import ast
    for name in ['certificate.py', 'verify.py', 'evidence.py', 'scope_check.py', 'counterexample_search.py']:
        tree = ast.parse((ROOT/'tools/p10'/name).read_text())
        forbidden = {'subprocess', 'os', 'rclpy', 'p9_run', 'run_experiment'}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not forbidden.intersection(x.name for x in node.names)
            if isinstance(node, ast.ImportFrom):
                assert (node.module or '').split('.')[0] not in forbidden


def test_exact_exponential_enclosure():
    from fractions import Fraction
    lo, hi = verify.rho_bounds()
    assert hi-lo < Fraction(1, 10**35)
    assert lo > Fraction(9048, 10000) and hi < Fraction(9049, 10000)


def test_non_markov_current_state():
    from fractions import Fraction as F
    model = json.loads((ROOT/'data/p9-20261024-freeze/model.json').read_text(), parse_float=F)
    a = verify.transition(model['kp'][0], model['kv'][0], verify.rho_bounds()[0])
    one, two = [F(0)]*25, [F(0)]*25
    two[-2:] = [F(1, 10), F(1, 5)]
    assert one[:3] == two[:3]
    assert verify.mv(a, one)[2] != verify.mv(a, two)[2]


def test_instant_jump_budget_covers_pre_ball_and_event_error_only():
    from fractions import Fraction as F
    doc = json.loads(CERT.read_text())
    p = [[F(x, doc['P_scale']) for x in row] for row in doc['axes'][0]['P_integer']]
    bound = verify.instant_jump_constraint(p, F(1, 10))
    full = verify.instant_jump_constraint(p, F(1))
    assert F(bound['pre_P_radius'])**2 == F(1, 100)
    assert F(bound['event_error_P_radius']) == F(1, 20)
    assert F(bound['remaining_squared_nominal_budget']) == (7-F(1, 10)-F(1, 20))**2
    assert F(bound['post_event_center_V']) == F(full['post_event_center_V'])/100
    assert bound['decision'] == 'PROXY_ADMISSIBLE'
    assert full['decision'] == 'UNKNOWN_TEST_REQUIRED'
    assert not bound['subsequent_prefixes_verified']
    assert not bound['complete_sequence_repair_guarantee']

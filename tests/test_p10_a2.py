"""P10-A2 source-semantic and proof-refusal tests; offline only."""
import copy
import csv
import gzip
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('p10a2verify', ROOT/'tools/p10r2/verify.py')
v = importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(v)
INPUT = ROOT/'data/p10-20261024-a2/construction-reviewed'


def fixture(tmp_path):
    cert = json.loads((INPUT/'certificate.json').read_text())
    with gzip.open(INPUT/'trace.csv.gz', 'rt') as f:
        rows = [[int(x) for x in row] for row in csv.reader(f)]
    out = tmp_path/'input';out.mkdir()
    return cert, rows, out


def save(cert, rows, out):
    (out/'certificate.json').write_text(json.dumps(cert))
    with gzip.open(out/'trace.csv.gz', 'wt', newline='') as f:
        csv.writer(f).writerows(rows)


def test_complete_class_and_strict_timeout():
    result = v.verify(INPUT)
    assert result['prefixes'] == 5251 and result['new_flights'] == 0
    assert [(e['kind'], e['native_us']) for e in result['events']] == [('CAPTURE',204000),('RESUME',520000),('CAPTURE',11704000)]
    assert any(g['native_us'] == 200000 and not g['stale'] for g in result['strict_equality_guards_verified'])
    assert result['old_raw_certificate_entire_set_counterexample']['native_us'] == -1800000
    assert result['height_and_task_cost'] == 'not certified; overall ABSTAIN'


@pytest.mark.parametrize('key,value', [('stale_operator','>='), ('native_period_us',8000),
    ('initial_recovery_active',True), ('history_reset_on_capture',True), ('rrec',1),
    ('ignored_jitter',True), ('observation_us',[-5000000,2000000]),
    ('initial_position_generator_m','0'), ('gap_windows_us',[]), ('rsh',0),
    ('active_throughout',False), ('binary32_RNE',False)])
def test_reject_wrong_guard_clock_extra_start_and_unknown_inputs(tmp_path, key, value):
    cert, rows, out = fixture(tmp_path);cert[key] = value;save(cert,rows,out)
    with pytest.raises((AssertionError,ValueError)):
        v.verify(out)


@pytest.mark.parametrize('mutation', ['clear_history', 'missing_event', 'publication_as_read_clock', 'wrong_constrained_reset'])
def test_reject_trace_semantic_mutations(tmp_path, mutation):
    cert, rows, out = fixture(tmp_path)
    index = next(i for i,r in enumerate(rows) if r[19] == 1)
    if mutation == 'clear_history':
        # Clearing the delay queue changes the next physical q response.
        rows[index+1][3] = 0
    elif mutation == 'missing_event':
        rows[index][19] = 0
    elif mutation == 'publication_as_read_clock':
        rows[0][17] = rows[0][16]
    else:
        # At capture, e/d generator must use the same body variables.
        rows[index][12] += 10**8
    save(cert,rows,out)
    with pytest.raises((AssertionError,ValueError)):
        v.verify(out)


def test_reject_saturation_and_threshold_crossing():
    from fractions import Fraction as F
    for ep,dv in [(F(1,2),F(0)), (F(0),F(1)), (F(3,5),F(1,5))]:
        with pytest.raises(ValueError, match='SATURATION'):
            v.require_unsaturated(ep,dv)


def test_stop_profile_sign_uncertainty_is_enclosed():
    from fractions import Fraction as F
    cap = ([F(2),F(0),F(0)],[F(0),F(1,1000),F(0)],F(0),F(0),0)
    rp,rv,pe,ve,phase = v.cap_reference(cap,4000)
    assert phase == 'STOPPED_ALL_SET' and rv == [0,0,0]
    assert pe >= F(1,1000)**2/4


def test_no_simulator_imports():
    import ast
    for name in ['construct.py','verify.py']:
        for node in ast.walk(ast.parse((ROOT/'tools/p10r2'/name).read_text())):
            if isinstance(node,ast.Import):
                assert not {'subprocess','rclpy','os'}.intersection(x.name for x in node.names)
            if isinstance(node,ast.ImportFrom):
                assert (node.module or '').split('.')[0] not in {'run_experiment','p9_run','subprocess'}


def test_portable_source_order_and_map_hash():
    import hashlib
    record = json.loads((ROOT/'data/p10-20261024-a2/source-map-final.json').read_text())
    excerpt = record['excerpts']['959-988']['text']
    assert excerpt.index('research_recovery_transition') < excerpt.index('_sample_clock.accept')
    expected = record['tracked_and_instruction_inputs']['config/p10_a2_events.json']
    assert hashlib.sha256((ROOT/'config/p10_a2_events.json').read_bytes()).hexdigest() == expected


def test_zero_clip_slope_mode_has_position_unit_eigenvector():
    from fractions import Fraction as F
    a = v.a_matrix(F(9),F(5),F(9,10))
    a[3] = [F(0)]*v.N  # current position clip slope zero
    a[4] = [F(0)]*v.N  # current velocity clip slope zero
    direction = [F(1)]+[F(0)]*(v.N-1)
    assert [sum(x*y for x,y in zip(row,direction)) for row in a] == direction

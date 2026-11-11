"""Mock-only optional active-timeout orchestration checks; no real runner setup."""
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from handover_mutation import runner as m


@pytest.mark.parametrize('target,delay,expected', [('N', None, False), ('C', .6, False), ('N', .6, True)])
def test_default_delegation_and_declared_stream_end(monkeypatch, target, delay, expected):
    calls = []
    monkeypatch.setattr(m.MutationExperiment.__mro__[1], 'switch', lambda self, *args: calls.append(args))
    obj = object.__new__(m.MutationExperiment)
    obj.spec = {} if delay is None else {'active_timeout_after_s': delay}
    obj.latest = {'raptor_status': SimpleNamespace(active=True, trajectory_setpoint_stale=False)}
    obj.reference_enabled = True
    obj.send_count = 33
    obj.pump = lambda value: calls.append(('pump', value))
    obj.native_bound_streaming = lambda: 12345
    obj.event = lambda *args, **kwargs: calls.append((args, kwargs))
    obj.switch('C', target, 1)
    assert calls[0] == ('C', target, 1)
    assert obj.reference_enabled is (not expected)
    if expected:
        assert calls[1] == ('pump', .6)
        assert calls[2][0] == ('mutation_active_reference_end',)
        assert calls[2][1]['end_bound_px4_us'] == 12345
        assert calls[2][1]['reference_count'] == 33
    else:
        assert len(calls) == 1


@pytest.mark.parametrize('status', [None, SimpleNamespace(active=False, trajectory_setpoint_stale=False), SimpleNamespace(active=True, trajectory_setpoint_stale=True)])
def test_missing_inactive_or_stale_setup_cannot_claim_timeout(monkeypatch, status):
    monkeypatch.setattr(m.MutationExperiment.__mro__[1], 'switch', lambda *args: None)
    obj = object.__new__(m.MutationExperiment)
    obj.spec = {'active_timeout_after_s': .6}
    obj.latest = {'raptor_status': status}
    obj.reference_enabled = True
    obj.pump = lambda value: None
    with pytest.raises(RuntimeError, match='fresh neural reference'):
        obj.switch('C', 'N', 1)
    assert obj.reference_enabled is True

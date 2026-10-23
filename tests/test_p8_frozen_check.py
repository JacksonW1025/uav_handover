"""Validate audit boundaries without changing or fitting experiment results."""
import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('audit',Path(__file__).resolve().parents[1]/'tools/p8_frozen_check.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
def test_wilson_zero_is_not_certainty():
    low,high=a.wilson(0,45)
    assert abs(low)<1e-12 and .07<high<.09
    assert a.wilson(0,0)==[None,None]
def test_budget_boundary_preserves_horizon_difference():
    case={'v':2.4,'heading_deg':28.,'durs':[.32,.27],'restored':[.46]}
    assert a.S.budget(case)==(1.,2.6)
    assert not a.same([1.,2.6],[1.,2.55])
def test_full_windows_retain_event_spacing():
    case={'v':2.,'heading_deg':0.,'durs':[.3,.3],'restored':[.5]}
    assert a.S.windows(case)==[[0.,.3],[.8,1.1]]

"""No-process tests of the later user-authorized independent-attempt ledger."""
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from cn_reference.runner import claim_resume

def history():
    return [e for a in 'ABC' for e in [dict(event='START_INTENT',arm=a),dict(event='PHYSICAL_END',arm=a,cleanup_error=None),dict(event='END',arm=a,infrastructure_ok=a=='A')]]

def test_new_authorization_accepts_three_failed_or_complete_terminated_starts():
    proof=claim_resume(history(),'C','C2')
    assert proof['prior_physical_starts']==3 and proof['physical_start_cap'] is None
    assert not proof['automatic_retry']
    claim_resume(history(),'C','C10')

@pytest.mark.parametrize('attempt',['C','B2','C0','C1','../C2','C2/flight','C2x','C02',None])
def test_invalid_or_wrong_arm_name(attempt):
    with pytest.raises(ValueError):claim_resume(history(),'C',attempt)

@pytest.mark.parametrize('change',['missing_end','double_end','missing_physical','uncertain','cleanup','used'])
def test_unresolved_or_duplicate_attempt_stops(change):
    rows=history()
    if change=='missing_end':rows.pop()
    if change=='double_end':rows.append(rows[-1])
    if change=='missing_physical':rows.pop(-2)
    if change=='uncertain':rows[-2]['event']='PHYSICAL_UNCERTAIN'
    if change=='cleanup':rows[-2]['cleanup_error']='unknown'
    if change=='used':rows+=[dict(event='START_INTENT',arm='C',attempt='C2')]
    with pytest.raises(RuntimeError):claim_resume(rows,'C','C2')


def test_extra_reference_ceiling_uses_physical_margin_only():
    from cn_reference.runner import reference_budget
    x=reference_budget([3.,0.,-4.17],[.8,.1,-2.2],0.,8.)
    assert x['inside'] and not x['original_5m_screen_inside']
    assert 5.<x['max_reference_altitude_m']<7.
    assert x['reference_altitude_ceiling_m']==7.
    assert not reference_budget([3.,0.,-6.5],[.8,.1,-2.2],0.,8.)['inside']
    assert not reference_budget([8.,0.,-3.],[.8,.1,0.],0.,8.)['inside']
    assert not reference_budget([3.,0.,-1.],[.8,.1,0.],0.,8.)['inside']

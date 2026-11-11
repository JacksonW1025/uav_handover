import sys,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from handover_explore.design import CASES,evaluate,geometry

def test_distinct_normal_cases():
    assert len(CASES)==20
    assert len({str(s.get('knots'))+str(s['switches'])+str(s.get('yaw_sweep_deg'))+s['reference_kind']+str(s.get('trigger_vertical'))+str(s.get('control_baseline')) for s in CASES.values()})==20
    assert all(s['planned_gaps'] is False for s in CASES.values())
    assert all(all(v==0 for v in s['state_parameters'].values()) for s in CASES.values())

def test_profile_derivatives_and_continuity():
    h=1e-4
    for spec in CASES.values():
        for t in [.5,1.5,2.5,3.5,4.5,5.5,6.5,8.5,10.5]:
            # At a C2 knot jerk may jump; central acceleration error is O(h).
            # Knot continuity is checked separately below.
            if any(abs(t-knot[0])<.001 for knot in spec.get("knots",[])):continue
            m=evaluate(spec,t-h,[0,0,-3],0);r=evaluate(spec,t,[0,0,-3],0);p=evaluate(spec,t+h,[0,0,-3],0)
            for j in range(3):
                assert abs((p[0][j]-m[0][j])/(2*h)-r[1][j])<1e-5
                assert abs((p[1][j]-m[1][j])/(2*h)-r[2][j])<1e-5
        for knot in spec.get('knots',[])[1:-1]:
            kh=1e-6
            before=evaluate(spec,knot[0]-kh,[0,0,-3],0);after=evaluate(spec,knot[0]+kh,[0,0,-3],0)
            exact=evaluate(spec,knot[0],[0,0,-3],0)
            assert max(abs(x) for x in exact[2])<1e-8
            assert max(abs(a-b) for a,b in zip(exact[1],knot[2]))<1e-8
            for field in range(3):assert max(abs(a-b) for a,b in zip(before[field],after[field]))<.003

def test_nominal_physical_geometry():
    for spec in CASES.values():
        g=geometry(spec)
        assert g['max_reference_radius_m']<8
        assert .5<g['min_reference_altitude_m']<=g['max_reference_altitude_m']<7

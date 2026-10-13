import sys,json
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import numpy as np
from p0_metrics import raptor_captures,controller_target,neural_intervals
from recovery import recovery
from p1_metrics import hold_durations
from p1_batch import build_plan
from run_experiment import Experiment

def test_captures_only_inside_neural_ownership():
    intervals=[(1_000_000,2_000_000)]
    messages=[(500_000,'[mc_raptor] trajectory_setpoint turned stale at: 9.0 9.0 9.0, yaw: 0 1 / 2 us'),
              (995_000,'[mc_raptor] trajectory_setpoint turned stale at: 1.000000 2.000000 -3.000000, yaw: 0.1 20000 / 200000 us'),
              (1_500_000,'[mc_raptor] trajectory_setpoint reset due to activation at: 4 5 -3, yaw: 0'),
              (1_600_000,'[mc_raptor] trajectory_setpoint turned non-stale at: 0 0 0'),
              (2_100_000,'[mc_raptor] trajectory_setpoint turned stale at: 7 7 7, yaw: 0 1 / 2 us')]
    # The same-Run capture logged just before the owner change is placed at the owner change.
    assert raptor_captures(messages,intervals)==[(1_000_000,[1.,2.,-3.]),(1_500_000,[4.,5.,-3.])]

def test_controller_target_merges_in_time_order():
    sp={'timestamp':np.array([0,1_000_000,3_000_000]),**{f'position[{k}]':np.array([0.,0.,9.]) if k==0 else np.zeros(3) for k in range(3)}}
    merged=controller_target(sp,[(1_000_000,[5.,0.,0.]),(2_000_000,[6.,0.,0.])])
    assert merged['timestamp'].tolist()==[0,1_000_000,1_000_000,2_000_000,3_000_000]
    # A capture at the same time as a setpoint sample wins (it is applied after the sample).
    assert merged['position[0]'].tolist()==[0.,0.,5.,6.,9.]

def test_neural_intervals_from_transitions():
    tr=[{'px4_us':10,'from':2,'to':1},{'px4_us':20,'from':1,'to':2},{'px4_us':30,'from':2,'to':1}]
    assert neural_intervals(tr,99)==[(10,20),(30,99)]

def test_controller_target_reference_uses_given_series():
    t=np.arange(0,3_000_000,10_000);l={'timestamp':t,**{k:np.zeros(len(t)) for k in ['x','y','z','vx','vy','vz']}}
    w={'timestamp':t,**{f'xyz[{i}]':np.zeros(len(t)) for i in range(3)}}
    cfg={'position_reference':'active_controller_target','position_reference_ned_m':[0,0,-3],'velocity_reference_ned_m_s':[0,0,0],
         'angular_velocity_reference_frd_rad_s':[0,0,0],'position_threshold_m':.2,'velocity_threshold_m_s':.1,
         'angular_velocity_threshold_rad_s':.1,'dwell_s':2,'max_observation_gap_s':.02}
    sp={'timestamp':np.array([0]),'position[0]':np.array([0.]),'position[1]':np.array([0.]),'position[2]':np.array([0.])}
    r=recovery(l,w,cfg,0,3_000_000,sp)
    assert r['position_reference']=='active_controller_target' and r['joint_recovery']['status']=='SETTLED'
    assert r['fixed_reference_comparison']['joint_recovery']['status']=='NOT_SETTLED'
    p0=dict(cfg,position_reference='active_trajectory_setpoint')
    assert recovery(l,w,p0,0,3_000_000,sp)['joint_recovery']==r['joint_recovery']

def test_hold_durations_clip_to_window():
    t=np.array([0,1_000_000,2_000_000,3_000_000])
    assert hold_durations(t,np.array([True,False,True,True]),500_000,3_500_000)==0.5+1.0+0.5

def test_reference_profile_hold_ramp_cruise():
    cfg=json.loads((ROOT/'config/p1.json').read_text());cfg['p1_speed_m_s']=1.0
    f=lambda t:Experiment.p1_profile(SimpleNamespace(cfg=cfg),t)
    assert f(1.0)==(0.,0.,0.)
    s,v,a=f(4.0);assert abs(s-.25)<1e-12 and abs(v-.5)<1e-12 and a==.5
    s,v,a=f(9.0);assert abs(s-5.0)<1e-12 and v==1.0 and a==0.

def test_plan_is_preregistered_s1_first_with_30_handovers():
    cfg=json.loads((ROOT/'config/p1.json').read_text());plan=build_plan('x',cfg)
    assert [r['condition'] for r in plan]==sorted([r['condition'] for r in plan])
    assert sum(r['kind'] in ['p1_c_to_n','p1_n_to_c'] for r in plan)==30
    assert sum(r['kind'].startswith('p1_baseline') for r in plan)==18
    assert len({r['directory'] for r in plan})==len(plan)

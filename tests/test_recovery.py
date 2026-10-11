import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import numpy as np
from recovery import sustained,recovery

def test_stage_boundary_and_insufficient_observation():
    t=np.arange(0,4000001,10000);good=np.ones(len(t),bool)
    assert sustained(t,good,good,0,1500000,2,.02)['status']=='INSUFFICIENT_OBSERVATION'
    assert sustained(t,good,good,0,3000000,2,.02)['confirmed_us']==2000000
    good[t<1500000]=False
    assert sustained(t,good,np.ones(len(t),bool),0,3000000,2,.02)['status']=='NOT_SETTLED'
    assert sustained(t,good,np.ones(len(t),bool),0,4000001,2,.02)['time_s']==1.5

def test_missing_data_does_not_count_as_continuous():
    t=np.r_[np.arange(0,1000000,10000),np.arange(3000000,4000000,10000)]
    assert sustained(t,np.ones(len(t),bool),np.ones(len(t),bool),0,4000000,2,.02)['status']=='INSUFFICIENT_OBSERVATION'

def test_joint_condition_and_between_position_samples_angular_spike():
    t=np.arange(0,3000000,10000);a=np.arange(0,3000000,5000)
    l={'timestamp':t,**{k:np.zeros(len(t)) for k in ['x','y','z','vx','vy','vz']}}
    l['z'][:]=-3
    w={'timestamp':a,**{f'xyz[{i}]':np.zeros(len(a)) for i in range(3)}}
    w['xyz[0]'][a==1505000]=.2
    cfg={'position_reference_ned_m':[0,0,-3],'velocity_reference_ned_m_s':[0,0,0],
         'angular_velocity_reference_frd_rad_s':[0,0,0],'position_threshold_m':.2,
         'velocity_threshold_m_s':.1,'angular_velocity_threshold_rad_s':.1,'dwell_s':2,'max_observation_gap_s':.02}
    r=recovery(l,w,cfg,0,3000000)
    assert r['position_band_entry']['status']=='SETTLED'
    assert r['joint_recovery']['status']=='NOT_SETTLED'
    w['xyz[0]'][:]=0;l['vx'][:]=.2
    assert recovery(l,w,cfg,0,3000000)['joint_recovery']['status']=='NOT_SETTLED'

def test_source_gap_breaks_even_with_fresh_other_topic_and_no_future_alignment():
    # 21ms position gap: angular samples fill every millisecond. At the last
    # held point age is exactly20ms, so age checks alone would miss this gap.
    t=np.r_[np.arange(0,1000000,1000),np.arange(1020000,3000000,1000)]
    a=np.arange(0,3000000,1000)
    l={'timestamp':t,**{k:np.zeros(len(t)) for k in ['x','y','z','vx','vy','vz']}};l['z'][:]=-3
    w={'timestamp':a,**{f'xyz[{i}]':np.zeros(len(a)) for i in range(3)}}
    cfg={'position_reference_ned_m':[0,0,-3],'velocity_reference_ned_m_s':[0,0,0],
         'angular_velocity_reference_frd_rad_s':[0,0,0],'position_threshold_m':.2,
         'velocity_threshold_m_s':.1,'angular_velocity_threshold_rad_s':.1,'dwell_s':2,'max_observation_gap_s':.02}
    result=recovery(l,w,cfg,0,3000000)['joint_recovery']
    assert result['status']=='INSUFFICIENT_OBSERVATION'
    assert result['true_first_recovery_uncertain']
    # A future first angular sample cannot provide evidence before it exists.
    w={k:v[a>=1000000] for k,v in w.items()}
    assert recovery(l,w,cfg,0,3000000)['joint_recovery']['status']=='INSUFFICIENT_OBSERVATION'

def test_first_verifiable_recovery_after_gap():
    t=np.r_[np.arange(0,1000000,10000),np.arange(1100000,4000000,10000)]
    r=sustained(t,np.ones(len(t),bool),np.ones(len(t),bool),0,4000000,2,.02)
    assert r['status']=='SETTLED' and r['entry_us']==1100000
    assert r['true_first_recovery_uncertain']

def _hover(offset_z, setpoint_rows):
    t=np.arange(0,3000000,10000);a=np.arange(0,3000000,5000)
    l={'timestamp':t,**{k:np.zeros(len(t)) for k in ['x','y','z','vx','vy','vz']}}
    l['z'][:]=-3+offset_z
    w={'timestamp':a,**{f'xyz[{i}]':np.zeros(len(a)) for i in range(3)}}
    sp={'timestamp':np.asarray(setpoint_rows[0],dtype=np.int64),**{f'position[{i}]':np.asarray(setpoint_rows[1])[:,i] for i in range(3)}}
    return l,w,sp

CFG={'position_reference':'active_trajectory_setpoint','position_reference_ned_m':[0,0,-3],'velocity_reference_ned_m_s':[0,0,0],
     'angular_velocity_reference_frd_rad_s':[0,0,0],'position_threshold_m':.2,'velocity_threshold_m_s':.1,
     'angular_velocity_threshold_rad_s':.1,'dwell_s':2,'max_observation_gap_s':.02}

def test_setpoint_reference_ignores_accumulated_setpoint_drift():
    # Controller holds a setpoint 0.25 m below the fixed reference and tracks it exactly.
    l,w,sp=_hover(.25,([-100000],[[0,0,-2.75]]))
    r=recovery(l,w,CFG,0,3000000,sp)
    assert r['position_reference']=='active_trajectory_setpoint'
    assert r['joint_recovery']['status']=='SETTLED'
    assert r['fixed_reference_comparison']['joint_recovery']['status']=='NOT_SETTLED'

def test_setpoint_held_across_stage_and_missing_before_first():
    # Last setpoint before the stage applies inside it (neural stages publish none).
    l,w,sp=_hover(0,([-500000],[[0,0,-3]]))
    assert recovery(l,w,CFG,1000000,3000000,sp)['joint_recovery']['status']=='INSUFFICIENT_OBSERVATION'  # 2 s stage exactly at dwell edge
    assert recovery(l,w,CFG,0,3000000,sp)['joint_recovery']['status']=='SETTLED'
    # No setpoint before 1.5 s: earlier samples invalid, so no complete 2 s interval.
    l,w,sp=_hover(0,([1500000],[[0,0,-3]]))
    assert recovery(l,w,CFG,0,3000000,sp)['joint_recovery']['status']=='INSUFFICIENT_OBSERVATION'
    # Setpoint moves away from the vehicle: not settled even though fixed reference matches.
    l,w,sp=_hover(0,([-1,1000000],[[0,0,-3],[0,0,-2.5]]))
    r=recovery(l,w,CFG,0,3000000,sp)
    assert r['joint_recovery']['status']=='NOT_SETTLED' and r['fixed_reference_comparison']['joint_recovery']['status']=='SETTLED'

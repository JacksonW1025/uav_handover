import sys,json
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import numpy as np
from p2_action_map import header_map,motor_to_action
from p2_metrics import longest_run,params_at
from p2_batch import parse_groups,build_plan
from run_experiment import Experiment

def test_header_map_matches_frozen_fit():
    fit=json.loads((ROOT/'data/p2-20261014-action-map/action-map.json').read_text())
    assert fit['header_matches_fit'] and fit['fitted']['motor_of_action']==header_map()['motor_of_action']==[0,3,1,2]
    assert all(m['max_abs_residual']<1e-6 for m in fit['per_motor']) and fit['pairs']>50000

def test_motor_to_action_inverse_and_clip():
    a,clipped=motor_to_action([0.25,0.6,0.65,0.55])
    assert clipped==0 and np.allclose(a,[-0.5,0.1,0.2,0.3])
    a,clipped=motor_to_action([1.2,-0.1,0.5,1.0]);assert clipped==2 and np.allclose(a,[1,1,-1,0])
    assert motor_to_action([0.5,float('nan'),0.5,0.5])==(None,0)

def test_longest_continuous_saturation():
    t=np.array([0,100_000,200_000,300_000,400_000]);mask=np.array([True,True,False,True,True])
    assert longest_run(t,mask,600_000)==0.3

def test_parameters_in_force_at_time():
    u=SimpleNamespace(initial_parameters={'MC_RAPTOR_RINI':0,'MC_RAPTOR_NCO':0,'MC_RAPTOR_RSH':0},
                      changed_parameters=[(10,'MC_RAPTOR_RSH',1),(20,'MC_RAPTOR_RINI',4),(99,'MC_RAPTOR_RINI',0)])
    assert params_at(u,50)=={'MC_RAPTOR_RINI':4,'MC_RAPTOR_NCO':0,'MC_RAPTOR_RSH':1}

def test_plan_interleaves_groups_with_unique_directories():
    g=parse_groups('p2_c_to_n:S1:N0:2,p2_c_to_n:S1:N1:2,p2_baseline_raptor:S1:B:1,state_restore:-:-:1@config/p0.json','config/p2.json')
    plan=build_plan('x',g)
    assert [r['id'] for r in plan]==['S1-c_to_n-N0-1','S1-c_to_n-N1-1','S1-baseline_raptor-B-1','state_restore-1','S1-c_to_n-N0-2','S1-c_to_n-N1-2']
    assert plan[3]['config']=='config/p0.json' and plan[3]['condition'] is None and len({r['directory'] for r in plan})==len(plan)

def test_exploration_profile_repositions_then_ramps():
    cfg=json.loads((ROOT/'config/p2.json').read_text());cfg['p1_speed_m_s']=3.0
    pcfg={k:v for k,v in cfg['p2'].items() if k not in ['conditions','treatments']};pcfg.update({'start_offset_m':-6.0,'cruise_s':1.5})
    e=SimpleNamespace(cfg=cfg,pcfg=pcfg);f=lambda t:Experiment.p1_profile(e,t)
    tr=Experiment.reposition(e,0.)[3];assert abs(tr-13.0)<1e-9
    s,v,a=f(0.5);assert s<0 and v<0
    s,v,a=f(tr+1.0);assert abs(s+6.0)<1e-9 and v==0
    s,v,a=f(tr+3+2+1.5);assert abs(s-(-6+3+4.5))<1e-9 and v==3.0
    assert abs(Experiment.profile_duration(e)-(tr+3+2+1.5))<1e-9
    # Without an offset the P2 profile is the P1 profile.
    e2=SimpleNamespace(cfg=dict(cfg,p1_speed_m_s=1.0),pcfg={k:v for k,v in cfg['p2'].items() if k not in ['conditions','treatments']})
    assert Experiment.reposition(e2,1.)==(0.,0.,0.,0.) and Experiment.p1_profile(e2,9.0)==(5.0,1.0,0.)

def test_p2_thresholds_equal_frozen_p1():
    p1=json.loads((ROOT/'config/p1.json').read_text());p2=json.loads((ROOT/'config/p2.json').read_text())
    for k in ['joint_recovery','hover_max_error_m','hover_max_tilt_deg','safety_radius_m','safety_altitude_m','safety_tilt_deg','safety_angular_rate_rad_s','inference_p99_us','seed']:
        assert p1[k]==p2[k],k
    assert p2['p2']['motor_saturation']==p1['p1']['motor_saturation']
    assert {t['rini'] for n,t in p2['p2']['treatments'].items() if n.startswith('N')}=={0,1,2,3,4,5}

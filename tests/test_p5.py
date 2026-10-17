import sys,json,math
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import numpy as np
from run_experiment import Experiment,P2_TREATMENT_KINDS,P5_TREATMENT_KINDS,p5_profile
import p0_metrics,p2_batch,p5_batch,p5_metrics

CFG=json.loads((ROOT/'config/p5.json').read_text())
P4C=json.loads((ROOT/'config/p4c.json').read_text())

def test_p5_frozen_thresholds_equal_p4c():
    for k in [k for k in P4C if k not in ['p2','p4','p4c']]:assert CFG[k]==P4C[k],k
    for k in [k for k in P4C['p2'] if k not in ['purpose','conditions','treatments','profile_overrides']]:assert CFG['p2'][k]==P4C['p2'][k],k
    assert CFG['p4c']['clipping']==P4C['p4c']['clipping'] and CFG['p4c']['settle']==P4C['p4c']['settle'] and CFG['p4c']['target_check']==P4C['p4c']['target_check']
    assert CFG['p5']['clipping']==P4C['p4c']['clipping'] and CFG['p5']['settle']==P4C['p4c']['settle']
    crit={k:v for k,v in CFG['p5']['failure_criteria'].items() if k!='window'};assert crit==P4C['p2']['exploration']['failure_criteria']
    assert CFG['p5']['equivalence']['metric_tolerance']==P4C['p4c']['equivalence']['metric_tolerance']
    assert CFG['p4']['host']==P4C['p4']['host'] and CFG['p4']['independence']['initial_yaw']['conditions']==[]

def test_e1_profiles_are_p4c_levels_with_a_direction():
    ne=math.sqrt(.5)
    for name,c in CFG['p2']['conditions'].items():
        if name=='N2.0':continue
        lvl,d=name.split('-');base=P4C['p2']['conditions'][lvl]
        assert c['speed_m_s']==base['speed_m_s'] and c['cruise_s']==base['cruise_s'] and c['flight_failures_are_results']
        assert np.allclose(c['motion_axis_ned'],[ne,ne,0] if d=='A45' else [1,0,0],atol=1e-8)
        assert c.get('initial_yaw_deg')==(45.0 if d=='Y45' else None)
    assert 'motion_axis_ned' in CFG['p2']['profile_overrides']
    t=CFG['p2']['treatments'];assert t['T0']==P4C['p2']['treatments']['T0'] and t['T1']==P4C['p2']['treatments']['T1'] and t['C0']=={**t['C0'],'rini':4,'nco':0}
    assert {'T0','T1'}<=set(P2_TREATMENT_KINDS['p2_c_to_n']) and 'C0' in P2_TREATMENT_KINDS['p2_n_to_c']

def test_p5_treatments_and_groups():
    t=CFG['p5']['treatments'];assert set(t)==set(P5_TREATMENT_KINDS['p5_gap'])
    assert all(x['rini']==4 for x in t.values()) and t['T0']['rtgt']==0 and all(t[k]['rtgt']==2 for k in ['T1','T1a1','T1a3'])
    assert [t[k]['rtdec'] for k in ['T1','T1a1','T1a3']]==[2.0,1.0,3.0]
    n={k:sum(g['n'] for g in p2_batch.parse_groups(v,'config/p5.json')) for k,v in CFG['p4']['groups'].items()}
    assert n=={'equivalence':4,'dev_10':10,'e1':15,'e2':12,'e3':6,'e4':2}
    for k in ['dev_10','e1','e2','e3','e4']:
        plan=p5_batch.build_plan('p5-test-'+k,p2_batch.parse_groups(CFG['p4']['groups'][k],'config/p5.json'))
        assert len({r['sim_seed'] for r in plan})==len(plan)
        for r in plan:assert ('--initial-yaw-deg' in r['extra_args'])==r['condition'].endswith('Y45')
    eq=p2_batch.parse_groups(CFG['p4']['groups']['equivalence'],'config/p5.json');assert [g['config'] for g in eq]==['config/p4.json','config/p4c.json']

def gap_experiment(cond):
    spec=CFG['p5']['conditions'][cond];pcfg=p5_profile(CFG['p5'],spec)
    return SimpleNamespace(cfg={'p1_speed_m_s':spec['speed_m_s'],'safety_radius_m':CFG['safety_radius_m'],'p5':CFG['p5']},pcfg=pcfg)

def test_gap_profiles_fit_the_safety_budget_and_place_the_gaps_in_the_cruise():
    for cond,spec in CFG['p5']['conditions'].items():
        e=gap_experiment(cond);p=e.pcfg;g=spec['gaps']
        e.p5_gap_windows=lambda e=e:Experiment.p5_gap_windows(e)
        w=Experiment.p5_gap_windows(e);assert len(w)==g['count'] and all(abs(b-a-g['duration_s'])<1e-9 for a,b in w)
        tr=Experiment.reposition(e,0.)[3];cruise0=tr+p['reference_hold_s']+p['accel_s']
        assert abs(w[0][0]-cruise0-p['pre_gap_s'])<1e-9 and abs(w[-1][1]+g['recover_s']*(g['count']>1)+p['post_gap_s']-(g['recover_s'] if g['count']>1 else 0.)-cruise0-p['cruise_s'])<1e-9
        for a,_ in w:assert Experiment.p1_profile(e,a)[1]==spec['speed_m_s'] and Experiment.p1_profile(e,a+g['duration_s']-1e-6)[1]==spec['speed_m_s']
        s_end=Experiment.p1_profile(e,Experiment.profile_duration(e))
        assert abs(s_end[0]-p['start_offset_m']-p['path_length_m'])<1e-6 and abs(s_end[1])<1e-9
        assert abs(p['start_offset_m']+p['path_length_m']/2)<1e-6
        c=Experiment.p5_path_check(e,[0.,0.,-3.])
        assert c['inside'] and c['interruption_drift_m']==0. and abs(c['radius_with_allowance_m']-spec['safety_budget_m']['radius_m'])<1e-3
        # The check fails when RAPTOR's hover capture is far from the origin.
        d=8.-spec['safety_budget_m']['radius_m']+0.01;ax=spec['motion_axis_ned'];assert not Experiment.p5_path_check(e,[d*ax[0],d*ax[1],-3.])['inside']
    r6=gap_experiment('R6-A0');w=Experiment.p5_gap_windows(r6);assert np.allclose(np.diff([a for a,_ in w]),0.8)

def test_mode_2_profile_rows_are_controller_targets():
    tg={'timestamp':np.array([990_000,994_000,1_004_000]),'kind':np.array([1,2,2]),'mode':np.array([2,2,2]),**{f'position[{k}]':np.array([0.,.1,.2])*(k==0) for k in range(3)}}
    assert [r[0] for r in p0_metrics.raptor_target_profile(tg,[(1_000_000,1_900_000)])]==[1_000_000,1_004_000]

def test_per_axis_clipping_and_true_error_ratio():
    cfg={'p5':CFG['p5']};t=np.arange(0,100_000,4_000,dtype=np.int64);n=len(t)
    x=np.zeros((n,22));x[:10,0]=0.5;x[:10,1]=0.5;x[10:15,13]=-1.0
    mem={'timestamp':t,'kind':np.ones(n,int),'active':np.ones(n,int),**{f'policy_input[{k}]':x[:,k] for k in range(22)}}
    c=p5_metrics.clipping_axes(cfg,mem,0,100_000)
    assert np.allclose(c['position']['per_axis_duration_s'],[0.04,0.04,0.]) and abs(c['position']['both_horizontal_axes_s']-0.04)<1e-9
    assert np.allclose(c['velocity']['per_axis_duration_s'],[0.,0.02,0.]) and c['velocity']['first_s']==0.04
    # True velocity error 2 m/s along the diagonal of the target frame: clipped to (1,1) -> retained |(1,1)|/2.
    v=np.full(n,math.sqrt(2.));local={'timestamp':t-1,'timestamp_sample':t-2,'x':np.zeros(n),'y':np.zeros(n),'z':np.zeros(n),'vx':v,'vy':v,'vz':np.zeros(n)}
    timing={'timestamp':t,'executor_called':np.ones(n,int),'local_position_sample':t-2}
    x[:,12]=1.;x[:,13]=1.;x[:,0]=x[:,1]=0.;mem.update({f'policy_input[{k}]':x[:,k] for k in range(22)})
    r=p5_metrics.unclipped_horizontal(mem,local,timing,lambda tt:(np.zeros((len(tt),3)),np.zeros((len(tt),3))),0,100_000)
    assert abs(r['velocity']['max_true_m_or_m_s']-2.)<1e-9 and abs(r['velocity']['min_retained_ratio']-math.sqrt(2.)/2)<1e-9

def test_t1_gating_is_mode_specific_in_the_research_header():
    text=(ROOT/'research/state/TargetProfile.hpp').read_text()
    assert 'TARGET_SPEED_MATCHED_ALL=2' in text and 'inline bool speed_matched_capture' in text
    apply=(ROOT/'tools/apply_research.py').read_text()
    assert "research_target_capture(!previous_active && next_active, next_active);" in apply and 'speed_matched_capture(mode,activation,active)' in apply

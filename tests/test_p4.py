import sys,json,math
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import numpy as np
from run_experiment import Experiment
import p4_batch,p4_metrics,p4_audit

CFG=json.loads((ROOT/'config/p4.json').read_text())
P2=json.loads((ROOT/'config/p2.json').read_text());P3=json.loads((ROOT/'config/p3.json').read_text())

def test_p4_thresholds_and_treatments_equal_p2_p3():
    for k in [k for k in P3 if k!='p3']:assert CFG[k]==P3[k],k
    for k in ['motor_saturation','motor_step_window_s','motor_rms_window_s','entry_check','motion_axis_ned','reference_hold_s','accel_s','cruise_s','setpoint_period_s','post_handover_s','return_hold_s']:
        assert CFG['p2'][k]==P2['p2'][k],k
    assert CFG['p2']['exploration']['failure_criteria']==P2['p2']['exploration']['failure_criteria']==CFG['p3']['flight_failures']['criteria']
    for k in ['sequence','entry_check','memory_length','flight_failures','motor_saturation','gru_distance_offsets_s','equivalence','dev_latency','host']:assert CFG['p3'][k]==P3['p3'][k],k
    assert CFG['p3']['conditions']['D2']==P3['p3']['conditions']['D2'] and CFG['p3']['conditions']['R']==P3['p3']['conditions']['R']
    assert {n:t['rini'] for n,t in CFG['p3']['treatments'].items()}=={'N0':0,'N3':6,'N2s':1,'N2':4,'B':0}
    assert {n:t.get('rini') for n,t in CFG['p2']['treatments'].items()}=={'N0':0,'N2':4,'B':0}
    assert CFG['p4']['baseline_condition']=={'D2':'R','M1':'M1','M2':'M2','M3':'M1'}

def p2_experiment(cond):
    p2=CFG['p2'];c=p2['conditions'][cond];pcfg={k:v for k,v in p2.items() if k not in ['conditions','treatments']}
    pcfg.update({k:v for k,v in c.items() if k in p2['profile_overrides']})
    return SimpleNamespace(cfg={'p1_speed_m_s':c['speed_m_s'],'safety_radius_m':CFG['safety_radius_m']},pcfg=pcfg)

def test_m1_constant_speed_and_m2_mid_deceleration_profiles():
    e=p2_experiment('M1');T=Experiment.profile_duration(e);assert T==9.0
    assert Experiment.p1_profile(e,T)==(5.0,1.0,0.0) and Experiment.p1_profile(e,T-0.2)[1:]==(1.0,0.0)
    vd=CFG['p2']['conditions']['M2']['decel_to_m_s'];assert 0.2<vd<0.5 and CFG['p2']['conditions']['M2']['decel_m_s2']==1.0
    e=p2_experiment('M2');T=Experiment.profile_duration(e);assert abs(T-(9+1-vd))<1e-9
    s,v,a=Experiment.p1_profile(e,T);assert abs(v-vd)<1e-9 and a==-1.0 and abs(s-(1+4+(1-vd**2)/2))<1e-9
    s2,v2,a2=Experiment.p1_profile(e,T+0.2);assert abs(v2-vd)<1e-9 and a2==0 and abs(s2-s-0.2*vd)<1e-9
    ts=np.linspace(0,T,4001);path=[Experiment.p1_profile(e,t) for t in ts]
    assert all(b[0]>=a[0]-1e-12 for a,b in zip(path,path[1:])) and max(p[1] for p in path)<=1.0+1e-12
    # Without decel_to_m_s the P2 S3 profile is unchanged (constant cruise after the ramp).
    p2=P2['p2'];pcfg={k:v for k,v in p2.items() if k not in ['conditions','treatments']}
    s3=SimpleNamespace(cfg={'p1_speed_m_s':1.0},pcfg=pcfg)
    for t in [0.,2.,3.5,5.,7.,9.,12.]:
        want=(0.,0.,0.) if t<3 else ((.5*(t-3)**2/2,(t-3)/2,.5) if t<5 else (1+(t-5),1.,0.))
        assert np.allclose(Experiment.p1_profile(s3,t),want)
    assert Experiment.profile_duration(s3)==9.0 and Experiment.planned_path_check(s3,[0,0,-3]) is None

def test_planned_paths_stay_inside_the_safety_margin():
    for cond in ['M1','M2']:
        c=Experiment.planned_path_check(p2_experiment(cond),[0.3,-0.3,-3.0]);assert c['inside'] and c['radius_with_allowance_m']<7.0 and c['limit_m']==8.0
    far=Experiment.planned_path_check(p2_experiment('M1'),[2.5,0.,-3.]);assert not far['inside']
    e=SimpleNamespace(cfg={'p3_condition_spec':CFG['p3']['conditions']['M3']})
    end=Experiment.p3_motion_end(e,[0.3,-0.3,-3.0]);assert np.allclose(end,[5.3,-0.3,-3.0])
    assert math.hypot(*end[:2])+CFG['p3']['conditions']['M3']['motion']['braking_allowance_m']<=CFG['safety_radius_m']-CFG['p3']['safety_check']['radius_margin_m']

def test_m3_second_takeover_in_the_same_state_as_m1():
    e=SimpleNamespace(cfg={'p3_condition_spec':CFG['p3']['conditions']['M3']});f=lambda t:Experiment.p3_motion(e,t)
    assert f(2.9)==(0.,0.,0.,0.,0.) and np.allclose(f(4.0),(.25,.5,.5,0,0)) and np.allclose(f(9.0),(5.,1.,0.,0.,0.))
    m1=p2_experiment('M1')
    # M3 motion from the N->C request equals the M1 profile from the reference start (3 s hold, 2 s ramp, 4 s cruise).
    for t in np.linspace(0,9,91):assert np.allclose(f(t)[:2],Experiment.p1_profile(m1,t)[:2])
    assert CFG['p3']['conditions']['M3']['deactivation_s']==Experiment.profile_duration(m1)
    # The deactivation keeps >= 2 s of classic hold before motion so the N->C stage can settle (P0 dwell).
    assert CFG['p3']['conditions']['M3']['motion']['start_after_s']>=CFG['joint_recovery']['dwell_s']+0.5

def test_plan_seeds_distinct_and_headings_only_in_01a():
    for part,n in [('01a',23),('01b',27),('dev_10',10)]:
        groups=p4_batch.parse_groups(CFG['p4']['groups'][part]);plan=p4_batch.build_plan('p4-x-'+part,groups,'config/p4.json',CFG)
        assert len(plan)==n and len({r['sim_seed'] for r in plan})==n and len({r['directory'] for r in plan})==n
        for r in plan:
            assert (r['initial_yaw_deg'] is not None)==(r['condition'] in ['D2','R'])
            if r['initial_yaw_deg'] is not None:assert -20<=r['initial_yaw_deg']<=20
            assert r['extra_args'][:2]==['--sim-seed',str(r['sim_seed'])]
    again=p4_batch.build_plan('p4-x-01a',p4_batch.parse_groups(CFG['p4']['groups']['01a']),'config/p4.json',CFG)
    assert [r['sim_seed'] for r in again]==[r['sim_seed'] for r in p4_batch.build_plan('p4-x-01a',p4_batch.parse_groups(CFG['p4']['groups']['01a']),'config/p4.json',CFG)]
    plan=p4_batch.build_plan('p4-x-01a',p4_batch.parse_groups(CFG['p4']['groups']['01a']),'config/p4.json',CFG)
    assert [r['id'] for r in plan[:5]]==['D2-N0-1','D2-N3-1','D2-N2s-1','D2-N2-1','R-B-1'] and plan[-1]['id']=='D2-N2-5'

def test_teacher_coverage_counts_consecutive_forced_native_steps_before_entry():
    rows=[]
    def row(t,kind,native,active,tf):rows.append((t,kind,native,active,tf))
    for i in range(5):row(100+8*i,1,1,0,0)          # free shadow
    for i in range(12):row(200+8*i,1,1,0,1);row(204+8*i,1,0,0,1)   # teacher forced, intermediate rows between
    row(300,2,0,0,0);row(304,1,1,1,0)               # entry, first active step
    mem={k:np.array([r[i] for r in rows]) for i,k in enumerate(['timestamp','kind','native_step','active','teacher_forced'])}
    c=p4_metrics.teacher_coverage(mem,302);assert c['consecutive_teacher_forced_native_steps']==12 and c['entry_px4_us']==300

def test_statistics_t_interval_and_bootstrap_ratio():
    s=p4_audit.stats([1.,2.,3.,4.,5.]);assert s['mean']==3 and abs(s['ci95'][1]-3-2.776445*math.sqrt(2.5)/math.sqrt(5))<1e-4
    r=p4_audit.bootstrap_ratio([1.,1.,1.],[.5,.5,.5],[0.,0.,0.],np.random.default_rng(0),200)
    assert r['ratio_ci95']==[.5,.5] and r['total_cost_ci95']==[1.,1.]

def test_baseline_stop_and_final_setpoint_parameters():
    for cond in ['M1','M2']:
        c=CFG['p2']['conditions'][cond];assert 'raptor_baseline_stop_early_s' in CFG['p2']['profile_overrides']
        assert 0.2<=c['raptor_baseline_stop_early_s']<=0.4 and 0<=c['raptor_baseline_final_setpoint_ahead_s']<=0.2
        e=p2_experiment(cond);T=Experiment.profile_duration(e);t=T-c['raptor_baseline_stop_early_s']+c['raptor_baseline_final_setpoint_ahead_s']
        s,v,a=Experiment.p1_profile(e,t);assert 0<v<=1.0 and s<=Experiment.p1_profile(e,T)[0]+0.2
    assert CFG['p4']['baseline_matching']['speed_tolerance_m_s']==0.05 and CFG['p4']['baseline_matching']['acceleration_tolerance_m_s2']==0.3

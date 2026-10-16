import sys,json,math
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import numpy as np
from run_experiment import Experiment,P2_TREATMENT_KINDS
import p4c_metrics,p0_metrics,p4_batch

CFG=json.loads((ROOT/'config/p4c.json').read_text())
P4=json.loads((ROOT/'config/p4.json').read_text())

def test_p4c_frozen_thresholds_equal_p4():
    for k in [k for k in P4 if k not in ['p2','p4']]:assert CFG[k]==P4[k],k
    for k in [k for k in P4['p2'] if k not in ['purpose','conditions','treatments','reference','planned_path_check']]:assert CFG['p2'][k]==P4['p2'][k],k
    for k in ['independence','statistics','teacher_forcing_min_native_steps','teacher_forcing_rule','dev_latency','equivalence','host']:
        if k=='independence':
            a={x:y for x,y in CFG['p4'][k].items() if x!='initial_yaw'};b={x:y for x,y in P4['p4'][k].items() if x!='initial_yaw'};assert a==b
            assert CFG['p4'][k]['initial_yaw']['conditions']==['D2','R']
        else:assert CFG['p4'][k]==P4['p4'][k],k
    assert CFG['p4c']['equivalence']['metric_tolerance']==P4['p3']['equivalence']['metric_tolerance']
    assert CFG['p2']['exploration']['failure_criteria']==P4['p2']['exploration']['failure_criteria']==CFG['p3']['flight_failures']['criteria']

def test_treatments_are_n2_memory_with_t0_t1_targets():
    t=CFG['p2']['treatments'];assert set(t)=={'T0','T1'}
    assert all(x['rini']==4 and x['rtdec']==2.0 for x in t.values()) and t['T0']['rtgt']==0 and t['T1']['rtgt']==1
    assert {'T0','T1'}<=set(P2_TREATMENT_KINDS['p2_c_to_n'])
    groups=p4_batch.parse_groups(CFG['p4']['groups']['01c'])
    assert [(g['condition'],g['treatment'],g['n']) for g in groups]==[(v,x,3) for v in ['V1.0','V1.5','V2.0'] for x in ['T0','T1']]+[('V3.0','T1',3)]
    dev=p4_batch.parse_groups(CFG['p4']['groups']['dev_10']);assert sum(g['n'] for g in dev)==10
    assert {(g['condition'],g['treatment']) for g in dev}=={(g['condition'],g['treatment']) for g in groups}
    assert all(c['flight_failures_are_results'] for c in CFG['p2']['conditions'].values())

def experiment(cond):
    p2=CFG['p2'];c=p2['conditions'][cond];pcfg={k:v for k,v in p2.items() if k not in ['conditions','treatments']}
    pcfg.update({k:v for k,v in c.items() if k in p2['profile_overrides']})
    return SimpleNamespace(cfg={'p1_speed_m_s':c['speed_m_s'],'safety_radius_m':CFG['safety_radius_m']},pcfg=pcfg)

def test_every_level_fits_the_safety_budget_and_v1_is_p4_m1():
    for cond,c in CFG['p2']['conditions'].items():
        e=experiment(cond);v=c['speed_m_s'];T=Experiment.profile_duration(e)
        s,speed,acc=Experiment.p1_profile(e,T);assert abs(speed-v)<1e-12 and acc==0.
        assert abs(s-(v*CFG['p2']['accel_s']/2+v*c['cruise_s']))<1e-9
        chk=Experiment.planned_path_check(e,[0.,0.,-3.]);b=c['safety_budget_m']
        assert abs(chk['braking_distance_m']-v*v/4)<1e-12 and abs(chk['radius_with_allowance_m']-b['total_m'])<1e-9
        assert chk['limit_m']==8.0 and chk['inside'] and b['total_m']<=8.0
        # 0.2 m of hover drift toward +N still fits.
        assert Experiment.planned_path_check(e,[0.2,0.,-3.])['inside']
    m1=SimpleNamespace(cfg={'p1_speed_m_s':1.0,'safety_radius_m':10},pcfg={**{k:v for k,v in P4['p2'].items() if k not in ['conditions','treatments']},**{k:v for k,v in P4['p2']['conditions']['M1'].items() if k in P4['p2']['profile_overrides']}})
    e=experiment('V1.0');assert Experiment.profile_duration(e)==Experiment.profile_duration(m1)==9.0
    for t in np.linspace(0,9,91):assert Experiment.p1_profile(e,t)==Experiment.p1_profile(m1,t)
    # Without braking_deceleration_m_s2 the P4 check is unchanged (braking term 0).
    assert Experiment.planned_path_check(m1,[0.,0.,-3.])['radius_with_allowance_m']==6.0

def test_closed_form_profile_is_the_integral_of_its_velocity():
    p0=[1.,-2.,-3.];v0=[1.8,-0.6];a=2.0;s0=math.hypot(*v0)
    t=np.arange(0,3,0.004);pos,vel,phase=p4c_metrics.profile(p0,v0,a,t)
    assert np.allclose(vel[0,:2],v0) and np.all(vel[:,2]==0) and np.all(pos[:,2]==-3.)
    assert np.allclose(np.cumsum(np.r_[0,.002*(vel[1:,0]+vel[:-1,0])])+p0[0],pos[:,0],atol=1e-6)
    sp=np.hypot(vel[:,0],vel[:,1]);assert np.allclose(sp,np.maximum(s0-a*t,0),atol=1e-12)
    end=p4c_metrics.profile(p0,v0,a,[100.])[0][0];assert abs(math.hypot(end[0]-p0[0],end[1]-p0[1])-s0*s0/(2*a))<1e-12
    assert set(phase[t<s0/a-1e-9])=={2} and set(phase[t>s0/a+1e-9])=={3}
    # Direction: the target moves along the captured velocity.
    assert abs((end[0]-p0[0])*v0[1]-(end[1]-p0[1])*v0[0])<1e-12

def test_clipping_counts_exact_limits_only():
    n=100;t=np.arange(n)*4000+10_000_000;x=np.zeros((n,22));x[10:20,13]=1.0;x[20:25,13]=0.999;x[30:32,1]=-0.5;x[40,0]=0.49999
    mem={'timestamp':t,'kind':np.ones(n,int),'active':np.ones(n,int),**{f'policy_input[{k}]':x[:,k] for k in range(22)}}
    c=p4c_metrics.clipping(CFG,mem,int(t[0]),int(t[-1])+4000)
    assert c['velocity']['rows']==10 and abs(c['velocity']['duration_s']-0.04)<1e-12 and abs(c['velocity']['first_after_change_s']-0.04)<1e-12
    assert c['position']['rows']==2 and c['position']['per_axis_rows']==[0,2,0] and abs(c['position']['longest_continuous_s']-0.008)<1e-12

def test_settle_time_is_last_crossing_of_the_speed_threshold():
    t=np.arange(0,3000)*4000;v=np.where(t<2_000_000,1.0-t/2e6,0.0)+np.where((t>3_000_000)&(t<3_100_000),0.2,0.)
    x=np.cumsum(v)*0.004
    local={'timestamp_sample':t,'x':x,'y':0*x,'z':0*x-3,'vx':v,'vy':0*v,'vz':0*v}
    s=p4c_metrics.settle(CFG,local,0,int(t[-1])+1,np.array([1.,0,0]),False)
    assert s['settled'] and abs(s['settle_time_s']-3.1)<0.005 and abs(s['settle_distance_m']-x[np.searchsorted(t,3_100_000)])<0.01
    assert not p4c_metrics.settle(CFG,local,0,int(t[-1])+1,np.array([1.,0,0]),True)['settled']
    v2=v.copy();v2[-1]=0.5;local['vx']=v2
    assert not p4c_metrics.settle(CFG,local,0,int(t[-1])+1,np.array([1.,0,0]),False)['settled']

def test_t1_profile_rows_become_the_controller_target_only_for_mode_1():
    tg={'timestamp':np.array([990_000,994_000,1_004_000,1_008_000,2_000_000]),'kind':np.array([1,2,2,2,2]),'mode':np.array([1,1,1,1,1]),
        **{f'position[{k}]':np.array([0.,0.,.1,.2,.3])*(k==0) for k in range(3)}}
    rows=p0_metrics.raptor_target_profile(tg,[(1_000_000,1_900_000)])
    assert [r[0] for r in rows]==[1_000_000,1_004_000,1_008_000] and [r[1][0] for r in rows]==[0.,.1,.2]
    target=p0_metrics.controller_target({'timestamp':np.array([500_000]),**{f'position[{k}]':np.array([9.]) for k in range(3)}},[(1_000_000,[0.,0.,0.])]+rows)
    assert list(target['timestamp'])==[500_000,1_000_000,1_000_000,1_004_000,1_008_000] and target['position[0]'][2]==0.
    tg['mode']=np.zeros(5,int);assert p0_metrics.raptor_target_profile(tg,[(1_000_000,1_900_000)])==[]
    assert p0_metrics.raptor_target_profile(None,[(0,1)])==[]

def test_open_neural_interval_ends_with_the_px4_log():
    import output_chain
    # dev-10 V2.0-T0-1: PX4 log ended at 56.480 s, Gazebo stepped on to 56.496 s without commands after the abort.
    assert output_chain.open_interval_end(56_496_000,56_480_000)==56_480_000
    assert output_chain.open_interval_end(56_496_000,None)==56_496_000
    # A trace that ends first is never extended.
    assert output_chain.open_interval_end(56_400_000,56_480_000)==56_400_000
    iv=output_chain.neural_intervals([{'px4_us':56_112_000,'from':2,'to':1}],output_chain.open_interval_end(56_496_000,56_480_000))
    t=np.arange(56_100_000,56_500_000,4000);m=output_chain.in_intervals(t,iv)
    assert t[m][0]==56_112_000 and t[m][-1]==56_476_000

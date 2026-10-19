import sys,json,math,glob
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import numpy as np
import pytest
from run_experiment import Experiment,P5_TREATMENT_KINDS,P6_GAP_TREATMENTS,P6_TREATMENT_KINDS,p5_profile
import p2_batch,p6_batch,p6_conditions as pc

CFG=json.loads((ROOT/'config/p6.json').read_text())
P5=json.loads((ROOT/'config/p5.json').read_text())

def test_frozen_thresholds_equal_p5():
    for k,v in P5.items():
        if not isinstance(v,dict):assert CFG[k]==v,k
    for k in ['gap_timing','catch_up','settle','clipping','failure_criteria','metrics','profile']:assert CFG['p5'][k]==P5['p5'][k],k
    for k in ['radius_margin_m','braking_allowance_m','stale_timeout_s']:assert CFG['p5']['planned_path_check'][k]==P5['p5']['planned_path_check'][k]
    assert CFG['p5']['planned_path_check']['worst_case_deceleration_m_s2']==min(t['rtdec'] for t in CFG['p5']['treatments'].values() if t['rtgt']==2)
    assert CFG['p4']['host']==P5['p4']['host'] and CFG['p4c']==P5['p4c']
    for k in ['T0','T1','T1a3']:assert CFG['p5']['treatments'][k]==P5['p5']['treatments'][k]
    t=CFG['p5']['treatments'];assert all(x['rini']==4 for x in t.values()) and t['T1a1.5']['rtdec']==1.5 and t['T1a0.75']['rtdec']==0.75
    assert set(t)==set(P5_TREATMENT_KINDS['p5_gap'])-{'T1a1'}|set(P6_GAP_TREATMENTS)
    assert CFG['p6']['ident']['treatments']['T0']=={**CFG['p6']['ident']['treatments']['T0'],'rini':4,'rtgt':0} and P6_TREATMENT_KINDS=={'p6_ident':['T0']}

def test_recorded_p5_profiles_unchanged():
    n=0
    for f in glob.glob(str(ROOT/'data/p5-20261018-*/config.json')):
        c=json.loads(Path(f).read_text())
        if 'p5_condition_spec' in c:assert json.dumps(p5_profile(c['p5'],c['p5_condition_spec']))==json.dumps(c['p2_profile']);n+=1
    if not n:pytest.skip('P5 run directories not present')

def gap_experiment(cond):
    spec=pc.gap_spec(CFG,cond);e=SimpleNamespace(cfg={'p1_speed_m_s':spec['speed_m_s'],'safety_radius_m':CFG['safety_radius_m'],'p5':CFG['p5']},pcfg=p5_profile(CFG['p5'],spec))
    e.p5_gap_windows=lambda:Experiment.p5_gap_windows(e);return spec,e

def test_groups_and_counts():
    n={k:sum(g['n'] for g in p2_batch.parse_groups(v,'config/p6.json')) for k,v in CFG['p4']['groups'].items()}
    assert n=={'a':18,'b1':61,'c':16,'equivalence':4,'dev':8}
    assert sorted(CFG['p6']['cancelled'])==['M3-A0:T1','M3-A45:T1','v2.5-D1.7-A0:T1a1.5']
    for k in ['a','b1','c','dev']:
        plan=p6_batch.build_plan('p6-test-'+k,p2_batch.parse_groups(CFG['p4']['groups'][k],'config/p6.json'),7)
        assert len({r['sim_seed'] for r in plan})==len(plan)
    b1=[g for g in p2_batch.parse_groups(CFG['p4']['groups']['b1'],'config/p6.json')]
    for f in CFG['p6']['b']['families']:
        for v in f['speeds_m_s']:
            got=sorted(float(pc.GAP_NAME.match(g['condition'])['D']) for g in b1 if g['treatment']==f['treatment'] and float(pc.GAP_NAME.match(g['condition'])['v'])==v)
            want=[D for D in f['durations_s'] if f"{pc.gap_name(v,D,'A0')}:{f['treatment']}" not in CFG['p6']['cancelled']];assert got==want

def test_generated_conditions_fit_and_shrink_in_order():
    for key,b in CFG['p5']['budget_table'].items():
        name,t=key.rsplit(':',1);spec=pc.gap_spec(CFG,name)
        assert {k:spec.get(k) for k in b}==b
        if spec.get('cancelled'):continue
        assert spec['safety_budget_m']['radius_m']<=8.0+1e-9
        # Shrink order: pre_gap_s only below 1.0 when post_gap_s is at its 2.0 s minimum.
        assert spec['pre_gap_s']==1.0 or spec['post_gap_s']==2.0
        assert 2.0<=spec['post_gap_s']<=3.0 and 0.75<=spec['pre_gap_s']<=1.0
        s,e=gap_experiment(name);w=Experiment.p5_gap_windows(e)
        D=[b-a for a,b in w];want=[b-a for a,b in spec['gaps']['windows_s']] if 'windows_s' in spec['gaps'] else [spec['gaps']['duration_s']]
        assert np.allclose(D,want)
        for a,b_ in w:assert Experiment.p1_profile(e,a)[1]==s['speed_m_s'] and Experiment.p1_profile(e,b_-1e-6)[1]==s['speed_m_s']
        end=Experiment.p1_profile(e,Experiment.profile_duration(e));assert abs(end[1])<1e-9 and abs(e.pcfg['start_offset_m']+e.pcfg['path_length_m']/2)<1e-6
    assert pc.gap_spec(CFG,'v2.0-D0.40-A0') is None and pc.gap_spec(CFG,'v3.0-D0.4-A0') is None and pc.gap_name(2.0,0.725,'A45')=='v2.0-D0.725-A45'

def test_ident_profiles():
    for name in CFG['p6']['ident']['conditions']:
        p=pc.ident_cfg(CFG,name);assert pc.ident_budget(CFG,name)['inside']
        e=SimpleNamespace(pcfg=p,cfg={'p1_speed_m_s':p.get('speed_m_s',0.)},p6_switch_s=1.0 if p['family']=='chase' else None)
        T=Experiment.p6_family_start(e)+pc.ident_motion_duration(p,e.p6_switch_s)+p['end_hold_s']
        S=np.array([Experiment.p6_profile(e,t) for t in np.arange(0,T,0.004)])
        ds=np.abs(np.diff(S[:,0]));big=np.flatnonzero(ds>0.05)
        assert len(big)==(1 if p['family'] in ['step','chase'] else 0)
        assert S[0,0]==0. and abs(Experiment.p6_profile(e,Experiment.p6_family_start(e)-1e-6)[0]-p['start_offset_m'])<1e-9 and abs(S[-1,1])<1e-9 and S[:,0].max()<=p['start_offset_m']+p['path_length_m']+1e-6
    assert CFG['p6']['ident']['safety_tilt_deg']==65.0 and CFG['safety_tilt_deg']==45

def test_bracket_rule():
    b=p6_batch.bracket
    assert b([(0.25,'S'),(0.3,'S'),(0.4,'F')])[:2]==(0.35,'refine')
    assert b([(0.25,'S'),(0.3,'F')])[1]=='bracketed' and b([(0.4,'S'),(0.5,'F'),(0.6,'S')])[1]=='non_monotone'
    assert b([(0.4,'S')])[1]=='all_success' and b([(0.4,'F')])[1]=='all_failure' and b([(1.2,'S'),(1.6,'F')])[0]==1.4

RUN=ROOT/'data/p5-20261018-e2-D0.7-A0-T1-1'
@pytest.mark.skipif(not (RUN/'flight.ulg').exists(),reason='raw P5 run not present')
def test_export_reconstruction_and_frozen_metrics():
    import p6_export,p6_metrics
    from pyulog import ULog
    u=ULog(str(RUN/'flight.ulg'),p6_export.TOPICS);T={d.name:d.data for d in u.data_list if d.multi_id==0}
    r=p6_export.reconstruct(T)['resid'];assert r['components_over_1e-4']==0 and r['rows_unmatched']==0 and r['position_max_abs']<1e-6
    m=p6_metrics.analyze(RUN);m.pop('p6');assert m==json.loads((RUN/'p5-metrics.json').read_text())

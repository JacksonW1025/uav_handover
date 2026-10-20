import sys,json,math
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import numpy as np
from run_experiment import Experiment,P5_TREATMENT_KINDS,P6_GAP_TREATMENTS,P7_GAP_TREATMENTS,p5_profile
import p6_batch,p7_conditions as pc,p7_metrics

CFG=json.loads((ROOT/'config/p7.json').read_text())
P6=json.loads((ROOT/'config/p6.json').read_text())

def test_frozen_thresholds_equal_p6():
    for k,v in P6.items():
        if not isinstance(v,dict) and k!='p6_note':assert CFG[k]==v,k
    for k in ['gap_timing','catch_up','settle','clipping','failure_criteria','metrics','profile']:assert CFG['p5'][k]==P6['p5'][k],k
    for k in ['radius_margin_m','braking_allowance_m','stale_timeout_s','worst_case_deceleration_m_s2','hover_offset_allowance_m']:
        assert CFG['p5']['planned_path_check'][k]==P6['p5']['planned_path_check'][k]
    for k in ['p2','p3','p4c','joint_recovery','short_stage_rule']:assert CFG[k]==P6[k],k
    assert CFG['p4']['host']==P6['p4']['host']

def test_frozen_conditions_equal_the_rule():
    """Every frozen spec in config/p7.json equals the generator; cancelled ones are absent and listed."""
    groups=CFG['p4']['groups'];names=set()
    for st in ['a','b','c']:
        for item in groups[st].split(','):
            kind,cond,treat,n=item.split(':');assert kind=='p5_gap' and n=='1';names.add((cond,treat))
            assert pc.make(CFG,cond)==CFG['p5']['conditions'][cond],cond
            assert treat in P7_GAP_TREATMENTS+P6_GAP_TREATMENTS+P5_TREATMENT_KINDS['p5_gap'] and treat in CFG['p5']['treatments']
    assert len(groups['a'].split(','))==33 and len(groups['b'].split(','))==12 and len(groups['c'].split(','))==14
    assert sorted(CFG['p7']['cancelled'])==sorted(['q4-D0.45-g0.5-A0:T1a3','q4-D0.6-g0.5-A0:T1a3','q4-D0.45-g0.5-A45:T1a3','h-v2.5-D2.0-A0:T1a3r2'])
    for c in CFG['p7']['cancelled']:
        cond,treat=c.split(':');assert pc.make(CFG,cond)['cancelled'] and (cond,treat) not in names
    # A: 4 groups x D x 5 intervals minus cancellations + 6 single references; C: 15 planned - 1.
    a=pc.a_conditions(CFG);assert len(a)==36 and sum(1 for x in a if x[2]=='A0')==6
    assert len(pc.c_conditions(CFG))==15

def test_budget_and_hold_rule():
    for cond,spec in CFG['p5']['conditions'].items():
        b=spec['safety_budget_m'];assert b['inside'] and b['radius_m']<=8.0+1e-9
        prof=p5_profile(CFG['p5'],spec)
        if cond.startswith('h-'):
            assert spec['end_hold_s']==6.0 and prof['end_hold_s']==6.0 and 2.0<=spec['post_gap_s']<=6.0
            # stream after the last resume = cruise + deceleration + stationary hold >= 9 s
            assert spec['post_gap_s']+spec['speed_m_s']/CFG['p5']['profile']['decel_m_s2']+prof['end_hold_s']>=9.0-1e-9
        else:assert prof['end_hold_s']==3.0 and 2.0<=spec['post_gap_s']<=3.0
        assert 0.75<=spec['pre_gap_s']<=1.0

def test_b_draw_reproducible_and_inside_both_budgets():
    seqs,stats=pc.draw_b(CFG);assert seqs==CFG['p7']['b']['sequences'] and stats==CFG['p7']['b']['draw_statistics']
    d=CFG['p7']['b']['draw']
    for n,s in seqs.items():
        w=s['windows_s'];assert 2<=len(w)<=5 and w[0][0]==0.
        Ds=[b-a for a,b in w];gs=[w[k+1][0]-w[k][1] for k in range(len(w)-1)]
        assert all(0.2-1e-9<=x<=0.6+1e-9 for x in Ds) and all(x>=0.05-1e-9 for x in gs)
        assert sum(Ds)<=2.4+1e-9 and w[-1][1]<=5.0+1e-9
        assert not CFG['p5']['conditions'][f'{n}-A0'].get('cancelled')
    assert sorted({s['count'] for s in seqs.values()})==[2,3,4,5]

def test_seq4_windows_and_runner_profile():
    w=pc.seq4_windows(0.38,0.15);assert w==[[0.0,0.38],[0.53,0.91],[1.06,1.44],[1.59,1.97]]
    spec=CFG['p5']['conditions']['q4-D0.38-g0.15-A0'];prof=p5_profile(CFG['p5'],spec)
    e=SimpleNamespace(pcfg=prof,cfg={'p1_speed_m_s':2.0,'safety_radius_m':10,'p5':CFG['p5']})
    e.p5_gap_windows=lambda:Experiment.p5_gap_windows(e)
    win=Experiment.p5_gap_windows(e);t0=win[0][0]
    assert [[round(a-t0,9),round(b-t0,9)] for a,b in win]==w

def test_treatments_set_rrec_explicitly():
    t=CFG['p5']['treatments'];assert set(t)=={'T0','T1a3','T1a3r2'}
    assert t['T0']['rrec']==0.0 and t['T1a3']['rrec']==0.0 and t['T1a3r2']=={**t['T1a3'],'rrec':2.0,'description':t['T1a3r2']['description']}
    assert t['T1a3']['rtgt']==2 and t['T1a3']['rtdec']==3.0 and t['T0']['rtgt']==0

def test_plan_rows_and_seeds():
    groups=__import__('p2_batch').parse_groups(CFG['p4']['groups']['a'],'config/p7.json')
    plan=p6_batch.build_plan('p7-test-a',groups,CFG['p7']['a']['order_seed'])
    assert len(plan)==33 and len({r['sim_seed'] for r in plan})==33

def _rows(segment):
    keys=['kind','end_reason','timestamp_sample','rate','limited']+[f'{n}[{k}]' for n in ['target_position','target_velocity','setpoint_position','setpoint_velocity'] for k in range(3)]
    return {k:np.array([r.get(k,0) for r in segment]) for k in keys}

def test_replay_reproduces_the_law():
    """Python replay of the virtual target (p7_metrics.replay) on a synthetic segment generated with the same law."""
    rate,w=2.0,1.5;p=np.array([0.,0.]);v=np.array([0.,0.]);t=1_000_000;rows=[{'kind':1,'timestamp_sample':t,'rate':rate,'target_position[0]':0.,'target_position[1]':0.,'target_velocity[0]':0.,'target_velocity[1]':0.}]
    for k in range(1,4000):
        t+=4000;sp=np.array([3.+2.*k*.004,0.]);sv=np.array([2.,0.])
        a=w*w*(sp-p)+2*w*(sv-v);n=math.hypot(*a);lim=n>rate
        if lim:a=a*rate/n
        v=v+a*.004;p=p+v*.004;dp=math.hypot(*(sp-p));dv=math.hypot(*(sv-v))
        row={'kind':2,'timestamp_sample':t,'rate':rate,'limited':lim,'setpoint_position[0]':sp[0],'setpoint_velocity[0]':sv[0],'target_position[0]':p[0],'target_position[1]':p[1],'target_velocity[0]':v[0],'target_velocity[1]':v[1]}
        if dp<.02 and dv<.02:row.update({'kind':3,'end_reason':1});rows.append(row);break
        rows.append(row)
    rec=_rows(rows);r=p7_metrics.replay(rec,list(range(len(rows))),1.5,0.05,0.02,0.02)
    assert rows[-1]['kind']==3 and r['converged_in_replay'] is True and r['limit_flags_match']
    assert r['max_position_residual_m']<1e-12 and r['limited_s']>0

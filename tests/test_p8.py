import sys,json
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import numpy as np
from run_experiment import Experiment,P6_TREATMENT_KINDS
import p6_conditions,p8_conditions as pc

CFG=json.loads((ROOT/'config/p8.json').read_text())
P6=json.loads((ROOT/'config/p6.json').read_text())

def test_frozen_thresholds_equal_p6():
    for k,v in P6.items():
        if not isinstance(v,dict) and k!='p6_note':assert CFG[k]==v,k
    for k in ['p2','p3','p4c','p5','joint_recovery','short_stage_rule']:assert CFG[k]==P6[k],k
    a,b=CFG['p6']['ident'],P6['p6']['ident']
    for k in ['kind','safety_tilt_deg','altitude_loss_abort_m','outcome']:assert a[k]==b[k],k
    for k in ['radius_margin_m','braking_allowance_m','hover_offset_allowance_m']:assert a['planned_path_check'][k]==b['planned_path_check'][k]
    assert {k:v for k,v in a['profile'].items() if k not in ['end_hold_s','note']}=={k:v for k,v in b['profile'].items() if k not in ['end_hold_s','note']}
    assert a['families']['chase']['stop_decel_m_s2']==b['families']['chase']['stop_decel_m_s2'] and a['families']['chase']['catch_up_m']==b['families']['chase']['catch_up_m']
    assert a['treatments']['T0']['rini']==4 and a['treatments']['T0']['rtgt']==0 and a['treatments']['T0']['rrec']==0.0 and P6_TREATMENT_KINDS=={'p6_ident':['T0']}
    assert CFG['p4']['host']==P6['p4']['host'] and CFG['p4']['independence']['master_seed']==20261021

def test_frozen_a_conditions_equal_the_rule():
    assert pc.a_conditions(CFG)==CFG['p6']['ident']['conditions']
    c=CFG['p6']['ident']['conditions'];assert len(c)==7 and not any(s.get('cancelled') for s in c.values())
    assert {n:s.get('post_jump_s',s.get('max_chase_s')) for n,s in c.items()}=={'jump-v1.5-L1.5-A0':3.0,'jump-v1.5-L3.0-A0':3.0,'jump-v2.5-L1.5-A0':2.7,'jump-v2.5-L3.0-A0':2.1,
        'jump-v2.0-L3.0-A45':3.0,'jump-v2.5-L3.0-A45':2.1,'chase-x4.0-V2.0-A0':3.9}
    for n,s in c.items():
        # the next longer value would not fit (shrink stops at the first fitting value)
        key='post_jump_s' if s['family']=='jump' else 'max_chase_s';start=3.0 if key=='post_jump_s' else 4.0
        if s[key]<start:
            probe=json.loads(json.dumps(CFG));probe['p6']['ident']['conditions'][n]={**s,key:round(s[key]+0.1,6)};assert not pc.ident_budget(probe,n)['inside'],n
    g=CFG['p4']['groups']['a'].split(',');assert len(g)==7 and sum(int(x.split(':')[3]) for x in g)==8

def test_jump_profile():
    for name in CFG['p6']['ident']['conditions']:
        p=pc.ident_cfg(CFG,name);assert pc.ident_budget(CFG,name)['inside']
        e=SimpleNamespace(pcfg=p,cfg={'p1_speed_m_s':p.get('speed_m_s',0.)},p6_switch_s=2.7 if p['family']=='chase' else None,ident=pc)
        T=Experiment.p6_family_start(e)+pc.ident_motion_duration(p,e.p6_switch_s)+p['end_hold_s'];fs=Experiment.p6_family_start(e)
        ts=np.arange(0,T,0.004);S=np.array([Experiment.p6_profile(e,t) for t in ts]);ds=np.diff(S[:,0]);big=np.flatnonzero(np.abs(ds)>0.05)
        assert len(big)==1 and abs(S[-1,1])<1e-9 and S[:,0].max()<=p['start_offset_m']+p['path_length_m']+1e-6 and p['end_hold_s']==6.0
        if p['family']=='jump':
            assert abs(ts[big[0]+1]-fs-pc.jump_time(p))<0.005 and abs(ds[big[0]]-p['jump_m'])<p['speed_m_s']*0.004+1e-9
            assert abs(S[-1,0]-(p['start_offset_m']+p['path_length_m']))<1e-9 and pc.ident_gap(p) is None
            v=np.array([pc.ident_motion(p,t)[1] for t in np.arange(0,pc.ident_motion_duration(p),0.01)]);assert abs(v.max()-p['speed_m_s'])<1e-9 and v.min()>=0
    # P6 conditions through the P8 module are the P6 profiles
    for name in P6['p6']['ident']['conditions']:
        a,b=pc.ident_cfg(P6,name),p6_conditions.ident_cfg(P6,name);assert a==b
        for t in np.arange(-0.5,12,0.05):assert pc.ident_motion(a,t,1.5)==p6_conditions.ident_motion(b,t,1.5)
        assert pc.ident_budget(P6,name)==p6_conditions.ident_budget(P6,name)

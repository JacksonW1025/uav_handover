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
    for k in ['p2','p3','p4c','joint_recovery','short_stage_rule']:assert CFG[k]==P6[k],k
    for k in P6['p5']:
        if k!='treatments':assert CFG['p5'][k]==P6['p5'][k],k
    for t,x in P6['p5']['treatments'].items():
        y=CFG['p5']['treatments'][t];assert {k:v for k,v in y.items() if k not in ['rrec','description']}=={k:v for k,v in x.items() if k!='description'},t
    assert CFG['p5']['treatments']['T0']['rrec']==0.0 and CFG['p5']['treatments']['T1']=={**CFG['p5']['treatments']['T1'],'rini':4,'rtgt':2,'rtdec':2.0,'rrec':0.0}
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


# ---- B --------------------------------------------------------------------------------------------------------------
import hashlib,p8_space,p8_campaign,p8_batch
B=CFG['p8']['b']

def test_b_frozen_files():
    want={'p8_space.py':'1a49419c504eb3cc22e450e7a90e556aa9826e8a2eb070f77e9e5dce87ebd1b6','p8_methods.py':'e2367b0923b5924afd179dd55e3c7c8c19965c2be2cb23bbf6c38524e6779f73',
          'p8_build_lists.py':'98b8fb30fdd0a1f3ba17752109510a954a9a7775c9dc07723851256387541312','p8_list_index.json':'566ef0b9b992a0c33d9fd882a78600a51695e2c824607ad62ff4cafde1b2bda6',
          'p8_lists.json':'f3327225f734c17d36d5006b58a8364373c728e60a22404968db837bb37db478'}
    for f,h in want.items():assert hashlib.sha256((ROOT/'tools/p8'/f).read_bytes()).hexdigest()==h==B['files_sha256'][f],f
    assert B['project_p8_frozen_json_sha256']=='fe784e62aa5ee8c1ea5cb29fc2ec2d44169c2d02a084130c31342d28d25ba7d4'
    assert sorted(B['rotation']['order'])==sorted(B['campaigns']) and len(B['campaigns'])==30
    import random;o=list(B['campaigns']);random.Random(B['rotation']['order_seed']).shuffle(o);assert o==B['rotation']['order']

def test_b_case_spec_and_heading0_bytes():
    import p6_conditions
    from run_experiment import p5_profile
    strip=lambda d:{k:v for k,v in d.items() if k!='description'}
    for p6n,p8n in [('v2.0-D0.3-A0','v2.0-H0.0-W0.0-0.3'),('M1-A0','v2.0-H0.0-W0.0-0.55_0.7-1.25_1.4-1.95_2.1-2.65')]:
        a,b=p6_conditions.gap_spec(P6,p6n),pc.case_spec(CFG,p8n);assert json.dumps(strip(a))==json.dumps(strip(b))
        assert json.dumps(strip(p5_profile(P6['p5'],a)))==json.dumps(strip(p5_profile(CFG['p5'],b)))
    assert pc.axis_of(0)==[1.0,0.0,0.0] and pc.axis_of(90)==[0.0,1.0,0.0] and pc.case_spec(CFG,'v2.0-D0.3-A0') is None
    for g in ['dev_b','equivalence_b']:
        for item in CFG['p4']['groups'][g].split(','):
            kind,cond,t,n=item.split(':');assert kind=='p5_gap' and not pc.case_spec(CFG,cond).get('cancelled')

def test_b_budget_check_lists_preregistered():
    L=json.loads((ROOT/'tools/p8/p8_lists.json').read_text())['lists'];bad=[]
    for k,lst in L.items():
        for i,e in enumerate(lst,1):
            r=pc.budget_check(CFG,e['case'],k.split('/')[1]);assert pc.case_condition(e['case'],k.split('/')[1])+':'+k.split('/')[1]==e['name']
            if not r['equal']:bad.append((k,i,e['name']))
    want=[(m['list'],m['position'],m['name']) for m in B['budget_check']['preflight_check_of_the_offline_lists']['mismatches']]
    assert sorted(bad)==sorted(want)

def fake_run(row,out):
    """Dry run: deterministic outcome from the case; the third run of bo/T1/0 round 2 is an infrastructure failure once."""
    h=int(hashlib.sha256(row['condition'].encode()).hexdigest()[:8],16);tilt=20+h%30
    if row['id']=='bo-T1-s0-k02':row.update({'status':'FAIL','accepted':False,'flight_failure':False,'checks':{'trace':False}});return row
    row.update({'status':'PASS','accepted':tilt<45,'flight_failure':tilt>=45,'fail_primary':tilt>=45,'fail_task':tilt>=45,'max_tilt_deg':float(tilt),'max_altitude_loss_m':0.1,'checks':{}})
    return row

def run_dry(tmp,monkeypatch,camps,segments):
    monkeypatch.setattr(p8_batch,'run_row',fake_run);monkeypatch.setattr(p8_campaign,'identity',lambda:{'x':1});monkeypatch.setattr(p8_campaign,'remote_session',lambda:False)
    from types import SimpleNamespace
    state=tmp/'state';plan=[]
    for a,b in segments:
        out=tmp/f'out{a}';out.mkdir(parents=True,exist_ok=True)
        args=SimpleNamespace(prefix='t',state=state,stage='dev',development=False)
        assert not p8_campaign.execute(args,CFG,out,{'x':1},plan,camps,(a,b))
    return {c:p8_campaign.load_state(state,c) for c in camps},plan

def test_b_campaign_dry_run_restart_and_rotation(tmp_path,monkeypatch):
    import p8_conditions
    monkeypatch.setattr(p8_campaign,'ROOT',tmp_path);(tmp_path/'tools/p8').mkdir(parents=True);(tmp_path/'tools/p8/p8_lists.json').write_bytes((ROOT/'tools/p8/p8_lists.json').read_bytes())
    camps=['bo/T1/0','fuzz/T0/1','ours/T1/2','random/T0/0']
    one,plan1=run_dry(tmp_path/'a',monkeypatch,camps,[(1,10)])
    many,plan2=run_dry(tmp_path/'b',monkeypatch,camps,[(1,3),(4,4),(5,10)])
    for c in camps:
        assert [r['name'] for r in one[c]['runs']]==[r['name'] for r in many[c]['runs']] and one[c]['k_done']==10 and one[c]['rng_state']==many[c]['rng_state']
    assert [r['id'] for r in plan1]==[r['id'] for r in plan2]
    # rotation: round k of every campaign before round k+1; the infrastructure failure was rerun with a new seed, same case
    ks=[r['k'] for r in plan1];assert ks==sorted(ks)
    r0,r1=[r for r in plan1 if r['campaign']=='bo/T1/0' and r['k']==2];assert r1['id']=='bo-T1-s0-k02-r1' and r1['infra_rerun'] and r0['condition']==r1['condition'] and r0['sim_seed']!=r1['sim_seed']
    L=json.loads((ROOT/'tools/p8/p8_lists.json').read_text())['lists']
    assert [r['name'] for r in one['ours/T1/2']['runs']]==[e['name'] for e in L['ours/T1/2'][:10]]
    # online history: (case, max tilt, primary failure) of each counted run
    h=one['fuzz/T0/1']['history'];assert len(h)==10 and all(x[2]==(x[1]>=45) for x in h)
    lines=(tmp_path/'a/state/runs/p8_b_cases.jsonl').read_text().splitlines();assert len(lines)==2*len(plan1)

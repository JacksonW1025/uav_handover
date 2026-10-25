"""A4 tests check mappings, timing, full metrics and exact enclosure arithmetic."""
from fractions import Fraction as F
import gzip
import json
from math import lcm
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/p10a4'))
import data as d4
import models as m4
import bench as b4
import independent_audit as ia
import contract_counterexample as cc

BASE=ROOT/'data/p10-20261025-a4'


def test_whole_condition_split_and_named_observation_clocks():
    meta=json.loads((BASE/'inputs-interface/manifest.json').read_text());roles={}
    assert len(meta['runs'])==8
    for r in meta['runs']:
        roles.setdefault(r['group'],set()).add(r['role']);a=dict(np.load(BASE/'inputs-interface'/r['file'],allow_pickle=False))
        assert d4.sha(BASE/'inputs-interface'/r['file'])==r['sha256']
        lp=a['t']-a['lp_age_us'];hold=np.diff(lp)==0
        assert np.isin(np.diff(lp),[0,8000]).all()
        assert np.array_equal(a['p'][1:][hold],a['p'][:-1][hold])
        assert np.array_equal(a['v'][1:][hold],a['v'][:-1][hold])
    assert all(len(x)==1 for x in roles.values())


def test_actual_virtual_target_correction_matches_network_input():
    from pyulog import ULog
    import p6_export,p7_export
    raw=ROOT/'data/p9-20261024-dev-03/run/flight.ulg'
    u=ULog(str(raw),p7_export.TOPICS);t={x.name:x.data for x in u.data_list if x.multi_id==0}
    old=p6_export.reconstruct(t);new=p7_export.reconstruct(t)
    assert old['resid']['components_over_1e-4']>10000
    assert new['resid']['components_over_1e-4']==0 and new['vt'].any()
    assert np.max(abs(np.clip(new['pf'][:,:2],-.5,.5)-new['pin'][:,:2]))<1e-4


def toy():
    n=100;t=np.arange(n)*4000+100000;age=np.arange(n)%2*4000
    return {'t':t,'att_age_us':age,'lp_age_us':age,'q':np.zeros((n,2)),
        'p':np.zeros((n,2)),'v':np.ones((n,2))*.2,'a':np.zeros((n,2)),
        'ep':np.ones((n,2))*.1,'dv':np.ones((n,2))*.2,'yaw':np.zeros(n),'frame_yaw0':np.zeros(n)}


def test_clock_conditioned_prediction_holds_observations_and_integrates_q():
    a=toy();m={**m4.baseline(),'sensor_clocks':True,'yaw_transport':'delayed_frame'};k=np.array([40,41])
    pn,vn,qn,_=m4.predict_rows(a,m,k)
    assert np.array_equal(pn[0],a['p'][40]) and np.array_equal(vn[0],a['v'][40])
    assert np.array_equal(qn[0],a['q'][40])
    rho=np.exp(-.004/m['tau']);u=-np.array(m['kp'])*.1-np.array(m['kv'])*.2
    assert np.allclose(qn[1],(1-rho**2)*m4.rot(u,0.),rtol=0,atol=1e-14)


@pytest.mark.parametrize('number',[0,1,2])
def test_rollout_never_reads_future_measured_body_state(number):
    a=dict(np.load(BASE/'inputs-interface/dev-02.npz',allow_pickle=False));model=json.loads((BASE/'model-comparison/models.json').read_text())['models'][number]
    start=1500;first=m4.rollout(a,model,start,100)
    other={k:v.copy() for k,v in a.items()}
    for key in ['p','v','q','a']:other[key][start+1:]+=123.
    assert np.array_equal(first,m4.rollout(other,model,start,100))


def test_complete_P_metric_keeps_physical_cross_terms():
    pf,pl=m4.physical_P();w=np.array([[.003,-.004,.1],[-.002,.005,-.03]])
    full=[]
    for path in ['data/p10-20261024-a2/construction-reviewed/certificate.json','data/p10-20261025-a3/source-08/matrix-candidate.json']:
        full.append(np.array(json.loads((ROOT/path).read_text())['P_integer'],float)/1e10)
    z=np.zeros((2,47));z[:,:3]=w
    whole=sum(z[i]@full[i]@z[i] for i in range(2));reduced=w[0]@pf@w[0]+w[1]@pl@w[1]
    diagonal=np.sum(w[0]**2*np.diag(pf))+np.sum(w[1]**2*np.diag(pl))
    assert abs(whole-reduced)<1e-12 and abs(whole-diagonal)>.01
    z[0,3]=.01
    assert abs(sum(z[i]@full[i]@z[i] for i in range(2))-whole)>1e-4


def test_exact_covariance_enclosure_dominates_both_rho_endpoints():
    rng=np.random.default_rng(7);b=rng.integers(-3,4,(49,7));S=np.asarray(b@b.T,dtype=object);Q=np.eye(49,dtype=object)*5
    rows=[ia.rows_A(F(9),F(6),rho,[F(3,5),F(1,7)],[F(0),F(2,5)],[1,0]) for rho in [F(95,100),F(96,100)]]
    result,_=ia.covariance_step(S,*rows,Q)
    for A in rows:
        diff=[]
        for i in range(49):
            rr=[]
            for j in range(49):
                exact=sum(x*int(S[k,l])*y for k,x in A[i].items() for l,y in A[j].items())
                rr.append(F(int(result[i,j]-Q[i,j]))-exact)
            diff.append(rr)
        assert all(diff[i][i]>=sum(abs(diff[i][j]) for j in range(49) if j!=i) for i in range(49))


def test_clip_remainder_formula_covers_both_boundaries():
    for c in [-2.,-.51,-.5,-.1,0,.499,.5,1.2]:
        for radius in [.001,.2,2.]:
            sigma=abs(c)<.5
            remainder=max(0,abs(c)+radius-.5) if sigma else min(1,max(0,radius-(abs(c)-.5)))
            for delta in np.linspace(-radius,radius,11):
                err=np.clip(c+delta,-.5,.5)-np.clip(c,-.5,.5)-sigma*delta
                assert abs(err)<=remainder+1e-14
    # This is a regression check of the implementation. The all-delta proof
    # is the scalar interval argument in the standalone proof document.


def test_original_full_T0_nominal_and_capture_history_are_preserved():
    trace=dict(np.load(BASE/'proof-inputs/T0/trace.npz',allow_pickle=False))
    old=[json.loads(l) for l in gzip.open(ROOT/'data/p10-20261025-a3/source-08/trace.jsonl.gz','rt')]
    expected=np.array([[r['p'],r['v'],r['q']] for r in old]).transpose(0,2,1)
    assert len(trace['center'])==7350 and np.max(abs(trace['center'][:,:,:3]-expected))<1e-7
    cap=next(i for i,r in enumerate(old) if r['oracle'][1])
    assert np.array_equal(trace['generators'][cap,:,47:49],trace['generators'][cap,:,:2])
    assert np.any(trace['generators'][cap,:,3:47]!=0)


def test_uniform_ball_counterexample_survives_real_queue_updates():
    r=cc.calculate();b=b4.load();y=b['center'][0].copy();w=np.array([float(F(x)) for x in r['per_step_w_p_v_q']]);rho=np.exp(-.05)
    u0=-b['kp'][0]*y[45]-b['kv'][0]*y[46]
    for k in range(22):
        assert abs(-b['kp'][0]*y[45]-b['kv'][0]*y[46]-u0)<1e-13
        q=rho*y[2]+(1-rho)*u0;v=y[1]+.002*(y[2]+q);p=y[0]+.002*(y[1]+v)
        e=np.clip(y[0]-b['r'][k,0],-.5,.5);d=np.clip(y[1]-b['s'][k,0],-1,1)
        y=np.r_[np.array([p,v,q])+w,e,d,y[3:45],y[47:49]]
    assert y[2]>=float(F(r['q_forward_lower']))-1e-12 and y[2]>9.80665
    assert F(r['exact_P_norm_squared'])<9


@pytest.mark.parametrize('mutation',['history','body_step'])
def test_exact_audit_rejects_numeric_mutation_before_long_computation(tmp_path,mutation):
    source=BASE/'proof-inputs/T0';target=tmp_path/'input';target.mkdir()
    arrays=dict(np.load(source/'trace.npz',allow_pickle=False))
    if mutation=='history':arrays['generators'][0,1,3,0]=0
    else:arrays['center'][1,0,2]+=.01
    d4.save(target/'trace.npz',arrays)
    for name in ['candidate.json','manifest.json']:(target/name).write_bytes((source/name).read_bytes())
    m=json.loads((target/'manifest.json').read_text());m['trace_sha256']=d4.sha(target/'trace.npz');(target/'manifest.json').write_text(json.dumps(m))
    with pytest.raises(AssertionError):ia.audit(target)


def test_A3_old_condition_reproduced_without_rewriting_old_output():
    assert d4.sha(BASE/'a3-reproduction/compatibility.json')==d4.sha(ROOT/'data/p10-20261025-a3/compatibility-02/compatibility.json')

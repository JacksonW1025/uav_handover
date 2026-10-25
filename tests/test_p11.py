"""P11 no-flight regression checks: causal interfaces, source semantics, accounting."""
import io
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
sys.path.insert(0,str(ROOT/'tools/p11'))
from p11.state import Target
from p11.models import assert_input,network
from p3_memory import load_policy
from run_experiment import Experiment,p5_profile
from p11.pack import source_plan
from p11.run import claim
from p11.score import so3,score


def test_strict_timeout_and_correlated_capture():
    x=Target();p=np.array([1.,2.,-3.]);v=np.array([1.8,.2,0.]);q=np.array([1.,0.,0.,0.])
    x.step(0,0,p,v,q,(p,v,0.))
    assert x.step(200000,200000,p,v,q)[3] is False
    r,s,_,stale=x.step(200001,200001,p+v,v,q)
    assert stale and np.array_equal(r,(p+v).astype(np.float32)) and np.array_equal(s,np.zeros(3))


def test_speed_capture_removes_horizontal_velocity_jump():
    x=Target(2,2);p=np.array([1.,2.,-3.]);v=np.array([1.8,.2,.1]);q=np.array([1.,0.,0.,0.])
    r,s,_,_=x.step(1,1,p,v,q,activation=True)
    assert np.array_equal(s[:2],v[:2].astype(np.float32)) and s[2]==0.
    r2,s2,_,_=x.step(100001,100001,p,v,q)
    direction=v[:2]/np.linalg.norm(v[:2]);assert np.max(abs(s2[:2]-(v[:2]-.2*direction)))<1e-6
    assert np.max(abs(r2[:2]-(p[:2]+v[:2]*.1-direction*.01)))<1e-6


def test_recovery_repeated_timeout_retains_actual_event_history():
    x=Target(0,2,2);p=np.array([0.,0.,-3.]);v=np.array([1.,0.,0.]);q=np.array([1.,0.,0.,0.])
    x.step(0,0,p,v,q,activation=True)
    x.step(4000,4000,p,v,q,(p,v,0.))
    x.step(208001,208001,p,v,q)
    x.step(212001,212001,p,v,q,(p+v,v,0.))
    x.step(416002,416002,p,v,q)
    assert [e['kind'] for e in x.events]==['CAPTURE','CAPTURE','START','CAPTURE','END_STALE']


def test_float32_sidecar_serialization_regression():
    class Message:
        def __setattr__(self,k,v):object.__setattr__(self,k,np.array(v,np.float32) if k in ['position','velocity','acceleration'] else v)
    fake=SimpleNamespace(cfg={'p1_speed_m_s':1.},p11_sends=io.StringIO(),
        msgs=SimpleNamespace(TrajectorySetpoint=Message),trajpub=SimpleNamespace(publish=lambda m:None),event=lambda *a,**kw:None,
        profile_cfg=lambda:{'motion_axis_ned':[1,0,0],'setpoint_period_s':.02},p1_profile=lambda t:(t,1.,0.))
    Experiment.start_stream(fake,[0.,0.,-3.],1.6,False);fake.stream_emit(1.)
    d=json.loads(fake.p11_sends.getvalue());assert d['send_id']==1 and d['position']==[1.,0.,-3.]
    assert fake.stream_state['p11_sidecar_ns']>0


def test_startup_caps_do_not_replace_failed_ids():
    starts=[{'event':'START_INTENT','id':str(i),'budget_class':'development'} for i in range(12)]
    with pytest.raises(RuntimeError,match='cap'):claim(starts,'new','development')
    with pytest.raises(RuntimeError,match='already'):claim(starts,'0','development')
    starts=[{'event':'START_INTENT','id':str(i),'budget_class':'formal'} for i in range(72)]
    with pytest.raises(RuntimeError,match='cap'):claim(starts,'new','formal')


def test_future_and_unknown_prediction_fields_rejected():
    with pytest.raises(ValueError):assert_input({'future_targets':[]})
    doc={'schema':'x','identity':'x','initial':{'future_hidden':[1]},'plan':{},'model_sha256':None,'policy_sha256':None}
    with pytest.raises(ValueError,match='forbidden'):assert_input(doc)


def test_intermediate_policy_output_differs_without_gru_commit():
    P=load_policy();h=np.zeros(16);x=np.zeros(22);x[3:12]=np.eye(3).ravel()
    temporary,raw,action=network(P,h,x)
    assert np.max(np.abs(temporary-h))>.01
    # The intermediate evaluation changes its output but not committed h.
    _,_,wrong=network(P,temporary,x)
    assert np.max(np.abs(wrong-action))>1e-3


def prepare(cfg,treatment='P11-Z'):
    cfg=json.loads(json.dumps(cfg));spec=cfg['p5']['conditions']['p11-case']
    cfg['p2_profile']=p5_profile(cfg['p5'],spec);cfg['p1_speed_m_s']=spec['speed_m_s']
    cfg['p2_treatment_parameters']=cfg['p5']['treatments'][treatment]
    return cfg


def test_deleting_events_never_moves_trajectory_or_remaining_events():
    docs=[]
    for b in ['NORMAL','A','B','AB','REPAIR']:
        c=prepare(json.loads((ROOT/f'config/p11-cases/F1-r1-{b}.json').read_text()))
        docs.append(source_plan(c,[0,0,-3],1.6))
    assert all(d['profile']==docs[0]['profile'] for d in docs)
    assert all(d['stream_end_profile_s']==docs[0]['stream_end_profile_s'] for d in docs)
    assert docs[0]['windows_profile_s']==[]
    assert docs[1]['windows_profile_s']+docs[2]['windows_profile_s']==docs[3]['windows_profile_s']


def test_72_fixed_rows_complete_groups_and_shared_pair_seeds():
    p=json.loads((ROOT/'config/p11.json').read_text());rows=p['rows']
    assert len(rows)==72 and len({r['id'] for r in rows})==72
    groups={}
    for r in rows:groups.setdefault(r['group'],set()).add(r['split'])
    assert all(len(v)==1 for v in groups.values())
    for family in [f'F{i}' for i in range(1,7)]:
        for rep in [1,2]:assert len({r['sim_seed'] for r in rows if r['family']==family and r['rep']==rep})==1
    assert {r['branch'] for r in rows if r['stage']=='main'}=={'NORMAL','A','B','AB','REPAIR'}


def test_observation_injection_not_duplicated():
    s=(ROOT/'uav_lab/.local/checkouts/px4-raptor/src/modules/mc_raptor/mc_raptor.cpp').read_text()
    for text in ['ResearchRecoveryView research_recovery_view','_p11_pub.advertise();','float p11_memory[32]','_p11_pub.publish(_p11);']:
        assert s.count(text)==1,text


def test_geometric_attitude_difference_respects_quaternion_sign():
    q=np.array([[.5,.5,.5,.5],[1.,0.,0.,0.]])
    assert np.max(so3(q,-q))<1e-6


def test_censored_safe_prefix_is_not_success_or_full_peak(tmp_path):
    packed=tmp_path/'packed';packed.mkdir();pred=tmp_path/'pred';pred.mkdir()
    n=20;t=np.arange(n)*.004;q=np.tile([1.,0.,0.,0.],(n,1))
    np.savez(packed/'measurement.npz',profile_s=t,attitude=q,position=np.zeros((n,3)),velocity=np.zeros((n,3)))
    (packed/'prediction-input.json').write_text(json.dumps({'plan':{'common_first_gap_profile_s':0.,'horizon_profile_s':1.,'windows_profile_s':[[.2,.4]]}}))
    trace=np.zeros((n,52));trace[:,0]=t;trace[:,35]=1.;trace[:,48]=1.
    np.savez(pred/'M0.npz',trace=trace)
    (pred/'prediction.json').write_text(json.dumps({'models':{'M0':{'stop':None,'compute_s':0.}}}))
    measurement=tmp_path/'measurement.json';measurement.write_text(json.dumps({'whole':{'max_tilt_deg':0.},'censored':True,'task_outcome':'UNKNOWN_CENSORED'}))
    r=score(pred,packed,measurement,tmp_path/'out')['models']['M0']
    assert r['risk_comparison']=='UNKNOWN_CENSORED' and r['peak_abs_error_deg'] is None
    assert all(e['risk_comparison']=='NOT_REACHED' for e in r['event_windows'])


def test_p11_treatment_constructor_without_sitl(tmp_path,monkeypatch):
    monkeypatch.setenv('HANDOVER_VARIANT','raptor')
    args=SimpleNamespace(startup_only=False,config=ROOT/'config/p11-cases/F1-r1-REPAIR.json',hover_s=None,
        kind='p5_gap',condition='p11-case',treatment='P11-C',sim_seed=1,initial_yaw_deg=0.,output=tmp_path/'case',capture_raw_sensors=False)
    e=Experiment(args)
    assert e.cfg['p2_treatment_parameters']['rtgt']==2 and e.cfg['safety_tilt_deg']==45
    assert e.procs==[] and e.node is None
    e.events.close();e.samples.close();e.resources.close()
    for f in e.files:f.close()

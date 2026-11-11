"""Offline-only unit tests; no experiment or simulator is started."""
import importlib.util
from pathlib import Path
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('cn_reference_analysis',ROOT/'tools/cn_reference/analyze.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def fixture_data():
    t=np.arange(0,2200001,4000,dtype=np.int64);zero=np.zeros(len(t));one=np.ones(len(t))
    l={'timestamp':t,**{k:zero.copy() for k in ['x','y','vx','vy','vz']},'z':-3*one}
    a={'timestamp':t,'q[0]':one,'q[1]':zero.copy(),'q[2]':zero,'q[3]':zero}
    w={'timestamp':t,**{f'xyz[{j}]':zero for j in range(3)}}
    motors={'timestamp':t,**{f'control[{j}]':.5*one for j in range(4)}}
    return {'vehicle_local_position':l,'vehicle_attitude':a,'vehicle_angular_velocity':w,'actuator_motors':motors}

def test_full_rate_peak_not_decimated():
    d=fixture_data();d['vehicle_attitude']['q[1]'][1]=np.sin(np.radians(30))
    w=m.window(d,0,1)
    assert w['complete'];assert w['vehicle_attitude_coverage']['samples']==251
    assert w['max_tilt_deg']==pytest.approx(60);assert w['local_task_envelope']=='FAILURE'

def test_missing_and_sparse_windows_unknown():
    assert m.window({},0,1)['local_task_envelope']=='UNKNOWN'
    d=fixture_data();d['vehicle_attitude']={k:v[::10] for k,v in d['vehicle_attitude'].items()}
    assert not m.window(d,0,1)['complete']

def test_nonfinite_not_success():
    d=fixture_data();d['vehicle_local_position']['z'][20]=np.nan
    assert m.window(d,0,1)['local_task_envelope']=='UNKNOWN'

def test_host_mapping_no_extrapolation():
    p={'timestamp':np.array([4,8]),'run_wall_ns':np.array([100,200])}
    assert m.host_bracket(p,50)['native_lower_us'] is None
    assert m.host_bracket(p,150)['native_lower_us']==4
    assert m.host_bracket(p,250)['native_upper_us'] is None

def test_quaternion_sign_equivalence_and_staleness():
    s={'position':[0,0,0],'velocity':[0,0,0],'quaternion':[1,0,0,0],'angular_rate':[0,0,0],'max_age_us':0}
    t=dict(s,quaternion=[-1,0,0,0]);assert m.compare(s,t)['status']=='MATCH'
    t=dict(s,position=[.21,0,0]);assert m.compare(s,t)['status']=='MISMATCH'
    t=dict(s,max_age_us=20001);assert m.compare(s,t)['status']=='UNKNOWN'
    assert m.compare(None,s)['status']=='UNKNOWN'

def test_snapshot_does_not_borrow_future():
    assert m.snapshot(fixture_data(),-1)['vehicle_attitude'] is None

def test_absent_run_and_arm_validation(tmp_path):
    assert m.analyze(tmp_path/'absent','B')['status']=='NOT_RUN'
    with pytest.raises(ValueError):m.analyze(tmp_path,'AB')

def test_missing_overlay_and_no_overwrite(tmp_path):
    out=tmp_path/'new';r=m.combined(tmp_path/'absent',out)
    assert all(v['status']=='NOT_RUN' for v in r['arms'].values())
    assert (out/'BC-local-overlay.png').stat().st_size>0
    assert len((out/'three-arm.csv').read_text().splitlines())==4
    with pytest.raises(FileExistsError):m.combined(tmp_path/'absent',out)

def test_motor_step_includes_preanchor():
    d=fixture_data();d['actuator_motors']['control[0]'][250:]=.9
    assert m.window(d,1000000,1)['max_motor_sample_step']==pytest.approx(.4)

def test_input_clipping_uses_target_frame():
    p={'target_yaw':np.array([0.])}
    for k in ['position','velocity','network_target_position','network_target_velocity']:
        for j in range(3):p[f'{k}[{j}]']=np.array([0.])
    p['position[0]']=np.array([.7]);p['velocity[1]']=np.array([2.])
    for j in range(22):p[f'policy_input[{j}]']=np.array([0.])
    p['policy_input[0]']=np.array([.5]);p['policy_input[13]']=np.array([-1.])
    r=m.input_clipping(p,np.array([0]));assert r['position_clipped_samples']==1;assert r['velocity_clipped_samples']==1;assert r['reconstruction_max_abs_residual']==0

def test_broken_ulog_is_incomplete(tmp_path):
    (tmp_path/'flight.ulg').write_bytes(b'not a ulog')
    r=m.analyze(tmp_path,'C');assert r['status']=='INCOMPLETE';assert r['errors'];assert not r['evidence_completion']['complete']

def test_empty_ulog_never_passes(monkeypatch,tmp_path):
    class Empty:
        data_list=[];dropouts=[]
    (tmp_path/'flight.ulg').write_bytes(b'')
    monkeypatch.setattr(m,'ULog',lambda _:Empty())
    r=m.analyze(tmp_path,'A');assert not r['evidence_completion']['complete'];assert 'px4 process lifecycle' in r['evidence_completion']['missing']

def test_explicit_attempt_mapping(tmp_path):
    assert m.arm_mapping(['A=A2','B=B2','C=C2'])=={'A':'A2','B':'B2','C':'C2'}
    assert m.arm_mapping(['C=C2'])=={'A':'A','B':'B','C':'C2'}
    for invalid in [['A=../A'],['A=/tmp'],['A=A2','A=A3'],['D=D2']]:
        with pytest.raises(ValueError):m.arm_mapping(invalid)
    r=m.combined(tmp_path/'absent',tmp_path/'new',{'A':'A2','B':'B2','C':'C2'})
    assert r['selected_attempts']['C']=='C2';assert r['arms']['C']['source_run'].endswith('/C2/flight')
    assert r['candidate_pairwise_equal']['BC'] is None

def audit_module():
    spec=importlib.util.spec_from_file_location('cn_reference_audit',ROOT/'tools/cn_reference/audit.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def test_audit_enumerates_ledger_not_fixed_arms(tmp_path):
    a=audit_module();ledger=[{'event':'START_INTENT','arm':'C','output':str(tmp_path/'C'/'flight')},{'event':'START_INTENT','arm':'C','output':str(tmp_path/'C2'/'flight')}]
    entries=a.attempts(tmp_path,ledger);assert list(entries)==['C','C2'];assert entries['C2']['arm']=='C'
    with pytest.raises(ValueError):a.attempts(tmp_path,[{'event':'START_INTENT','arm':'C','output':'../../outside/flight'}])

def test_cost_missing_not_zero_success():
    a=audit_module();r=a.cost_total({'C':{'wall_s':3,'cpu_s':1},'C2':{'wall_s':4}})
    assert r['recorded_total']=={'wall_s':7,'cpu_s':1};assert not r['complete'];assert r['missing_by_metric']['cpu_s']==['C2']

def test_audit_missing_logs_preserves_attempt_and_cost(tmp_path,monkeypatch):
    import json
    a=audit_module();root=tmp_path/'runs';root.mkdir();monkeypatch.setattr(a,'ROOT',tmp_path)
    events=[{'event':'START_INTENT','arm':'C','output':str(root/'C2'/'flight')},{'event':'PHYSICAL_END','arm':'C','attempt':'C2','wall_s':4,'cpu_s':2}]
    (root/'attempts.jsonl').write_text('\n'.join(json.dumps(x) for x in events))
    r=a.audit(root,tmp_path/'audit');assert r['physical_start_count']==1;assert r['arms']['C2']['status']=='NO_ULOG';assert r['cost']['physical']['recorded_total']['wall_s']==4
    assert r['conclusion']['actual_neural_handoffs']==[]

def test_compressed_local_rows_include_predecessor(tmp_path):
    import gzip,json
    a=audit_module();d=fixture_data();p=tmp_path/'rows.gz';r=a.local_evidence(d,1000000,1100000,p)
    rows=[json.loads(x) for x in gzip.open(p,'rt')];first=next(v for v in rows if v['topic']=='vehicle_attitude')
    assert first['timestamp']==796000;assert r['topic_rows']['vehicle_attitude']>0;assert r['sha256']


def receipt_fixture():
    p={'timestamp':np.array([100,104,108]),'active':np.array([1,1,1]),'external_valid':np.array([1,1,1]),'read_wall_ns':np.array([900,1100,1200])}
    send={'before_ns':1000,'after_ns':1050,'position':[1.,2.,3.],'velocity':[4.,5.,6.]}
    for name in ['position','velocity']:
        for j in range(3):p[f'external_{name}[{j}]']=np.array([99.,send[name][j],send[name][j]])
    return p,send

def test_reference_receipt_excludes_inherited_valid():
    p,send=receipt_fixture()
    assert m.match_first_send(p,np.arange(3),send)==1
    for name in ['position','velocity']:
        for j in range(3):p[f'external_{name}[{j}]'][0]=send[name][j]
    assert m.match_first_send(p,np.arange(3),send)==1  # Same payload before send still excluded.

def test_reference_receipt_missing_match_is_unknown():
    p,send=receipt_fixture();send['position']=[20.,30.,40.]
    assert m.match_first_send(p,np.arange(3),send) is None
    assert m.match_first_send(p,np.arange(3),None) is None
    p,send=receipt_fixture();p['active'][:]=0
    assert m.match_first_send(p,np.arange(3),send) is None

def test_reference_receipt_requires_all_six_finite_components():
    p,send=receipt_fixture();p['external_velocity[2]'][1]=np.nan
    assert m.match_first_send(p,np.arange(3),send)==2
    p['external_velocity[2]'][2]+=0.0001
    assert m.match_first_send(p,np.arange(3),send) is None


def owner_fixture():
    own={'timestamp':np.array([100,104,108]),'actuator_timestamp':np.array([100,104,108]),'owner':np.array([2,1,1])}
    for j in range(4):own[f'control[{j}]']=np.array([.5,.7,.9])
    motors={'timestamp':np.array([100,108])}
    for j in range(4):motors[f'control[{j}]']=np.array([.5,.9])
    return {'research_actuator':own,'actuator_motors':motors}

def test_owner_boundary_recovers_exact_owner_topic_not_next_motor():
    r=m.owner_boundary_step(owner_fixture(),104)
    assert r['source']=='research_actuator.control[0:4]';assert r['after']==[.7]*4
    assert r['max_abs_step']==pytest.approx(.2);assert r['exact_publication_timestamp_match']
    assert not r['actuator_motors_exact_publication_logged'];assert r['limitation']

def test_owner_boundary_missing_exact_remains_incomplete():
    d=owner_fixture();d.pop('research_actuator');r=m.owner_boundary_step(d,104)
    assert not r['exact_publication_timestamp_match'];assert not r['finite'];assert 'after' not in r

def test_owner_boundary_detects_conflicting_exact_topics():
    d=owner_fixture();d['actuator_motors']['timestamp']=np.array([100,104]);r=m.owner_boundary_step(d,104)
    assert r['cross_topic_exact_controls_match'] is False


def test_audit_reanalyzes_without_overwriting_recorded_gate(tmp_path,monkeypatch):
    import json
    a=audit_module();root=tmp_path/'runs';f=root/'C3'/'flight';f.mkdir(parents=True)
    (root/'attempts.jsonl').write_text(json.dumps({'event':'START_INTENT','arm':'C','attempt':'C3','output':str(f)})+'\n')
    recorded={'status':'INCOMPLETE','evidence_completion':{'complete':False,'missing':['old gate']},'native_timeline':{'first_active_valid_external_read_us':100}}
    path=f/'cn-reference-measurement.json';path.write_text(json.dumps(recorded));original=path.read_bytes();(f/'flight.ulg').write_bytes(b'fake')
    class Empty:
        data_list=[];dropouts=[]
    monkeypatch.setattr(a,'ROOT',tmp_path);monkeypatch.setattr(a,'ULog',lambda _:Empty())
    monkeypatch.setattr(a,'analyze',lambda folder,arm:{'status':'MEASURED','evidence_completion':{'complete':True,'missing':[]},'native_timeline':{'first_active_valid_external_read_us':104}})
    result=a.audit(root,tmp_path/'audit');r=result['arms']['C3']
    assert r['recorded_evidence_completion']['complete'] is False
    assert r['evidence_completion']['complete'] is True
    assert r['current_native_timeline']['first_active_valid_external_read_us']==104
    assert path.read_bytes()==original

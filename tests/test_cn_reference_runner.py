"""Mock-only tests: never construct a simulator, ROS node, or real process."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from cn_reference import runner as r
from cn_single import design


def ledger(*arms):
    return [x for a in arms for x in [dict(event='START_INTENT',arm=a),dict(event='END',arm=a,infrastructure_ok=True)]]

@pytest.mark.parametrize('rows,arm', [([], 'A'),(ledger('A'),'B'),(ledger('A','B'),'C')])
def test_ordered_budget(rows,arm):r.claim(rows,arm)

@pytest.mark.parametrize('rows,arm', [([], 'B'),(ledger('A'),'A'),(ledger('A'),'C'),(ledger('A','B','C'),'C'),([dict(event='START_INTENT',arm='A')],'B'),([dict(event='START_INTENT',arm='A'),dict(event='END',arm='A',infrastructure_ok=False)],'B'),(ledger('A')+[dict(event='END',arm='A',infrastructure_ok=True)],'B')])
def test_no_retry_and_terminal_prior_failure(rows,arm):
    with pytest.raises(RuntimeError):r.claim(rows,arm)

@pytest.mark.parametrize('active,reason,stamp,recv,req_ns,ok',[(True,0,101,200,200,True),(False,0,101,201,200,False),(True,1,101,201,200,False),(True,0,100,201,200,False),(True,0,99,201,200,False),(True,0,101,199,200,False),(True,0,101,201,None,False)])
def test_fresh_gate(active,reason,stamp,recv,req_ns,ok):
    assert r.fresh_active(NS(active=active,exit_reason=reason,timestamp=stamp),recv,req_ns,100) is ok

class Clock:
    now=10.
    def monotonic(self):return self.now
    def monotonic_ns(self):return int(self.now*1e9)
    def time(self):return self.now+1000000

class Mission:
    sent=False
    closed=False
    def recv_match(self,**kw):
        if self.sent:return None
        self.sent=True
        return NS(get_srcSystem=lambda:22,get_type=lambda:'MISSION_CURRENT',seq=1)
    def close(self):self.closed=True

@pytest.fixture
def harness(tmp_path,monkeypatch):
    experiments=[]
    monkeypatch.setattr(r,'wait_mission_ready',lambda e:e.event('mock_mission_ready'))
    monkeypatch.setattr(r,'mission_sequence',lambda e:dict(seq_current=1))
    def make(arm,ack=0,activate=True,nav=True):
        c=Clock();monkeypatch.setattr(r,'time',c);monkeypatch.setattr(r.base,'time',c)
        e=r.Experiment.__new__(r.Experiment);experiments.append(e)
        e.cfg={'cn_reference':{'arm':arm},'safety_altitude_m':8.};e.instance=21;e.out=tmp_path/arm;e.out.mkdir()
        e.files=[];e.checks={};e.received={};e.acks=[];e.stream=None;e.record=[];e.published=[];e.pending=None
        e.msgs=NS(VehicleStatus=NS(NAVIGATION_STATE_AUTO_MISSION=3,NAVIGATION_STATE_AUTO_LOITER=4),VehicleCommand=NS,TrajectorySetpoint=NS)
        e.latest=dict(vehicle_status=NS(nav_state=4,timestamp=100),vehicle_local_position=NS(x=3.,y=1.,z=-3.2,vx=.4,vy=1.,vz=.1,heading=.5),raptor_status=NS(active=False,exit_reason=0,timestamp=100,timestamp_sample=100))
        e.event=lambda event,**kw:e.record.append(dict(event=event,**kw))
        m=Mission();e.mission=m;e.mav_open=lambda:m;e.upload_mission=lambda mav:None;e.command=lambda *args:None;e.hover=lambda *a,**kw:None
        e.native_phase_end_bound=lambda:int(c.now*1e6);e.native_bound_streaming=e.native_phase_end_bound
        def send(msg):e.pending=[int(msg.param1),0];e.event('fake_send',mode=int(msg.param1))
        e.cmdpub=NS(publish=send)
        e.trajpub=NS(publish=lambda msg:e.published.append((e.latest['vehicle_status'].nav_state,e.latest['raptor_status'].active,msg)))
        def pump(seconds=.1):
            c.now+=seconds
            if e.pending:
                mode,phase=e.pending
                if phase==0:
                    if mode==23:
                        for active,reason,stamp in [(False,0,101),(True,0,100),(True,1,102)]:
                            e.receive('raptor_status',NS(active=active,exit_reason=reason,timestamp=stamp,timestamp_sample=stamp))
                            if e.stream:e.stream()
                            assert not e.published
                        if activate:e.receive('raptor_status',NS(active=True,exit_reason=0,timestamp=103,timestamp_sample=103))
                    e.receive('vehicle_command_ack',NS(command=100001,result=ack if mode==23 else 0,timestamp=104));e.pending[1]=1
                elif mode!=23 or nav:e.latest['vehicle_status']=NS(nav_state=mode,timestamp=105);e.pending=None
            if e.stream:e.stream()
        e.pump=pump
        return e
    yield make
    for e in experiments:
        for f in e.files:f.close()

@pytest.mark.parametrize('arm',['B','C'])
def test_actual_flight_first_wait_phase_zero_identical_trajectory_and_gap(harness,arm):
    e=harness(arm);e.p1_flight(23)
    rows=[json.loads(s) for s in (e.out/'cn-setpoints.jsonl').read_text().splitlines()]
    assert rows[0]['profile_s']==0.
    first=next(x for x in e.record if x['event']=='cn_first_external_publish')
    assert first['mode_confirmed'] is (arm=='B')
    assert e.published[0][:2]==(23 if arm=='B' else 3,True)
    if arm=='C':
        assert first['active_gate']['timestamp']==103
        assert first['active_gate']['received_ns']>=e.cn_request_ns
    else:assert first['active_gate'] is None
    for row in rows:
        assert not design.in_gap(row['profile_s'])
        expected=design.trajectory(row['profile_s'],[3.,1.,-3.2],[.4,1.,.1],.5)
        for key,value in zip(('position','velocity','acceleration','yaw','yawspeed'),expected):assert row[key]==pytest.approx(value)
    assert all(b['profile_s']-a['profile_s']>=.02-1e-12 for a,b in zip(rows,rows[1:]))
    for event in ['cn_gap_started','cn_gap_ended']:assert sum(x['event']==event for x in e.record)==1
    assert [x['mode'] for x in e.record if x['event']=='mode_confirmed']==[3,23,4]
    assert e.stream is None and e.mission.closed and e.checks['cn_case']=='COMPLETE'

@pytest.mark.parametrize('arm',['B','C'])
def test_actual_ack_rejection_is_not_bypassed(harness,arm):
    e=harness(arm,ack=1)
    with pytest.raises(RuntimeError,match='rejected'):e.p1_flight(23)
    assert not any(x['event']=='cn_reference_finished' for x in e.record)
    if arm=='B':assert not e.published

@pytest.mark.parametrize('arm',['B','C'])
def test_actual_nav_wait_timeout_is_not_bypassed(harness,arm):
    e=harness(arm,nav=False)
    with pytest.raises(TimeoutError,match='nav_state=23'):e.p1_flight(23)
    assert not any(x['event']=='cn_reference_finished' for x in e.record)

def test_c_without_fresh_gate_never_publishes_even_if_nav_confirms(harness):
    e=harness('C',activate=False)
    with pytest.raises(RuntimeError,match='first reference was not released'):e.p1_flight(23)
    assert not e.published

def test_a_native_2_2_seconds_mission_no_neural_no_reference(harness):
    e=harness('A');e.p1_flight(23)
    assert not e.published and not e.files
    assert [x['mode'] for x in e.record if x['event']=='fake_send']==[3,4]
    end=next(x for x in e.record if x['event']=='cn_classic_control_finished')
    assert end['end_px4_us']-end['start_px4_us']>=2200000 and end['duration_s']>=2.2
    assert not any(x['event']=='handover_requested' for x in e.record)
    assert e.checks['cn_case']=='COMPLETE'

def test_normal_safety_command_paths_and_geometry_are_inherited():
    assert r.Experiment.mode is r.base.Experiment.mode
    assert r.Experiment.ros_command is r.base.Experiment.ros_command
    assert r.Experiment.wait is r.base.Experiment.wait
    assert r.Experiment.pump is r.original.Experiment.pump
    assert r.trajectory is design.trajectory and r.in_gap is design.in_gap
    assert r.SEED==20261109 and r.DURATION==design.DURATION

def test_run_records_constructor_failure_and_refuses_retry_or_next_arm(tmp_path,monkeypatch):
    # Exercise the real launch ledger with the entire Experiment replaced before
    # construction. No execute(), simulator, subprocess, host mutation, or ROS.
    evidence=tmp_path/'evidence';config=tmp_path/'input.json'
    config.write_text(json.dumps({'cn_reference':{}}))
    monkeypatch.setattr(r,'ROOT',tmp_path);monkeypatch.setattr(r,'EVIDENCE',evidence)
    monkeypatch.setattr(r,'CONFIG',config)
    monkeypatch.setattr(r,'host_gate',lambda:{'ok':True})
    monkeypatch.setattr(r,'identity',lambda:{'candidate':'fixed'})
    attempts=[]
    def fail(args):
        attempts.append(args)
        assert args.sim_seed==20261109
        raise RuntimeError('offline injected constructor failure')
    monkeypatch.setattr(r,'Experiment',fail)
    assert r.run('A')==1
    rows=[json.loads(s) for s in (evidence/'attempts.jsonl').read_text().splitlines()]
    assert [x['event'] for x in rows]==['START_INTENT','PHYSICAL_END','END']
    assert rows[-1]['infrastructure_ok'] is False
    for arm in ['A','B','C']:
        with pytest.raises(RuntimeError):r.run(arm)
    assert len(attempts)==1


def test_blocked_host_is_not_a_launch(tmp_path,monkeypatch):
    monkeypatch.setattr(r,'EVIDENCE',tmp_path/'evidence')
    def blocked():raise RuntimeError('offline mocked host gate failure')
    monkeypatch.setattr(r,'host_gate',blocked)
    with pytest.raises(RuntimeError,match='host gate'):r.run('A')
    rows=[json.loads(s) for s in (r.EVIDENCE/'attempts.jsonl').read_text().splitlines()]
    assert len(rows)==1 and rows[0]['event']=='BLOCKED_BEFORE_START'
    assert rows[0]['counts_as_start'] is False
    r.claim(rows,'A')

@pytest.fixture(autouse=True)
def forbid_any_launch(monkeypatch):
    """Fail closed if any supposedly offline test reaches a launch mechanism."""
    import os
    import subprocess
    def forbidden(*args,**kwargs):
        raise AssertionError('Offline tests must never launch a process or execute an experiment')
    monkeypatch.setattr(subprocess,'Popen',forbidden)
    monkeypatch.setattr(os,'system',forbidden)
    monkeypatch.setattr(r.base.Experiment,'execute',forbidden)
    monkeypatch.setattr(r.base.Experiment,'spawn',forbidden)


@pytest.fixture
def classic_traces(tmp_path):
    """Real binary encoder/reader and summary; synthetic data, no flight files."""
    import numpy as np
    from output_chain import ROW, summarize
    root=tmp_path/'classic';root.mkdir();(root/'gz-motor').mkdir()
    times=100000+np.arange(1001,dtype=np.uint64)*4000
    def write(ages=4000,missing_step=False,tail=False,disagree=False,boundaries=True):
        motors={};tails={}
        for k in range(4):
            rows=np.zeros(len(times),dtype=ROW)
            rows['sim_us']=times
            rows['applied_sample_us']=times-np.asarray(ages,dtype=np.uint64)
            if disagree and k==3:rows['applied_sample_us'][20]-=1
            if missing_step:rows=np.delete(rows,20)
            motors[k]=rows;tails[str(k)]=int(tail and k==3)
            header=b'HOMTRC01'+np.asarray([ROW.itemsize,k],dtype='<u4').tobytes()
            (root/'gz-motor'/f'motor-{k}.bin').write_bytes(header+rows.tobytes()+(b'x' if tails[str(k)] else b''))
        events=[dict(event='cn_control_trigger',end_bound_px4_us=int(times[0])),dict(event='cn_classic_control_finished',end_px4_us=int(times[-1]))]
        (root/'events.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in (events if boundaries else events[:1])))
        chain=summarize(motors,[]);chain['partial_tail_bytes']=tails
        return root,chain
    return write


def test_classic_four_complete_traces_pass_original_age_limit(classic_traces):
    out,chain=classic_traces()
    errors,local=r.classic_chain_gate(out,chain)
    assert errors==[] and set(local)=={'0','1','2','3'}
    assert all(v['steps']==1001 and v['applied_age_us']['p99']==r.GATE['p99_us'] for v in local.values())


@pytest.mark.parametrize('kind,expected',[
    ('p99','age gate'),('max','age gate'),('consecutive','consecutive age gate'),
    ('missing_step','missing physical steps'),('tail','incomplete traces'),
    ('disagree','four motor samples disagree'),('boundary','classic control boundaries missing'),
    ('missing_motor','four motors missing'),('missing_tail','incomplete traces')])
def test_classic_gate_rejects_incomplete_or_over_limit_evidence(classic_traces,kind,expected):
    import numpy as np
    ages=np.full(1001,4000,dtype=np.uint64)
    if kind=='p99':ages[:]=r.GATE['p99_us']+1
    if kind=='max':ages[10]=r.GATE['max_us']+1
    if kind=='consecutive':ages[10:10+r.GATE['longest_over_target_steps']+1]=r.GATE['p99_us']+1
    out,chain=classic_traces(ages,missing_step=kind=='missing_step',tail=kind=='tail',disagree=kind=='disagree',boundaries=kind!='boundary')
    if kind=='missing_motor':chain['motors'].pop('3')
    if kind=='missing_tail':chain['partial_tail_bytes'].pop('3')
    errors,_=r.classic_chain_gate(out,chain)
    assert any(expected in e for e in errors),errors


def test_classic_exact_max_and_consecutive_limits_pass(classic_traces):
    import numpy as np
    ages=np.full(1001,4000,dtype=np.uint64)
    ages[10:10+r.GATE['longest_over_target_steps']]=r.GATE['max_us']
    out,chain=classic_traces(ages)
    errors,local=r.classic_chain_gate(out,chain)
    assert not errors
    assert all(x['applied_age_us']['max']==r.GATE['max_us'] and x['longest_over_target_steps']==r.GATE['longest_over_target_steps'] for x in local.values())


def test_classic_control_does_not_gate_on_unused_neural_trajectory(harness,monkeypatch):
    monkeypatch.setattr(r,'reference_budget',lambda *args:dict(inside=False))
    e=harness('A');e.p1_flight(23)
    assert e.checks['cn_case']=='COMPLETE' and not e.published
    assert any(x['event']=='cn_classic_control_finished' for x in e.record)

@pytest.mark.parametrize('arm',['B','C'])
def test_neural_arms_keep_reference_budget_before_subject(harness,monkeypatch,arm):
    monkeypatch.setattr(r,'reference_budget',lambda *args:dict(inside=False))
    e=harness(arm)
    with pytest.raises(RuntimeError,match='physical-margin budget'):e.p1_flight(23)
    assert not e.published and not any(x['event']=='handover_requested' for x in e.record)

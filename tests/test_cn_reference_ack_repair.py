"""Offline Mission receive-queue regression; no simulator or live socket."""
from collections import deque
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from cn_reference import runner as r


@pytest.fixture(autouse=True)
def no_process_launch(monkeypatch):
    import subprocess,os
    def fail(*args,**kwargs):raise AssertionError('offline-only: process/flight launch forbidden')
    monkeypatch.setattr(subprocess,'Popen',fail)
    monkeypatch.setattr(os,'system',fail)
    monkeypatch.setattr(r.base.Experiment,'execute',fail)
    monkeypatch.setattr(r.base.Experiment,'spawn',fail)


class Clock:
    def __init__(self):self.now=0.
    def monotonic(self):return self.now
    def monotonic_ns(self):return int(self.now*1e9)


class Packet:
    def __init__(self,kind='ATTITUDE',seq=0,result=0,system=22,component=1,target=245,target_component=191,mission_type=0):
        self.kind=kind;self.seq=seq;self.type=result;self.system=system;self.component=component
        self.target_system=target;self.target_component=target_component;self.mission_type=mission_type
    def get_type(self):return self.kind
    def get_srcSystem(self):return self.system
    def get_srcComponent(self):return self.component


class Link:
    def __init__(self,clock,packets,noise=False,receive_cost=.00001):
        self.clock=clock;self.queue=deque(packets);self.noise=noise;self.cost=receive_cost
        self.mav=self;self.calls=[];self.receives=0;self.since_pump=0;self.max_per_pump=0
    def recv_match(self,**kwargs):
        assert kwargs.get('blocking') is False
        self.clock.now+=self.cost;self.receives+=1;self.since_pump+=1
        self.max_per_pump=max(self.max_per_pump,self.since_pump)
        if self.queue:return self.queue.popleft()
        return Packet() if self.noise else None
    def mission_count_send(self,*args):self.calls.append(('count',args))
    def mission_item_int_send(self,*args):self.calls.append(('int',args))
    def mission_item_send(self,*args):self.calls.append(('float',args))


def requests():return [Packet('MISSION_REQUEST_INT' if i%2==0 else 'MISSION_REQUEST',seq=i) for i in range(5)]


@pytest.fixture
def harness(monkeypatch):
    def make(packets,noise=False,cost=.00001):
        c=Clock();monkeypatch.setattr(r,'time',c);monkeypatch.setattr(r.original,'time',c)
        e=r.Experiment.__new__(r.Experiment);e.instance=21
        e.latest={'vehicle_local_position':NS(xy_global=True,z_global=True,ref_lat=47.,ref_lon=8.,ref_alt=500.)}
        e.records=[];e.event=lambda name,**kw:e.records.append(dict(event=name,**kw))
        link=Link(c,packets,noise,cost);e.pumps=[]
        def pump(seconds=.1):
            e.pumps.append(c.now);link.since_pump=0;c.now+=seconds
        e.pump=pump
        return e,link,c
    return make


def test_reproduction_old_loop_times_out_but_bounded_drain_accepts_same_queue(harness):
    packets=[Packet() for _ in range(1600)]+requests()+[Packet('MISSION_ACK')]
    old,link,c=harness(packets)
    with pytest.raises(TimeoutError,match='mission upload acknowledgement'):
        r.original.Experiment.upload_mission(old,link)
    assert c.now>=15 and not any(x['event']=='cn_mission_ack' for x in old.records)
    new,link,c=harness(packets)
    new.upload_mission(link)
    assert c.now<15
    assert link.calls[0]==('count',(22,1,5))
    assert len(link.calls)==6 and link.calls[1][1][-1]==503.
    ack=next(x for x in new.records if x['event']=='cn_mission_ack')
    assert ack['result']==0 and ack['sent']==[0,1,2,3,4]
    assert 1<link.max_per_pump<=256 and len(new.pumps)>1


@pytest.mark.parametrize('bad',[
    {'system':23},{'component':2},{'target':99},{'target_component':99},{'mission_type':1}])
def test_foreign_or_wrong_type_ack_never_accepts(harness,bad):
    e,m,c=harness(requests()+[Packet('MISSION_ACK',**bad)])
    with pytest.raises(TimeoutError,match='mission upload acknowledgement'):e.upload_mission(m)
    assert not any(x['event']=='cn_mission_ack' for x in e.records)
    assert 15<=c.now<15.03


@pytest.mark.parametrize('packets',[
    requests()+[Packet('MISSION_ACK',result=1)],
    requests()[:-1]+[Packet('MISSION_ACK')],
    [Packet('MISSION_ACK')],
    [Packet('MISSION_REQUEST_INT',seq=5)],
    [Packet('MISSION_REQUEST_INT',seq=-1)]])
def test_invalid_ack_missing_items_and_out_of_range_request_fail(harness,packets):
    e,m,c=harness(packets)
    with pytest.raises(RuntimeError):e.upload_mission(m)
    assert c.now<15


def test_foreign_request_does_not_count_toward_complete_upload(harness):
    e,m,c=harness(requests()[:-1]+[Packet('MISSION_REQUEST_INT',seq=4,system=23),Packet('MISSION_ACK')])
    with pytest.raises(RuntimeError,match='not fully accepted'):e.upload_mission(m)


@pytest.mark.parametrize('cost',[0.,.00001,.0006])
def test_endless_noise_is_bounded_and_safety_pump_is_fair(harness,cost):
    e,m,c=harness([],noise=True,cost=cost)
    with pytest.raises(TimeoutError,match='mission upload acknowledgement'):e.upload_mission(m)
    assert 15<=c.now<15.03
    assert len(e.pumps)>1000
    assert m.max_per_pump<=256
    # The slow-message case forces the 2ms wall-time bound rather than count.
    if cost==.0006:assert m.max_per_pump<=4
    assert max(b-a for a,b in zip(e.pumps,e.pumps[1:]))<=.0127


def test_no_global_reference_is_rejected_before_count(harness):
    e,m,c=harness(requests()+[Packet('MISSION_ACK')]);e.latest['vehicle_local_position'].xy_global=False
    with pytest.raises(RuntimeError,match='global'):e.upload_mission(m)
    assert not m.calls


def test_safety_pump_exception_is_not_swallowed(harness):
    e,m,c=harness(requests()+[Packet('MISSION_ACK')])
    def fail(*args):raise RuntimeError('injected safety abort')
    e.pump=fail
    with pytest.raises(RuntimeError,match='injected safety abort'):e.upload_mission(m)
    assert m.receives==0


def continuation_rows():
    return [dict(event='START_INTENT',arm='A'),dict(event='END',arm='A',infrastructure_ok=True),
            dict(event='START_INTENT',arm='B'),dict(event='END',arm='B',infrastructure_ok=False)]


def test_continuation_is_explicit_and_only_remaining_c():
    rows=continuation_rows()
    with pytest.raises(RuntimeError):r.claim(rows,'C')
    r.claim(rows,'C',continue_after_ack=True)
    for arm in ('A','B'):
        with pytest.raises(RuntimeError):r.claim(rows,arm,continue_after_ack=True)
    with pytest.raises(RuntimeError):r.claim(rows+[dict(event='START_INTENT',arm='C')],'C',True)
    with pytest.raises(RuntimeError):r.claim([], 'A',True)
    with pytest.raises(RuntimeError):r.claim(rows[:2], 'B',True)


@pytest.mark.parametrize('mutation',['a_failed','b_missing_end','b_duplicate_end','reordered'])
def test_continuation_preserves_prior_completion_and_order(mutation):
    rows=continuation_rows()
    if mutation=='a_failed':rows[1]['infrastructure_ok']=False
    if mutation=='b_missing_end':rows.pop()
    if mutation=='b_duplicate_end':rows.append(dict(rows[-1]))
    if mutation=='reordered':rows[0]['arm']='B';rows[2]['arm']='A'
    with pytest.raises(RuntimeError):r.claim(rows,'C',True)


@pytest.fixture
def continuation_evidence(tmp_path,monkeypatch):
    import json
    b=tmp_path/'B';(b/'flight').mkdir(parents=True)
    monkeypatch.setattr(r,'EVIDENCE',tmp_path)
    result=dict(reason="TimeoutError('mission upload acknowledgement')",cleanup_error=None,candidate_unchanged=True)
    measured=dict(subject_requests=[],full_neural_analysis={'actual_neural_entries':0})
    old=dict(lab={'binary':'fixed'},policy_sha256='policy',gz_research_plugin_sha256='plugin',files={'tools/cn_reference/runner.py':'old','config/cn_reference/quickcheck.json':'fixed'})
    candidate=json.loads(json.dumps(old));candidate['files']['tools/cn_reference/runner.py']='new'
    def write():
        (b/'result.json').write_text(json.dumps(result))
        (b/'flight/cn-reference-measurement.json').write_text(json.dumps(measured))
        (b/'candidate-before.json').write_text(json.dumps(old))
    return result,measured,candidate,write


def test_exact_known_failure_and_only_receive_repair_allowed(continuation_evidence):
    result,measured,candidate,write=continuation_evidence;write()
    proof=r.verify_ack_continuation(candidate)
    assert proof['remaining_start']=='C only' and proof['original_budget']==3 and proof['no_B_retry']
    assert proof['changed_files']==['tools/cn_reference/runner.py']


@pytest.mark.parametrize('mutation',['other_failure','cleanup','changed_old','subject','neural_entry','unknown_entries','lab','policy','plugin','config','other_source'])
def test_unrelated_failures_subjects_or_scientific_changes_cannot_continue(continuation_evidence,mutation):
    result,measured,candidate,write=continuation_evidence
    if mutation=='other_failure':result['reason']="TimeoutError('mode acknowledgement')"
    if mutation=='cleanup':result['cleanup_error']='uncertain shutdown'
    if mutation=='changed_old':result['candidate_unchanged']=False
    if mutation=='subject':measured['subject_requests']=[{'subject':True}]
    if mutation=='neural_entry':measured['full_neural_analysis']['actual_neural_entries']=1
    if mutation=='unknown_entries':measured['full_neural_analysis']={}
    if mutation=='lab':candidate['lab']={'binary':'changed'}
    if mutation=='policy':candidate['policy_sha256']='changed'
    if mutation=='plugin':candidate['gz_research_plugin_sha256']='changed'
    if mutation=='config':candidate['files']['config/cn_reference/quickcheck.json']='changed'
    if mutation=='other_source':candidate['files']['tools/cn_single/runner.py']='added'
    write()
    with pytest.raises(RuntimeError):r.verify_ack_continuation(candidate)

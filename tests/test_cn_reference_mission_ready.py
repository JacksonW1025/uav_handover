"""Synthetic native listener data only; process launching is forbidden."""
from pathlib import Path
from types import SimpleNamespace as NS
import copy
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from cn_reference import mission_ready as m

GOOD = dict(mission=dict(timestamp=48556000, mission_id=3496065719, count=5),
    mission_result=dict(timestamp=48556000, mission_id=3496065719, seq_total=5, seq_current=0, valid=1, failure=0),
    health_report=dict(timestamp=48644000, can_run_mode_flags=16726712),
    failsafe_flags=dict(timestamp=48644000, auto_mission_missing=0, mission_failure=0))

@pytest.fixture(autouse=True)
def no_processes(monkeypatch):
    import subprocess, os
    def forbidden(*args, **kwargs):raise AssertionError('offline only')
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    monkeypatch.setattr(os, 'system', forbidden)


def output(topic, row):
    return '\nTOPIC: '+topic+'\n '+topic+'\n'+''.join('    '+key+': '+str(value)+(' (0.020000 seconds ago)' if key=='timestamp' else '')+'\n' for key,value in row.items())


def test_native_real_format_and_large_unsigned_id():
    for topic,row in GOOD.items():assert m.parse_native(topic, output(topic,row))==row
    text=output('mission_result',GOOD['mission_result']).replace('valid: 1','valid: True').replace('failure: 0','failure: False')
    assert m.parse_native('mission_result',text)==GOOD['mission_result']

@pytest.mark.parametrize('text',['never published','TOPIC: wrong\n timestamp: 1', 'TOPIC: mission\n timestamp: 1\n mission_id: 2\n count: NaN', 'TOPIC: mission\n timestamp: 1\n mission_id: 2\n count: 5\n count: 5'])
def test_parser_fails_closed(text):
    with pytest.raises(ValueError):m.parse_native('mission',text)

@pytest.mark.parametrize('topic,key,value',[
    ('mission','timestamp',0),('mission','mission_id',0),('mission','count',4),
    ('mission_result','mission_id',1),('mission_result','seq_total',4),('mission_result','valid',0),('mission_result','failure',1),
    ('health_report','timestamp',48320000),('health_report','can_run_mode_flags',16726704),
    ('failsafe_flags','timestamp',48320000),('failsafe_flags','auto_mission_missing',1),('failsafe_flags','mission_failure',1)])
def test_ready_rejects_stale_or_ineligible_evidence(topic,key,value):
    rows=copy.deepcopy(GOOD);rows[topic][key]=value
    assert m.readiness(rows,3)

def test_exact_updated_evidence_is_ready():assert not m.readiness(GOOD,3)

class Clock:
    now=0.
    def monotonic(self):return self.now

@pytest.fixture
def fake(monkeypatch):
    def make(ready_after=0.):
        c=Clock();monkeypatch.setattr(m,'time',c)
        e=NS(msgs=NS(VehicleStatus=NS(NAVIGATION_STATE_AUTO_MISSION=3)),calls=[],events=[],pumps=[])
        e.event=lambda event,**kw:e.events.append((event,kw))
        def pump(seconds):e.pumps.append(seconds);e.calls.append(('pump',seconds));c.now+=seconds
        def command(module,topic,*args,timeout):
            assert module=='listener' and args==('-n','1') and 0<timeout<=.25
            e.calls.append(('listener',topic));c.now+=.001
            rows=copy.deepcopy(GOOD)
            if c.now<ready_after:
                rows['health_report'].update(timestamp=48320000,can_run_mode_flags=16726704)
                rows['failsafe_flags'].update(timestamp=48320000,auto_mission_missing=1)
            return output(topic,rows[topic])
        e.pump=pump;e.command=command
        return e,c
    return make


def test_cached_mission_race_waits_until_health_refresh_then_returns(fake):
    e,c=fake(.2);proof=m.wait_mission_ready(e)
    assert c.now>=.2 and proof['attempts']>1
    assert proof['native']['health_report']['can_run_mode_flags']&8
    assert e.events[-1][0]=='cn_mission_readiness_confirmed'
    for i,call in enumerate(e.calls):
        if call[0]=='listener':assert e.calls[i-1][0]==e.calls[i+1][0]=='pump'
    assert all(call[0] in ('listener','pump') for call in e.calls)


def test_no_ready_cache_times_out_without_mode_or_upload(fake):
    e,c=fake(100.)
    with pytest.raises(TimeoutError):m.wait_mission_ready(e,timeout_s=.4)
    assert .4<=c.now<.41
    assert not any(name=='cn_mission_readiness_confirmed' for name,_ in e.events)


def test_safety_and_listener_errors_propagate(fake):
    e,c=fake()
    def fail(*args,**kw):raise RuntimeError('safety abort')
    e.pump=fail
    with pytest.raises(RuntimeError,match='safety abort'):m.wait_mission_ready(e)
    e,c=fake();e.command=fail
    with pytest.raises(RuntimeError,match='safety abort'):m.wait_mission_ready(e)


def test_missing_fields_never_fabricate_readiness(fake):
    e,c=fake();e.command=lambda *args,**kw:'never published'
    with pytest.raises(TimeoutError):m.wait_mission_ready(e,timeout_s=.2)


def test_sequence_requires_successful_readiness(fake):
    e,c=fake()
    with pytest.raises(RuntimeError,match='readiness'):m.mission_sequence(e)
    assert not e.calls


def test_sequence_accepts_matching_native_update_and_preserves_dwell_responsibility(fake):
    e,c=fake();m.wait_mission_ready(e)
    row=copy.deepcopy(GOOD['mission_result']);row.update(timestamp=52272000,seq_current=1)
    calls=[]
    def command(*args,**kw):
        calls.append((args,kw));return output('mission_result',row)
    e.command=command
    assert m.mission_sequence(e)==row
    assert calls==[(('listener','mission_result','-n','1'),{'timeout':.25})]
    assert e.pumps[-2:]==[.01,.01]
    count=len(e.events)
    assert m.mission_sequence(e)==row  # Event topic need not advance every read.
    assert len(e.events)==count
    assert not hasattr(e,'dwell')  # The helper never changes scientific dwell.


@pytest.mark.parametrize('key,value',[
    ('mission_id',1),('timestamp',1),('seq_total',4),('seq_current',5),
    ('valid',0),('failure',1)])
def test_sequence_rejects_unrelated_or_invalid_native_rows(fake,key,value):
    e,c=fake();m.wait_mission_ready(e)
    row=copy.deepcopy(GOOD['mission_result']);row[key]=value
    e.command=lambda *a,**kw:output('mission_result',row)
    with pytest.raises(RuntimeError):m.mission_sequence(e)


def test_sequence_rejects_regression_after_valid_update(fake):
    e,c=fake();m.wait_mission_ready(e)
    row=copy.deepcopy(GOOD['mission_result']);row['timestamp']+=100000
    e.command=lambda *a,**kw:output('mission_result',row)
    m.mission_sequence(e);row['timestamp']-=1
    with pytest.raises(RuntimeError,match='stale'):m.mission_sequence(e)


def test_sequence_propagates_safety_and_listener_failures(fake):
    e,c=fake();m.wait_mission_ready(e)
    def fail(*a,**kw):raise RuntimeError('injected safety')
    e.pump=fail
    with pytest.raises(RuntimeError,match='injected safety'):m.mission_sequence(e)
    e,c=fake();m.wait_mission_ready(e);e.command=fail
    with pytest.raises(RuntimeError,match='injected safety'):m.mission_sequence(e)


def test_sequence_parser_requires_actual_seq_current():
    row=copy.deepcopy(GOOD['mission_result']);row.pop('seq_current')
    with pytest.raises(ValueError,match='seq_current'):m.parse_native('mission_result',output('mission_result',row))

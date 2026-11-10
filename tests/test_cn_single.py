import json
import math
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from cn_single.design import hermite, trajectory, global_waypoint, in_gap, budget, SEED

@pytest.mark.parametrize('p0,v0,p1,v1,T',[(0,1,2,0,2),(-2,-.3,3,.4,3),(1,0,1,0,4)])
def test_quintic_boundaries(p0,v0,p1,v1,T):
    assert hermite(p0,v0,p1,v1,T,0)==pytest.approx((p0,v0,0))
    assert hermite(p0,v0,p1,v1,T,T)==pytest.approx((p1,v1,0))

@pytest.mark.parametrize('t',[2,5,8,11,14])
def test_c2_knots(t):
    a=trajectory(t-1e-7,[3,1,-3.2],[.4,1,.1],.5)
    b=trajectory(t+1e-7,[3,1,-3.2],[.4,1,.1],.5)
    for x,y in zip(a[:3],b[:3]):assert x==pytest.approx(y,abs=1e-5)
    assert a[3:]==pytest.approx(b[3:],abs=1e-6)

def test_start_and_final_hold():
    p,v=[3,1,-3.2],[.4,1,.1]
    a=trajectory(0,p,v,.5);assert a[0]==p;assert a[1]==v
    b=trajectory(18,p,v,.5);assert b[:3]==(p,[0]*3,[0]*3);assert b[3:]==pytest.approx((.5,0))

def test_gap_and_budget():
    assert not in_gap(6.999);assert in_gap(7);assert in_gap(7.31999);assert not in_gap(7.32)
    assert budget([3,1,-3.2],[.4,1,.1],.5)['inside']
    assert not budget([9,1,-3.2],[.4,1,.1],.5)['inside']

def test_global_reference():
    assert global_waypoint([0,0,-3],47,8,500)==(470000000,80000000,503)
    a=global_waypoint([3,3,-3.4],47,8,500)
    assert a[0]>470000000 and a[1]>80000000 and a[2]==pytest.approx(503.4)

def test_finite_reference_and_configuration():
    for i in range(1801):
        p,v,a,y,yr=trajectory(i*.01,[3,1,-3.2],[.4,1,.1],.5)
        assert all(math.isfinite(x) for x in p+v+a+[y,yr])
    root=Path(__file__).resolve().parents[1]
    cfg=json.loads((root/'config/cn_single/single.json').read_text());base=json.loads((root/'config/experiment.json').read_text())
    for key in base:
        if key.startswith('safety_'):assert cfg[key]==base[key]
    assert cfg['seed']==SEED and cfg['repetitions']==1

from cn_single.runner import claim, close_experiment, require_neural, upload_packet_valid
from types import SimpleNamespace


def test_duplicate_start_is_never_retry():
    claim([{'event':'BLOCKED_BEFORE_START'}])
    with pytest.raises(RuntimeError):claim([{'event':'START_INTENT'},{'event':'END'}])
    with pytest.raises(RuntimeError):claim([{'event':'START_INTENT'}])


def test_mode_loss_is_failure():
    require_neural({'vehicle_status':SimpleNamespace(nav_state=23),'raptor_status':SimpleNamespace(active=True)},23)
    for nav,active in [(4,True),(23,False),(4,False)]:
        with pytest.raises(RuntimeError):require_neural({'vehicle_status':SimpleNamespace(nav_state=nav),'raptor_status':SimpleNamespace(active=active)},23)


def test_cleanup_exception_remains_terminal_evidence():
    class Fake:
        stream=True
        def cleanup(self):raise OSError('simulated cleanup error')
    e=Fake();assert 'simulated cleanup error' in close_experiment(e);assert e.stream is None
    assert close_experiment(None) is None


@pytest.mark.parametrize('system,component,target,mission,expected',[(22,1,245,0,True),(23,1,245,0,False),(22,2,245,0,False),(22,1,8,0,False),(22,1,245,1,False)])
def test_mission_packet_scope(system,component,target,mission,expected):
    m=SimpleNamespace(get_srcSystem=lambda:system,get_srcComponent=lambda:component,target_system=target,target_component=191,mission_type=mission)
    assert upload_packet_valid(m,22)==expected

from cn_single.analyze import longest_continuous

def test_missing_data_never_counts_as_continuous():
    assert longest_continuous([0,10000,20000,1000000,1010000],[True]*5)==pytest.approx(.02)
    assert longest_continuous([0,10000,20000],[True,False,True])==0
    assert longest_continuous([],[])==0

from cn_single.runner import Experiment

class _Message:
    def __init__(self,typ,seq=0,result=0):self.typ=typ;self.seq=seq;self.type=result
    def get_srcSystem(self):return 22
    def get_srcComponent(self):return 1
    def get_type(self):return self.typ

class _MissionLink:
    def __init__(self,messages):self.messages=iter(messages);self.calls=[];self.mav=self
    def mission_count_send(self,*args):self.calls.append(('count',args))
    def mission_item_int_send(self,*args):self.calls.append(('int',args))
    def mission_item_send(self,*args):self.calls.append(('float',args))
    def recv_match(self,**kw):return next(self.messages,None)

def _upload_experiment():
    e=Experiment.__new__(Experiment);e.instance=21
    e.latest={'vehicle_local_position':SimpleNamespace(xy_global=True,z_global=True,ref_lat=47.,ref_lon=8.,ref_alt=500.)}
    e.pump=lambda *args:None;e.record=[];e.event=lambda event,**kw:e.record.append((event,kw))
    return e

def test_real_mission_protocol_mixed_request_formats():
    e=_upload_experiment();m=_MissionLink([_Message('MISSION_REQUEST_INT' if i%2==0 else 'MISSION_REQUEST',i) for i in range(5)]+[_Message('MISSION_ACK')])
    e.upload_mission(m)
    assert [c[0] for c in m.calls]==['count','int','float','int','float','int']
    assert e.record[-1][0]=='cn_mission_ack'
    assert m.calls[1][1][-1]==503.

@pytest.mark.parametrize('messages',[[ _Message('MISSION_REQUEST_INT',6)],[_Message('MISSION_ACK')],[_Message('MISSION_REQUEST_INT',i) for i in range(5)]+[_Message('MISSION_ACK',result=1)]])
def test_mission_rejection_never_counts_as_uploaded(messages):
    with pytest.raises(RuntimeError):_upload_experiment().upload_mission(_MissionLink(messages))

def test_mission_requires_real_global_reference():
    e=_upload_experiment();e.latest['vehicle_local_position'].xy_global=False
    with pytest.raises(RuntimeError):e.upload_mission(_MissionLink([]))

from cn_single.analyze import classify_task
@pytest.mark.parametrize('tilt,loss,finite,status',[(40,.3,True,'SUCCESS'),(46,.3,True,'FAILURE'),(40,1.1,True,'FAILURE'),(float('nan'),.3,True,'UNKNOWN'),(40,.3,False,'UNKNOWN')])
def test_missing_or_nonfinite_task_evidence_is_never_success(tilt,loss,finite,status):
    assert classify_task({'max_tilt_deg':tilt,'max_altitude_loss_m':loss,'observations_finite':finite})==status

def test_repair_needs_exactly_one_terminated_presubject_attempt(tmp_path,monkeypatch):
    import cn_single.runner as r
    monkeypatch.setattr(r,'ROOT',tmp_path)
    out=tmp_path/'data/cn-single-20261109-flight';out.mkdir(parents=True)
    m={'subject_requests':[],'actual_neural_entries':0,'flight_execution':{'reason':"RuntimeError('owned SITL mission connection not verified')"}}
    (out/'cn-measurement.json').write_text(json.dumps(m))
    with pytest.raises(RuntimeError):r.claim([],True)
    with pytest.raises(RuntimeError):r.claim([{'event':'START_INTENT'}],True)
    r.claim([{'event':'START_INTENT'},{'event':'END'}],True)
    with pytest.raises(RuntimeError):r.claim([{'event':'START_INTENT'},{'event':'END'},{'event':'START_INTENT'}],True)
    m['actual_neural_entries']=1;(out/'cn-measurement.json').write_text(json.dumps(m))
    with pytest.raises(RuntimeError):r.claim([{'event':'START_INTENT'},{'event':'END'}],True)


def test_reuses_verified_udp_peer_for_mission():
    # Real loopback sockets and MAVLink encoding, but no PX4/Gazebo or flight.
    import socket,threading,time
    from pymavlink import mavutil
    server=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);server.bind(('127.0.0.1',0));server.settimeout(.1)
    stop=threading.Event();peers=[]
    encoder=mavutil.mavlink.MAVLink(None,srcSystem=22,srcComponent=1)
    packet=encoder.heartbeat_encode(mavutil.mavlink.MAV_TYPE_QUADROTOR,mavutil.mavlink.MAV_AUTOPILOT_PX4,0,0,0).pack(encoder)
    def service():
        first=None
        while not stop.is_set():
            try:_,peer=server.recvfrom(4096)
            except socket.timeout:continue
            if first is None:first=peer
            peers.append(peer);server.sendto(packet,first)
    worker=threading.Thread(target=service,daemon=True);worker.start()
    link=mavutil.mavlink_connection('udpout:127.0.0.1:'+str(server.getsockname()[1]),source_system=245,source_component=191)
    try:
        link.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_GCS,mavutil.mavlink.MAV_AUTOPILOT_INVALID,0,0,0)
        assert link.recv_match(type='HEARTBEAT',blocking=True,timeout=2).get_srcSystem()==22
        first_port=link.port.getsockname()[1]
        e=_upload_experiment();e.cn_mavlink=link;e.pump=lambda seconds=.01:time.sleep(.001)
        assert e.mav_open() is link
        assert link.port.getsockname()[1]==first_port
        assert len(peers)>=2 and len(set(peers))==1
    finally:link.close();stop.set();worker.join(1);server.close()

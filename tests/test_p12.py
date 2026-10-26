"""P12 offline accounting and dual-clock regressions; no SITL starts."""
from pathlib import Path
import sys,json
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from p12.clock import clock_edges
from p12.run import claim
from p12.execution import step,bound,DTYPE
from p12.state import EventTarget
from p12.state import Controller
from p3_memory import load_policy


def test_plateau_is_retained_not_divided_or_suppressed():
    r=clock_edges([80336000,80344000,80344000,80348000],
        [80336000,80340000,80344000,80348000],[1000000,8886000,9091000,12957000])
    assert r['plateaus']==1 and len(r['exceptions'])==2
    assert r['exceptions'][1]['wall_native_ratio'] is None
    assert r['exceptions'][1]['sample_delta_us']==4000
    assert r['exceptions'][1]['host_delta_ns']==205000
    json.dumps(r,allow_nan=False)


def test_regression_not_mislabelled_plateau():
    r=clock_edges([5,4],[1,2],[10,20])
    assert r['regressions']==1 and r['plateaus']==0


@pytest.mark.parametrize('kind,n',[('development',12),('formal',48)])
def test_caps_count_invalid_starts(kind,n):
    items=[{'event':'START_INTENT','id':str(i),'budget_class':kind} for i in range(n)]
    with pytest.raises(RuntimeError,match='hard'):claim(items,'other',kind)
    with pytest.raises(RuntimeError,match='already'):claim(items,'0',kind)


def test_errors_stop_automatic_continuation():
    with pytest.raises(RuntimeError,match='prior error'):claim([{'event':'STOP'}],'new','development')


def test_singleton_plateau_statistics_are_json_finite():
    r=clock_edges([5,5],[1,2],[10,20])
    assert r['positive_native_wall_ratio_range'] is None
    assert r['plateaus']==1
    json.dumps(r,allow_nan=False)


def test_filter_jump_bound_including_branch_crossing():
    # Analytic proof is in THOR_P12_THEORY; these exercise implementation corners.
    for f,g,u,v in [(400,410,399,420),(0,1000,1000,0),(600,600,600,600),(700,200,0,1000)]:
        assert abs(step(f,u,.004)-step(g,v,.004))<=bound(abs(f-g),abs(u-v),.004)+1e-12
    assert DTYPE.itemsize==152


def test_legacy_motor_header_is_validated_before_execution_comparison(tmp_path):
    from output_chain import read_trace,ROW
    path=tmp_path/'motor-0.bin';row=np.zeros(2,ROW);row['sim_us']=[1000,5000]
    path.write_bytes(b'HOMTRC01'+np.array([ROW.itemsize,0],'<u4').tobytes()+row.tobytes())
    motor,r,trailing=read_trace(path)
    assert motor==0 and trailing==0 and np.array_equal(r['sim_us'],[1000,5000])


def test_repair_activation_is_original_and_later_capture_is_correlated():
    p=np.array([1.,2.,-3.]);v=np.array([1.8,.2,.1]);q=np.array([1.,0,0,0])
    a=EventTarget(False);b=EventTarget(True)
    for t,msg,activation in [(0,None,True),(4000,(p,v,0.),False),(204000,None,False)]:
        ar=a.step(t,t,p,v,q,msg,activation);br=b.step(t,t,p,v,q,msg,activation)
        assert np.array_equal(ar[0],br[0]) and np.array_equal(ar[1],br[1])
    ar=a.step(208000,208000,p,v,q);br=b.step(208000,208000,p,v,q)
    assert np.array_equal(ar[1],np.zeros(3))
    assert np.allclose(br[1][:2],v[:2]) and np.array_equal(ar[0],br[0])


def test_duplicate_can_cross_guard_before_network_rejection():
    initial={'h':[0.]*16,'previous':[0.]*4,'history':[0.]*4,'history_count':0,'call_index':2,'force_sync':2,
        'sample_us':4000,'external_seen':True,'target_p':[0.,0.,-3.],'target_v':[1.,0.,0.],
        'target_yaw':0.,'stale':False,'last_read_us':0}
    # An initially moving external target is valid; only active braking profile unsupported.
    initial['target_v']=[0.,0.,0.]
    c=Controller(initial);h=c.h.copy()
    a,info=c.step(204000,4000,np.array([1.,0.,-3.]),np.array([1.,0,0]),np.array([1.,0,0,0]),np.zeros(3),None,load_policy())
    assert a is None and info['rejected'] and info['stale']
    assert np.array_equal(c.target.r,[1.,0.,-3.]) and np.array_equal(c.h,h) and c.index==2


def native_row(now,read=False,sample=None,mode=0):
    return [100000000+now,100000000+now if sample is None else sample,read,True,mode,0.,1.,1.8,0.,0.,2.,.5,0.,0.]


def test_real_p12_source_keeps_strict_guard_before_duplicate_rejection():
    from p12.native_oracle import Oracle
    o=Oracle()
    try:
        o.tick(native_row(-5000));o.tick(native_row(0,True))
        assert o.tick(native_row(200000))[0]==0
        r=o.tick(native_row(204000,sample=100200000))
        assert r[:4]==[1,1,0,1]
    finally:o.close()


def test_real_p12_repair_does_not_act_at_first_activation():
    from p12.native_oracle import Oracle
    o=Oracle(True)
    try:
        r=o.tick(native_row(0));assert r[8]==0.
        o.tick(native_row(4000,True))
        r=o.tick(native_row(208000));assert abs(r[8]-1.8)<1e-6
    finally:o.close()


def test_real_p12_invalid_message_keeps_native_read_age():
    from p12.native_oracle import Oracle
    o=Oracle()
    try:
        o.tick(native_row(0,True));row=native_row(100000,True);row[10]=float('nan')
        assert o.tick(row)[4]==100000000
        assert o.tick(native_row(204000))[0]==1
    finally:o.close()


def test_common_world_task_epoch_uses_confirmed_native_row(monkeypatch):
    import run_experiment as module
    from types import SimpleNamespace as S
    monkeypatch.setattr(module,'time',S(monotonic=lambda:100.005,monotonic_ns=lambda:100005000000))
    events=[]
    fake=S(cfg={'neural_s':0,'p11':{'event_mask':[]},'p12':{'common_world_reference':
        {'position_ned_m':[0,0,-3],'yaw_rad':1.6755},'native_stream_anchor':True}},
        pcfg={'gaps':{},'end_hold_s':0,'cruise_s':0,'start_offset_m':0,'post_stream_s':0,'return_hold_s':0},checks={},
        native_phase_end_bound=lambda:0,mode=lambda *x:None,wait_raptor_active=lambda:None,
        capture_states=lambda *x:None,hover=lambda *x,**kw:None,raptor_target=lambda:([1,2,-4],.2,'capture'),
        p5_path_check=lambda p:{'inside':True},p5_gap_windows=lambda:[],profile_duration=lambda:0,
        event=lambda name,**kw:events.append((name,kw)),pump=lambda *x:None,
        command=lambda *x:'timestamp: 100000\ntimestamp_sample: 100000\nrun_wall_ns: 100000000000\nlocal_position_sample: 92000\nnative_step: True\n',
        native_bound_streaming=lambda:0,stop_stream=lambda:None)
    def start(origin,yaw,*x,**kw):
        fake.sent_origin=origin;fake.sent_yaw=yaw;fake.stream_t0=None;fake.stream_state={'gaps_log':[]}
    fake.start_stream=start
    module.Experiment.p5_gap_flight(fake,1)
    assert fake.sent_origin==[0.,0.,-3.] and fake.sent_yaw==1.6755
    assert fake.stream_t0==100. and any(n=='p12_confirmed_native_stream_anchor' for n,k in events)


def test_real_source_p12_disabled_preserves_legacy_rtgt2_activation():
    from p12.native_oracle import Oracle
    o=Oracle(enabled=False)
    try:assert abs(o.tick(native_row(0,mode=2))[8]-1.8)<1e-6
    finally:o.close()

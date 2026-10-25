"""A3 tests exercise source branches, initialization and numeric relations."""
from fractions import Fraction as F
import gzip
import importlib.util
import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/p10a3'))
import source as src
from generate import Adapter
spec=importlib.util.spec_from_file_location('a3independent',ROOT/'tools/p10a3/verify.py')
checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)
DATA=ROOT/'data/p10-20261025-a3/source-08'
COMP=ROOT/'data/p10-20261025-a3/compatibility-02/compatibility.json'


def row(us,read=False,sample=None,position=1.,velocity=1.8,mode=0):
    return [100000000+us,100000000+us if sample is None else sample,read,True,mode,0.,position,velocity,0.,0.,2.,.5,0.,0.]


def test_actual_profile_keeps_reposition_tail_and_all_windows():
    r,c=src.runner();tr=r.reposition(0.)[3]
    p,v,a=r.p1_profile(tr-.002)
    assert abs(p-r.pcfg['start_offset_m']-1e-6)<1e-12
    assert abs(v+.001)<1e-12
    assert r.p1_profile(tr)[1]==0
    assert len(r.p5_gap_windows())==3
    assert r.p5_gap_windows()[0][0]==tr+3+1+1
    c.us=0;r.stream();assert r.trajpub.messages[-1].position==[0.,0.,-3.]
    c.us=12000;before=len(r.trajpub.messages);r.stream();assert len(r.trajpub.messages)==before


def test_real_native_read_equality_and_transition_before_duplicate():
    o=src.Oracle();a=Adapter()
    try:
        for rr in [row(-5000),row(0,True),row(200000)]:
            assert o.tick(rr)==a.tick(rr)
        rr=row(204000,sample=100200000,position=3.)
        native=o.tick(rr);proof=a.tick(rr)
        assert native==proof
        assert native[0:4]==[1,1,0,1]  # capture already happened before duplicate rejection
        assert native[7:]==[3.,0.,0.,0.]
    finally:o.close()


def test_invalid_updated_message_does_not_refresh_read_clock():
    o=src.Oracle()
    try:
        o.tick(row(0,True))
        bad=row(100000,True);bad[10]=float('nan')
        x=o.tick(bad);assert x[4]==100000000
        assert x[7:]==[2.,.5,0.,0.]
        out=o.tick(row(204000));assert out[4]==100000000 and out[0]==1
    finally:o.close()


def test_extracted_missing_fresh_branch_reproduces_preserved_failure():
    old=json.loads((ROOT/'data/p10-20261025-a3/source-02/source-snapshot.json').read_text())
    o=src.Oracle(old);a=Adapter()
    try:
        for rr in [row(-5000),row(0,True)]:o.tick(rr);a.tick(rr)
        x=o.tick(row(204000));y=a.tick(row(204000))
        assert x[1]==0 and y[1]==1 and x[7:]!=y[7:]
    finally:o.close()


def test_wrong_ge_guard_changes_source_event_at_equality():
    snap=src.snapshot();snap['guard']=snap['guard'].replace(' > TRAJECTORY_SETPOINT_TIMEOUT',' >= TRAJECTORY_SETPOINT_TIMEOUT')
    o=src.Oracle(snap)
    try:
        o.tick(row(-5000));o.tick(row(0,True))
        x=o.tick(row(200000));assert x[0:2]==[1,1]
    finally:o.close()


def test_real_target_profile_uses_gyro_elapsed_not_hrt_elapsed():
    o=src.Oracle()
    try:
        x=o.tick(row(0,position=1.,velocity=1.8,mode=2))
        y=o.tick(row(4000,sample=100008000,position=9.,velocity=9.,mode=2))
        assert abs(x[8]-1.8)<1e-6
        assert abs(y[8]-(1.8-.016))<1e-6
        assert abs(y[7]-(1.+1.8*.008-.008**2))<1e-6
    finally:o.close()


def test_complete_source_and_exact_nonzero_prefix_refusal():
    a=checker.verify(DATA,COMP);f=a['first_certificate_failure']
    assert a['source_replayed_rows']==7350
    assert a['axis_unsaturated_prefixes_verified']==f['profile_us']//4000
    assert F(f['axis_velocity_error_lower'])>1
    assert F(f['axis_velocity_error_upper'])<F(181,100)
    assert a['certified_axis']==1 and a['actual_startup_bound']==53708000
    assert (f['profile_us'],'CAPTURE') in a['events']
    assert F(a['full_clipped_nominal_max_coordinate_residual'])<F(1,10**10)
    assert F(a['max_difference_rounding_P_upper'])<=F(1,10**8)


@pytest.mark.parametrize('mutation',['invented_history','wrong_nominal_step','independent_capture_generator'])
def test_numeric_mutations_fail_beyond_hash_validation(tmp_path,mutation):
    dest=tmp_path/'input';shutil.copytree(DATA,dest)
    with gzip.open(dest/'trace.jsonl.gz','rt') as f:rows=[json.loads(line) for line in f]
    if mutation=='invented_history':rows[0]['forward_generators'][3][0]=0
    elif mutation=='wrong_nominal_step':rows[100]['q'][0]+=.001
    else:
        i=next(i for i,r in enumerate(rows) if r['oracle'][1])
        rows[i]['forward_error_generators'][0][0]+=10**8
    with gzip.open(dest/'trace.jsonl.gz','wt') as f:
        for r in rows:f.write(json.dumps(r)+'\n')
    m=json.loads((dest/'manifest.json').read_text());m['files']['trace.jsonl.gz']=src.sha(dest/'trace.jsonl.gz')
    (dest/'manifest.json').write_text(json.dumps(m))
    with pytest.raises(AssertionError):checker.verify(dest,COMP)


def test_data_counterexample_recomputes_quaternion_and_delay_innovation():
    d=json.loads(COMP.read_text());values=checker.portable_data_check(d)
    assert values[0]['sample_us']==53800000
    assert F(values[0]['exact_abs_residual_lower'])>F(29,10000)
    d['portable_counterexamples'][0]['q'][0]+=.01
    with pytest.raises(AssertionError):checker.portable_data_check(d)


def test_actual_origin_yaw_and_named_initial_samples_are_not_zeroed():
    startup=src.startup_observation();r,c=src.runner(startup)
    assert startup['state_sample_us']==53708000 and startup['first_confirmed_stream_read_us']==53712000 and startup['profile_native_bound_us']==53716000
    assert startup['local_position_sample_us']==startup['attitude_sample_us']==53704000
    c.us=0;r.stream();m=r.trajpub.messages[-1]
    assert m.position==startup['origin_event']['origin_ned_m']
    assert m.yaw==startup['origin_event']['yaw_rad'] and m.yaw>1.6
    assert startup['velocity_flu'][1]!=0 and startup['q_flu'][1]!=0
    with gzip.open(DATA/'trace.jsonl.gz','rt') as f:first=json.loads(next(f))
    assert first['p']==startup['relative_position_flu'] and first['q']==startup['q_flu']

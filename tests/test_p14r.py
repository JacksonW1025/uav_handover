import sys,json,base64
from pathlib import Path
import numpy as np
import pytest
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'tools'))
B=R/'data/p14r-20261027'
@pytest.fixture
def algebra():
 from p14.affine import A,Context
 from p14r.affine import install
 names=['noise','rounding','__add__','__radd__','__mul__','__rmul__','linear','relu','clip','smooth'];old={n:getattr(A,n) for n in names};install(True)
 yield A,Context
 for n,v in old.items():setattr(A,n,v)

def test_stable_clip_preserves_the_existing_shared_columns(algebra):
 A,C=algebra;c=C();x=c.variable([.1,-.1],.01);y=x.clip(.5);assert np.array_equal(x.c,y.c) and np.array_equal(x.g,y.g)
 z=c.variable([2.,-2.],.01).clip(1);assert max(z.radius())==0

def test_shared_quadratic_and_smooth_enclose_the_declared_real_curve(algebra):
 A,C=algebra;c=C();x=c.variable([.2],.03);c.initial_n=1;y=(x*x).smooth('tanh');lo,hi=y.bounds()
 # Analytic third derivative bound supplies proof; dense points regress code.
 truth=np.tanh(np.linspace(.17,.23,101)**2);assert min(truth)>=lo[0] and max(truth)<=hi[0]
 assert c.monomials and 'shared_quadratic' in c.tags

def test_compression_keeps_the_same_monomial_origin(algebra):
 A,C=algebra;from p14r.affine import compress
 c=C();x=c.variable([.1],.01);c.initial_n=1;y=x*x;new,record=compress({'x':x,'y':y},1,1)
 assert (0,0) in c.monomials
 y2=new['x']*new['x'];d=y2-new['y'];assert max(d.radius())<1e-12

def test_source_output_buffer_snapshot_roundtrip():
 from p14r.op import Op
 doc=json.load(open(B/'source-inputs-v3/d02/input.json'));lib=B/'offline-build-v2/libop.bin';o=Op(lib,doc['initial']['observer']);packet={'fusion_base64':base64.b64encode(o.snapshot()).decode(),'past_operations':[]};z=Op(lib,packet)
 assert np.array_equal(o.fields(),z.fields())
 for k in range(4):
  for p in [o,z]:p.advance(66552000+4000*k,[1e-5,-1e-5,2e-5],[0,0,-.0392])
 assert np.array_equal(o.fields(),z.fields());o.close();z.close()

def test_real_handover_operator_preserves_shared_origins_and_D(algebra):
 A,C=algebra;from p14r.handover import cn,inactive_classic_position_callback
 c=C();p=c.variable([1,2,-3],.01);h=c.variable([.1]*16,.001);u=c.variable([.4]*4,.01);s={'LP':p,'estimated_yaw':c.constant([.3]),'h':h,'f':c.variable([700]*4,1),'D':.9,'failure_latch':True};z=cn(s,u,h)
 assert z['h'] is h and z['previous'] is u and z['reference_p'] is p and z['f'] is s['f'];assert z['D']==.9 and z['failure_latch'] and z['classic_position_reset_pending']
 z=inactive_classic_position_callback(z);assert max(z['classic_velocity_integral'].radius())==0 and not z['classic_position_reset_pending']

def test_exact_point_edge_continuation_has_no_hidden_reset():
 from p14r.model import forecast
 P=dict(np.load(R/'data/p13-20261026-freeze/models/policy.npz'));doc=json.load(open(B/'source-inputs-v3/d02/input.json'));t0=doc['initial']['profile_s'];lib=B/'offline-build-v2/libop.bin';whole=forecast(doc,{},P,limit=t0+.08,observer_library=lib,checkpoint_times=[t0+.04]);cp=whole['checkpoints'][0];nextdoc=dict(doc,initial=cp['initial']);part=forecast(nextdoc,{},P,limit=t0+.08,observer_library=lib);j=10;n=min(len(part['states']),len(whole['states'])-j);assert np.max(abs(part['states'][:n]-whole['states'][j:j+n]))<1e-10;assert cp['initial']['physical_D0_m']>=doc['initial']['physical_D0_m']

def test_publisher_exits_gap_without_waiting_another_period():
 from p14r.delivery import Delivery,Word
 doc=json.load(open(B/'source-inputs-v3/d02/input.json'));d=Delivery(doc,Word());a,b=doc['plan']['windows_profile_s'][0]
 for t in np.arange(doc['initial']['profile_s']+.004,b+.012,.004):d.step(t)
 after=[t for t in d.emissions if t>=b];assert after and after[0]-b<.004001

def test_clock_scope_does_not_claim_spin_timeout_certifies_scheduler():
 from p14r.clock_reach import reach
 doc=json.load(open(B/'source-inputs-v3/d02/input.json'));x=reach(doc);assert not x['conditions']['poll_upper_certified_by_source'];assert x['events'][0]['capture_profile_interval'][0]<x['events'][0]['capture_profile_interval'][1]

def test_four_event_checkpoint_composition_is_marked_nominal():
 d=json.load(open(B/'compose-v2/composition.json'));assert len(d['rows'])==4 and d['all_checkpoint_continuations_close'];assert all('nominal' in r['type'] for r in d['rows']);assert not d['future_actual_used']

def test_quarantined_first_run_is_not_relabelled_valid():
 ledger=[json.loads(s) for s in (B/'attempts.jsonl').read_text().splitlines()];assert len([r for r in ledger if r['event']=='START_INTENT'])<=8;first=[r for r in ledger if r['id']=='p14r-d01-NORMAL-s270101'];assert any(r['event']=='EXECUTION_REVIEW_REQUIRED' for r in first);assert not any(r['event']=='FINISH' for r in first)

def test_fair_joint_seed_membership_has_an_explicit_witness():
 d=json.load(open(B/'B-joint-hulls-v2/summary.json'));assert d['support_count']==66 and d['all_observed_membership_witnessed'];assert all(g['rotor_phase_projection_included'] and g['reconstruction_max_abs']<1e-10 for g in d['groups'])

def test_final_scores_keep_height_unknown_and_both_misses():
 d=json.load(open(B/'registered-score-v1/summary.json'));s=d['summaries']['PRE-phase0.0-jointdelay0.0'];assert d['independent_units']==5;assert s['tilt']['actual_failures']==2 and s['tilt']['danger_miss']==1;assert s['height']['actual_unknown']==1 and s['height']['danger_miss']==1

def test_target_slot_survives_forbidden_read():
 from p14r.affine import install
 # Isolate the global algebra overrides from other regression tests.
 import subprocess
 code="""import sys,json,numpy as np
 sys.path.insert(0,'tools')
 from p14r.affine import install
 install(False)
 from p14r.tube import run
 from p14r.delivery import Delivery,Word
 from p11.models import reference
 doc=json.load(open('data/p14r-20261027/source-inputs-v3/d02/input.json'));i=doc['initial'];i['call_index']=1;i['publisher_last_emit_s']=i['profile_s']-.020;i['publisher_unconsumed_past']=None;P=dict(np.load('data/p13-20261026-freeze/models/policy.npz'));end=i['profile_s']+.008;r,s=run(doc,P,0,end=end,compress_rank=None,group=True);m=reference(i['profile_s']+.004,doc['plan']['profile'],np.array(doc['plan']['profile']['table']));assert max(abs(s['r'].c-np.array(m[0],np.float32)))<1e-10
 """
 subprocess.run([str(R/'uav_lab/.local/venv/bin/python'),'-c','\n'.join(x[1:] if x.startswith(' ') else x for x in code.splitlines())],cwd=R,check=True)

def test_height_reserve_preserves_all_prefixes_and_irreversible_history():
 from p14r.height_constraint import reserve
 L,D=reserve(-.1,.9,-.3,2,.004,100,.00001)
 W=-.3;z=-.1;maximum=.9
 for j in range(101):
  if j:W+=2*.004;z+=W*.004+.00001
  maximum=max(maximum,z)
  assert abs(L[j]-z)<1e-12 and abs(D[j]-maximum)<1e-12
 assert min(D)>=.9 and np.all(np.diff(D)>=0)

def test_initial_joint_inputs_are_past_only_but_explicitly_multirate():
 d=json.load(open(B/'initial-stage-v1/result.json'));assert d['all_pass'] and len(d['rows'])==5
 for r in d['rows']:
  assert r['producer_cutoff_wall_ns']<=r['same_call_end_wall_ns']<r['first_predicted_call_begin_wall_ns']
  assert 'Not a simultaneous' in r['snapshot_scope']

def test_checkpoint_restore_rejects_unvalidated_generic_configuration():
 from p14r.tube import run
 with pytest.raises(NotImplementedError,match='one joint-root'):
  run({}, {},1,restore_region='not-opened')

def test_active_classic_source_fixture_has_nonempty_first_torque_condition():
 x=json.load(open(B/'classic-kernel-v5/result.json'));assert x['integral_condition_feasible']
 assert x['required_integral_max_abs']<.3 and x['external_raw_torque_target_repair_error']<1e-7

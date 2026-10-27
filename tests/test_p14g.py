import sys,json,subprocess
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'tools'));B=R/'data/p14g-20261027'

def test_source_capture_precedes_duplicate_and_invalid_read_does_not_refresh():
 from p14g.partition import State,transition
 s=State(10000,200000,1,1,0,pending=2,latest_generated=5)
 z,e=transition(s,sample=10000,native=204000)
 assert e['capture_before_duplicate'] and z.index==s.index and z.pending==2
 z,e=transition(s,sample=14000,native=204000,publish=3,phase=0,valid=False)
 assert e['read'] and z.last_read==0 and e['capture']

def test_first_read_zones_retain_time_and_reject_early_delivery():
 from p14g.partition import resume_zones,member
 cells=resume_zones(0,.010,.004,[-.001,.007,.015]);assert len(cells)>=2
 for p in np.linspace(0,.01,9):
  for d in p+np.linspace(0,.004,9):
   r=next(r for r in [-.001,.007,.015] if r>=d-1e-13)
   assert any(member(c,p,d,r) for c in cells)
 assert not any(member(c,.003,.002) for c in cells)
 assert not any(member(c,0,.006) for c in cells)

def test_native_platform_and_catchup_do_not_advance_hidden_on_duplicate():
 from p14g.partition import State,transition
 s=State(4000,8000,2,0,0);s,e=transition(s,sample=8000,native=8000);assert e['commit']
 old=s;s,e=transition(s,sample=8000,native=12000);assert e['duplicate_rejected'] and s.index==old.index
 s,e=transition(s,sample=12000,native=12000);assert not e['commit']

def test_adjoint_is_not_a_nonlinear_certificate():
 d=json.load(open(B/'weighted-v4/weights-d02/result.json'));assert d['calls']==192 and d['adjoint_identity_max_abs']<1e-10 and 'nonlinear' in str(d['limitations'])

def test_compression_preserves_support_and_same_origin(tmp_path):
 code='''import sys,json,numpy as np
sys.path.insert(0,'tools')
from p14.affine import A,Context
from p14g.compress import SETTINGS,compress
c=Context();c.n=6;c.tags=['initial']*2+['nonlinear']*4;c.monomials={};g=np.array([[1,.2,.3,.4,.5,.6],[.2,1,.4,.5,.6,.7]])
s={'p':A(c,np.zeros(2),g)};layout={'p':[0,2]};W=np.eye(2)[np.arange(8)%2];np.savez('/tmp/p14g-test-weight.npz',W0=W,W1=W);SETTINGS.update(weights=np.load('/tmp/p14g-test-weight.npz'),layout=layout,call=1)
z,m=compress(s,2,1);assert np.array_equal(z['p'].g[:,:2],g[:,:2]);rng=np.random.default_rng(1)
for v in rng.normal(size=(100,2)):assert np.sum(abs(v@z['p'].g))+1e-12>=np.sum(abs(v@g))
'''
 subprocess.run([str(R/'uav_lab/.local/venv/bin/python'),'-c',code],cwd=R,check=True)

def test_consume_order_guard_is_explicitly_conditional_and_repeats_are_legal():
 from p14g.partition import State,transition
 import pytest
 s=State(0,0,0,0,0,latest_generated=5,consumed=4)
 with pytest.raises(ValueError,match='ordered-single-producer'):
  transition(s,sample=4000,native=4000,consume=3)
 assert transition(s,sample=4000,native=4000,consume=4)[0].consumed==4
 assert transition(s,sample=4000,native=4000,consume=3,component_override=True)[1]['source_component_or_reordered_transport_requires_separate_mode']

def test_full_domain_methods_have_same_cells_and_original_metrics_reproduce():
 x=json.load(open(B/'analysis-v2/summary.json'))
 for v in ['default','none','relations','weighted']:
  g=x['B_groups']['joint-'+v];assert g['completed_attempts']==8 and g['expected_domain_cells']==8 and not g['whole_union_A_hold_resume_completed']
 assert x['max_core_metric_change']==0 and len(x['same_core_metric_checks'])==64
 assert x['B_groups']['zero-default']['horizon_s']==.064 and x['B_groups']['joint-default']['horizon_s']==.8

def test_passive_rich_metrics_preserve_values_columns_and_history():
 from p14.affine import Context
 from p14g.rich_sets import annotate
 c=Context();s={k:c.variable(v,.001) for k,v in {'p':[0,0,-3],'H0':[-3.2],'D':[.3],'lp':[0,0,-2.9],'LP_H0':[-3.1],'DLP':[.4],'q':[1,0,0,0],'att':[1,0,0,0]}.items()};n=c.n;before={k:(v.c.copy(),v.g.copy()) for k,v in s.items()};r=annotate(s,{})
 assert c.n==n
 for k,v in s.items():assert np.array_equal(v.c,before[k][0]) and np.array_equal(v.g,before[k][1])
 assert r['COM_D_lower_m']>r['COM_L_interval_m'][1] and r['LP_D_lower_m']>r['LP_L_interval_m'][1]

def test_capture_on_duplicate_does_not_reset_neural_or_action_history():
 from p14_motion.core import Ctl
 d=json.load(open(B/'inputs-v1/d02/input.json'));i=d['initial'];ctl=Ctl(i,d['plan']);ctl.target.last_read=i['native_us']-204000;ctl.target.stale=False;before=[x.copy() for x in [ctl.h,ctl.previous,ctl.mean]];count,index=ctl.count,ctl.index
 a,info=ctl.step(i['native_us']+4000,i['sample_us'],np.array(i['position']),np.array(i['velocity']),np.array(i['attitude']),np.array(i['omega']),None,{})
 assert a is None and info['rejected'] and info['stale'] and ctl.count==count and ctl.index==index
 for x,y in zip([ctl.h,ctl.previous,ctl.mean],before):assert np.array_equal(x,y)


def test_new_fading_state_checkpoint_keeps_queue_history_and_D():
 d=json.load(open(B/'validation-state-v1/result.json'));assert max(d['max_difference'].values())<1e-9 and d['original_innovation_reference_retained'] and d['preserved_D']>0 and d['preserved_LP_D']>0


def test_corrected_pool_is_uniform_permutation_with_canonical_aliases():
 d=json.load(open(B/'D-baseline-v4/ranking/ranking.json'));ids={r['id'] for r in d['rows']};assert len(ids)==29
 for values in d['rankings'].values():assert len(values)==29 and set(values)==ids
 old=json.load(open(B/'D-v2/ranking/ranking.json'));assert d['rankings']['set_separation']==old['rankings']['set_separation']
 assert d['rankings']['uniform']!=old['rankings']['uniform'] and 'post-exposure' in d['exposure']


def test_actual_coverage_withdrawn_without_hiding_point_misses():
 w=json.load(open(B/'analysis-v1/withdrawal-ledger.json'));assert len(w)==5 and all(r['actual_safety_status']=='UNKNOWN_PREMISE_REJECTED' for r in w)
 c=json.load(open(B/'C-score-v1/summary.json'))['summaries']['fading-PRE-0.0-0.0'];assert c['tilt']['miss']==1 and c['height']['miss']==1 and c['height']['actual_unknown']==1 and c['tilt']['prediction_UNKNOWN']==0


def test_selector_sandbox_and_inputs_are_separate_from_actual_labels():
 d=json.load(open(B/'D-v1/isolation.json'));assert d['rc']==0 and d['actual_future_hidden']
 d=json.load(open(B/'D-baseline-v3/isolation.json'));assert d['rc']==0 and d['future_hidden']
 r=json.load(open(B/'D-v2/ranking/ranking.json'));assert all(not x['actual_future_used'] for x in r['rows']) and all(x['full_feature_window'] for r in r['rows'] for v in r['model_details'].values() for x in v)


def test_source_commonmode_proof_is_not_fullflight_certificate():
 d=json.load(open(B/'C-PI-proof.json'));g=d['numeric_g'];assert 0<g<=1 and .1*g*g>0 and 4-2*g-.1*g*g>0
 r=json.load(open(B/'C-source-transfer-v1/result.json'));assert r['source_Cpp_velocity_probe_max_abs']<1e-6 and any('EKF' in x for x in d['not_certified'])


def test_no_launcher_imports_or_new_run_directory():
 import ast
 for p in (R/'tools/p14g').glob('*.py'):
  t=ast.parse(p.read_text());names=[n.module or '' for n in ast.walk(t) if isinstance(n,ast.ImportFrom)]+[a.name for n in ast.walk(t) if isinstance(n,ast.Import) for a in n.names]
  assert not any(any(s in n.split('.') for s in ['campaign','run_experiment']) for n in names)
 assert not (B/'runs').exists()

def test_poststate_adjoint_uses_current_output_and_future_feedback():
 from p14g.weights import backward_importance
 J=[np.array([[2.]]),np.array([[.5]])];F=[np.array([[3.]]),np.array([[4.]])];Z,W=backward_importance(J,F,np.array([[5.]]))
 # Independentforward: x1=2,x2=1, outputs3*x1+4*x2+5*x2=15.
 assert Z[0][0,0]==15 and W[1][0,0]==7.5 and W[2][0,0]==9
 # The historical misplaced Cpost-onpre formula gives16, so thisregressionfailsit.
 assert Z[0][0,0] != (3+(4+5*.5)*2)


def test_corrected_weighting_rechecks_every_same_domain_job():
 d=json.load(open(B/'analysis-v2/summary.json'));assert d['weighted_fix_complete_jobs']==10
 for p in ['zero','small','joint']:assert d['B_groups'][p+'-weighted']['corrected_phase_semantics']
 e=json.load(open(B/'weighted-v4/execution.json'));assert e['CPU_s_exact']<=240

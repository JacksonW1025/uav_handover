import sys,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'tools'));B=R/'data/p14h-20261027'

def test_boundary_choice_is_common_before_after_and_has_actual_lead():
 from p14h.runner import choose_boundary
 for since in [100_000,4_000_000,7_900_000,12_000_000]:
  wall=1_000_000_000;before=choose_boundary(wall,wall+since,10,'BEFORE');after=choose_boundary(wall,wall+since,10,'AFTER')
  assert before[:2]==after[:2] and before[2]>=wall+since+500_000
  assert before[2]<before[0]<after[2] and after[1]>10

def test_passive_snapshot_prefix_survives_overflow_and_abnormal_exit():
 from p14h.snapshot import read
 for name in ['normal','abnormal']:
  a,h=read(B/'buffer-host-v2'/name/'ekf-p14h.bin');assert h['count']==3 and h['dropped']==2 and h['complete']==0
  assert np.array_equal(a['sequence'],[0,1,2]) and a['ndof'][0]==24

def test_full_covariance_not_silently_replaced_by_diagonal():
 a=json.load(open(B/'recovery-audit-v1/result.json'));assert len(a['rows'])==5 and all(not r['complete_P_recorded'] for r in a['rows']);assert all(r['first_recorded_OP_fusion_native']<r['ULog_start_native'] for r in a['rows'])

def test_source_model_default_preserves_old_held_point_prediction():
 jobs=json.load(open(B/'offline-v2/jobs.json'))
 for n,j in enumerate(jobs):
  if j['axis']!='base':continue
  new=np.load(B/'offline-v2'/f'{n:03d}/result/trace.npz');old=np.load(R/'data/p14g-20261027/C-v2/predictions'/j['case']/'held.npz')
  assert np.array_equal(new['trace'],old['trace']) and np.array_equal(new['states'],old['states'])

def test_inflight_bookkeeping_caps_do_not_borrow_old_budget():
 p=json.load(open(R/'config/p14h/protocol-v1.json'));assert p['budget']=={'mechanism_START_INTENT':4,'independent_START_INTENT':12,'total_START_INTENT':16,'no_transfers':True}
 plan=json.load(open(B/'mechanism-plan-v1/plan.json'));assert len(plan['rows'])==4 and len({r['id'] for r in plan['rows']})==4



def test_scoped_audit_keeps_old_failure_and_safe_truncated_tail():
 d=json.load(open(B/'runs/p14h-d02-F4-A-after-s142710202/neural-scope-v3/result.json'))
 assert d['original_full_run_status']=='FAIL' and d['old_fullrun_count']['source_missed_total']==8
 assert d['status']=='PASS_FOR_NEURAL_SCOPE' and d['active_counter_increment']['source_missed_total']==0
 assert d['ULog_censored_tail_unscored_direct_calls']==5 and d['measurement']['censored']
 assert d['measurement']['task_outcome']=='FAILURE' and all(d['tests'].values())


def test_resource_reserves_open_begin_and_exec_enforces_limit(tmp_path,monkeypatch):
 import p14h.common as c,pytest,subprocess
 monkeypatch.setattr(c,'B',tmp_path);(tmp_path/'resource-transition-v2.json').write_text(json.dumps({'legacy_charged_CPU_s':0}))
 c._reserve('open-heavy',13000,[], 'testtemporaryonly')
 with pytest.raises(AssertionError):c._reserve('would-overbook',1000,[], 'testtemporaryonly')
 out=subprocess.check_output([str(c.PY),str(R/'tools/p14h/guard.py'),'1','2',str(c.PY),'-c','import resource;print(resource.getrlimit(resource.RLIMIT_CPU)[1],resource.getrlimit(resource.RLIMIT_AS)[1])'],text=True)
 assert out.split()==['1',str(2*1024**3)]

def test_source_cadence_recovery_is_fusion_start_membership_not_full_EKF():
 r=json.load(open(B/'cadence-recovery-v2/result.json'))
 assert r['all_finite_prefixes_match'] and len(r['rows'])==4
 assert all(not x['actual_not_predicted'] and not x['predicted_no_completed_fusion_except_current'] for x in r['rows'])
 assert [x['current_callback_pending_fusion'] for x in r['rows']]==[False,False,False,True]
 # The source audit reads FUSION_PRE kind3. Old misleading completed labels
 # remain in the historical output; metadata/report separately correct them.
 source=(R/'tools/p14h/recover_cadence.py').read_text();assert "['kind']==3" in source

def test_initial_cache_stamps_and_source_cadence_are_separate_states():
 from p14h.causal_observer import Observer
 lib=B/'cadence-recovery-v2/cadence.bin';op=R/'data/p14r-20261027/offline-build-v2/libop.bin'
 import shutil,tempfile
 with tempfile.TemporaryDirectory() as t:
  dst=Path(t)/'libop.bin';shutil.copyfile(op,dst);shutil.copyfile(lib,Path(t)/'cadence.bin')
  for n,lp_age,att_age in [(1,4000,4000),(2,16000,16000),(3,4000,0),(4,12000,8000)]:
   i=json.load(open(B/f'cadence-recovery-v2/d{n:02d}/input.json'))['initial'];o=Observer(i,dst)
   assert i['sample_us']-o.lp_sample==lp_age and i['sample_us']-o.att_sample==att_age
   assert o.cadence.dump()==i['p14h_schedule_model']['cadence_state'];assert o.imu_times==i['p14h_schedule_model']['downsampled_time_queue'];o.close()

def test_true_AB_point_checkpoint_keeps_joint_history_and_failure_memory(tmp_path):
 from p14h.selection import apply_parameters
 from p14h.model import forecast
 import shutil,copy
 shutil.copyfile(R/'data/p14r-20261027/offline-build-v2/libop.bin',tmp_path/'libop.bin');shutil.copyfile(B/'cadence-recovery-v2/cadence.bin',tmp_path/'cadence.bin')
 d=apply_parameters(json.load(open(B/'cadence-recovery-v2/d01/input.json')),.36,.85,'BEFORE');a=d['plan']['windows_profile_s'][0][0];P=dict(np.load(R/'data/p13-20261026-freeze/models/policy.npz'));d['plan']['horizon_profile_s']=a+2.2
 f=forecast(d,{},P,observer_library=tmp_path/'libop.bin',checkpoint_times=[a+.8]);cp=f['checkpoints'][0];e=copy.deepcopy(d);e['initial']=cp['initial'];g=forecast(e,{},P,observer_library=tmp_path/'libop.bin');k=int(round((cp['actual_time']-d['initial']['profile_s'])/.004))
 assert np.allclose(g['trace'],f['trace'][k:],rtol=0,atol=1e-10,equal_nan=True)
 assert np.allclose(g['states'],f['states'][k:],rtol=0,atol=1e-10)
 assert cp['D_not_reset'] and cp['initial']['physical_D0_m']>=d['initial'].get('physical_D0_m',0)
 assert 'controller_live' in cp['initial'] and 'delivery_live' in cp['initial'] and 'p14h_producer_live' in cp['initial']
 bs=d['plan']['windows_profile_s'][1][0];assert any(x['capture'] and x['sample_us']>d['initial']['sample_us']+int((bs-d['initial']['profile_s'])*1e6) for x in f['branches'])

def test_search_rules_keep_equal_domain_and_shared_units_explicit():
 r=json.load(open(B/'selection-v3/rules.json'));assert len(r['pool'])==18 and len(r['initial_ensemble'])==4
 assert len(r['seeds'])==4 and r['execution_budget_per_method']==4
 assert set(r['methods'])=={'random','continuous','branch'}
 assert 'full initial-set' in r['initial_coverage'] and r['all_prior_exposed']

def test_unknown_censored_scoring_does_not_hide_mechanism_tilt_miss():
 r=json.load(open(B/'response-score-v1/risk.json'))['rows']
 for case in r:
  for x in case['models'].values():
   if case['case'] in [2,4]:assert x['observed']['height']=='UNKNOWN' and not x['classification_eligible']['height']
   if case['case']==4:assert x['comparisons']['tilt']=='DANGER_MISS'


def test_terminal_endpoint_analysis_keeps_original_fail_and_exact_source_identity():
 r=json.load(open(B/'terminal-audit-revision-v1/all-affected.json'));row=next(x for x in r['rows'] if x['id'].startswith('p14h-e11-'))
 assert row['original_status']=='DATA_QUARANTINE' and row['original_FAIL_retained']
 assert row['terminal_sample_equal'] and row['terminal_source_before_consumer']
 assert row['source_completed_before_read_ns']==25150 and row['exact_sample_not_time_tolerance']
 assert row['last_source_sample_us']==row['last_control_sample_us']==68432000

def test_initial_completed_row_availability_is_interval_and_before_event():
 r=json.load(open(B/'timing-window-audit-v2/result.json'));assert len(r['rows'])==16
 assert r['strict_Runstart_cut_claim'].startswith('WITHDRAWN')
 for x in r['rows']:
  assert x['all_controller_row_fields_available_before_A'] and x['initial_end_before_next_forecasted_control']
  assert x['initial_origin_interval_ns'][0]<x['initial_information_upper_cycleend_ns']
 assert sum(x['actual_attitude_post_inside_window'] for x in r['rows'])==65

def test_all_starts_have_unique_identities_and_no_remaining_budget():
 a=[json.loads(l) for l in (B/'attempts.jsonl').read_text().splitlines()];s=[x for x in a if x['event']=='START_INTENT'];assert len(s)==len({x['id'] for x in s})==16
 assert sum(x['budget_class']=='mechanism' for x in s)==4 and sum(x['budget_class']=='independent' for x in s)==12
 assert json.load(open(B/'independent-execution-v2/complete.json'))['status']=='FINISHED'

def test_known_timestamp_replacements_never_become_autonomous_predictions():
 rows=[json.load(open(p)) for p in (B/'producer-diagnostic-v2').glob('d*-*/result/result.json')];assert len(rows)==8
 assert sum(x['status']=='DIAGNOSTIC_UNCLOSED' for x in rows)==4
 assert all(x['not_in_autonomous_scores'] for x in rows)
 r=json.load(open(B/'counterfactual-response-v1/result.json'));assert len(r['rows'])==8 and r['future_data_hidden']
 assert all(x['no_real_same_initial_counterfactual'] for x in r['rows'])

def test_independent_scores_keep_height_censoring_and_misses_visible():
 r=json.load(open(B/'delivery-v1/classification.json'))
 for m in ['held','source-queue']:
  assert r[m]['height']['observed_FAILURE']==6 and r[m]['height']['UNKNOWN']==6 and r[m]['height']['DANGER_MISS']==3
  assert r[m]['tilt']['DANGER_MISS']==0 and r[m]['tilt']['FALSE_ALARM']==1
  assert r[m]['task']['DANGER_MISS']==1 and r[m]['task']['N']==12

def test_actual_AB_storage_extension_is_full_prefix_linear_only():
 r=json.load(open(B/'AB-storage-v2/d02/result/result.json'))
 assert r['actual_AB'] and r['calls']==490 and r['requested_horizon_s']==1.96
 assert r['forward_backward_energy_absolute_error']<1e-18
 assert r['PSD_semidefinite_not_full_state_norm'] and 'not certified' in r['nonlinear_error_relation']
 assert r['first_source_domain_loss'] is None

def test_search_extrapolation_limit_and_saturated_pool_are_not_hidden():
 r=json.load(open(B/'selection-v3/selection.json'));assert len(r['validation'])==16
 assert all(x['valid_same_branch'] for x in r['validation'])
 assert not any(x['branches_at_validation_equal'] for x in r['validation'])
 m=json.load(open(B/'delivery-v1/methods.json'))['methods'];assert all(x['N']==x['task_failures']==4 for x in m.values())

def test_full_forward_risk_never_erases_common_prefix_height_misses():
 rows=json.load(open(B/'risk-scope-v1/result.json'))['rows'];assert len(rows)==12
 assert sum(r['models']['source-queue']['old_common_window_risk']['comparisons']['height']=='DANGER_MISS' for r in rows)==3
 assert sum(r['models']['source-queue']['full_forward_risk']['comparisons']['height']=='DANGER_MISS' for r in rows)==1
 delays=[r['models']['source-queue']['delay_intervals_s']['height'] for r in rows];delays=[x for x in delays if x is not None];assert len(delays)==5 and all(x[0]>0 for x in delays)

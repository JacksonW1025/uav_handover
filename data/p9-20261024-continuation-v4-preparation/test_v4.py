import copy,json,shutil,sys,subprocess
from pathlib import Path
import numpy as np
import pytest
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(HERE));sys.path.insert(0,str(ROOT/'data/p9-20261024-continuation-v3-preparation'));sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(ROOT/'data/p9-20261024-continuation-v2-preparation'))
import opportunity_v3 as o
import run_v4 as r
import p7_batch,p7_metrics
from measurement_v2 import analyze as measure
from p9_model import write

@pytest.fixture(autouse=True)
def forbid_flight(monkeypatch):
 original=subprocess.run
 def guarded(cmd,*args,**kw):
  parts=[str(x) for x in cmd] if not isinstance(cmd,str) else [cmd]
  if len(parts)>1 and parts[1]==str(ROOT/'tools/p7_metrics.py'):return original(cmd,*args,**kw)
  raise AssertionError('No-flight test forbids command '+str(parts[:2]))
 monkeypatch.setattr(subprocess,'run',guarded)
 monkeypatch.setattr(p7_batch.p2_batch,'run_one',lambda *a:(_ for _ in ()).throw(AssertionError('SITL forbidden')))

def checks():return {k:True for k in ['px4_exit','no_crash_markers','trace','output_chain','p9_measured','p9_reconstruction','remote_disconnected','candidate_unchanged','p7_measured','execution','subject_measured']}
def proof():return dict(rate=1.,recovery_rows=0,eligible_resumes=0,legacy_verified=False,**{k:True for k in ['safety_abort','native_open_anchor_valid','active_stale_coverage','memory_coverage','parameters_match','capture_profile_match','no_log_dropout','no_resume','activation_observed']})
def gate_fixture(e,arm='P9-R',extra=None):
 rate=0. if arm in ['P9-Z','P9-C'] else 1.;e=dict(e,rate=rate);problems=[]
 # Real frozen P7 recovery branch participates in each matrix case.
 cfg={'p2_treatment_parameters':{'rrec':rate},'p7':{'recovery':{}}}
 T={'research_recovery':{'timestamp':np.arange(e.get('recovery_rows',0))}} if rate<=0 and e.get('recovery_rows',0)>0 else {}
 b=p7_metrics.recovery_block(Path('/not-used'),cfg,{'gaps':[]},T,problems)
 if extra:problems.append(extra)
 base={'status':'INCOMPLETE' if problems else 'MEASURED','problems':problems,'p7':{'recovery':b}}
 c=checks();c['p7_measured']=not problems;c['execution']=False;c['subject_measured']=False
 row={'checks':c,'flight_outcome':'FAILURE'};m={'kind':'OPEN_GAP_CENSORED','measurement':{'status':'MEASURED','recoveries':[],'final_task_cost_outcome':'UNOBSERVED_FINAL_RESUME'}}
 state=o.classify(e);return row,m,{'state':state,'evidence':e},base

@pytest.mark.parametrize('arm',['P9-Z','P9-C','P9-R','P9-CR'])
def test_first_open_joint_P7_measurement_runner(arm):
 args=gate_fixture(proof(),arm);before=copy.deepcopy(args[0]);v=o.decide(*args)
 assert v['evidence_admissible'] and v['observed_flight_failure'];assert args[0]==before
 assert v['exception_not_reached']==(arm in ['P9-R','P9-CR'])
 assert args[1]['measurement']['recoveries']==[]

@pytest.mark.parametrize('field',['safety_abort','native_open_anchor_valid','active_stale_coverage','memory_coverage','parameters_match','capture_profile_match','no_log_dropout','no_resume','activation_observed'])
@pytest.mark.parametrize('arm',['P9-R','P9-CR'])
def test_missing_or_wrong_native_evidence_joint_chain(field,arm):
 e=proof();e[field]=False;args=gate_fixture(e,arm);assert args[2]['state']=='UNKNOWN';assert not o.decide(*args)['evidence_admissible']

@pytest.mark.parametrize('tail,state',[(True,'REACHED_UNVERIFIED'),(False,'UNKNOWN')])
@pytest.mark.parametrize('arm',['P9-R','P9-CR'])
def test_resume_missing_topic_and_short_tail(arm,tail,state):
 e=proof();e.update(eligible_resumes=1,resume_tail_complete=tail);args=gate_fixture(e,arm);assert args[2]['state']==state;assert not o.decide(*args)['evidence_admissible']

def test_later_open_cannot_erase_earlier_recovery_obligation():
 e=proof();e.update(eligible_resumes=2,resume_tail_complete=True);args=gate_fixture(e);assert not o.decide(*args)['evidence_admissible']

def test_other_P7_problem_or_physical_failure_never_exempted():
 assert not o.decide(*gate_fixture(proof(),extra='wrong treatment'))['evidence_admissible']
 for key in checks():
  if key in ['p7_measured','execution','subject_measured']:continue
  args=gate_fixture(proof());args[0]['checks'][key]=False;v=o.decide(*args);assert not v['evidence_admissible'] and v['observed_flight_failure']
 args=gate_fixture(proof());args[1]['measurement']=None;assert not o.decide(*args)['evidence_admissible']

def test_Z_C_disabled_unexpected_recovery_rows_and_missing_field():
 for arm in ['P9-Z','P9-C']:
  e=proof();e.update(recovery_rows=1);args=gate_fixture(e,arm);args[0]['checks']['p7_measured']=False;assert args[2]['state']=='REACHED_UNVERIFIED' and not o.decide(*args)['evidence_admissible']
 args=gate_fixture(proof());del args[0]['checks']['output_chain'];assert not o.decide(*args)['evidence_admissible']

@pytest.mark.parametrize('arm',['P9-Z','P9-C','P9-R','P9-CR','OPEN_R164'])
def test_real_raw_P7_batch_then_actual_new_runner_helpers(tmp_path,monkeypatch,arm):
 if arm=='OPEN_R164':batch='data/p9-20261024-continuation-v2-formal';rid='D-07-P9-R'
 else:batch='data/p9-20261024-continuation-v1-formal';rid='D-01-'+arm
 source=ROOT/batch/rid;orig=json.loads((source/'result.json').read_text());attempt=tmp_path/rid;run=attempt/'run';run.mkdir(parents=True)
 for p in (source/'run').iterdir():
  if p.is_file() and (p.suffix=='.json' or p.name=='events.jsonl'):shutil.copy2(p,run/p.name)
 (run/'flight.ulg').symlink_to(source/'run/flight.ulg')
 row=copy.deepcopy(orig);row['directory']=str(run);row['config']='config/p9.json'
 def no_flight(row,out):
  row['checks']={k:v for k,v in orig['checks'].items() if k not in ['p7_measured','subject_measured','p9_measured','p9_reconstruction']}
 monkeypatch.setattr(p7_batch.p2_batch,'run_one',no_flight)
 p7_batch.run_row(row,attempt) # real P7 CLI, real raw ULog, only temporary outputs
 saved=(run/'p7-metrics.json').read_bytes()
 r.measure_row(row,attempt,ROOT) # actual measurement/export/opportunity helper
 gate=r.decide_row(row,attempt) # actual production helper
 assert gate['evidence_admissible'];assert (run/'p7-metrics.json').read_bytes()==saved
 assert gate['exception_not_reached']==(arm=='OPEN_R164')
 if arm=='OPEN_R164':assert row['checks']['p7_measured'] is False and gate['observed_flight_failure']

@pytest.mark.parametrize('end',[None,1,2,3])
def test_actual_P7_START_END_semantics_no_vehicle_recovery(end):
 n=1 if end is None else 2
 rec={'timestamp':np.full(n,1000000),'timestamp_sample':np.full(n,1000000),'kind':np.array([1] if n==1 else [1,3]),'end_reason':np.array([0] if n==1 else [0,end]),'rate':np.ones(n),'limited':np.zeros(n),'position_difference':np.zeros(n),'velocity_difference':np.zeros(n)}
 for field in ['target_position','target_velocity','vehicle_position','vehicle_velocity','setpoint_position','setpoint_velocity']:
  for k in range(3):rec[f'{field}[{k}]']=np.zeros(n)
 T={'research_recovery':rec,'research_timing':{'timestamp_sample':np.array([1000000]),'local_position_sample':np.array([1000000])},'vehicle_local_position':{'timestamp_sample':np.array([1000000]),**{k:np.zeros(1) for k in ['x','y','z','vx','vy']}}}
 cfg={'p2_treatment_parameters':{'rrec':1},'p2_profile':{'motion_axis_ned':[1,0,0]},'p7':{'recovery':{'omega_rad_s':1.5,'max_dt_s':.05,'exit_position_m':.02,'exit_velocity_m_s':.02}}}
 base={'gaps':[{'index':0,'first_reception_px4_us':1000000}],'aborted':True};problems=[]
 block=p7_metrics.recovery_block(Path('/unused'),cfg,base,T,problems)
 assert not problems
 item=block['recoveries'][0]
 assert (item['catch_up_s']==0.) if end==1 else (item['catch_up_s'] is None)
 if end is None:assert item['end'] is None
 args=list(gate_fixture(proof()));args[0]['checks']['p7_measured']=True;args[2]={'state':'REACHED_VERIFIED','evidence':dict(proof(),legacy_verified=True,eligible_resumes=1)};args[3]={'status':'MEASURED','problems':[]}
 assert o.decide(*args)['evidence_admissible']
 assert args[1]['measurement']['recoveries']==[] # virtual END never fills P9 vehicle recovery

def setup_transaction(tmp_path,monkeypatch):
 fake=tmp_path/'root';fake.mkdir();freeze=fake/'freeze';freeze.mkdir();out=fake/'out';out.mkdir();prep=fake/'prep';prep.mkdir()
 plan=json.loads((ROOT/'data/p9-20261024-continuation-v4-freeze/plan.json').read_text());write(freeze/'plan.json',plan)
 (fake/'data/p9-20261024-continuation-v4-freeze').mkdir(parents=True);write(fake/'data/p9-20261024-continuation-v4-freeze/plan.json',plan)
 (fake/'data/p9-20261024-freeze').mkdir(parents=True);shutil.copy2(ROOT/'data/p9-20261024-freeze/predictions.json',fake/'data/p9-20261024-freeze/predictions.json');shutil.copy2(ROOT/'data/p9-20261024-freeze/model.json',freeze/'model.json');write(freeze/'manifest.json',{})
 (prep/'attempts.jsonl').write_bytes((ROOT/'data/p9-20261024-continuation-v4-freeze/prior-ledger.jsonl').read_bytes())
 monkeypatch.setattr(r,'ROOT',fake);monkeypatch.setattr(r,'verify_freeze',lambda f:None);monkeypatch.setattr(r.p2_batch,'identity',lambda:{});monkeypatch.setattr(r,'host_gate',lambda:{'remote_desktop_session_running':False});monkeypatch.setattr(r.p2_batch,'host_state',lambda:{'remote_desktop_session_running':False});monkeypatch.setattr(r,'storage_gate',lambda *a:{})
 order=[];actual_append=r.append
 def append(path,item):
  if item['event']=='START_INTENT':assert (fake/item['output']/'prediction-before-query.json').exists()
  if item['event']=='FINISH':assert (out/item['id']/'result.json').exists()
  order.append(item['event']);actual_append(path,item)
 monkeypatch.setattr(r,'append',append)
 def fly(row,attempt):
  assert order[-1]=='START_INTENT';order.append('EXECUTION_FIXTURE');(attempt/'run').mkdir();row.update(checks=checks(),status='PASS',flight_outcome='SUCCESS')
 def meas(row,attempt,out):
  row['p9']={'status':'MEASURED','max_tilt_deg':1.};row['measurement_kind']='ORIGINAL_COMPATIBLE';row['opportunity_v3']={'state':'NOT_REACHED','evidence':{'rate':0.}}
  write(attempt/'run/p9-v2-assessment.json',{'kind':'ORIGINAL_COMPATIBLE','measurement':row['p9']});write(attempt/'run/p7-metrics.json',{'status':'MEASURED','problems':[]})
 monkeypatch.setattr(r.p7_batch,'run_row',fly);monkeypatch.setattr(r,'measure_row',meas)
 return plan['runs'][0],json.loads((ROOT/'config/p9.json').read_text()),json.loads((ROOT/'data/p9-20261024-freeze/model.json').read_text()),prep,out,freeze,order

def test_actual_execute_order_ledger_and_duplicate(tmp_path,monkeypatch):
 row,cfg,model,prep,out,f,order=setup_transaction(tmp_path,monkeypatch)
 result=r.execute_one(row,cfg,model,prep,out,{},f);assert result['admissible_v3'];assert order==['START_INTENT','EXECUTION_FIXTURE','FINISH']
 with pytest.raises(RuntimeError,match='already attempted'):r.execute_one(row,cfg,model,prep,out,{},f)

def test_actual_execute_failure_stops_and_still_counts(tmp_path,monkeypatch):
 row,cfg,model,prep,out,f,order=setup_transaction(tmp_path,monkeypatch)
 def fail(*a):raise RuntimeError('fixture process disappeared')
 monkeypatch.setattr(r.p7_batch,'run_row',fail)
 with pytest.raises(RuntimeError,match='disappeared'):r.execute_one(row,cfg,model,prep,out,{},f)
 assert order==['START_INTENT','INTERRUPTED_OR_EXCEPTION']
 with pytest.raises(RuntimeError,match='already attempted'):r.execute_one(row,cfg,model,prep,out,{},f)

def test_actual_unknown_measurement_stop_no_false_FINISH(tmp_path,monkeypatch):
 row,cfg,model,prep,out,f,order=setup_transaction(tmp_path,monkeypatch)
 monkeypatch.setattr(r,'measure_row',lambda *a:(_ for _ in ()).throw(RuntimeError('UNMEASURABLE missing logs')))
 with pytest.raises(RuntimeError,match='UNMEASURABLE'):r.execute_one(row,cfg,model,prep,out,{},f)
 assert order[-1]=='INTERRUPTED_OR_EXCEPTION' and 'FINISH' not in order

def test_actual_duplicate_directory_cap_and_original_slots(tmp_path,monkeypatch):
 row,cfg,model,prep,out,f,order=setup_transaction(tmp_path,monkeypatch);(out/row['id']).mkdir()
 with pytest.raises(RuntimeError,match='existing attempt'):r.execute_one(row,cfg,model,prep,out,{},f)
 assert not order
 L=[json.loads(x) for x in (prep/'attempts.jsonl').read_text().splitlines()]
 for rid in ['C-CZ15-g0.1-reference-P9-Z','D-07-P9-Z','D-07-P9-R']:
  with pytest.raises(RuntimeError,match='already attempted'):r.claim_continuation(L,{'id':rid})
 for i in range(4):L.append({'event':'START_INTENT','id':'future'+str(i),'budget_class':'formal'})
 with pytest.raises(RuntimeError):r.claim_continuation(L,row)
 bad=copy.deepcopy(row);bad['case']['heading_deg']=91
 with pytest.raises(RuntimeError):r.execute_one(bad,cfg,model,prep,out,{},f)
 assert not order

def test_real_CR_truncated_capture_profile_and_bad_trajectory():
 from pyulog import ULog
 source=ROOT/'data/p9-20261024-continuation-v1-formal/D-01-P9-CR/run'
 u=ULog(str(source/'flight.ulg'),['research_target']);tg=next(d.data for d in u.data_list if d.name=='research_target')
 start=json.loads((source/'p7-metrics.json').read_text())['times_px4_us']['profile_start']
 cap=int(tg['timestamp'][(tg['kind']==o.T_CAPTURE)&(tg['activation']==0)&(tg['timestamp']>start)][0]);tp=json.loads((source/'config.json').read_text())['p2_treatment_parameters']
 good,diag=o.profile_check(tg,cap,cap+40000,tp);assert good and diag['profile_max_position_error']<=1e-4
 broken={k:np.copy(v) for k,v in tg.items()};idx=np.flatnonzero((broken['kind']==o.T_PROFILE)&(broken['timestamp']>=cap))[0];broken['position[0]'][idx]+=.01
 assert not o.profile_check(broken,cap,cap+40000,tp)[0]
 args=gate_fixture(dict(proof(),capture_profile_match=good),'P9-CR');assert o.decide(*args)['evidence_admissible']
 args=gate_fixture(dict(proof(),capture_profile_match=False),'P9-CR');assert not o.decide(*args)['evidence_admissible']

@pytest.mark.parametrize('index',range(4))
def test_each_of_nine_original_slots_uses_actual_transaction(index,tmp_path,monkeypatch):
 row,cfg,model,prep,out,f,order=setup_transaction(tmp_path,monkeypatch)
 row=json.loads((f/'plan.json').read_text())['runs'][index]
 result=r.execute_one(row,cfg,model,prep,out,{},f)
 assert result['id']==row['id'] and result['sim_seed']==row['sim_seed'] and result['case']==row['case']
 assert result['admissible_v3'] and order==['START_INTENT','EXECUTION_FIXTURE','FINISH']

@pytest.mark.parametrize('reason',['ToDesk connected','other simulation','no global namespace','clock drift'])
def test_host_gate_blocks_before_start(reason,tmp_path,monkeypatch):
 row,cfg,model,prep,out,f,order=setup_transaction(tmp_path,monkeypatch)
 def blocked():raise RuntimeError(reason)
 monkeypatch.setattr(r,'host_gate',blocked)
 with pytest.raises(RuntimeError,match=reason):r.execute_one(row,cfg,model,prep,out,{},f)
 assert not order

@pytest.mark.parametrize('state',['UNKNOWN','REACHED_UNVERIFIED'])
def test_uncertain_opportunity_cannot_hide_behind_legacy_check(state):
 args=list(gate_fixture(proof()));args[0]['checks']['p7_measured']=True;args[2]['state']=state
 assert not o.decide(*args)['evidence_admissible']

@pytest.mark.parametrize('unknown',[False,True])
def test_actual_execute_open_failure_admission_or_stop(unknown,tmp_path,monkeypatch):
 row,cfg,model,prep,out,f,order=setup_transaction(tmp_path,monkeypatch)
 def fly(row,attempt):
  assert order[-1]=='START_INTENT';order.append('EXECUTION_FIXTURE');(attempt/'run').mkdir();c=checks();c.update(execution=False,subject_measured=False,p7_measured=False);row.update(checks=c,status='FAIL',flight_outcome='FAILURE')
 def meas(row,attempt,out):
  e=proof()
  if unknown:e['memory_coverage']=False
  row['p9']={'status':'MEASURED','max_tilt_deg':48.,'censored':True,'recoveries':[],'final_task_cost_outcome':'UNOBSERVED_FINAL_RESUME'};row['measurement_kind']='OPEN_GAP_CENSORED';row['opportunity_v3']={'state':o.classify(e),'evidence':e}
  write(attempt/'run/p9-v2-assessment.json',{'kind':'OPEN_GAP_CENSORED','measurement':row['p9']});write(attempt/'run/p7-metrics.json',{'status':'INCOMPLETE','problems':[o.MISSING]})
 monkeypatch.setattr(r.p7_batch,'run_row',fly);monkeypatch.setattr(r,'measure_row',meas)
 if unknown:
  with pytest.raises(RuntimeError,match='evidence failure'):r.execute_one(row,cfg,model,prep,out,{},f)
  assert order==['START_INTENT','EXECUTION_FIXTURE','FINISH','INTERRUPTED_OR_EXCEPTION']
 else:
  result=r.execute_one(row,cfg,model,prep,out,{},f)
  assert result['admissible_v3'] and result['observed_flight_failure'] and result['checks']['p7_measured'] is False and result['infrastructure_ok'] is False
  assert order==['START_INTENT','EXECUTION_FIXTURE','FINISH']
 events=[json.loads(x) for x in (prep/'attempts.jsonl').read_text().splitlines()]
 finish=next(x for x in events if x['event']=='FINISH' and x['id']==row['id'])
 assert finish['observed_flight_failure'] and finish['evidence_admissible_v3']==(not unknown)

@pytest.mark.parametrize('stop_second',[False,True])
def test_actual_campaign_full9_or_stops_without_remaining_queries(stop_second,tmp_path,monkeypatch):
 row,cfg,model,prep,out,f,order=setup_transaction(tmp_path,monkeypatch);fake=r.ROOT;out.rmdir()
 (fake/'config').mkdir();write(fake/'config/p9.json',cfg)
 (fake/'data/p9-20261024-formal').mkdir();write(fake/'data/p9-20261024-formal/candidate.json',{'project_head':'fixture'})
 monkeypatch.setattr(r.p2_batch,'identity',lambda:{'project_head':'fixture'})
 shutil.copy2(ROOT/'data/p9-20261024-formal/searches-sealed-before-reference.json',fake/'data/p9-20261024-formal/searches-sealed-before-reference.json')
 def read_only_process(cmd,*a,**kw):
  assert cmd==['pgrep','-x','ToDesk_Session'];return subprocess.CompletedProcess(cmd,1)
 monkeypatch.setattr(r.subprocess,'run',read_only_process)
 original=r.measure_row;calls=[]
 def measurement(row,attempt,out):
  calls.append(row['id']);original(row,attempt,out)
  if stop_second and len(calls)==2:row['opportunity_v3']['state']='UNKNOWN'
 monkeypatch.setattr(r,'measure_row',measurement)
 if stop_second:
  with pytest.raises(RuntimeError,match='evidence failure'):r.campaign(prep,f,out)
  assert len(calls)==2
 else:
  r.campaign(prep,f,out);assert len(calls)==4
 doc=json.loads((out/'results.json').read_text());events=[json.loads(x) for x in (prep/'attempts.jsonl').read_text().splitlines()]
 assert len([x for x in events if x['event']=='START_INTENT' and x['budget_class']=='formal'])==(171 if stop_second else 173)
 assert doc['status']==('STOPPED_INFRASTRUCTURE' if stop_second else 'COMPLETE')
 with pytest.raises(RuntimeError,match='output exists'):r.campaign(prep,f,out)

def test_original169_is_never_retried():
 L=[json.loads(x) for x in (ROOT/'data/p9-20261024-continuation-v4-freeze/prior-ledger.jsonl').read_text().splitlines()]
 with pytest.raises(RuntimeError,match='already attempted'):r.claim_continuation(L,{'id':'D-08-P9-CR'})

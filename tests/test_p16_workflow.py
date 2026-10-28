import json,copy
from pathlib import Path
import pytest
from p16.common import write,sha,append
from p16.workflow import Flow,read,digest,CAP
from p16.sequential import next_query

@pytest.fixture
def flow(tmp_path):
 pool=[dict(id=f'{f}-{i}',family=f,G=.55+.2*i) for f in ['F2','F4'] for i in range(6)]
 initial={c['id']:dict(peak_tilt=35.,peak_loss=.4,model_complete=True,prefix_failed_before_B=False) for c in pool}
 rows={c['id']:dict(id='run-'+c['id'],cell_id=c['id'],family=c['family'],G=c['G'],stage='main',seed=123,config='config/test-only.json',config_sha256='fixture') for c in pool}
 source=tmp_path/'synthetic-model.py';source.write_text('# unit fixture only, not an adopted real model\n')
 ledger=tmp_path/'attempts.jsonl';f=Flow(tmp_path/'query-workflow',ledger)
 f.initialize(pool,initial,rows,dict(model='synthetic unit test',query_cap=8),dict(adopted=True,scope='unit fixture only',files={str(source):sha(source)}))
 return f

def physical_result(f,ticket,*,prefix=False,finish=True):
 d=read(ticket);row=d['row'];target=f.root.parent/'runs'/row['id'];write(target/'row.json',row)
 result=dict(id=row['id'],valid=True,complete=True,peak_tilt=46. if prefix else 35.,peak_loss=.2,tilt='FAIL' if prefix else 'SUCCESS',height='SUCCESS',task='FAIL' if prefix else 'SUCCESS',prefix_failed_before_B=prefix,actual_future_capture=999.)
 p=target/'analysis-v1/result.json';write(p,result)
 append(f.ledger,dict(event='START_INTENT',id=row['id'],stage='main'))
 if finish:append(f.ledger,dict(event='FINISH',id=row['id']))
 return p

def eight(f):
 for _ in range(CAP):
  p=f.prepare_next();assert f.authorize(read(p)['row'],p)['kind']=='model_query'
  result=physical_result(f,p);f.record_result(p,result)
 return f.terminal()

def test_unknown_initial_then_actual_finite_does_not_zero_or_typeerror():
 pool=[dict(id='a',family='F2',G=.55),dict(id='b',family='F2',G=.75)]
 initial={'a':dict(peak_tilt=None,peak_loss=None,model_complete=False),'b':dict(peak_tilt=40.,peak_loss=.2,model_complete=True)}
 h={'a':dict(valid=True,complete=True,peak_tilt=30.,peak_loss=.1,tilt='SUCCESS',height='SUCCESS',task='SUCCESS',prefix_failed_before_B=False)}
 q=next_query(pool,initial,h);assert q['selected']['id']=='b'
 a=q['prediction']['a'];assert a['peak_tilt'] is None and a['peak_loss'] is None and a['own_error_evidence']==dict(peak_tilt=None,peak_loss=None)
 assert a['observed_peaks']==dict(peak_tilt=30.,peak_loss=.1) and a['task']=='SUCCESS'
 assert q['prediction']['b']['peak_tilt']==40. # no fabricated residual from unknown a

def test_prefix_failure_cannot_disappear_from_nominal_map():
 pp=[dict(id='x',family='F2',G=1.)];initial={'x':dict(peak_tilt=20.,peak_loss=.1,model_complete=True,prefix_failed_before_B=True)}
 q=next_query(pp,initial,{});assert q['prediction']['x']['task']=='FAIL' and q['prediction']['x']['prefix_failed_before_B']

def test_ticket_bound_to_row_history_pool_and_map(flow):
 p=flow.prepare_next();d=read(p);assert flow.authorize(d['row'],p)['kind']=='model_query'
 row=copy.deepcopy(d['row']);row['seed']+=1
 with pytest.raises(AssertionError,match='row changed'):flow.authorize(row,p)
 original=flow.path('pool.json').read_text();flow.path('pool.json').write_text(original+' ')
 with pytest.raises(AssertionError,match='input drift'):flow.authorize(d['row'],p)
 flow.path('pool.json').write_text(original)
 mp=flow.path('maps/q00.json');original=mp.read_text();mp.write_text(original+' ')
 with pytest.raises(AssertionError,match='map binding'):flow.authorize(d['row'],p)
 mp.write_text(original)
 bad=copy.deepcopy(d);bad['history_digest']='fake';p.write_text(json.dumps(bad))
 with pytest.raises(AssertionError):flow.authorize(d['row'],p)

def test_changed_choice_prediction_is_rejected(flow):
 p=flow.prepare_next();d=read(p);bad=copy.deepcopy(d);bad['selected_prediction']['task']='FAIL';p.write_text(json.dumps(bad))
 with pytest.raises(AssertionError,match='prediction/reason'):flow.authorize(d['row'],p)

def test_no_next_query_or_update_until_actual_review_returns(flow):
 p=flow.prepare_next()
 with pytest.raises(AssertionError,match='pending decision'):flow.prepare_next()
 result=physical_result(flow,p,finish=False)
 with pytest.raises(AssertionError,match='review must return'):flow.record_result(p,result)
 append(flow.ledger,dict(event='FINISH',id=read(p)['row']['id']))
 flow.record_result(p,result);history,_=flow.history();assert len(history)==1
 assert 'actual_future_capture' not in next(iter(history.values()))
 assert read(flow.path('maps/q00.json'))['zero_query_model']
 assert read(flow.path('maps/q01.json'))['seen_ids']==list(history)

def test_query_cannot_return_different_run_or_clear_prefix(flow):
 p=flow.prepare_next();result=physical_result(flow,p,prefix=True);record=read(result);record['task']='SUCCESS';result.write_text(json.dumps(record))
 with pytest.raises(AssertionError,match='irreversible'):flow.record_result(p,result)
 record['task']='FAIL';record['id']='wrong-run';result.write_text(json.dumps(record))
 with pytest.raises(AssertionError):flow.record_result(p,result)

def test_fill_requires_full_terminal_seal_and_cannot_replace_queries(flow):
 with pytest.raises(FileNotFoundError):flow.prepare_fill('F2-0')
 with pytest.raises(AssertionError,match='all8'):flow.terminal()
 eight(flow);terminal,h=flow.verify_terminal();docs,_=flow.inputs();unseen=next(c['id'] for c in docs['pool.json'] if c['id'] not in terminal['seen_ids']);p=flow.prepare_fill(unseen)
 assert flow.authorize(read(p)['row'],p)['kind']=='truth_fill'
 with pytest.raises(AssertionError,match='closed'):flow.prepare_next()
 with pytest.raises(AssertionError,match='replacement'):flow.prepare_fill(terminal['seen_ids'][0])
 # Fill result has no entry point into model calibration after terminal.
 assert terminal['truth_fill_labels_seen'] is False and terminal['no_more_updates']

def test_terminal_detects_return_source_and_map_mutation(flow):
 eight(flow);terminal,_=flow.verify_terminal();p=flow.path('maps/q08.json');original=p.read_text();p.write_text(original+' ')
 with pytest.raises(AssertionError,match='terminal artifact drift'):flow.verify_terminal()
 p.write_text(original);q=flow.path('queries/q01/return.json');source=Path(read(q)['source_result']);source.write_text(source.read_text()+' ')
 with pytest.raises(AssertionError,match='analysis modified'):flow.verify_terminal()

def test_main_campaign_always_requires_workflow_authorization():
 text=(Path(__file__).resolve().parents[1]/'tools/p16/campaign.py').read_text()
 assert "if row['stage']=='main':" in text and "authorization=authorize(row,prediction_path)" in text
 assert 'every main START requires a bound query/fill ticket' in text

def test_prefix_height_reference_kept_at_A():
 text=(Path(__file__).resolve().parents[1]/'tools/p16/analyze.py').read_text()
 assert 'window_basics(cfg,topics,prefix_start,prefix_stop,prefix_start)' in text
 assert "prefix_height_reference='same A task start" in text

def test_return_update_rejected_after_terminal(flow):
 eight(flow);p=flow.path('queries/q08/decision.json');r=Path(read(flow.path('queries/q08/return.json'))['source_result'])
 with pytest.raises(AssertionError,match='no result/update'):flow.record_result(p,r)

def test_adopted_source_drift_blocked_before_query(flow):
 adoption=read(flow.path('adoption.json'));source=Path(next(iter(adoption['files'])));source.write_text('changed\n')
 with pytest.raises(AssertionError,match='model source drift'):flow.prepare_next()

def test_prefix_missing_tail_not_reported_as_safe_before_B():
 text=(Path(__file__).resolve().parents[1]/'tools/p16/analyze.py').read_text()
 assert "else False if prefix_risks['task']=='SUCCESS' else None" in text
 assert "d['run_wall_ns'][jB]<=scored_host_stop" in text

def test_truncated_lower_peak_is_not_absolute_error_evidence():
 from p16.sequential import residual_evidence
 a=dict(peak_tilt=40.,peak_loss=.5);r=dict(peak_tilt=30.,peak_loss=.7,complete=False)
 assert residual_evidence(a,r)==dict(peak_tilt=None,peak_loss=pytest.approx(.2))
 r['complete']=True;assert residual_evidence(a,r)['peak_tilt']==-10.

def test_nonmonotone_edges_require_one_to_one_not_two_to_one():
 from p16.quality import boundary_error
 a=['SUCCESS','FAIL','SUCCESS'];p=['SUCCESS','FAIL','FAIL']
 r=boundary_error(a,p);assert r['status']=='UNMATCHED_TRANSITION' and r['error_cells'] is None

def test_baseline_interpolation_uses_physical_G_not_array_index():
 from p16.baseline import predict
 pool=[dict(id='a',family='F2',G=.55),dict(id='b',family='F2',G=.60),dict(id='c',family='F2',G=2.)]
 history={'a':dict(valid=True,tilt='SUCCESS',height='SUCCESS',task='SUCCESS'),'c':dict(valid=True,tilt='FAIL',height='SUCCESS',task='FAIL')}
 assert predict(pool,history)['b']['tilt']=='SUCCESS'

def test_real_historical_prefix_failure_witness_retained():
 from p16.common import sha
 root=Path(__file__).resolve().parents[1];p=root/'data/p16-20261028/material-integration-v3/prefix-real-record-v5.json';q=read(p)
 assert q['new_START']==0 and not q['old_results_rewritten']
 assert q['prefix']['risks']==dict(tilt='FAIL',height='SUCCESS',task='FAIL')
 assert q['prefix']['measurement']['max_tilt_deg']>45 and q['prefix']['measurement']['max_altitude_loss_m']<1
 assert q['helper_sha256']==sha(root/'tools/p16/analyze.py')

def test_material_adoption_gate_required_before_any_real_start(tmp_path):
 from p16.common import verify_model_adoption
 with pytest.raises(FileNotFoundError):verify_model_adoption(tmp_path/'absent.json')
 q=tmp_path/'fake.json';write(q,dict(status='PLANNED',adopted=False))
 with pytest.raises(AssertionError):verify_model_adoption(q)
 source=(Path(__file__).resolve().parents[1]/'tools/p16/campaign.py').read_text()
 assert source.index("verify_model_adoption(B/'model-adoption.json')")<source.index("append(ledger,dict(event='START_INTENT'")

def test_query_ticket_model_adoption_has_explicit_binding(flow):
 p=flow.prepare_next();q=flow.authorize(read(p)['row'],p)
 assert q['adoption_digest']==digest(read(flow.path('adoption.json')))
 text=(Path(__file__).resolve().parents[1]/'tools/p16/campaign.py').read_text()
 assert "authorization['adoption_digest']==adoption['content_digest']" in text

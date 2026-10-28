from p16.quality import label,task,boundary_error,evaluate
from p16.baseline import choose,replay

def pool():return [dict(id=f'{f}-{i}',family=f,G=float(i)) for f in ['F2','F4'] for i in range(4)]
def test_censoring_and_strict_threshold():
 assert label(45,45,False)=='UNKNOWN';assert label(45.1,45,False)=='FAIL';assert label(45,45,True)=='SUCCESS';assert task('UNKNOWN','FAIL')=='FAIL';assert task('UNKNOWN','SUCCESS')=='UNKNOWN'
def test_multiple_boundary_and_false_transition():
 a=['SUCCESS','FAIL','SUCCESS','FAIL'];assert boundary_error(a,a)['error_cells']==0
 assert boundary_error(a,['FAIL']*4)['error_cells'] is None
 assert boundary_error(['SUCCESS']*4,['SUCCESS','FAIL','SUCCESS','SUCCESS'])['status']=='UNMATCHED_TRANSITION'
def test_unknown_truth_remains_denominator():
 pp=pool();truth={c['id']:dict(valid=True,tilt='UNKNOWN',height='UNKNOWN',task='UNKNOWN') for c in pp};pred={c['id']:dict(tilt='SUCCESS',height='SUCCESS',task='SUCCESS') for c in pp};r=evaluate(pp,truth,pred);assert r['components']['task']['N_valid']==8 and r['components']['task']['accuracy']==0 and not r['same_quality']
def test_invalid_is_not_safe_or_hidden():
 pp=pool();truth={c['id']:dict(valid=False,tilt='UNKNOWN',height='UNKNOWN',task='UNKNOWN') for c in pp};r=evaluate(pp,truth,{});assert r['fixed_grid_invalid']==8 and not r['same_quality']
def test_blind_oracle_one_return_per_query():
 pp=pool();seen=[]
 def oracle(ident):seen.append(ident);return dict(valid=True,tilt='FAIL',height='UNKNOWN',task='FAIL')
 maps=replay(pp,oracle);assert len(seen)==len(set(seen))==8
 for i,m in enumerate(maps):assert len(m['seen_ids'])==i
 assert seen[:4]==['F2-0','F4-0','F2-3','F4-3']
def test_no_transition_not_positive_boundary_discovery():
 pp=pool();truth={c['id']:dict(valid=True,tilt='FAIL',height='UNKNOWN',task='FAIL') for c in pp};pred={c['id']:dict(tilt='FAIL',height='UNKNOWN',task='FAIL') for c in pp};r=evaluate(pp,truth,pred);assert r['same_quality'];assert all(e['status']=='NO_TRANSITION' for e in r['components']['task']['edges'])

def test_unique_start_and_stage_caps():
 from p16.campaign import claim
 import pytest
 row=dict(id='a',stage='main');assert claim([],row)==1
 with pytest.raises(AssertionError):claim([dict(event='START_INTENT',id='a',stage='main')],row)
 old=[r for i in range(24) for r in [dict(event='START_INTENT',id=str(i),stage='main'),dict(event='FINISH',id=str(i))]]
 with pytest.raises(AssertionError):claim(old,row)

def test_shutdown_no_live_task_signal():
 from p16.campaign import eligible
 assert not eligible([])
 ev=[dict(event='p5_stream_ended'),dict(event='p1_phase_ended',label='post_stream'),dict(event='p1_phase_ended',label='return_classic'),dict(event='landing_requested'),dict(event='ready',condition='disarmed')]
 assert eligible(ev);assert not eligible(ev+[dict(event='failure')]);assert not eligible(ev+[dict(event='process_stopped',name='px4')])

def test_model_query_only_own_labels_and_eight_cap():
 from p16.sequential import next_query
 import pytest
 pp=pool();initial={c['id']:dict(peak_tilt=40,peak_loss=.5,model_complete=True) for c in pp};history={};q=next_query(pp,initial,history);assert q['seen_ids']==[] and q['query']==1
 for c in pp:history[c['id']]=dict(valid=False)
 with pytest.raises(AssertionError):next_query(pp,initial,history)

def test_censored_peak_never_fitted_as_negative_residual():
 from p16.sequential import calibrated
 pp=pool();init={c['id']:dict(peak_tilt=50,peak_loss=.5,model_complete=True) for c in pp};r=dict(valid=True,complete=False,peak_tilt=46,peak_loss=.3,tilt='FAIL',height='UNKNOWN',task='FAIL');p=calibrated(pp,init,{'F2-0':r});assert p['F2-1']['peak_tilt']==50 and p['F2-1']['peak_loss']==.5
 r.update(peak_tilt=55);p=calibrated(pp,init,{'F2-0':r});assert p['F2-1']['peak_tilt']>50

def test_future_fields_not_consulted_in_calibration_selection():
 from p16.sequential import next_query
 pp=pool();init={c['id']:dict(peak_tilt=40,peak_loss=.5,model_complete=True) for c in pp};a=next_query(pp,init,{})
 for r in init.values():r.update(actual_future_capture=999,truth_label='FAIL')
 b=next_query(pp,init,{});assert a==b

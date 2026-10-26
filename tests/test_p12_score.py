"""Risk classification must not turn a safe truncated prefix into task success."""
import json,sys
from pathlib import Path
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from p12.score import score,bundle


def fixture(tmp,stop=.8,reason='PREDICTED_ENVELOPE',pred_tilt=0.,pred_height=0.,
            observed_tilt=0.,observed_height=0.,observed_end=2.,censored=False,name='M3'):
    packed=tmp/'packed';packed.mkdir();prediction=tmp/'prediction';prediction.mkdir()
    t=np.arange(0,observed_end+.001,.004);q=np.zeros((len(t),4));q[:,0]=1
    observed_angles=np.where(t>=.4,observed_tilt,0.);q[:,0]=np.cos(np.radians(observed_angles)/2);q[:,1]=np.sin(np.radians(observed_angles)/2)
    p=np.zeros((len(t),3));p[:,2]=np.where(t>=.4,observed_height,0.)
    np.savez(packed/'measurement.npz',profile_s=t,attitude=q,position=p,velocity=np.zeros((len(t),3)),
        action=np.zeros((len(t),4)),h_after=np.zeros((len(t),16)))
    (packed/'prediction-input.json').write_text(json.dumps({'plan':{'common_first_gap_profile_s':0.,'horizon_profile_s':2.,'windows_profile_s':[[.2,.3],[1.2,1.3]]}}))
    pt=np.arange(0,(2. if stop is None else stop)+.001,.004);trace=np.zeros((len(pt),52));trace[:,0]=pt;trace[:,35]=1.;trace[:,48]=1.
    trace[:,7]=np.where(pt>=.7,pred_tilt,0.);trace[:,3]=np.where(pt>=.7,pred_height,0.);trace[:,44]=trace[:,3]
    np.savez(prediction/(name+'.npz'),trace=trace)
    stop_meta=None if stop is None or reason is None else {'profile_s':stop,'reason':reason}
    (prediction/'prediction.json').write_text(json.dumps({'models':{name:{'stop':stop_meta,'compute_s':0.}}}))
    observed_fail=observed_tilt>45 or observed_height>1
    measurement=tmp/'measurement.json';measurement.write_text(json.dumps({'whole':{'max_tilt_deg':observed_tilt,'max_altitude_loss_m':observed_height},
        'censored':censored,'task_outcome':'FAILURE' if observed_fail else 'UNKNOWN_CENSORED' if censored else 'SUCCESS'}))
    return packed,prediction,measurement,trace


@pytest.mark.parametrize('reason',['PREDICTED_ENVELOPE','NUMERICAL_UNCERTAIN','ANOTHER_STOP',None])
def test_any_safe_short_prediction_is_unknown(tmp_path,reason):
    packed,prediction,measurement,_=fixture(tmp_path,reason=reason)
    r=score(prediction,packed,measurement,tmp_path/'out')['models']['M3']
    assert all(r[k]=='UNKNOWN_PREDICTION_TRUNCATED' for k in ['risk_comparison','height_risk_comparison','task_risk_comparison'])
    assert not any(r['risk']['classification_eligible'].values())
    assert r['peak_abs_error_deg'] is None and r['common_prefix_peak_abs_error_deg'] is not None


def test_envelope_tilt_witness_is_false_alarm_without_angle_metadata(tmp_path):
    packed,prediction,measurement,_=fixture(tmp_path,pred_tilt=46.)
    r=score(prediction,packed,measurement,tmp_path/'out')['models']['M3']
    assert r['risk_comparison']==r['task_risk_comparison']=='FALSE_ALARM'
    assert r['height_risk_comparison']=='UNKNOWN_PREDICTION_TRUNCATED'
    assert r['risk']['predicted']=={'tilt':'FAILURE','height':'UNKNOWN','task':'FAILURE'}
    assert r['risk']['classification_eligible']['task'] and not r['risk']['full_trajectory_eligible']['task']
    assert r['peak_abs_error_deg'] is None


def test_height_witness_alone_classifies_task_failure(tmp_path):
    packed,prediction,measurement,_=fixture(tmp_path,pred_height=1.2)
    r=score(prediction,packed,measurement,tmp_path/'out')['models']['M3']
    assert r['height_risk_comparison']==r['task_risk_comparison']=='FALSE_ALARM'
    assert r['risk_comparison']=='UNKNOWN_PREDICTION_TRUNCATED'


def test_failure_agreement_is_prefix_witness_not_complete_trajectory(tmp_path):
    packed,prediction,measurement,_=fixture(tmp_path,pred_tilt=46.,observed_tilt=46.)
    r=score(prediction,packed,measurement,tmp_path/'out')['models']['M3']
    assert r['task_risk_comparison']=='AGREEMENT'
    assert r['risk']['predicted']['task']==r['risk']['observed']['task']=='FAILURE'
    assert not r['risk']['full_trajectory_eligible']['task'] and r['peak_abs_error_deg'] is None


def test_safe_truncated_prediction_of_observed_failure_is_not_a_complete_miss(tmp_path):
    packed,prediction,measurement,_=fixture(tmp_path,observed_tilt=46.)
    r=score(prediction,packed,measurement,tmp_path/'out')['models']['M3']
    assert r['task_risk_comparison']=='UNKNOWN_PREDICTION_TRUNCATED'


def test_complete_safe_prediction_of_observed_failure_is_danger_miss(tmp_path):
    packed,prediction,measurement,_=fixture(tmp_path,stop=None,observed_height=1.2)
    r=score(prediction,packed,measurement,tmp_path/'out')['models']['M3']
    assert r['height_risk_comparison']==r['task_risk_comparison']=='DANGER_MISS'


def test_numerical_stop_row_cannot_supply_a_failure_witness(tmp_path):
    packed,prediction,measurement,trace=fixture(tmp_path,reason='NUMERICAL_UNCERTAIN')
    trace[-1,7]=60.;np.savez(prediction/'M3.npz',trace=trace)
    r=score(prediction,packed,measurement,tmp_path/'out')['models']['M3']
    assert r['task_risk_comparison']=='UNKNOWN_PREDICTION_TRUNCATED' and r['invalid_or_uncertain_tail_rows']==1


def test_no_prediction_overlap_does_not_invent_agreement_or_error_metrics(tmp_path):
    packed,prediction,measurement,trace=fixture(tmp_path,stop=.1)
    doc=json.loads((packed/'prediction-input.json').read_text());doc['plan']['common_first_gap_profile_s']=.2
    (packed/'prediction-input.json').write_text(json.dumps(doc))
    r=score(prediction,packed,measurement,tmp_path/'out')['models']['M3']
    assert r['scored_rows']==0 and r['position_norm_m'] is None and r['task_risk_comparison']=='UNKNOWN_PREDICTION_TRUNCATED'


def test_event_completeness_uses_own_window_not_whole_prediction(tmp_path):
    packed,prediction,measurement,_=fixture(tmp_path)
    r=score(prediction,packed,measurement,tmp_path/'out')['models']['M3'];early=r['event_windows'][0];late=r['event_windows'][2]
    assert early['prediction_complete'] and not early['censored'] and early['task_risk_comparison']=='AGREEMENT'
    assert not late['prediction_complete'] and late['task_risk_comparison']=='UNKNOWN_PREDICTION_TRUNCATED'


def test_censored_safe_observation_is_not_false_alarm_or_success(tmp_path):
    packed,prediction,measurement,_=fixture(tmp_path,pred_tilt=46.,observed_end=.8,censored=True)
    r=score(prediction,packed,measurement,tmp_path/'out')['models']['M3']
    assert r['task_risk_comparison']=='UNKNOWN_CENSORED'
    assert all(e['task_risk_comparison']=='NOT_REACHED' for e in r['event_windows'] if e['index']==1)


def test_known_or_failure_dominates_unmodelled_height():
    b=bundle(46.,None,False,0.,0.,True,height=False)
    assert b['comparisons']['task']=='FALSE_ALARM' and b['comparisons']['height']=='UNKNOWN_UNMODELLED_HEIGHT'


def test_nonfinite_internal_state_cannot_establish_full_prediction_success(tmp_path):
    packed,prediction,measurement,trace=fixture(tmp_path,stop=None)
    trace[-1,12]=float('nan');np.savez(prediction/'M3.npz',trace=trace)
    r=score(prediction,packed,measurement,tmp_path/'out')['models']['M3']
    assert not r['full_prediction'] and r['task_risk_comparison']=='UNKNOWN_PREDICTION_TRUNCATED'


def test_denominators_separate_prefix_labels_and_complete_trajectory_metrics(tmp_path):
    from p12.rescore import aggregate
    a=tmp_path/'prefix';a.mkdir();p,x,m,_=fixture(a,pred_tilt=46.)
    first=score(x,p,m,a/'out')
    b=tmp_path/'complete';b.mkdir();p,x,m,_=fixture(b,stop=None)
    second=score(x,p,m,b/'out')
    result=aggregate({'prefix':first,'complete':second})['M3']
    assert result['whole']['task']['classifiable_label_n']==2
    assert result['whole']['task']['safe_agreement_n']==1 and result['whole']['task']['false_alarm_n']==1
    assert result['whole']['task']['both_complete_trajectory_n']==1
    assert result['whole']['height']['classifiable_label_n']==1 and result['whole']['height']['unknown_n']==1
    assert result['error_denominators']=={'common_prefix_rmse_n':2,'complete_trajectory_rmse_n':1,'complete_peak_error_n':1}


def test_exact_task_thresholds_remain_strict_without_relaxation():
    b=bundle(45.,1.,True,45.,1.,True)
    assert b['predicted']==b['observed']=={'tilt':'SUCCESS','height':'SUCCESS','task':'SUCCESS'}
    assert all(v=='AGREEMENT' for v in b['comparisons'].values())

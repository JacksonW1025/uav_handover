import copy
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from p0_closure import measurement_errors,startup_ok

def measurement():
    return {'status':'MEASURED','partial_tail_bytes':{str(motor):0 for motor in range(4)},
            'px4_overwritten_publications':{'neural_bracketed':0},
            'motors':{str(motor):{'neural':{'steps':10,'negative_age_steps':0,
                'applied_age_us':{'count':10,'p99':4000,'max':4000}}} for motor in range(4)}}

def test_missing_or_invalid_motor_evidence_fails():
    original=measurement()
    assert not measurement_errors(original)
    for mutation in ['missing_motor','partial','missing_counter','missing_samples','negative','nan']:
        changed=copy.deepcopy(original)
        if mutation=='missing_motor':del changed['motors']['3']
        if mutation=='partial':changed['partial_tail_bytes']['2']=4
        if mutation=='missing_counter':changed['px4_overwritten_publications']['neural_bracketed']=None
        if mutation=='missing_samples':changed['motors']['1']['neural']['applied_age_us']['count']=9
        if mutation=='negative':changed['motors']['3']['neural']['negative_age_steps']=1
        if mutation=='nan':changed['motors']['2']['neural']['applied_age_us']['p99']=float('nan')
        assert measurement_errors(changed),mutation

def test_startup_summary_cannot_hide_failed_or_missing_run():
    audit={'startups':{'passed':True,'count':1,'runs':[{'passed':True}]}}
    assert startup_ok(audit)
    audit['startups']['runs'][0]['passed']=False
    assert not startup_ok(audit)
    audit['startups']['runs']=[]
    assert not startup_ok(audit)

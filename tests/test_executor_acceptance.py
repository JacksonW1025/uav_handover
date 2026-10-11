import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from p0_metrics import executor_acceptance

def scopes():
    return {n:{'calls_total':1000,'hard_faults_total':0,'input_rejections_total':0,
        'unclassified_warning_total':0,'p99_budget_proven':True,'executor_warnings_total':0}
        for n in ['whole_run','active','neural_actuator_authority']}

def test_inactive_warning_is_explicit_warning_pass():
    s=scopes();assert executor_acceptance(s,0,0)[0]=='PASS'
    s['whole_run']['executor_warnings_total']=45
    assert executor_acceptance(s,0,0)[0]=='PASS_WITH_WARNINGS'

def test_activity_and_actual_publication_are_independent_failure_scopes():
    for name in ['active','neural_actuator_authority']:
        s=scopes();s[name]['executor_warnings_total']=1
        assert executor_acceptance(s,0,0)[0]=='FAIL'

def test_missing_or_invalid_evidence_never_passes():
    for field,value in [('calls_total',0),('hard_faults_total',1),('input_rejections_total',1),
                        ('unclassified_warning_total',1),('p99_budget_proven',False)]:
        s=scopes();s['whole_run'][field]=value
        assert executor_acceptance(s,0,0)[0]=='FAIL'
    assert executor_acceptance(scopes(),1,0)[0]=='FAIL'
    assert executor_acceptance(scopes(),0,1)[0]=='FAIL'

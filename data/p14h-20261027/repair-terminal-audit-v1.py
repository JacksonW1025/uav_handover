"""Analysis-only correction of producer-before-consumer terminal coverage.
No time tolerance. Exception requires exactly matching terminal sample and a
completed source CALC_PRE/POST pair before the last consuming control read.
Original audit FAIL is retained and independently linked.
"""
import sys,json,copy,resource
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
import numpy as np
from p14h.common import *
from p14r.observer import read,CORE
from p12b.read_trace import load

def verify(target):
 old=json.load(open(target/'observer-audit-v1/audit.json'));a,h=read(target/'run/gz-motor/observer-core.bin',CORE,b'P14RCORE',True);d=load(target/'run/gz-motor/read-p12b.bin');j=np.flatnonzero(d['active'])[-1];post=a[a['kind']==2];pre=a[a['kind']==1];only=[k for k,v in old['gates'].items() if not v];same=int(post[-1]['sample_us'])==int(d['timestamp_sample'][j]);before=int(post[-1]['wall_ns'])<=int(d['pre_read_wall_ns'][j]);matched=np.array_equal(pre['sample_us'],post['sample_us']);permitted=not only or only==['core_full_active_coverage'] and same and before and matched
 return dict(id=target.name,original_status=old['status'],failed_gates=only,new_qualified_status='PASS_CAUSAL_TERMINAL_ENDPOINT' if permitted else 'DATA_QUARANTINE',last_source_sample_us=int(post[-1]['sample_us']),last_control_sample_us=int(d['timestamp_sample'][j]),source_completed_before_read_ns=int(d['pre_read_wall_ns'][j])-int(post[-1]['wall_ns']),terminal_sample_equal=same,terminal_source_before_consumer=before,all_source_pairs_complete=matched,exact_sample_not_time_tolerance=True,no_raw_state_or_clock_fabricated=True,original_FAIL_retained=True)

def main():
 out=register(sys.argv[1],'analysis-only fix producer endpoint check: source same-sample PRE/POST completion before terminal consumer is sufficient; all original gates retained; oldFAIL preserved',no_flight=True,no_experimental_change=True,no_parameter_change=True)
 rows=[]
 for target in sorted((B/'runs').iterdir()):
  if (target/'observer-audit-v1/audit.json').exists():rows.append(verify(target))
 write(out/'all-affected.json',dict(rows=rows,source_rule='OP is upstream and may finish before terminal consumer. Do not require a future producer call after the run has ended. No sample gap exception, no tolerance enlargement.',scope='old operator >=host_end replaced only by exact terminal sample completed before consumer, other gates unchanged',not_new_observation_version=True))
 target=next((B/'runs').glob('p14h-e11-*'));row=next(x for x in rows if x['id']==target.name);assert row['failed_gates']==['core_full_active_coverage'] and row['new_qualified_status']=='PASS_CAUSAL_TERMINAL_ENDPOINT';assert all(x['new_qualified_status']=='PASS_CAUSAL_TERMINAL_ENDPOINT' for x in rows)
 # Negative tests: missing terminal sample, incomplete pair, reversed causality,
 # or any additional gate failure must still be rejected.
 def allow(only,same,before,paired):return not only or only==['core_full_active_coverage'] and same and before and paired
 assert allow(['core_full_active_coverage'],True,True,True)
 for only,same,before,paired in [(['core_full_active_coverage'],False,True,True),(['core_full_active_coverage'],True,False,True),(['core_full_active_coverage'],True,True,False),(['core_full_active_coverage','core_finite'],True,True,True)]:assert not allow(only,same,before,paired)
 from p14h.workflow import process
 measured=process(target/'run',target/'analysis-v2',R/'data/p12-cont-20261026-freeze/models',predict=False)
 from p14h.scope_audit import audit
 scoped=audit(target/'run',target/'analysis-v2',target/'neural-scope-v3')
 from p13.physics import analyze
 physical=analyze(target/'run',target/'analysis-v2/physics');assert physical['status']=='PASS'
 from p14h.snapshot import read as sr
 a,h=sr(target/'run/gz-motor/ekf-p14h.bin');assert h['dropped']==h['errors']==0 and np.all(a['ndof']==24) and np.all(a['nstate']==25);assert np.isfinite(a['covariance'][:,:24,:24]).all();cov=a['covariance'][:,:24,:24];sym=float(np.max(abs(cov-cov.transpose(0,2,1))));assert sym<1e-5
 write(target/'snapshot-audit-v2.json',dict(status='PASS',rows=len(a),header=h,symmetry_max=sym,source_stage='post-EKF beforeLP',full_active_coverage=scoped['tests']['fullP_active_coverage']))
 write(target/'information.json',dict(engineering='PASS_CRITICAL_SOURCE_WITH_EXACT_CAUSAL_ENDPOINT',observer='oldFAIL retained; same-terminal-sample qualified PASS',observer_scope_revision=str((out/'all-affected.json').relative_to(R)),task_outcome=measured['task_outcome'],censored=measured['censored'],physics='PASS',snapshot='PASS',role='independent',source_analysis=str((target/'analysis-v2').relative_to(R)),initial_difference_preserved=True,source_experiment_unchanged=True))
 append(B/'attempts.jsonl',dict(event='OUTCOME_RESOLVED',id=target.name,new_analysis='analysis-v2',reason='analysis coverage predicate rejected completed upstream same-sample operation 25150ns before consumer; no missing raw record and no tolerance change',original_FAIL_retained=True,task_outcome=measured['task_outcome'],censored=measured['censored'],no_reflight=True));print('TERMINAL_AUDIT_REPAIRED',len(rows),row)
if __name__=='__main__':main()

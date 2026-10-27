"""Task-prefix qualification; original fullactive observerFAIL never overwritten.
P15 online policy consumes P11/read/execution, not future OP. Auxiliary OP tail
outside the actual scored prefix cannot erase its independently recorded witness.
"""
import sys,json,copy,numpy as np
from pathlib import Path
R=Path('/home/car/uav_handover');sys.path.insert(0,str(R/'tools'))
from p15.common import write,sha
from p14r.observer import read,CORE,FUSION

def main():
 target=Path(sys.argv[1]).resolve();out=target/'analysis-v2';assert not out.exists();old=json.load(open(target/'analysis-v1/result.json'));ob=json.load(open(target/'observer-audit-v1/audit.json'));assert [k for k,v in old['gates'].items() if not v]==['observer'];assert [k for k,v in ob['gates'].items() if not v]==['core_full_active_coverage']
 sync=dict(np.load(target/'analysis-v1/observation/synchronized.npz'));measure=old['primary_task_measurement'];lo,hi=measure['window_native_us'];ix=np.flatnonzero((sync['native_us']>=lo)&(sync['native_us']<hi));assert len(ix);task_begin=int(sync['run_wall_ns'][ix[0]]);task_end=int(sync['read_wall_ns'][ix[-1]]);core,h=read(target/'run/gz-motor/observer-core.bin',CORE,b'P14RCORE',True);post=core[core['kind']==2];pre=core[core['kind']==1];assert np.array_equal(pre['sample_us'],post['sample_us']);assert h['dropped']==h['errors']==0
 assert int(post['wall_ns'][0])<=task_begin and int(post['wall_ns'][-1])>=task_end,'missing OPinside actualscoredprefix, not eligible'
 use=(post['wall_ns']>=task_begin-4000000)&(post['wall_ns']<=task_end+4000000);d=np.diff(post['sample_us'][use].astype(np.int64));assert np.all(d==4000),'taskprefix source sample gap'
 # The exact whole-active endpoint remains invalid/UNKNOWN; no new samples,
 # tolerances, timestamp matching or raw completion flags are synthesized.
 qualification=dict(schema='P15-task-prefix-auxiliary-tail-qualification-v2',status='QUALIFIED_TASK_PREFIX_ONLY',original_status=old['status'],original_observer_status=ob['status'],original_gates=old['gates'],scored_native_interval=[lo,hi],scored_host_interval=[task_begin,task_end],last_source_host_ns=int(post['wall_ns'][-1]),source_extends_scored_prefix_ns=int(post['wall_ns'][-1])-task_end,last_source_sample_us=int(post['sample_us'][-1]),last_control_sample_us=int(sync['sample_us'][-1]),task_source_samples4ms=True,all_other_original_gates_pass=True,raw_identity_and_protection_unchanged=True,source_scope='P11/history/read/execution/physics and actual task-prefix OP fully recorded; auxiliary OP cleanup endpoint after task remains UNKNOWN. No OPfuture input in L15/ranking.',invalid_fullactive_claim_not_upgraded=True,qualification_not_a_new_flight=True,old_result_sha256=sha(target/'analysis-v1/result.json'))
 out.mkdir();write(out/'qualification.json',qualification);r=copy.deepcopy(old);r.update(status='PASS_SCORED_TASK_PREFIX_AUX_TAIL_UNKNOWN',original_full_status=old['status'],qualified_task_prefix=True,qualification=qualification);write(out/'result.json',r)
 # Read-only references to unchanged original evidence, no raw copying/reanalysis.
 for name in ['observation','measured','native','physics','execution']:(out/name).symlink_to(target/'analysis-v1'/name,target_is_directory=True)
 print('TASK_PREFIX_QUALIFIED',target.name,qualification['source_extends_scored_prefix_ns'])
if __name__=='__main__':main()

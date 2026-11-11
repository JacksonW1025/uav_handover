"""Explicit round only, no implicit retries; stops on infrastructure/cleanup/identity failure."""
import json,sys,subprocess,time,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from handover_100.run_batch import observed
from cn_single.runner import append
from preparation_batch import identity
p=Path(sys.argv[1]);plan=json.loads(p.read_text());batch=ROOT/plan['batch'];batch.mkdir(exist_ok=True)
ph=hashlib.sha256(p.read_bytes()).hexdigest();initial=identity();result=[]
for case,spec in plan['cases'].items():
    if identity()!=initial or hashlib.sha256(p.read_bytes()).hexdigest()!=ph:raise RuntimeError('IDENTITY_DRIFT')
    name=case+'-a1';target=batch/name
    if target.exists():raise RuntimeError('prior attempt exists; explicit new attempt required')
    append(batch/'round-events.jsonl',dict(event='WHY_BEFORE_START',round=plan['round'],case=case,rationale=spec['rationale'],plan_sha256=ph,time_ns=time.time_ns()))
    print('START',case,spec['rationale'],flush=True)
    with (batch/(name+'-console.log')).open('x') as f:
        rc=subprocess.run([str(ROOT/'tools/handover_mutation/experiment'),'--plan',str(p),'--case',case,'--execute'],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT).returncode
    r=observed(target);r['runner_exit_code']=rc;result.append(r)
    append(batch/'round-events.jsonl',dict(event='ATTEMPT_RETURNED',round=plan['round'],time_ns=time.time_ns(),**r))
    (batch/('round-'+str(plan['round'])+'-progress.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('END',case,r['execution_status'],r.get('reason'),flush=True)
    detail=json.loads((target/'result.json').read_text()) if (target/'result.json').exists() else {}
    if rc or detail.get('cleanup_error') or not detail.get('candidate_unchanged') or not r['actual_subject_boundaries']:raise RuntimeError('infrastructure/cleanup/identity/no-subject blocker; inspect before next start')
    if detail.get('reason') and 'safety:' not in detail['reason']:raise RuntimeError('non-safety failure requires diagnosis')
print('ROUND_COMPLETE',plan['round'],len(result),flush=True)

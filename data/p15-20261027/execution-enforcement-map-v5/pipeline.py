"""Same frozen scientific protocol, full candidate/plan guard on every START.
Infra amendment only: original model/source/head/order preserved, no reflight.
"""
import sys,json,subprocess,time,resource,os,hashlib
from pathlib import Path
R=Path('/home/car/uav_handover');sys.path.insert(0,str(R/'tools'))
from p15.common import B,PY,sha,write,append
import p2_batch
D=Path(__file__).resolve().parent

def gate(plan):
 seal=json.load(open(D/'seal.json'))
 for p,h in seal['files'].items():assert sha(R/p)==h,'enforcementseal '+p
 freeze=json.load(open(B/'experiment-freeze-v1.json'));inputs=json.load(open(B/'freeze-inputs-v1.json'));assert sha(B/'freeze-inputs-v1.json')==freeze['inputs_sha256'];assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==freeze['commit']
 for p,h in inputs['plans'].items():assert sha(R/p)==h,'frozen plan drift '+p
 assert str(plan.relative_to(R)) in inputs['plans'],'not sealed search/map plan'
 expected=json.load(open(D/'full-candidate-anchor.json'));assert p2_batch.identity()==expected,'full frozen candidate drift, includes all Lab/source/policy/plugin'
 for p,h in inputs['source_files'].items():assert sha(R/p)==h,'source drift '+p
 subprocess.run(['git','diff','--exit-code',freeze['commit'],'--','tools','research','config'],check=True,stdout=subprocess.DEVNULL)
 return expected

def bind_adaptive(row,out):
 cfg=json.load(open(R/row['config']));path=cfg['p15'].get('local_update_path');binding=dict(id=row['id'],rule_sha256=sha(R/'tools/p15/update.py'),functional_rule_frozen=True)
 if path:
  p=R/path;assert p.exists(),'required pastmap update not reached; stop this dependency beforeSTART'
  previous=p.parents[1];records=[json.loads(l) for l in (B/'attempts.jsonl').read_text().splitlines()];assert any(x.get('id')==previous.name and x['event'] in ['FINISH','REVIEW_RESOLVED'] for x in records)
  assert json.load(open(previous/'candidate.json'))==json.load(open(D/'full-candidate-anchor.json'))
  prior=json.load(open(previous/'run/p15-map-prior.json'));pi=json.load(open(previous/'run/p15-map-prior-input.json'));state=json.load(open(previous/'run/p15-decision-state.json'));from p15.update import local
  expected=local(prior['rows'][0]['prediction'],state,pi['context']);actual=json.load(open(p));assert actual==expected,'adaptive payload differs from frozenpastdata rule'
  assert state['available_by_ns']<time.monotonic_ns();binding.update(previous_id=previous.name,payload_sha256=sha(p),prior_sha256=sha(previous/'run/p15-map-prior.json'),state_sha256=sha(previous/'run/p15-decision-state.json'),future_validation_data_used=False)
 write(out/('before-start-binding-'+row['id']+'.json'),binding)

def main():
 plan=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]).resolve();out.mkdir(exist_ok=False,parents=True);write(out/'before.json',dict(plan=str(plan.relative_to(R)),plan_sha256=sha(plan),enforcement_sha256=sha(Path(__file__)),same_semantic_recovery=True));st=time.perf_counter();self0=resource.getrusage(resource.RUSAGE_SELF)
 for r in json.load(open(plan))['rows']:
  records=[json.loads(l) for l in (B/'attempts.jsonl').read_text().splitlines()];starts=[x for x in records if x['event']=='START_INTENT'];done={x['id'] for x in records if x['event'] in ['FINISH','REVIEW_RESOLVED']};pending=[x['id'] for x in starts if x['id'] not in done]
  if pending:write(out/'stop.json',dict(reason='unreviewed prior outcome',ids=pending));return
  if any(x['id']==r['id'] for x in starts):continue
  before=gate(plan);bind_adaptive(r,out);row=dict(event='BEFORE_START_GATE',id=r['id'],time_ns=time.time_ns(),candidate_sha256=sha(D/'full-candidate-anchor.json'),plan_sha256=sha(plan));append(D/'gate-ledger.jsonl',row)
  import importlib.util
  spec=importlib.util.spec_from_file_location('owned_shutdown',B/'shutdown-recovery-v1/supervisor.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);code=mod.run(r['id'],plan,out/('postdisarm-'+r['id']))
  assert p2_batch.identity()==before,'postflight full identity drift'
  records=[json.loads(l) for l in (B/'attempts.jsonl').read_text().splitlines()]
  if not any(x['id']==r['id'] and x['event'] in ['FINISH','REVIEW_RESOLVED'] for x in records):
   target=B/'runs'/r['id'];source=target/'analysis-v1/result.json'
   if source.exists() and [k for k,v in json.load(open(source))['gates'].items() if not v]==['observer']:
    from p15.common import cost_run
    q=cost_run([PY,B/'analysis-qualification-v2/review.py',target],target/'qualified-task-prefix-process-v2',cpu=120,wall=180,scope='optionalOP cleanupendpoint scopedreview, oldFAIL kept')
    if q['rc']==0:append(B/'attempts.jsonl',dict(event='REVIEW_RESOLVED',id=r['id'],scope='critical fullstate+actualscoredprefix valid; wholeactive auxiliaryOPtail stillUNKNOWN, originalFAIL retained',new_analysis='analysis-v2',no_reflight=True));records=[json.loads(l) for l in (B/'attempts.jsonl').read_text().splitlines()]
  if code or not any(x['id']==r['id'] and x['event'] in ['FINISH','REVIEW_RESOLVED'] for x in records):write(out/'stop.json',dict(id=r['id'],reason='scoped review required',rc=code));return
 after=resource.getrusage(resource.RUSAGE_SELF);write(out/'complete.json',dict(planned=len(json.load(open(plan))['rows']),all_prior_START_skipped=True,wall_s=time.perf_counter()-st,CPU_s_manager=after.ru_utime+after.ru_stime-self0.ru_utime-self0.ru_stime,source='additional fullfreeze guards, actualphysical/analysisCPU elsewhere'))
if __name__=='__main__':main()

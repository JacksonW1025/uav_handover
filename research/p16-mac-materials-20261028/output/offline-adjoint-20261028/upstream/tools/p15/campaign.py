"""One counted P15 run. No retry/replacement; explicit phase caps and exit gate."""
import sys,os,time,json,subprocess,resource,fcntl,signal
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from p15.common import *
from p9_run import host_gate
import p2_batch

def main():
 self_start=resource.getrusage(resource.RUSAGE_SELF)
 ident=sys.argv[1];plan=json.load(open(sys.argv[2]));row=next(x for x in plan['rows'] if x['id']==ident);ledger=B/'attempts.jsonl'
 with (B/'attempts.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);rows=[json.loads(l) for l in ledger.read_text().splitlines()] if ledger.exists() else [];starts=[x for x in rows if x['event']=='START_INTENT'];cls=row['budget_class'];assert len(starts)<48;assert sum(x['budget_class']==cls for x in starts)<{'development':8,'search':32,'map':8}[cls];assert not any(x['id']==ident for x in starts)
  unresolved=[x for x in starts if not any(y.get('id')==x['id'] and y['event'] in ['FINISH','REVIEW_RESOLVED'] for y in rows)];assert not unresolved,'old outcome unresolved inspect realhost'
  host=host_gate();g=json.load(open(B/'preflight-current.json'));assert g['status']=='PASS'
  for p,h in g['files'].items():assert sha(R/p)==h,'P15 preflight drift '+p
  assert sha(R/row['config'])==row['config_sha256'];assert os.statvfs(R).f_bavail*os.statvfs(R).f_frsize>12*1024**3
  if cls!='development':
   f=json.load(open(B/'experiment-freeze-v1.json'));assert f['remote_verified'];assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==f['commit']
  target=B/'runs'/ident;target.mkdir(parents=True,exist_ok=False);candidate=p2_batch.identity();write(target/'candidate.json',candidate);write(target/'plan.json',row);write(target/'host-before.json',host);write(target/'before-start.json',dict(time=p2_batch.now(),prior=row.get('prestart_prediction','development prior unavailable'),new_run_state='not yet created; frozen commonstartup and legal state acquisition paid by every method',candidate_pool_sha256=sha(R/'config/p15/candidate-pool-v1.json'),model_parameters_sha256=sha(R/'config/p15/model-v1.json'),source_information='past development/previousfinished map only; no new run future information',expected_branch='phase1 commit-read, strict200ms timeout, latestcommand nextphysics nominal; actual branch and action verified raw after'))
  cmd=[R/'tools/p15/experiment',row['kind'],'--config',R/row['config'],'--output',target/'run','--condition',row['condition'],'--treatment',row['treatment'],'--sim-seed',str(row['seed']),'--initial-yaw-deg','0'];cmd=list(map(str,cmd));append(ledger,dict(event='START_INTENT',id=ident,budget_class=cls,ordinal=len(starts)+1,time=p2_batch.now(),config_sha256=row['config_sha256'],all_failures_count=True));print('P15_START',len(starts)+1,ident,flush=True);st=time.perf_counter();before=resource.getrusage(resource.RUSAGE_CHILDREN)
  with (target/'wrapper.log').open('w') as out:
   proc=subprocess.Popen(cmd,stdout=out,stderr=subprocess.STDOUT,env=dict(os.environ,HANDOVER_CPU_AFFINITY='px4=8-11;gazebo=12-13;agent=6-7;runner=4-5',OPENBLAS_NUM_THREADS='1'))
   try:rc=proc.wait(timeout=180)
   except subprocess.TimeoutExpired:
    append(ledger,dict(event='OWNED_WRAPPER_WALL_LIMIT',id=ident,pid=proc.pid,signal='SIGINT ownwrapper, normal finally cleanup, noforeignprocesskill'));proc.send_signal(signal.SIGINT)
    try:rc=proc.wait(timeout=30)
    except subprocess.TimeoutExpired:rc='OWNED_WRAPPER_EXIT_UNCERTAIN'
  after=resource.getrusage(resource.RUSAGE_CHILDREN);events=[json.loads(l) for l in (target/'run/events.jsonl').read_text().splitlines()] if (target/'run/events.jsonl').exists() else [];exits=[x['exit_code'] for x in events if x['event']=='process_stopped' and x['name']=='px4'];stable=candidate==p2_batch.identity();write(target/'execution-result.json',dict(wrapper_exit=rc,PX4_exit_codes=exits,candidate_unchanged=stable,wall_s=time.perf_counter()-st,CPU_s=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,includes='startup/warmup/controller/physics/online scoring worker/queries/shutdown, no free prefix reuse',command=cmd));append(ledger,dict(event='PHYSICAL_END' if exits==[0] else 'PHYSICAL_UNCERTAIN',id=ident,exit_codes=exits,stable=stable))
  if exits!=[0] or not stable:append(ledger,dict(event='EXECUTION_REVIEW_REQUIRED',id=ident));return
  result=cost_run([PY,R/'tools/p15/analyze.py',target],target/'analysis-process',cpu=120,wall=180,scope='mandatory raw/control/execution/physics review before next physical item')
  self_end=resource.getrusage(resource.RUSAGE_SELF);write(target/'manager-cost.json',dict(CPU_s=self_end.ru_utime+self_end.ru_stime-self_start.ru_utime-self_start.ru_stime,scope='campaign identity/hash/locking/controlplane; excludes separately measured physical and analysis children; finalwrite tail not measured'))
  append(ledger,dict(event='FINISH' if result['rc']==0 else 'ANALYSIS_PENDING',id=ident,time=p2_batch.now(),analysis_rc=result['rc']));write(target/'host-after.json',host_gate());print('P15_FINISH',ident,result['rc'],flush=True)
if __name__=='__main__':main()

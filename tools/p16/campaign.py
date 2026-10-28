"""One unique P16 START. Never infer retries from service disconnection."""
import os,sys,json,subprocess,time,resource,fcntl,signal
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from p16.common import *
from p9_run import host_gate
from preparation_batch import identity
from p16.workflow import Flow
CAPS=dict(development=2,main=24,replication=6)
def claim(old,row):
 ss=[r for r in old if r['event']=='START_INTENT'];assert len(ss)<32
 assert row['stage'] in CAPS and sum(r['stage']==row['stage'] for r in ss)<CAPS[row['stage']]
 assert not any(r['id']==row['id'] for r in ss),'alreadySTART: inspect, do not repeat'
 assert not [r for r in ss if not any(q.get('id')==r['id'] and q['event'] in ['FINISH','SCOPED_REVIEW_RESOLVED'] for q in old)],'unresolved own outcome'
 return len(ss)+1

def eligible(ev):
 return not any(e['event']=='failure' for e in ev) and any(e['event']=='p5_stream_ended' for e in ev) and all(any(e['event']=='p1_phase_ended' and e.get('label')==n for e in ev) for n in ['post_stream','return_classic']) and any(e['event']=='landing_requested' for e in ev) and any(e['event']=='ready' and e.get('condition')=='disarmed' for e in ev) and not any(e['event']=='process_stopped' and e.get('name')=='px4' for e in ev)

def run(row,seal_path,prediction_path=None):
 startcpu=time.process_time();all_wall=time.perf_counter();all_child0=resource.getrusage(resource.RUSAGE_CHILDREN);ledger=B/'attempts.jsonl';B.mkdir(exist_ok=True)
 with (B/'attempts.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);old=[json.loads(l) for l in ledger.read_text().splitlines()] if ledger.exists() else [];ordinal=claim(old,row);seal=json.load(open(seal_path));assert seal['status']=='PASS'
  for p,h in seal['files'].items():assert sha(R/p)==h,'source/config/runtime drift '+p
  assert sha(R/row['config'])==row['config_sha256'];adoption=verify_model_adoption(B/'model-adoption.json');host=host_gate();assert os.statvfs(R).f_bavail*os.statvfs(R).f_frsize>8*1024**3
  if row['stage']!='development':
   freeze=json.load(open(B/'freeze-receipt.json'));assert freeze['remote_verified'];assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==freeze['commit']
   for p,h in freeze['data_files'].items():assert sha(R/p)==h,'frozen plan/model/rule drift '+p
  authorization=None
  if row['stage']=='main':
   assert prediction_path is not None and prediction_path.exists(),'every main START requires a bound query/fill ticket'
   from p16.dual import authorize
   authorization=authorize(row,prediction_path)
   assert authorization['adoption_digest']==adoption['content_digest'],'query map uses another model adoption'
  if row['stage']=='replication':
   assert prediction_path is not None and prediction_path.exists(),'fixed secondseed ticket required'
   from p16.dual import authorize
   authorization=authorize(row,prediction_path)
   assert authorization['adoption_digest']==adoption['content_digest']
  target=B/'runs'/row['id'];target.mkdir(parents=True,exist_ok=False);before=identity();write(target/'candidate-before.json',before);write(target/'row.json',row);write(target/'host-before.json',host);write(target/'before-start.json',dict(time=now(),prediction=None if prediction_path is None else dict(path=str(prediction_path),sha256=sha(prediction_path)),seal=str(seal_path),seal_sha256=sha(seal_path),future_new_data_seen=False,workflow_authorization=authorization,model_adoption=adoption))
  cmd=[str(R/'tools/p16/experiment'),'p5_gap','--config',str(R/row['config']),'--output',str(target/'run'),'--condition','p11-case','--treatment','P11-Z','--sim-seed',str(row['seed']),'--initial-yaw-deg','0'];env=dict(os.environ,HANDOVER_CPU_AFFINITY='px4=8-11;gazebo=12-13;agent=6-7;runner=4-5',OPENBLAS_NUM_THREADS='1')
  for k in ['HANDOVER_P14H_TRACE_DIR','HANDOVER_P14R_TRACE_DIR']:env.pop(k,None)
  append(ledger,dict(event='START_INTENT',id=row['id'],stage=row['stage'],ordinal=ordinal,time=now(),config_sha256=row['config_sha256'],role=authorization['kind'] if authorization else row.get('role'),workflow_authorization=authorization,all_aborts_count=True));print('P16_START',ordinal,row['id'],flush=True)
  st=time.perf_counter();child=resource.getrusage(resource.RUSAGE_CHILDREN);ev=[];offset=0;buf='';sent=False;uncertain=False
  with (target/'wrapper.log').open('w') as log:
   proc=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,env=env);file=target/'run/events.jsonl'
   while proc.poll() is None:
    if file.exists():
     with file.open() as f:f.seek(offset);buf+=f.read();offset=f.tell()
     while '\n' in buf:
      line,buf=buf.split('\n',1)
      if line:ev.append(json.loads(line))
    if not sent and eligible(ev):
     gz=next(e for e in ev if e['event']=='process_started' and e['name']=='gazebo');px=next(e for e in ev if e['event']=='process_started' and e['name']=='px4');pid=gz['pid'];cmdline=Path('/proc')/str(pid)/'cmdline';disarm=next(e for e in reversed(ev) if e['event']=='ready' and e.get('condition')=='disarmed')
     if cmdline.exists() and (Path('/proc')/str(px['pid'])).exists() and b'gz' in cmdline.read_bytes() and os.getpgid(pid)==pid and time.monotonic_ns()-disarm['monotonic_ns']<500000000:
      os.killpg(pid,signal.SIGINT);sent=True;write(target/'owned-postdisarm-signal.json',dict(pid=pid,signal='SIGINT',time_ns=time.monotonic_ns(),disarmed_ns=disarm['monotonic_ns'],scope='P15 d06 verified ordering only after full scientific task, returnclassic,landing,DISARM; no liveflight intervention'))
    if time.perf_counter()-st>180:
     proc.send_signal(signal.SIGINT)
     try:proc.wait(timeout=30)
     except subprocess.TimeoutExpired:uncertain=True
     break
    time.sleep(.002 if any(e['event']=='landing_requested' for e in ev) and not sent else .03)
  after=resource.getrusage(resource.RUSAGE_CHILDREN);events=[json.loads(l) for l in file.read_text().splitlines()] if file.exists() else [];exits=[e['exit_code'] for e in events if e['event']=='process_stopped' and e['name']=='px4'];stable=identity()==before;execution=dict(wrapper_exit=proc.returncode,PX4_exit=exits,candidate_unchanged=stable,wall_s=time.perf_counter()-st,CPU_s=after.ru_utime+after.ru_stime-child.ru_utime-child.ru_stime,complete_prefix_charged=True,postdisarm_signal=sent,command=cmd);write(target/'execution.json',execution)
  append(ledger,dict(event='PHYSICAL_UNCERTAIN' if uncertain or exits!=[0] else 'PHYSICAL_END',id=row['id'],time=now(),PX4_exit=exits,candidate_unchanged=stable))
  if uncertain or exits!=[0] or not stable:raise RuntimeError('inspect owned processes, no implicitretry')
  review_start=time.perf_counter();review0=resource.getrusage(resource.RUSAGE_CHILDREN)
  with (target/'analysis.log').open('w') as out:rc=subprocess.run([str(PY),str(R/'tools/p16/analyze.py'),str(target),str(target/'analysis-v1')],stdout=out,stderr=subprocess.STDOUT).returncode
  review1=resource.getrusage(resource.RUSAGE_CHILDREN);review_cpu=review1.ru_utime+review1.ru_stime-review0.ru_utime-review0.ru_stime;review_wall=time.perf_counter()-review_start;write(target/'review-cost.json',dict(CPU_s=review_cpu,wall_s=review_wall,rc=rc))
  append(ledger,dict(event='FINISH' if rc==0 else 'ANALYSIS_PENDING',id=row['id'],time=now(),analysis_rc=rc));totalchild=review1.ru_utime+review1.ru_stime-all_child0.ru_utime-all_child0.ru_stime;write(target/'manager-cost.json',dict(CPU_s=time.process_time()-startcpu+max(0,totalchild-execution['CPU_s']-review_cpu),wall_s=time.perf_counter()-all_wall,overhead_wall_s=max(0,time.perf_counter()-all_wall-execution['wall_s']-review_wall),scope='selfCPU + git/hash children not in physical/review, walltotal components notdoublecounted',final_write_tail='unmeasured'))
  assert rc==0,'review dependency before nextSTART';write(target/'host-after.json',host_gate());return target
if __name__=='__main__':
 plan=json.load(open(sys.argv[1]));row=next(x for x in plan['rows'] if x['id']==sys.argv[2]);run(row,Path(sys.argv[3]),Path(sys.argv[4]) if len(sys.argv)>4 else None)

"""Independent P14H identities and append-only offline resource accounting."""
from pathlib import Path
import sys,json,resource,time,subprocess,datetime,os,hashlib,fcntl,atexit,uuid
R=Path(__file__).resolve().parents[2];B=R/'data/p14h-20261027';PY=R/'uav_lab/.local/venv/bin/python';sys.path.insert(0,str(R/'tools'))
from p14.common import sha,write

def register(out,question,**extra):
 out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
 write(out/'before-compute.json',{'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'question':question,'protocol_sha256':sha(R/'config/p14h/protocol-v1.json'),'source_hashes':{str(p.relative_to(R)):sha(p) for p in (R/'tools/p14h').glob('*.py')},**extra})
 return out

def limit(cpu=30,memory=24):
 resource.setrlimit(resource.RLIMIT_CPU,(cpu,cpu));resource.setrlimit(resource.RLIMIT_AS,(memory*1024**3,memory*1024**3))

def append(p,x):
 with Path(p).open('a') as f:f.write(json.dumps(x,ensure_ascii=False,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())

_SELF_MARK=0.
_ACTIVE_IDS=set()
def _manager_cpu():
 global _SELF_MARK
 r=resource.getrusage(resource.RUSAGE_SELF);now=r.ru_utime+r.ru_stime;delta=now-_SELF_MARK;_SELF_MARK=now;return delta

def _reserve(ident,cpu,command,scope):
 ledger=B/'resource-ledger-v2.jsonl'
 with (B/'resource-ledger-v2.lock').open('a') as f:
  fcntl.flock(f,fcntl.LOCK_EX)
  rows=[json.loads(l) for l in ledger.read_text().splitlines()] if ledger.exists() else []
  finished={r['id'] for r in rows if r['event']=='END'};active=sum(r['reservation_CPU_s'] for r in rows if r['event']=='BEGIN' and r['id'] not in finished)
  used=sum(r.get('CPU_s_child',0)+r.get('CPU_s_manager',0) for r in rows if r['event'] in ['END','MANAGER_FINAL'])
  legacy=json.load(open(B/'resource-transition-v2.json'))['legacy_charged_CPU_s'];assert legacy+used+active+cpu+600<=14400,'global reservations include concurrentBEGIN and validationreserve'
  append(ledger,{'event':'BEGIN','id':ident,'manager_pid':os.getpid(),'reservation_CPU_s':cpu,'scope':scope,'command':list(map(str,command)),'global_used':used,'other_active_reservations':active,'legacy_charge':legacy})

def run(command,out,cpu=30,wall=40,scope='offline',reserve_cpu=None,extra_cpu_report=None):
 out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False);ident=str(out.relative_to(R));reserved=cpu if reserve_cpu is None else reserve_cpu;_reserve(ident,reserved,command,scope);before=resource.getrusage(resource.RUSAGE_CHILDREN);start=time.perf_counter()
 guarded=[str(PY),str(R/'tools/p14h/guard.py'),str(cpu),'24',*map(str,command)]
 with (out/'process.log').open('w') as f:
  try:rc=subprocess.run(guarded,stdout=f,stderr=subprocess.STDOUT,timeout=wall).returncode
  except subprocess.TimeoutExpired:rc='WALL_LIMIT'
 after=resource.getrusage(resource.RUSAGE_CHILDREN);inner=0.;inner_source=None
 if extra_cpu_report is not None:
  p=Path(extra_cpu_report)
  if p.exists():
   values=p.read_text().strip().splitlines()[-1].split();inner=float(values[0])+float(values[1]);inner_source={'file':str(p),'user_s':float(values[0]),'system_s':float(values[1]),'RSS_kib':int(values[2]),'scope':'namespace inner worker waited by /usr/bin/time; disjoint from outer bwrap usage on this host'}
  else:inner=float(cpu);inner_source={'file':str(p),'scope':'missing inner report, full direct-worker cap charged as allowance, not measured'}
 row={'event':'END','id':ident,'CPU_s_child':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime+inner,'CPU_s_namespace_worker':inner,'namespace_meter':inner_source,'CPU_s_manager':_manager_cpu(),'wall_s':time.perf_counter()-start,'rc':rc,'reservation_CPU_s':reserved,'direct_worker_limit_CPU_s':cpu,'scope':scope,'RSS_kib_cumulative_waited_children':after.ru_maxrss,'CPU_enforcement':'RLIMIT_CPU perprocess inherited; explicitly metered namespace worker if requested. Generic subtree cap not certified; standalone scientific workers do not spawn further workers.'}
 with (B/'resource-ledger-v2.lock').open('a') as f:fcntl.flock(f,fcntl.LOCK_EX);append(B/'resource-ledger-v2.jsonl',row)
 write(out/'resource.json',row);row['CPU_s']=row['CPU_s_child']+row['CPU_s_manager'];return row

def _finish_manager():
 if not (B/'resource-ledger-v2.jsonl').exists() or _SELF_MARK==0:return
 delta=_manager_cpu()
 with (B/'resource-ledger-v2.lock').open('a') as f:
  fcntl.flock(f,fcntl.LOCK_EX);append(B/'resource-ledger-v2.jsonl',{'event':'MANAGER_FINAL','id':'pid-'+str(os.getpid()),'CPU_s_manager':delta,'scope':'finalsnapshotbeforeledgerwrite; cleanup/write tail not separatelymeasured'})
atexit.register(_finish_manager)

"""P15 independent paths, immutable outputs and append-only measured costs."""
from pathlib import Path
import sys,json,hashlib,os,time,resource,subprocess,fcntl,datetime
R=Path(__file__).resolve().parents[2];B=R/'data/p15-20261027';PY=R/'uav_lab/.local/venv/bin/python'
sys.path.insert(0,str(R/'tools'))
from p14.common import write,sha

def append(path,row):
 with Path(path).open('a') as f:f.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())

def register(path,question,**extra):
 p=Path(path).resolve();p.mkdir(parents=True,exist_ok=False);write(p/'before.json',dict(time=datetime.datetime.now(datetime.timezone.utc).isoformat(),question=question,**extra));return p

def cost_run(command,out,cpu=120,wall=180,scope='offline'):
 out=register(out,scope,command=list(map(str,command)),CPU_limit_s=cpu,wall_limit_s=wall)
 ledger=B/'costs.jsonl';ident=str(out.relative_to(R))
 with (B/'costs.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX);rows=[json.loads(l) for l in ledger.read_text().splitlines()] if ledger.exists() else [];ended={r['id'] for r in rows if r['event']=='END'};active=sum(r['reservation'] for r in rows if r['event']=='BEGIN' and r['id'] not in ended);used=sum(r.get('CPU_s',0) for r in rows if r['event']=='END');assert used+active+cpu+600<=7200,'P15 offline reservation cap';append(ledger,dict(event='BEGIN',id=ident,reservation=cpu,pid=os.getpid(),used=used,active=active))
 before=resource.getrusage(resource.RUSAGE_CHILDREN);mine=resource.getrusage(resource.RUSAGE_SELF);st=time.perf_counter()
 with (out/'process.log').open('w') as f:
  try:rc=subprocess.run([PY,R/'tools/p14h/guard.py',str(cpu),'24',*map(str,command)],stdout=f,stderr=subprocess.STDOUT,timeout=wall).returncode
  except subprocess.TimeoutExpired:rc='WALL_LIMIT'
 after=resource.getrusage(resource.RUSAGE_CHILDREN);me=resource.getrusage(resource.RUSAGE_SELF);row=dict(event='END',id=ident,CPU_s=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime+me.ru_utime+me.ru_stime-mine.ru_utime-mine.ru_stime,wall_s=time.perf_counter()-st,rc=rc,peak_child_RSS_kib=after.ru_maxrss,scope=scope,enforcement='perprocess inheritedRLIMIT; standalone workers, no namespace. Total includes waited children; controlplane tail separately reported')
 with (B/'costs.lock').open('a') as lock:fcntl.flock(lock,fcntl.LOCK_EX);append(ledger,row)
 write(out/'cost.json',row);return row

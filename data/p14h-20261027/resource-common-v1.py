"""Independent P14H identities and append-only offline resource accounting."""
from pathlib import Path
import sys,json,resource,time,subprocess,datetime,os,hashlib
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

def run(command,out,cpu=30,wall=40,scope='offline'):
 out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False);ledger=B/'resource-ledger.jsonl';old=[json.loads(l) for l in ledger.read_text().splitlines()] if ledger.exists() else [];used=sum(x.get('CPU_s',0) for x in old if x['event']=='END');assert used+cpu<=13800,'leave600CPUvalidationreserve';append(ledger,{'event':'BEGIN','id':str(out.relative_to(R)),'reservation_CPU_s':cpu,'scope':scope,'command':list(map(str,command))});before=resource.getrusage(resource.RUSAGE_CHILDREN);start=time.perf_counter()
 with (out/'process.log').open('w') as f:
  try:rc=subprocess.run(list(map(str,command)),stdout=f,stderr=subprocess.STDOUT,timeout=wall).returncode
  except subprocess.TimeoutExpired:rc='WALL_LIMIT'
 after=resource.getrusage(resource.RUSAGE_CHILDREN);row={'event':'END','id':str(out.relative_to(R)),'CPU_s':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,'wall_s':time.perf_counter()-start,'rc':rc,'reservation_CPU_s':cpu,'scope':scope,'RSS_kib_cumulative_waited_children':after.ru_maxrss};append(ledger,row);write(out/'resource.json',row);return row

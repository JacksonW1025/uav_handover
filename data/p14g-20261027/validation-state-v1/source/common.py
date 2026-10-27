import sys,json,time,datetime,resource,subprocess,os,shutil
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'));B=R/'data/p14g-20261027';OLD=R/'data/p14r-20261027';PY=R/'uav_lab/.local/venv/bin/python'
from p14.common import write,sha

def protocol():return json.load(open(R/'config/p14g/protocol-v1.json'))
def cases():return protocol()['cases']
def doc(name):return json.load(open(R/cases()[name]['input']))
def register(out,question,**extra):
 out.mkdir(parents=True,exist_ok=False);(out/'source').mkdir()
 for p in (R/'tools/p14g').glob('*.py'):shutil.copyfile(p,out/'source'/p.name)
 write(out/'before-compute.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'question':question,'protocol_sha256':sha(R/'config/p14g/protocol-v1.json'),'source':{str(p.relative_to(R)):sha(p) for p in (R/'tools/p14g').glob('*.py')},'new_SITL':0,**extra})
def limit(cpu=90,memory=24):
 resource.setrlimit(resource.RLIMIT_CPU,(cpu,cpu));resource.setrlimit(resource.RLIMIT_AS,(memory*1024**3,memory*1024**3))
def child(command,out,cpu=90,wall=110):
 out.mkdir(parents=True,exist_ok=False);start=time.perf_counter()
 with (out/'compute.log').open('w') as f:
  try:p=subprocess.run([str(PY),*command],stdout=f,stderr=subprocess.STDOUT,timeout=wall);rc=p.returncode
  except subprocess.TimeoutExpired:rc='WALL_RESOURCE_LIMIT'
 return {'command':command,'rc':rc,'wall_s':time.perf_counter()-start,'CPU_limit_s':cpu,'wall_limit_s':wall,'scope':'offline-only, no launcher'}

"""Same P14H fixed lightweight observation platform; P15 changes runner only."""
import sys,shutil,json,os,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from p15.common import *

def main():
 out=register(sys.argv[1],'P15 current version gate, real ordinary runtime snapshots, source/policy inherited unchanged');old=json.load(open(R/'data/p14h-20261027/preflight-v5/gate.json'));runtime={}
 for p,item in old['actual_runtime'].items():
  src=R/p;assert sha(src)==item['sha256'],'unexpected runtime change '+p;dst=out/Path(item['copy']).name;shutil.copyfile(src,dst);runtime[p]={'copy':str(dst.relative_to(R)),'sha256':sha(src)}
 for item in old['plugins']:
  assert sha(R/item['path'])==item['sha256'];shutil.copyfile(R/item['path'],out/Path(item['copy']).name)
 paths=[p for folder in ['tools/p15','config/p15'] for p in (R/folder).rglob('*') if p.is_file() and '__pycache__' not in str(p)];paths.extend(R/p for p in runtime)
 
 for p in paths:
  if str(p.relative_to(R)).startswith(('tools/p15/','config/p15/')):
   dst=out/'source'/p.relative_to(R);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dst)
 avail=os.statvfs(R).f_bavail*os.statvfs(R).f_frsize;assert avail>48*1024**3
 gate=dict(status='PASS',files={str(p.relative_to(R)):sha(p) for p in paths},runtime=runtime,plugins=old['plugins'],capacity_available=avail,capacity_required=48*1024**3,source_no_change_vs_H=True,control_policy_protections_unchanged=True,new_scope='same P14H passive binary/plugin; existing listener and direct execution read at decision; no new physical sampler. Logical source event B adapted before actual B, common reference constant',tests=json.load(open(B/'tests-latest.json')))
 assert gate['tests']['status']=='PASS';write(out/'gate.json',gate);gate['receipt']=str((out/'gate.json').relative_to(R));tmp=B/'preflight-current.tmp';tmp.write_text(json.dumps(gate,indent=2)+'\n');os.replace(tmp,B/'preflight-current.json')
if __name__=='__main__':main()

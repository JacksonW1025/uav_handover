"""Source closure, bounded recording format, identity and capacity before start."""
import sys,re,json,subprocess,os,datetime
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p14.common import write,sha
from p14r.observer import CORE,FUSION,read

def strip(text):
 lines=text.splitlines(keepends=True);out=[];j=0
 while j<len(lines):
  if lines[j].strip()=='#ifdef __PX4_POSIX':
   k=j+1;depth=1
   while k<len(lines) and depth:
    s=lines[k].strip()
    if s.startswith(('#if ','#ifdef ','#ifndef ')):depth+=1
    if s.startswith('#endif'):depth-=1
    k+=1
   block=''.join(lines[j:k])
   if any(x in block for x in ['P14R','p14r::','research_snapshot','research_delay']):j=k;continue
  out.append(lines[j]);j+=1
 return re.sub(r'/\*.*?\*/|//[^\n]*|\s+','', ''.join(out),flags=re.S)

def main():
 out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);old=json.load(open(R/'data/p14r-20261027/pre-change-runtime/manifest.json'));closure=[]
 for source,v in old.items():
  if '/build/' in source:continue
  a=(R/v['snapshot']).read_text();b=(R/source).read_text();closure.append({'source':source,'original':v['sha256'],'current':sha(R/source),'control_tokens_same_after_explicit_passive_block_removal':strip(a)==strip(b)})
 write(out/'source-closure.json',closure);assert all(x['control_tokens_same_after_explicit_passive_block_removal'] for x in closure)
 normal,nh=read(R/'data/p14r-20261027/buffer-host-v2/normal.bin',CORE,b'P14RCORE',allow_incomplete=False);abnormal,ah=read(R/'data/p14r-20261027/buffer-host-v2/abnormal.bin',CORE,b'P14RCORE',allow_incomplete=True)
 assert nh['count']==2 and nh['dropped']==1 and ah['count']==10 and ah['complete']==0
 capacity=json.load(open(R/'data/p14r-20261027/capacity-host-v2/audit.json'));assert capacity['prefix_sequence_exact'] and capacity['virtual_run_seconds']==300
 lifetime=json.load(open(R/'data/p14r-20261027/lifetime-host-v2/results.json'));assert len(lifetime)==20 and all(x['exit_code']==0 for x in lifetime)
 sizes={'core':CORE.itemsize,'fusion':FUSION.itemsize};assert sizes=={'core':744,'fusion':5096}
 paths=[R/'uav_lab/.local/checkouts/px4-raptor/build/px4_sitl_raptor/bin/px4',R/'config/p14r/protocol-v1.json',R/'config/p14r/protocol-v2.json',R/'config/p14r/protocol-v3.json',R/'config/p14r/protocol-v4.json',R/'config/p14r/passive-v3.json',R/'config/p14r/protocol-v5.json',R/'data/p14r-20261027/additional-plan.json']+list((R/'config/p14r/additional').glob('*.json'))+list((R/'research/state').glob('P14R*'))+list((R/'tools/p14r').glob('*.py'))+[R/'tools/apply_p14r.py',R/'tools/run_experiment.py',R/'tools/apply_research.py']
 cap=os.statvfs(R);free=cap.f_bavail*cap.f_frsize;assert free>24*1024**3
 write(out/'gate.json',{'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'PASS','source_closure':True,'host_normal_overflow_and_abnormal_prefix':True,'format_sizes':sizes,'capacity_available_bytes':free,'required_bytes':24*1024**3,'new_starts':sum(json.loads(line)['event']=='START_INTENT' for line in (R/'data/p14r-20261027/attempts.jsonl').read_text().splitlines()),'active_protocol':'config/p14r/protocol-v5.json','passive_plan':'config/p14r/passive-v3.json','fields':'actual source snapshots only; no estimator/control mutation','files':{str(p.relative_to(R)):sha(p) for p in paths}})
 print('P14R_PREFLIGHT_PASS',sizes,free)

if __name__=='__main__':main()

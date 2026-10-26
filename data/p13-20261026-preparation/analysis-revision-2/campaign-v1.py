#!/usr/bin/env python3
"""P13 count before launch; no retries/replacements; separate physical and analysis outcomes."""
import json,sys,fcntl,os,subprocess,time,shutil
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
import p2_batch
from p9_run import host_gate,append
from p9_model import write,sha
P=R/'data/p13-20261026-preparation';Z=R/'data/p13-20261026-freeze'
def counts(rows):return {k:sum(x['event']=='START_INTENT' and x['budget_class']==k for x in rows) for k in ['development','formal']}
def claim(rows,ident,kind):
 c=counts(rows)
 if kind not in c or c[kind]>={'development':12,'formal':72}[kind] or sum(c.values())>=84:raise RuntimeError('hard startup cap')
 if any(x['event']=='START_INTENT' and x['id']==ident for x in rows):raise RuntimeError('already started; never replace/retry')
 if any(x['event']=='STOP_CRITICAL' and x.get('queue')==kind for x in rows):raise RuntimeError('affected queue stopped; preserve and version before independent development')
 return sum(c.values())+1

def seal_check():
 s=json.load(open(P/'preflight-v1.json'))
 for n,h in s['files'].items():
  if sha(R/n)!=h:raise RuntimeError('preflight identity drift '+n)
 return s

def formal_rows():
 receipt=json.load(open(Z/'receipt.json'));head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()
 if head!=receipt['commit'] or head!=receipt['remote_main']:raise RuntimeError('freeze commit/remote mismatch')
 manifest=json.load(open(Z/'manifest.json'))
 for n,h in manifest['files'].items():
  if sha(R/n)!=h:raise RuntimeError('experiment layer drift '+n)
 expected=json.load(open(Z/'candidate.json'));expected['project_head']=head
 if p2_batch.identity()!=expected:raise RuntimeError('runtime identity drift')
 return json.load(open(R/'config/p13-formal.json'))['rows']

def analyze(target,kind):
 from p12c_platform.workflow import process
 from p13.physics import analyze as physical
 a=target/'analysis-v1';models=R/'data/p12-cont-20261026-freeze/models'
 measured=process(target/'run',a,models,predict=False)
 ph=physical(target/'run',a/'physics')
 if ph['status']!='PASS':raise RuntimeError('P13 physical interface not accepted '+str([k for k,v in ph['gates'].items() if not v]))
 write(target/'analysis-result-v1.json',{'schema':'p13-analysis-result-1','status':'PASS','engineering':json.load(open(a/'engineering.json'))['status'],'physics':ph['status'],'task_outcome':measured['task_outcome'],'censored':measured['censored'],'theory_status':'NOT_PROVEN_SEPARATE'})
 return measured

def execute(row,kind):
 if kind=='formal':formal_rows()
 else:seal_check()
 host=host_gate();ledger=P/'attempts.jsonl'
 with (P/'attempts.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);records=[json.loads(x) for x in ledger.read_text().splitlines()] if ledger.exists() else [];ordinal=claim(records,row['id'],kind)
  st=os.statvfs(R);avail=st.f_bavail*st.f_frsize;required=(84-sum(counts(records).values()))*600000000+30000000000
  if avail<required:raise RuntimeError('capacity insufficient, no old log deletion')
  if sha(R/row['config'])!=row['config_sha256']:raise RuntimeError('case input mismatch')
  target=R/('data/p13-20261026-development' if kind=='development' else 'data/p13-20261026-formal')/row['id'];target.mkdir(parents=True,exist_ok=False)
  plan=dict(row,directory=str((target/'run').relative_to(R)),repetition=row.get('block',1),extra_args=['--sim-seed',str(row['sim_seed']),'--initial-yaw-deg','0'])
  candidate=p2_batch.identity();write(target/'candidate.json',candidate);write(target/'plan.json',plan);write(target/'host-before.json',host)
  append(ledger,{'event':'START_INTENT','id':row['id'],'budget_class':kind,'ordinal':ordinal,'old_P12_series':66,'time':p2_batch.now(),'config_sha256':row['config_sha256'],'question':row.get('question'),'output':str(target.relative_to(R)),'available_bytes':avail,'required_bytes':required,'all_failed_invalid_count':True});print('P13_START',ordinal,kind,row['id'],flush=True);started=time.monotonic()
  try:
   p2_batch.run_one(plan,target);write(target/'wrapper-result.json',plan)
   if p2_batch.identity()!=candidate:raise RuntimeError('candidate changed during run')
   ok=all(v for k,v in plan['checks'].items() if k not in ['execution','subject_measured'])
   if not plan['checks']['execution'] and not str(plan.get('reason','')).startswith('safety:'):ok=False
   if not ok:raise RuntimeError('physical wrapper/identity/protection failure')
   write(target/'host-after.json',host_gate());append(ledger,{'event':'PHYSICAL_END','id':row['id'],'budget_class':kind,'time':p2_batch.now(),'wrapper_ok':True,'elapsed_s':time.monotonic()-started})
  except BaseException as e:
   append(ledger,{'event':'STOP_CRITICAL','id':row['id'],'budget_class':kind,'queue':kind,'time':p2_batch.now(),'reason':repr(e),'retry':'NONE inspect process/outcome first'});raise
  try:
   measured=analyze(target,kind)
  except BaseException as e:
   append(ledger,{'event':'ANALYSIS_PENDING','id':row['id'],'budget_class':kind,'time':p2_batch.now(),'reason':repr(e),'physical_result':'retained; classify implementation vs data/semantics before continuation'});raise
  write(target/'result.json',dict(plan,evidence_ok=True,task_outcome=measured['task_outcome'],censored=measured['censored'],elapsed_s=time.monotonic()-started))
  append(ledger,{'event':'FINISH','id':row['id'],'budget_class':kind,'time':p2_batch.now(),'evidence_ok':True,'task_outcome':measured['task_outcome'],'censored':measured['censored']});print('P13_FINISH',ordinal,row['id'],measured['task_outcome'],flush=True)

def main():
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--stage',choices=['development','formal'],required=True);p.add_argument('--id');a=p.parse_args()
 rows=json.load(open(P/'development-v1.json'))['rows'] if a.stage=='development' else formal_rows()
 for row in rows:
  if a.id and row['id']!=a.id:continue
  ledger=P/'attempts.jsonl';records=[json.loads(x) for x in ledger.read_text().splitlines()] if ledger.exists() else []
  if any(x['event']=='START_INTENT' and x['id']==row['id'] for x in records):
   if any(x['event']=='FINISH' and x['id']==row['id'] for x in records):continue
   raise RuntimeError('already started uncertain/analysis pending; inspect, never duplicate')
  execute(row,a.stage)
if __name__=='__main__':main()

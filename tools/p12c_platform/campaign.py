#!/usr/bin/env python3
"""P12c count every start; fixed preparation, frozen formal only; no replacements."""
import json,sys,fcntl,os,subprocess,time
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
import p2_batch
from p9_run import host_gate,append
from p9_model import sha,write
from p12c_platform.workflow import process
P=R/'data/p12c-20261026-preparation';Z=R/'data/p12c-20261026-freeze'
def claim(rows,ident,kind):
 if kind not in ['preparation','formal']:raise ValueError(kind)
 starts=[r for r in rows if r['event']=='START_INTENT']
 if any(r['id']==ident for r in starts):raise RuntimeError('already started, never retry')
 if sum(r['budget_class']==kind for r in starts)>={'preparation':12,'formal':24}[kind] or len(starts)>=36:raise RuntimeError('startup cap')
 if any(r['event']=='STOP_CRITICAL' for r in rows):raise RuntimeError('critical stop remains, no automatic next run')
 return len(starts)+1

def baseline():
 # Post-stop-only guard: actual preparation driver is archived, no new runtime.
 if (P/'formal-stop.json').exists():raise RuntimeError('P12c engineering queue is stopped; no automatic preparation/formal continuation')
 b=json.load(open(P/'baseline.json'))
 for n,h in b['old_files'].items():
  if sha(R/n)!=h:raise RuntimeError('old history changed '+n)
 seal=json.load(open(P/'preflight-seal.json'))
 for n,h in seal['files'].items():
  if sha(R/n)!=h:raise RuntimeError('sealed preflight source/config changed '+n)
 if seal['offline_status']!='PASS':raise RuntimeError('offline prerequisites not passed')
 return b

def verify_formal():
 baseline();a=json.load(open(P/'acceptance.json'))
 if a['engineering_status']!='PASS' or any(v!='PASS' for v in a['gates'].values()):raise RuntimeError('engineering not released')
 receipt=json.load(open(Z/'receipt.json'));head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()
 if head!=receipt['commit'] or head!=receipt['remote_main']:raise RuntimeError('freeze publication mismatch')
 manifest=json.load(open(Z/'manifest.json'))
 if sha(Z/'manifest.json')!=receipt['manifest_sha256']:raise RuntimeError('manifest mismatch')
 for n,h in manifest['files'].items():
  if sha(R/n)!=h:raise RuntimeError('frozen drift '+n)
 expected=json.load(open(Z/'candidate.json'));expected['project_head']=head
 if p2_batch.identity()!=expected:raise RuntimeError('frozen runtime changed')
 return json.load(open(R/'config/p12c-platform.json'))['rows']

def execute(row,kind):
 b=baseline()
 if kind=='formal':verify_formal()
 host=host_gate()
 ledger=P/'attempts.jsonl'
 with (P/'attempts.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);items=[json.loads(x) for x in ledger.read_text().splitlines()] if ledger.exists() else [];ordinal=claim(items,row['id'],kind);remaining=36-len([r for r in items if r['event']=='START_INTENT']);st=os.statvfs(R);available=st.f_bavail*st.f_frsize;required=remaining*300_000_000+22_000_000_000
  if available<required:raise RuntimeError('capacity gate, preserve all raw')
  if sha(R/row['config'])!=row['config_sha256']:raise RuntimeError('config changed')
  target=R/('data/p12c-20261026-development' if kind=='preparation' else 'data/p12c-20261026-formal')/row['id'];target.mkdir(parents=True,exist_ok=False);plan=dict(row,directory=str((target/'run').relative_to(R)),repetition=row.get('block',1),extra_args=['--sim-seed',str(row['sim_seed']),'--initial-yaw-deg','0']);candidate=p2_batch.identity();write(target/'candidate.json',candidate);write(target/'plan.json',plan);write(target/'host-before.json',host);append(ledger,{'event':'START_INTENT','id':row['id'],'budget_class':kind,'new_total_ordinal':ordinal,'old_total':56,'cumulative_ordinal':56+ordinal,'time':p2_batch.now(),'input_sha256':row['config_sha256'],'output':str(target.relative_to(R)),'available_bytes':available,'required_bytes':required,'all_failed_invalid_count':True});print('P12C_START',ordinal,kind,row['id'],flush=True);t=time.monotonic()
  try:
   p2_batch.run_one(plan,target);write(target/'wrapper-result.json',plan)
   if p2_batch.identity()!=candidate:raise RuntimeError('candidate changed during run')
   models=Z/'models' if kind=='formal' else R/'data/p12-cont-20261026-freeze/models';meas=process(target/'run',target/'analysis',models)
   ok=all(v for k,v in plan['checks'].items() if k not in ['execution','subject_measured']) and meas['status']=='MEASURED'
   if not plan['checks']['execution'] and not str(plan.get('reason','')).startswith('safety:'):ok=False
   baseline();after=host_gate();write(target/'host-after.json',after)
   if not ok:raise RuntimeError('critical wrapper/identity/protection failure')
   result=dict(plan,evidence_ok=True,flight_outcome=meas['frozen_flight_outcome'],task_outcome=meas['task_outcome'],censored=meas['censored'],elapsed_s=time.monotonic()-t);write(target/'result.json',result);append(ledger,{'event':'FINISH','id':row['id'],'budget_class':kind,'time':p2_batch.now(),'evidence_ok':True,'flight_outcome':result['flight_outcome']['outcome'],'task_outcome':result['task_outcome'],'censored':result['censored'],'elapsed_s':result['elapsed_s']});print('P12C_FINISH',ordinal,row['id'],result['task_outcome'],flush=True)
  except BaseException as e:
   append(ledger,{'event':'STOP_CRITICAL','id':row['id'],'budget_class':kind,'time':p2_batch.now(),'reason':repr(e),'retry':'NONE; inspect owned processes/outcome first'});write(target/'diagnosis.json',{'status':'STOPPED_AFFECTED_QUEUE','reason':repr(e),'counted':True,'not_started':'pending, no replacement'});raise

def main():
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--stage',choices=['preparation','formal'],required=True);a=p.parse_args();rows=json.load(open(P/'protocol.json'))['rows'] if a.stage=='preparation' else verify_formal()
 for row in rows:
  ledger=P/'attempts.jsonl';records=[json.loads(x) for x in ledger.read_text().splitlines()] if ledger.exists() else []
  if any(r['event']=='STOP_CRITICAL' for r in records):raise RuntimeError('critical queue stopped')
  if any(r['event']=='START_INTENT' and r['id']==row['id'] for r in records):
   if any(r['event']=='FINISH' and r['id']==row['id'] and r['evidence_ok'] for r in records):continue
   raise RuntimeError('uncertain or invalid prior start, inspect; never duplicate')
  execute(row,a.stage)
 if a.stage=='preparation':
  from p12c_platform.accept import main as accept
  accept(P/'acceptance.json')
if __name__=='__main__':main()

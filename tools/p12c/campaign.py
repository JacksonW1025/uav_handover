#!/usr/bin/env python3
"""Frozen P12 continuation, counted starts, distinct experimental and theory gates."""
import argparse,fcntl,json,subprocess,sys,shutil,time,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
import p2_batch
from p9_model import sha,write
from p9_run import host_gate,append
from p12c.workflow import process
PREP=ROOT/'data/p12-cont-20261026-preparation';FROZEN=ROOT/'data/p12-cont-20261026-freeze';OUT=ROOT/'data/p12-cont-20261026-formal'
def verify():
 m=json.loads((FROZEN/'manifest.json').read_text());r=json.loads((FROZEN/'receipt.json').read_text())
 head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
 if head!=r['commit'] or head!=r['remote_main'] or sha(FROZEN/'manifest.json')!=r['manifest_sha256']:raise RuntimeError('freeze commit / remote receipt mismatch')
 blob=subprocess.check_output(['git','show',head+':'+str((FROZEN/'manifest.json').relative_to(ROOT))],cwd=ROOT)
 if hashlib.sha256(blob).hexdigest()!=r['manifest_sha256']:raise RuntimeError('uncommitted freeze manifest')
 for p,h in m['files'].items():
  if sha(ROOT/p)!=h:raise RuntimeError('frozen input drift '+p)
 expected=json.loads((FROZEN/'candidate.json').read_text());expected['project_head']=head
 if p2_batch.identity()!=expected:raise RuntimeError('candidate drift')
 g=json.loads((PREP/'acceptance.json').read_text())
 if g['engineering_experimental_status']!='PASS':raise RuntimeError('engineering/design not released')
 return json.loads((ROOT/'config/p12-cont.json').read_text()),g

def claim(items,row):
 starts=[x for x in items if x['event']=='START_INTENT'];formal=[x for x in starts if x['budget_class']=='formal']
 old=[json.loads(x) for x in (ROOT/'data/p12-20261026-preparation/attempts.jsonl').read_text().splitlines()]
 if len([x for x in old if x['event']=='START_INTENT'])!=9:raise RuntimeError('old budget altered')
 if len(formal)>=48 or len(starts)>=60 or 9+len(starts)>=69:raise RuntimeError('hard budget cap')
 if any(x['id']==row['id'] for x in starts):raise RuntimeError('already started ID; never retry')
 if any(x['event'] in ['STOP','EXCEPTION'] for x in items):raise RuntimeError('prior critical error stops affected batch')
 return len(formal)+1,len(starts)+1

def execute(row,g):
 verify();host=host_gate();ledger=PREP/'attempts.jsonl'
 with (PREP/'attempts.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  items=[json.loads(s) for s in ledger.read_text().splitlines()];ordinal,total=claim(items,row)
  free=shutil.disk_usage(ROOT).free;required=g['capacity']['reserve_bytes']+(49-ordinal)*g['capacity']['per_start_bound_bytes']
  if free<required:raise RuntimeError('capacity gate before start; no deletion')
  if sha(ROOT/row['config'])!=row['config_sha256']:raise RuntimeError('config drift')
  attempt=OUT/row['id'];attempt.mkdir(parents=True,exist_ok=False)
  r=dict(row,directory=str((attempt/'run').relative_to(ROOT)),repetition=row['block'],extra_args=['--sim-seed',str(row['sim_seed']),'--initial-yaw-deg','0'])
  write(attempt/'plan.json',r);write(attempt/'host-before.json',host)
  append(ledger,{'event':'START_INTENT','id':row['id'],'budget_class':'formal','ordinal':ordinal,'continuation_ordinal':total,'cumulative_ordinal':9+total,'time':p2_batch.now(),'input_sha256':row['config_sha256'],'frozen_manifest_sha256':sha(FROZEN/'manifest.json'),'output':str(attempt.relative_to(ROOT)),'free_bytes':free,'required_remaining_bytes':required,'randomized_block':row['block'],'assigned_phase':row['phase'],'branch':row['branch'],'model_seal_sha256':sha(FROZEN/'models/seal.json'),'count_rule':'all intent/failed/aborted/invalid count'})
  print('FORMAL_START',ordinal,'/48',row['id'],flush=True);t=time.monotonic()
  try:
   p2_batch.run_one(r,attempt);write(attempt/'wrapper-result.json',r)
   measured=process(attempt/'run',attempt/'analysis',FROZEN/'models')
   infra=all(v for k,v in r['checks'].items() if k not in ['execution','subject_measured']) and measured['status']=='MEASURED'
   if not r['checks']['execution'] and not str(r.get('reason','')).startswith('safety:'):infra=False
   verify();write(attempt/'host-after.json',host_gate())
   r.update(evidence_ok=infra,flight_outcome=measured['frozen_flight_outcome'],task_outcome=measured['task_outcome'],censored=measured['censored'],elapsed_s=time.monotonic()-t)
   write(attempt/'result.json',r)
   append(ledger,{'event':'FINISH','id':row['id'],'budget_class':'formal','ordinal':ordinal,'time':p2_batch.now(),'evidence_ok':infra,'flight_outcome':r['flight_outcome']['outcome'],'task_outcome':r['task_outcome'],'censored':r['censored'],'elapsed_s':r['elapsed_s']})
   print('FORMAL_FINISH',ordinal,row['id'],r['flight_outcome']['outcome'],r['task_outcome'],'censored',r['censored'],flush=True)
   if not infra:raise RuntimeError('new critical infrastructure/evidence failure')
  except BaseException as exc:
   append(ledger,{'event':'STOP','id':row['id'],'budget_class':'formal','time':p2_batch.now(),'reason':repr(exc),'retry':'NONE; no new-version bypass'})
   write(OUT/'diagnosis.json',{'status':'STOPPED','id':row['id'],'reason':repr(exc),'remaining':'UNSTARTED_PENDING','same_semantics_recovery':'only after confirming original processes ended and explicit evidence audit; no retry of this ID'})
   raise

def main():
 p=argparse.ArgumentParser();p.add_argument('--block',type=int,required=True);a=p.parse_args();plan,g=verify();OUT.mkdir(exist_ok=True)
 for row in plan['rows']:
  if row['block']!=a.block:continue
  result=OUT/row['id']/'result.json'
  if result.exists():
   if not json.loads(result.read_text()).get('evidence_ok'):raise RuntimeError('prior invalid result')
   continue
  execute(row,g)
 items=[json.loads(s) for s in (PREP/'attempts.jsonl').read_text().splitlines()];starts=[s for s in items if s['event']=='START_INTENT'];fin=[s for s in items if s['event']=='FINISH' and s['budget_class']=='formal']
 write(OUT/f'checkpoint-block-{a.block}.json',{'block':a.block,'status':'COMPLETE','old_starts':9,'new_preparation_starts':sum(s['budget_class']=='development' for s in starts),'formal_starts':sum(s['budget_class']=='formal' for s in starts),'cumulative_starts':9+len(starts),'valid_formal_results':sum(s.get('evidence_ok',False) for s in fin),'strict_same_initial_pairs':0,'randomized_complete_blocks':a.block,'theory':'FULL_FEEDBACK_NOT_PROVEN'})
 print('BLOCK_COMPLETE',a.block,flush=True)
if __name__=='__main__':main()

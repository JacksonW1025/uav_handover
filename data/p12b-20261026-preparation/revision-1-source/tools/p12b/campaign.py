#!/usr/bin/env python3
"""Count P12b independently; no replacements, no post-error mixed-version runs."""
import argparse,fcntl,json,subprocess,sys,time,os
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
import p2_batch
from p9_run import host_gate,append
from p9_model import write,sha
P=R/'data/p12b-20261026-preparation';Z=R/'data/p12b-20261026-freeze';PY=R/'uav_lab/.local/venv/bin/python'
def claim(items,ident,kind):
 starts=[r for r in items if r['event']=='START_INTENT'];caps={'preparation':8,'formal':45}
 if any(r['id']==ident for r in starts):raise RuntimeError('already started identity; never retry')
 if sum(r['budget_class']==kind for r in starts)>=caps[kind] or len(starts)>=53:raise RuntimeError('P12b startup cap')
 if any(r['event'] in ['STOP_CRITICAL','EXCEPTION'] for r in items):raise RuntimeError('prior critical stop; no automatic continuation')
 return sum(r['budget_class']==kind for r in starts)+1

def baseline():
 b=json.load(open(P/'baseline.json'))
 if b['old_total_starts']!=48:raise RuntimeError('old count baseline')
 for name,h in b['files'].items():
  if sha(R/name)!=h:raise RuntimeError('old history changed '+name)

def verify_frozen():
 baseline();receipt=json.load(open(Z/'receipt.json'));head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()
 if head!=receipt['commit'] or head!=receipt['remote_main']:raise RuntimeError('freeze commit/remote mismatch')
 m=json.load(open(Z/'manifest.json'))
 if sha(Z/'manifest.json')!=receipt['manifest_sha256']:raise RuntimeError('manifest receipt')
 for p,h in m['files'].items():
  if sha(R/p)!=h:raise RuntimeError('frozen drift '+p)
 expected=json.load(open(Z/'candidate.json'));expected['project_head']=head
 if p2_batch.identity()!=expected:raise RuntimeError('runtime/source candidate drift')
 if json.load(open(P/'acceptance.json'))['experimental_engineering_status']!='PASS':raise RuntimeError('preparation not released')
 return json.load(open(R/'config/p12b.json'))

def baseline_analysis(run,out):
 out.mkdir(exist_ok=False)
 def tool(name,args,label):
  with (out/(label+'.log')).open('w') as f:subprocess.run(['taskset','-c','0-3',str(PY),str(R/'tools'/name),*map(str,args)],cwd=R,stdout=f,stderr=subprocess.STDOUT,check=True)
 tool('p12/observe.py',[run,'--output',out/'observation'],'observation');tool('p12/execution.py',[run,'--output',out/'execution'],'execution');tool('p11/pack.py',['measure',run,'--sync',out/'observation/synchronized.npz','--output',out/'measured'],'measure')
 return json.load(open(out/'measured/measurement.json'))

def execute(row,kind):
 baseline()
 if kind=='formal':verify_frozen()
 host=host_gate();ledger=P/'attempts.jsonl'
 with (P/'attempts.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);items=[json.loads(s) for s in ledger.read_text().splitlines()] if ledger.exists() else [];ordinal=claim(items,row['id'],kind)
  st=os.statvfs(R);available=st.f_bavail*st.f_frsize;remaining=53-len([r for r in items if r['event']=='START_INTENT']);required=22_000_000_000+remaining*600_000_000
  if available<required:raise RuntimeError('capacity gate: no deletion/decimation')
  if sha(R/row['config'])!=row['config_sha256']:raise RuntimeError('input config drift')
  target=R/('data/p12b-20261026-development' if kind=='preparation' else 'data/p12b-20261026-formal')/row['id'];target.mkdir(parents=True,exist_ok=False)
  plan=dict(row,directory=str((target/'run').relative_to(R)),repetition=row.get('block',1),extra_args=['--sim-seed',str(row['sim_seed']),'--initial-yaw-deg','0'])
  before=p2_batch.identity();lib=R/json.load(open(R/row['config']))['p12b']['solver_library'];libhash=sha(lib);write(target/'candidate.json',before);write(target/'plan.json',plan);write(target/'host-before.json',host)
  append(ledger,{'event':'START_INTENT','id':row['id'],'budget_class':kind,'ordinal':ordinal,'new_total_ordinal':len([r for r in items if r['event']=='START_INTENT'])+1,'old_total_starts':48,'cumulative_ordinal':49+len([r for r in items if r['event']=='START_INTENT']),'time':p2_batch.now(),'input_sha256':row['config_sha256'],'observer_sha256':libhash,'output':str(target.relative_to(R)),'available_bytes':available,'required_bytes':required,'source_id':row.get('source_id'),'count_rule':'all intent/failed/invalid; no replacement'})
  print('P12B_START',kind,ordinal,row['id'],'old48',flush=True);start=time.monotonic()
  try:
   p2_batch.run_one(plan,target);write(target/'wrapper-result.json',plan)
   if p2_batch.identity()!=before or sha(lib)!=libhash:raise RuntimeError('candidate changed during flight')
   cfg=json.load(open(R/row['config']))
   if cfg['p12b']['observe']:
    from p12b.workflow import process
    models=Z/'models' if kind=='formal' else R/'data/p12-cont-20261026-freeze/models'
    measured=process(target/'run',target/'analysis',models)
   else:measured=baseline_analysis(target/'run',target/'analysis')
   ok=all(v for k,v in plan['checks'].items() if k not in ['execution','subject_measured']) and measured['status']=='MEASURED'
   if not plan['checks']['execution'] and not str(plan.get('reason','')).startswith('safety:'):ok=False
   baseline();write(target/'host-after.json',host_gate())
   if not ok:raise RuntimeError('new critical infrastructure/evidence failure')
   result=dict(plan,evidence_ok=True,flight_outcome=measured['frozen_flight_outcome'],task_outcome=measured['task_outcome'],censored=measured['censored'],elapsed_s=time.monotonic()-start,theory='NOT_PROVEN_FULL_FEEDBACK')
   write(target/'result.json',result);append(ledger,{'event':'FINISH','id':row['id'],'budget_class':kind,'ordinal':ordinal,'time':p2_batch.now(),'evidence_ok':True,'flight_outcome':result['flight_outcome']['outcome'],'task_outcome':result['task_outcome'],'censored':result['censored'],'elapsed_s':result['elapsed_s']});print('P12B_FINISH',kind,ordinal,row['id'],result['task_outcome'],flush=True)
  except BaseException as e:
   append(ledger,{'event':'STOP_CRITICAL','id':row['id'],'budget_class':kind,'time':p2_batch.now(),'reason':repr(e),'retry':'NONE; inspect evidence and owned process status'});write(target/'diagnosis.json',{'status':'STOPPED','reason':repr(e),'remaining':'UNSTARTED_PENDING','uncertain':'check exact owned processes if no complete wrapper'});raise

def main():
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--prep',type=int);g.add_argument('--formal',action='store_true');a=p.parse_args()
 if a.prep:
  if not 1<=a.prep<=8:raise ValueError('preparation ordinal')
  execute(json.load(open(P/'protocol.json'))['rows'][a.prep-1],'preparation')
 else:
  plan=verify_frozen()
  for row in plan['rows']:
   records=[json.loads(s) for s in (P/'attempts.jsonl').read_text().splitlines()]
   if any(r['event']=='START_INTENT' and r['id']==row['id'] for r in records):
    if any(r['event']=='FINISH' and r['id']==row['id'] and r.get('evidence_ok') for r in records):continue
    raise RuntimeError('started item not accepted; inspect, never retry')
   execute(row,'formal')
if __name__=='__main__':main()

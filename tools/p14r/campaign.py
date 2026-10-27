"""P14R counted persistent-session launcher. One item, then evidence review.
No blanket stop on scientific/analysis failure; no replacement or blind retry.
"""
import sys,json,fcntl,time,os,subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p9_run import host_gate,append
from p14.common import write,sha
import p2_batch
BASE=R/'data/p14r-20261027'

def main():
 ident=sys.argv[1];plans=json.load(open(R/'config/p14r/passive-v3.json'))['rows']
 extra=BASE/'additional-plan.json'
 if extra.exists():plans+=json.load(open(extra))['rows']
 row=next(x for x in plans if x['id']==ident);ledger=BASE/'attempts.jsonl'
 with (BASE/'attempts.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);old=[json.loads(l) for l in ledger.read_text().splitlines()] if ledger.exists() else [];starts=[x for x in old if x['event']=='START_INTENT']
  if len(starts)>=8 or any(x['id']==ident for x in starts):raise RuntimeError('budget/duplicate identity; inspect old outcome, no replacement')
  unresolved=[x for x in starts if not any(y.get('id')==x['id'] and y['event'] in ['PHYSICAL_END','FINISH','DATA_QUARANTINE','ANALYSIS_PENDING','OUTCOME_RESOLVED'] for y in old)]
  if unresolved:raise RuntimeError('old process/physical outcome unresolved '+str(unresolved))
  host=host_gate();stat=os.statvfs(R);avail=stat.f_bavail*stat.f_frsize
  if avail<16*1024**3:raise RuntimeError('capacity gate; no deletion')
  gate=json.load(open(BASE/'preflight-current.json'));assert gate['status']=='PASS'
  for name,h in gate['files'].items():
   if sha(R/name)!=h:raise RuntimeError('preflight source/binary identity changed '+name)
  assert sha(R/row['config'])==row['config_sha256'];target=BASE/'runs'/ident;target.mkdir(parents=True,exist_ok=False)
  plan=dict(row,directory=str((target/'run').relative_to(R)),repetition=1,extra_args=['--sim-seed',str(row['seed']),'--initial-yaw-deg','0'])
  candidate=p2_batch.identity();write(target/'candidate.json',candidate);write(target/'plan.json',plan);write(target/'host-before.json',host)
  append(ledger,{'event':'START_INTENT','id':ident,'ordinal':len(starts)+1,'time':p2_batch.now(),'source':row.get('source'),'question':row['question'],'config_sha256':row['config_sha256'],'output':str(target.relative_to(R)),'available_bytes':avail,'all_failures_count':True});print('P14R_START',len(starts)+1,'/8',ident,flush=True);st=time.monotonic()
  try:
   p2_batch.run_one(plan,target);write(target/'wrapper.json',plan)
   stable=p2_batch.identity()==candidate
   ended=plan.get('px4_exit_codes')==[0]
   append(ledger,{'event':'PHYSICAL_END' if ended else 'PHYSICAL_UNCERTAIN','id':ident,'time':p2_batch.now(),'elapsed_s':time.monotonic()-st,'candidate_unchanged':stable,'px4_exit_codes':plan.get('px4_exit_codes'),'wrapper_reason':plan.get('reason')})
   if not stable or not ended or plan.get('crash_markers'):raise RuntimeError('identity/process/control failure; inspect affected scope')
   write(target/'host-after.json',host_gate())
  except BaseException as e:
   append(ledger,{'event':'EXECUTION_REVIEW_REQUIRED','id':ident,'time':p2_batch.now(),'error':repr(e),'retry':'NONE: inspect owned processes and ledger first'});raise
  try:
   from p14r.observer import audit
   obs=audit(target/'run',target/'observer-audit-v1')
   from p12c_platform.workflow import process
   measured=process(target/'run',target/'analysis-v1',R/'data/p12-cont-20261026-freeze/models',predict=False)
   from p13.physics import analyze
   ph=analyze(target/'run',target/'analysis-v1/physics')
   if ph['status']!='PASS':raise RuntimeError('physical interface evidence failed')
   write(target/'information.json',{'id':ident,'observer':obs['status'],'engineering':'PASS','physics':ph['status'],'scientific_task':measured['task_outcome'],'censored':measured['censored'],'new_data_role':'passive diagnostic, no independent prospective claim','elapsed_s':time.monotonic()-st,'obtained':['OutputPredictor full buffers/corrections+integrals/prepost','gyro delays/bias/device','canonical read/cache/native/commit','same-step physical body/rotor'],'not_obtained':['full EKF covariance/fusion internals beyond output target state'],'next':'review numerical source replay and information before next start'})
   append(ledger,{'event':'FINISH','id':ident,'time':p2_batch.now(),'task_outcome':measured['task_outcome'],'censored':measured['censored'],'information':'observer/engineering/physics audited'});print('P14R_FINISH',ident,measured['task_outcome'],flush=True)
  except BaseException as e:
   append(ledger,{'event':'ANALYSIS_PENDING','id':ident,'time':p2_batch.now(),'error':repr(e),'raw':'preserved; distinguish missing/identity vs deterministic analysis implementation; no duplicate flight'});raise

if __name__=='__main__':main()

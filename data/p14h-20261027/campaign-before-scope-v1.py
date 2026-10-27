"""One counted P14H headless SITL item thenmandatoryraw/evidence review."""
import sys,json,fcntl,subprocess,time,os
import numpy as np
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from p14h.common import *
from p9_run import host_gate
import p2_batch

def main():
 ident=sys.argv[1];plan=Path(sys.argv[2]);rows=json.load(open(plan))['rows'];row=next(r for r in rows if r['id']==ident);ledger=B/'attempts.jsonl'
 with (B/'attempts.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);old=[json.loads(l) for l in ledger.read_text().splitlines()] if ledger.exists() else [];starts=[x for x in old if x['event']=='START_INTENT'];cls=row['budget_class'];assert cls in ['mechanism','independent'];assert len(starts)<16 and sum(x['budget_class']==cls for x in starts)<{'mechanism':4,'independent':12}[cls];assert not any(x['id']==ident for x in starts),'alreadycounted no replacement'
  unresolved=[x for x in starts if not any(y.get('id')==x['id'] and y['event'] in ['FINISH','DATA_QUARANTINE','ANALYSIS_PENDING','OUTCOME_RESOLVED'] for y in old)];assert not unresolved,'oldoutcomeunresolved, inspectownedprocessfirst'
  host=host_gate();gate=json.load(open(B/'preflight-current.json'));assert gate['status']=='PASS'
  for p,h in gate['files'].items():assert sha(R/p)==h,'preflightidentitydrift '+p
  assert sha(R/row['config'])==row['config_sha256'];assert os.statvfs(R).f_bavail*os.statvfs(R).f_frsize>16*1024**3
  target=B/'runs'/ident;target.mkdir(parents=True,exist_ok=False);runout=target/'run';candidate=p2_batch.identity();write(target/'candidate.json',candidate);write(target/'plan.json',row);write(target/'host-before.json',host)
  command=[str(R/'tools/p14h/experiment'),row['kind'],'--config',str(R/row['config']),'--output',str(runout),'--condition',row['condition'],'--treatment',row['treatment'],'--sim-seed',str(row['seed']),'--initial-yaw-deg','0'];append(ledger,{'event':'START_INTENT','id':ident,'budget_class':cls,'ordinal':len(starts)+1,'time':p2_batch.now(),'config_sha256':row['config_sha256'],'prestart_prediction':row['prestart_prediction'],'allfailurescount':True,'output':str(target.relative_to(R))});print('P14H_START',len(starts)+1,ident,flush=True);st=time.perf_counter();before=resource.getrusage(resource.RUSAGE_CHILDREN)
  with (target/'wrapper.log').open('w') as f:rc=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,env=dict(os.environ,HANDOVER_CPU_AFFINITY='px4=8-11;gazebo=12-13;agent=6-7;runner=4-5')).returncode
  after=resource.getrusage(resource.RUSAGE_CHILDREN);events=[json.loads(l) for l in (runout/'events.jsonl').read_text().splitlines()] if (runout/'events.jsonl').exists() else [];exits=[x['exit_code'] for x in events if x['event']=='process_stopped' and x['name']=='px4'];stable=candidate==p2_batch.identity();write(target/'execution-result.json',{'wrapper_exit':rc,'PX4_exit_codes':exits,'candidate_unchanged':stable,'physical_wall_s':time.perf_counter()-st,'CPU_s_wrapper_and_children':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,'command':command});append(ledger,{'event':'PHYSICAL_END' if exits==[0] else 'PHYSICAL_UNCERTAIN','id':ident,'time':p2_batch.now(),'PX4_exit_codes':exits,'candidate_unchanged':stable})
  if exits!=[0] or not stable:append(ledger,{'event':'EXECUTION_REVIEW_REQUIRED','id':ident,'reason':'process/identity, inspectownedprocesses noautorerun'});return
  try:
   from p14r.observer import audit
   observer=audit(runout,target/'observer-audit-v1')
   from p12c_platform.workflow import process
   measured=process(runout,target/'analysis-v1',R/'data/p12-cont-20261026-freeze/models',predict=False)
   from p13.physics import analyze
   physical=analyze(runout,target/'analysis-v1/physics');assert physical['status']=='PASS'
   from p14h.snapshot import read
   a,h=read(runout/'gz-motor/ekf-p14h.bin');assert h['dropped']==h['errors']==0 and len(a)>0;d=json.load(open(target/'observer-audit-v1/audit.json'));begin,end=d['active_host_interval_ns'];assert a['wall_ns'][0]<=begin and a['wall_ns'][-1]+16000000>=end;assert np.all(a['ndof']==24) and np.all(a['nstate']==25)
   # FullcrossP finite andsymmetric, independentofdiagonal-onlyULog.
   cov=a['covariance'][:,:24,:24];assert np.isfinite(cov).all();sym=float(np.max(abs(cov-cov.transpose(0,2,1))));assert sym<1e-5
   write(target/'snapshot-audit-v1.json',{'status':'PASS','header':h,'rows':len(a),'ndof':24,'nstate':25,'full_crossP_symmetry_max':sym,'full_active_coverage':True,'source_stage':'afterEKFupdate beforeLPpublish','not_full_EKF_restore':'aidingqueue/auxfilters unrecorded; noallfutureclosedclaim'});write(target/'information.json',{'engineering':'PASS','task_outcome':measured['task_outcome'],'censored':measured['censored'],'observer':observer['status'],'physics':physical['status'],'snapshot':'PASS','role':cls,'initial_difference_preserved':True});append(ledger,{'event':'FINISH','id':ident,'time':p2_batch.now(),'task_outcome':measured['task_outcome'],'censored':measured['censored']});write(target/'host-after.json',host_gate());print('P14H_FINISH',ident,measured['task_outcome'],flush=True)
  except BaseException as e:append(ledger,{'event':'ANALYSIS_PENDING','id':ident,'time':p2_batch.now(),'error':repr(e),'scope':'isolateaffecteddata/analysis; no duplicateflight'});raise
if __name__=='__main__':main()

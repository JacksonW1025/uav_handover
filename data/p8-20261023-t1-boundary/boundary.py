import sys,os,json,pathlib,copy,hashlib,subprocess,time,fcntl,traceback
ROOT=pathlib.Path('/home/car/uav_handover');OUT=pathlib.Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/p8')]
import p8_conditions as cond,p8_batch,p2_batch
from p2_batch import identity,host_state,now
sha=lambda b:hashlib.sha256(b).hexdigest()
def save(n,v):(OUT/n).write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
def prepare():
 if (OUT/'plan.json').exists():raise RuntimeError('plan exists; refusing replacement')
 cfg=json.loads((ROOT/'config/p8.json').read_text());old=sum([json.loads((ROOT/f'data/p8-20261022-batch-{b}/results.json').read_text())['runs'] for b in ['b1','b2']],[])
 names=['contest-T1-s1-k20','contest-T1-s0-k27','ours-T1-s0-k21','ours-T1-s0-k01'];sources={n:next(x for x in old if x['id']==n) for n in names};seeds={n:[int(sha(f'p8-t1-boundary-20261023/{n}/{rep}'.encode())[:8],16)&0x7fffffff for rep in range(3)] for n in names};assert len(set(z for a in seeds.values() for z in a))==12
 rows=[]
 groups=[(n,0.) for n in names];variants=[(n,d) for n in [names[0],names[3]] for d in [-.05,.05]]
 for stage,gs in [('repeat',groups),('perturb',variants)]:
  for rep in range(3):
   for n,delta in gs:
    source=sources[n];case=copy.deepcopy(source['case']);case['restored'][0]=round(case['restored'][0]+delta,6);check=cond.budget_check(cfg,case,'T1');base=cond.budget_check(cfg,source['case'],'T1');assert check['equal'] and check['runner_budget']==base['runner_budget'] and check['safety_budget_m']['inside'];name=cond.case_condition(case,'T1');rid=f'{stage}-{n}-d{delta:+.2f}-r{rep+1}'
    rows.append({'id':rid,'kind':'p5_gap','condition':name,'treatment':'T1','config':'config/p8.json','repetition':rep+1,'directory':str(OUT/'runs'/rid),'status':'NOT_RUN','source_id':n,'source_directory':source['directory'],'stage':stage,'delta_first_restored_s':delta,'case':case,'original_case':source['case'],'budget_check':check,'sim_seed':seeds[n][rep],'extra_args':['--sim-seed',str(seeds[n][rep])],'initial_yaw_deg':None})
 save('plan.json',{'created_at':now(),'exploratory':True,'max_new_flights':24,'purpose':'Repeat fixed T1 inputs and perturb only first restored interval; no method tuning or ranking claim','seed_rule':'12 independent SHA256-derived seeds, shared between baseline and +/- variants for same case/replicate','rules':{'no_reruns':True,'infra_failure_stops':True,'identity_drift_stops':True,'concurrent_work_stops':True,'remote_session_wait_max_s':900,'flight_failures_are_results':True,'no_real_hardware':True,'primary':'unchanged P6 frozen flight criteria','task':'unchanged tilt>=45 or altitude loss>1m','no_change':['model','controller','failure criteria','export tolerance','core runner']},'sources':sources,'runs':rows})
 save('candidate.json',identity());save('host-before.json',host_state());diff=subprocess.check_output(['git','diff','--binary'],cwd=ROOT);(OUT/'preexisting-worktree.patch').write_bytes(diff);save('fingerprints.json',{'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'diff_sha256':sha(diff),'status':subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True),'plan_sha256':sha((OUT/'plan.json').read_bytes()),'driver_sha256':sha(pathlib.Path(__file__).read_bytes())});print('PLAN READY',now(),len(rows),flush=True)
def conflicts():
 text=subprocess.check_output(['ps','-eo','pid=,args='],text=True);bad=[]
 for line in text.splitlines():
  pid,_,args=line.strip().partition(' ')
  if int(pid)==os.getpid():continue
  parts=args.split()
  if not parts:continue
  exe=pathlib.Path(parts[0]).name
  if (exe.startswith('python') and any(t in args for t in ['run_experiment.py','p8_campaign.py','p8_audit.py','p8_export.py'])) or exe in ['px4','MicroXRCEAgent'] or args.startswith('gz sim '):bad.append(line.strip())
 return bad
def run():
 lock=(OUT/'batch.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 plan=json.loads((OUT/'plan.json').read_text());rows=plan['runs'];candidate=json.loads((OUT/'candidate.json').read_text());assert not (OUT/'results.json').exists();started=now();done=0
 def persist(complete=False,reason=None):save('results.json',{'started_at':started,'updated_at':now(),'complete':complete,'stop_reason':reason,'completed':done,'planned':24,'runs':rows})
 persist()
 for row in rows:
  bad=conflicts()
  if bad:persist(reason={'concurrent_work':bad});return
  t=time.monotonic()
  while subprocess.run(['pgrep','-x','ToDesk_Session'],capture_output=True).stdout.strip():
   print('WAIT remote desktop',now(),flush=True)
   if time.monotonic()-t>900:persist(reason='remote desktop remained connected');return
   time.sleep(30)
  if identity()!=candidate:persist(reason='IDENTITY_DRIFT');return
  row['remote_desktop_session_at_start']=False
  print('START',done+1,row['id'],now(),flush=True)
  try:p8_batch.run_row(row,OUT)
  except Exception as ex:row['error']=repr(ex);traceback.print_exc();persist(reason='run/analyzer exception');return
  row['remote_desktop_session_at_end']=bool(subprocess.run(['pgrep','-x','ToDesk_Session'],capture_output=True).stdout.strip());done+=1;persist()
  print('END',done,row['id'],'infra',row.get('infrastructure_ok'),'primary',row.get('fail_primary'),'task',row.get('fail_task'),now(),flush=True)
  if row['remote_desktop_session_at_end'] or not row.get('infrastructure_ok') or not (row.get('accepted') or row.get('flight_failure')):persist(reason='infrastructure/evidence/session failure; no rerun');return
 persist(complete=True);save('host-after.json',host_state());print('COMPLETE',now(),flush=True)
if __name__=='__main__':prepare() if sys.argv[1]=='prepare' else run()

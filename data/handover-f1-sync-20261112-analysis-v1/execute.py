import os,json,time,hashlib,subprocess,sys
from pathlib import Path
R=Path('/home/car/uav_handover');A=Path(__file__).parent;B=R/'data/handover-f1-sync-20261112';PY=R/'uav_lab/.local/venv/bin/python';ENV=dict(os.environ,OPENBLAS_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):
 if p.exists():raise RuntimeError('immutable exists '+str(p))
 p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def run(plan):
 for name,spec in load(plan)['cases'].items():
  f=B/(name+'-a1');out=A/(name+'-a1')
  if (out/'audit.json').exists():continue
  if f.exists():raise RuntimeError('unresolved existing '+str(f))
  dump(B/(name+'-prelaunch.json'),{'created_ns':time.time_ns(),'plan_sha256':sha(plan),'execute_sha256':sha(Path(__file__)),'experience_runner_sha256':sha(A/'f1_runner.py'),'launcher_sha256':sha(A/'experiment.sh'),'name':name})
  with (B/(name+'-a1-console.log')).open('x') as log:
   print('START',name,flush=True);rc=subprocess.call(['bash',str(A/'experiment.sh'),'--plan',str(plan),'--case',name,'--attempt','a1','--execute'],cwd=R,stdout=log,stderr=subprocess.STDOUT,env=ENV)
  if rc:raise RuntimeError('infrastructure exit '+str(rc))
  result=load(f/'result.json')
  if not result['candidate_unchanged'] or result['cleanup_error']:raise RuntimeError('identity/cleanup')
  if result.get('reason') and 'safety' not in result['reason'].lower():raise RuntimeError('infrastructure '+result['reason'])
  cmd=['taskset','-c','0-3',str(PY),str(A/'score.py'),'--run',str(f/'flight'),'--out',str(out)]
  if spec.get('classic_capture_control'):cmd+=['--classic-event','f1_classic_continues']
  subprocess.run(cmd,cwd=R,env=ENV,check=True,stdout=subprocess.DEVNULL)
  subprocess.run(['taskset','-c','0-3',str(PY),str(A/'audit.py'),'--score-dir',str(out),'--out',str(out/'audit.json')],cwd=R,env=ENV,check=True,stdout=subprocess.DEVNULL)
  s=load(out/'score.json');a=load(out/'audit.json')
  if not a['ulog_hash_matches_metadata'] or not a['four_motors_observed'] or s['dropouts']:raise RuntimeError('integrity')
  print('DONE',name,'peak',s['physical']['peak_tilt_deg'],'physical',s['physical_task'],'execution',result['execution_status'],flush=True)
if __name__=='__main__':run(Path(sys.argv[1]))

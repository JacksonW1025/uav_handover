import sys,time,datetime,subprocess,json
from pathlib import Path
sys.path.insert(0,'tools')
from p9_run import host_gate
b=Path('data/p16-20261028')
for i in range(120):
 try:
  state=host_gate()
 except RuntimeError as e:
  if not str(e).startswith('WAIT_HOST:'):raise
  print(datetime.datetime.now(datetime.timezone.utc).isoformat(),str(e),flush=True);time.sleep(30);continue
 (b/'host-release-before-main.json').write_text(json.dumps(dict(time=datetime.datetime.now(datetime.timezone.utc).isoformat(),host=state,condition='originalhostgate now passes, no ownedprocessadoption'),indent=2)+'\n')
 with (b/'orchestration-v2.log').open('w') as f:rc=subprocess.run([sys.executable,'-m','p16.orchestrate'],stdout=f,stderr=subprocess.STDOUT).returncode
 print('ORCHESTRATOR_EXIT',rc,flush=True);raise SystemExit(rc)
raise RuntimeError('hostpending3600s noSTART')

import pathlib,json,hashlib,subprocess,datetime,os
ROOT=pathlib.Path('/home/car/uav_handover');OUT=pathlib.Path(__file__).resolve().parent
now=lambda:datetime.datetime.now().astimezone().isoformat()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
rows=[];protected=[]
for stage in ['b1','b2']:
 b=ROOT/f'data/p8-20261022-batch-{stage}';rows+=json.loads((b/'results.json').read_text())['runs'];protected += [b/'results.json',b/'batch-audit.json']
protected += [ROOT/'data/p8-20261022-batch-b2/diagnosis.json',ROOT/'data/p8-20261022-batch-b2/export-diagnosis.json']
protected+=list((ROOT/'data/p8-20261022-batch-b2/export-failure-scene').rglob('*'))
protected=[p for p in protected if p.is_file()]
protected += [ROOT/r['directory']/'p8-metrics.json' for r in rows]
before={str(p):sha(p) for p in protected};start=now();(OUT/'baseline.json').write_text(json.dumps({'started_at':start,'hashes':before,'sources':{p:sha(ROOT/p) for p in ['tools/p6_export.py','tools/p8_export.py']}},indent=1))
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH='tools')
cmd=[str(ROOT/'uav_lab/.local/venv/bin/python'),'tools/p8_export.py','data/p8-20261022-batch-b1','data/p8-20261022-batch-b2','--out',str(OUT/'exports')]
with (OUT/'export.log').open('w') as f:rc=subprocess.run(cmd,cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT).returncode
report={'started_at':start,'finished_at':now(),'command':cmd,'returncode':rc,'protected_files_unchanged':all(sha(pathlib.Path(p))==h for p,h in before.items())}
if rc==0:
 m=json.loads((OUT/'exports/manifest.json').read_text());bad=[];mismatch=[];maxp=maxv=0;unmatched=0
 for r in rows:
  n=pathlib.Path(r['directory']).name;s=json.loads((OUT/'exports'/n/'summary.json').read_text());z=s['reconstruction'];maxp=max(maxp,z['position_max_abs'] or 0);maxv=max(maxv,z['velocity_max_abs'] or 0);unmatched+=z['rows_unmatched']
  if z['components_over_1e-4'] or z['rows_unmatched']:bad.append(n)
  if s['fail_primary']!=r['fail_primary'] or s['fail_task']!=r['fail_task']:mismatch.append(n)
 report.update(checked=len(rows),manifest_runs=len(m['runs']),passed=len(rows)-len(bad),failed=bad,statistics_mismatches=mismatch,max_position_residual=maxp,max_velocity_residual=maxv,unmatched_rows=unmatched,primary_failures=sum(bool(r['fail_primary']) for r in rows),task_failures=sum(bool(r['fail_task']) for r in rows))
report['source_files_unchanged_during_run']=json.loads((OUT/'baseline.json').read_text())['sources']=={p:sha(ROOT/p) for p in ['tools/p6_export.py','tools/p8_export.py']}
(OUT/'verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

import pathlib,time,subprocess,json,sys
root=pathlib.Path('/home/car/uav_handover');py=root/'uav_lab/.local/venv/bin/python';b=root/'data/p8-20261022-batch-b2'
while pathlib.Path('/proc/1380846').exists():time.sleep(10)
r=json.loads((b/'results.json').read_text())
if not (r.get('complete') and r.get('status')=='PASS' and len(r['runs'])==450 and r.get('candidate_unchanged')):
 print('STOP: resume incomplete or failed; preserve scene',flush=True);sys.exit(1)
for stage in ['b1','b2']:
 log=root/f'data/p8-20261022-{stage}-final-audit.log'
 with log.open('w') as f:
  rc=subprocess.run([str(py),'tools/p8_audit.py',f'data/p8-20261022-batch-{stage}','--jobs','8'],cwd=root,stdout=f,stderr=subprocess.STDOUT).returncode
 print('audit',stage,rc,flush=True)
 if rc or not json.loads((root/f'data/p8-20261022-batch-{stage}/batch-audit.json').read_text()).get('passed'):sys.exit(2)
with (root/'data/p8-20261022-b-final-export.log').open('w') as f:
 rc=subprocess.run([str(py),'tools/p8_export.py','data/p8-20261022-batch-b1','data/p8-20261022-batch-b2'],cwd=root,stdout=f,stderr=subprocess.STDOUT).returncode
if rc:sys.exit(3)
m=json.loads((root/'export/manifest.json').read_text())
for stage in ['b1','b2']:
 rows=json.loads((root/f'data/p8-20261022-batch-{stage}/results.json').read_text())['runs']
 for row in rows:
  if not (row.get('accepted') or row.get('flight_failure')):continue
  run=pathlib.Path(row['directory']).name;e=m['runs'][run]
  assert e['reconstruction_components_over_1e-4']==0,run
  assert e['trace_bytes']<=150000,run
print('900 exports verified',flush=True)
subprocess.run([str(py),'tools/p8_report.py','--b','data/p8-20261022-batch-b1','data/p8-20261022-batch-b2','--state','data/p8-20261022-b-state'],cwd=root,check=True)
print('READY FOR REPORT REVIEW AND COMMIT',flush=True)

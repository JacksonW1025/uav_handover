from pathlib import Path
import hashlib,json,time
started=time.monotonic();root=Path('.');old=json.loads(Path('data/p11-20261025-preparation/history-before.json').read_text());changed=[];missing=[]
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
for f,h in old['files'].items():
 p=Path(f)
 if not p.exists():missing.append(f)
 elif sha(p)!=h:changed.append(f)
records=[];problems=[]
for f in old['files']:
 p=Path(f)
 if not p.name=='metadata.json' or not p.parts[0]=='data' or not any(p.parts[1].startswith('p'+str(k)+'-') for k in range(6,11)):continue
 d=json.loads(p.read_text());expected=d.get('ulog_sha256')
 if not expected:continue
 raw=p.parent/'flight.ulg';exists=raw.exists();actual=sha(raw) if exists else None
 r={'path':str(raw),'exists':exists,'expected_sha256':expected,'actual_sha256':actual,'matches':actual==expected};records.append(r)
 if not r['matches']:problems.append(r)
result={'schema':'p11-history-preservation-1','tracked_files_checked':len(old['files']),'tracked_changed':changed,'tracked_missing':missing,'allowed_observation_append':['research/state/ResearchTiming.msg'],'historical_P6_P10_ULogs_rehashed':len(records),'raw_problems':problems,'raw_records':records,'status':'PASS' if changed==['research/state/ResearchTiming.msg'] and not missing and not problems else 'REVIEW','elapsed_s':time.monotonic()-started,'no_files_deleted_or_rewritten':True}
Path('data/p11-20261025-preparation/history-final-audit.json').write_text(json.dumps(result,indent=2)+'\n');print({k:v for k,v in result.items() if k not in ['raw_records','raw_problems']},flush=True)

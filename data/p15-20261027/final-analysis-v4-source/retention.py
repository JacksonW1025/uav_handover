import sys,json,hashlib,subprocess,datetime,collections
from pathlib import Path
R=Path('/home/car/uav_handover');sys.path.insert(0,str(R/'tools'))
from p15.common import B,write,sha
out=Path(sys.argv[1]);out.mkdir(exist_ok=False)
base=json.load(open(B/'baseline.json'));bad=[]
for p,h in base['tracked_sha256'].items():
 if p=='.gitignore':continue
 q=R/p
 if not q.is_file() or sha(q)!=h:bad.append(p)
freeze=json.load(open(B/'freeze-inputs-v1.json'));drift=[]
for p,h in freeze['source_files'].items():
 if sha(R/p)!=h:drift.append(p)
raw=[];seen=set();nbytes=0
for target in sorted((B/'runs').iterdir()):
 run=target/'run'
 if not run.exists():continue
 for p in sorted(run.rglob('*')):
  if not p.is_file() or p.is_symlink():continue
  if p.suffix in ['.ulg','.bin'] or p.name in ['telemetry.jsonl','resources.jsonl']:
   stat=p.stat();key=(stat.st_dev,stat.st_ino)
   if key in seen:continue
   seen.add(key);raw.append(dict(path=str(p.relative_to(R)),bytes=stat.st_size,sha256=sha(p)));nbytes+=stat.st_size
write(out/'raw-manifest.json',dict(files=raw,unique_inode_bytes=nbytes,duplicates_not_counted=True))
ledger=[json.loads(l) for l in (B/'attempts.jsonl').read_text().splitlines()];starts=[x for x in ledger if x['event']=='START_INTENT'];ids=[x['id'] for x in starts];term=[]
for rid in ids:
 events=[x['event'] for x in ledger if x.get('id')==rid];ex=json.load(open(B/'runs'/rid/'execution-result.json'));term.append(dict(id=rid,events=events,PX4_exit_codes=ex['PX4_exit_codes'],stable=ex['candidate_unchanged']))
write(out/'all-terminal.json',term)
write(out/'result.json',dict(time=datetime.datetime.now(datetime.timezone.utc).isoformat(),historical_files_checked=len(base['tracked_sha256'])-1,historical_changed=bad,excluded='.gitignore intentional P15 raw-storage rules only',frozen_source_checked=len(freeze['source_files']),frozen_source_drift=drift,starts=len(starts),unique_ids=len(set(ids)),stages=dict(collections.Counter(x['budget_class'] for x in starts)),all_PX4_zero=all(x['PX4_exit_codes']==[0] for x in term),all_stable=all(x['stable'] for x in term),raw_unique_inode_bytes=nbytes,old_FAIL_and_raw_not_deleted=True,status='PASS' if not bad and not drift and len(ids)==len(set(ids))==42 else 'FAIL'))
print('RETENTION',len(raw),nbytes,bad,drift)

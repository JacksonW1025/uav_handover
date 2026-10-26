from pathlib import Path
import hashlib,json,subprocess
root=Path('.');p=root/'data/p12-20261026-preparation';before=json.loads((p/'history-before.json').read_text());changed=[];missing=[]
for name,expected in before.items():
 f=root/name
 if not f.exists():missing.append(name)
 elif hashlib.sha256(f.read_bytes()).hexdigest()!=expected:changed.append(name)
print('tracked historical checked',len(before),'changed',len(changed),'missing',len(missing),flush=True)
old=json.loads((root/'data/p11-20261026-analysis/raw-data-manifest.json').read_text());print('P11 raw manifest keys',list(old),flush=True)
# Historical manifest contains run-level and raw-file sections, walk only path+sha pairs.
entries=[]
def walk(value):
 if isinstance(value,dict):
  path=value.get('path') or value.get('file')
  h=value.get('sha256') or value.get('actual_ulog_sha256')
  if isinstance(path,str) and isinstance(h,str) and len(h)==64:entries.append((path,h))
  for v in value.values():walk(v)
 elif isinstance(value,list):
  for v in value:walk(v)
walk(old)
cache={};bad=[]
for path,h in entries:
 f=Path(path)
 if not f.is_absolute():f=root/f
 if not f.exists():bad.append({'path':path,'reason':'missing'});continue
 st=f.stat();key=(st.st_dev,st.st_ino)
 if key not in cache:cache[key]=hashlib.sha256(f.read_bytes()).hexdigest()
 if cache[key]!=h:bad.append({'path':path,'reason':'hash mismatch'})
print('P11 raw explicit hashes',len(entries),'unique',len(cache),'bad',len(bad),flush=True)
r={'schema':'p12-history-retention-audit-1','historical_tracked_checked':len(before),'changed':changed,'missing':missing,'p11_explicit_raw_hashes_checked':len(entries),'p11_unique_raw_inodes_checked':len(cache),'p11_raw_problems':bad,'P11_status':'69 valid /1 invalid /2 unstarted remains unchanged','status':'PASS' if not changed and not missing and not bad else 'FAIL','new_source_semantics':'shared source changes deliberately versioned in P12; old frozen identities not promoted to current build'}
(p/'history-final-audit.json').write_text(json.dumps(r,indent=2)+'\n')

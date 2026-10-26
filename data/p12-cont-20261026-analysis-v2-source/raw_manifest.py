#!/usr/bin/env python3
"""Streaming hashes of every continuation raw/derived file, including invalid attempts."""
import json,hashlib,sys,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def main(out):
 if out.exists():raise FileExistsError(out)
 paths=set()
 for parent in [ROOT/'data/p12-cont-20261026-development',ROOT/'data/p12-cont-20261026-formal']:
  for run in parent.glob('*/run'):
   for name in ['flight.ulg','telemetry.jsonl','resources.jsonl','p11-sends.jsonl','logs/gz-stats.log','logs/tegrastats.log']:
    if (run/name).exists():paths.add(run/name)
   paths.update((run/'rootfs/log').glob('**/*.ulg'));paths.update((run/'gz-motor').glob('*.bin'))
 for folder in (ROOT/'data').glob('p12-cont-*'):
  if folder.is_dir():paths.update(folder.rglob('*.npz'))
 cache={};rows=[]
 for p in sorted(paths):
  st=p.stat();key=(st.st_dev,st.st_ino)
  if key not in cache:cache[key]=sha(p)
  rows.append({'path':str(p.relative_to(ROOT)),'bytes':st.st_size,'allocated_bytes':st.st_blocks*512,'device':st.st_dev,'inode':st.st_ino,'sha256':cache[key],'kind':'full_derived_array_or_frozen_policy' if p.suffix=='.npz' else 'raw; invalid/interrupted retained equally'})
 old={}
 for name in ['data/p12-20261026-preparation/attempts.jsonl','data/p11-20261025-preparation/attempts.jsonl']:
  prior=subprocess.check_output(['git','show','b6feb296:'+name],cwd=ROOT);old[name]=hashlib.sha256(prior).hexdigest()==sha(ROOT/name)
 history=[];prior=ROOT/'data/p12-20261026-delivery-v1/raw-data-manifest.json'
 if prior.exists():
  for row in json.loads(prior.read_text())['files']:
   p=ROOT/row['path'];history.append({'path':row['path'],'unchanged':p.exists() and sha(p)==row['sha256']})
 p11=[];seen={}
 for meta in (ROOT/'data').glob('p11-*/**/metadata.json'):
  m=json.loads(meta.read_text());u=meta.parent/'flight.ulg'
  if not u.exists() or not m.get('ulog_sha256'):continue
  st=u.stat();key=(st.st_dev,st.st_ino)
  if key not in seen:seen[key]=sha(u)
  p11.append({'path':str(u.relative_to(ROOT)),'metadata_ulog_match':seen[key]==m['ulog_sha256']})
 result={'schema':'p12-cont-all-raw-derived-manifest-1','files':rows,'unique_inodes':len(cache),'no_deletion_or_decimation':True,'all_full_npz_local_uniformly':True,'original_ledgers_unchanged':old,'old_p12_raw_check':history,'old_p11_ulog_check':p11,'historical_cli_note':'CLI link text/history preserved, shared Lab binary target changed by declared build; old symlinks are not binary snapshots; actual new runtime files separately copied and hashed'}
 out.write_text(json.dumps(result,indent=2)+'\n')
 if not all(old.values()) or not all(x['unchanged'] for x in history) or not all(x['metadata_ulog_match'] for x in p11):raise RuntimeError('history/hash mismatch retained; do not rewrite old evidence')
 print('RAW_HISTORY_PASS',len(rows),'paths',len(cache),'unique inodes',len(p11),'old P11 ULogs')
if __name__=='__main__':main(Path(sys.argv[1]))

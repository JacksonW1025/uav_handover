from pathlib import Path
import json,hashlib,time
start=time.monotonic();cache={};files=[];runs=[]
for base in [Path('data/p11-20261025-development'),Path('data/p11-20261025-formal')]:
 for u in sorted(base.glob('**/run/flight.ulg')):
  run=u.parent;meta=json.loads((run/'metadata.json').read_text());chosen=[p for p in run.rglob('*') if p.is_file() and (p.suffix=='.ulg' or 'gz-motor' in p.parts or p.name in ['telemetry.jsonl','resources.jsonl','p11-sends.jsonl'])]
  for p in chosen:
   st=p.stat();key=(st.st_dev,st.st_ino)
   if key not in cache:
    h=hashlib.sha256()
    with p.open('rb') as f:
     for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    cache[key]=h.hexdigest()
   files.append({'path':str(p),'absolute_path':str(p.resolve()),'bytes':st.st_size,'sha256':cache[key],'device':st.st_dev,'inode':st.st_ino,'hardlinks':st.st_nlink})
  actual=next(x['sha256'] for x in files if x['path']==str(u));runs.append({'run':str(run),'recorded_ulog_sha256':meta.get('ulog_sha256'),'actual_ulog_sha256':actual,'matches':meta.get('ulog_sha256')==actual,'policy_sha256':meta.get('policy_sha256'),'binary_sha256':meta.get('binary_sha256')})
r={'schema':'p11-raw-data-manifest-1','storage_policy':'all raw bytes remain at existing local paths; Git holds hashes/metadata/derived evidence only. Hardlink paths retained, no raw deletion.','runs':runs,'raw_files':files,'run_count':len(runs),'unique_inodes':len(cache),'all_metadata_hashes_match':all(x['matches'] for x in runs),'elapsed_s':time.monotonic()-start};Path('data/p11-20261026-analysis/raw-data-manifest.json').write_text(json.dumps(r,indent=2)+'\n');print(r['run_count'],r['all_metadata_hashes_match'],len(files))

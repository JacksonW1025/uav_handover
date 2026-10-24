#!/usr/bin/env python3
"""Enumerate only related small publication files; no Git mutation."""
import hashlib,json,re,subprocess
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
tracked=subprocess.check_output(['git','diff','--name-only','-z'],cwd=ROOT).decode().split('\0')
untracked=subprocess.check_output(['git','ls-files','--others','--exclude-standard','-z'],cwd=ROOT).decode().split('\0')
allowed={'README.md','Experiment Status.md','data/README.md','docs/THOR_P9_FINAL_REPORT.md','data/p9-20261024-preparation/attempts.jsonl'}
exclude={'data/p9-20261024-continuation-v4-publication/manifest.json','data/p9-20261024-continuation-v4-publication/receipt.json','data/p9-20261024-continuation-v4-publication/ci-observation.json'}
account=json.loads((ROOT/'data/p9-20261024-continuation-v4-delivery/final-disclosure/final-accounting.json').read_text())
assert account['formal_starts']==173 and account['main_measurements']==169 and account['NOT_RUN_static']==0
paths=sorted({p for p in tracked+untracked if p and (p in allowed or p.startswith('data/p9-20261024-continuation-v4-')) and p not in exclude})
for p in paths:
    assert Path(ROOT/p).is_file() and not Path(ROOT/p).is_symlink(),p
    assert not any(k in p.split('/') for k in ['rootfs','cli','gz-motor','__pycache__']),p
    assert Path(p).name not in ['flight.ulg','telemetry.jsonl','resources.jsonl','attempts.lock'],p
    assert Path(ROOT/p).stat().st_size<5_000_000,p
secret=re.compile(rb'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,}')
hashes={};bad=[]
for p in paths:
    b=(ROOT/p).read_bytes();hashes[p]=hashlib.sha256(b).hexdigest()
    if (ROOT/p).suffix not in ['.gz','.png','.pdf'] and secret.search(b):bad.append(p)
assert not bad,'possible secret files: '+str(bad)
manifest={'created_at':datetime.now(timezone.utc).isoformat(),'status':'COMPLETED_AUTHORIZED_EXECUTION_WITH_HISTORICAL_EXCEPTIONS','scope':'related small preserved evidence only; raw ULog/telemetry/resources/Gazebo motor traces remain Thor-local, including failures','files':hashes,'file_count':len(hashes),'logical_bytes':sum((ROOT/p).stat().st_size for p in paths),'excluded_self_and_later_attestations':sorted(exclude),'budget':{'development':10,'formal_started':173,'main_measurements':169,'FINISH':171,'D_main':33,'D_complete_four_arm_clusters':7,'exceptions':[102,162,164,169],'static_NOT_RUN':0,'unused_search_slots':7,'continuation_cap':173,'original_cap':180},'secret_scan':'no strong private-key/access-token patterns found; binary image/pdf/gz formats excluded from textual scan','user_AGENTS_preserved_untracked':True}
(HERE/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
Path('/tmp/p9-v4-publication-paths.nul').write_bytes(b'\0'.join(p.encode() for p in paths+['data/p9-20261024-continuation-v4-publication/manifest.json'])+b'\0')
print(json.dumps({'files':len(paths),'bytes':manifest['logical_bytes'],'manifest_sha256':hashlib.sha256((HERE/'manifest.json').read_bytes()).hexdigest()}))

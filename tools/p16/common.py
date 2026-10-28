from pathlib import Path
import json,hashlib,os,datetime
R=Path(__file__).resolve().parents[2];B=R/'data/p16-20261028';PY=R/'uav_lab/.local/venv/bin/python'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for s in iter(lambda:f.read(4*1024*1024),b''):h.update(s)
 return h.hexdigest()
def write(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def append(p,x):
 with Path(p).open('a') as f:f.write(json.dumps(x,ensure_ascii=False,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()

def verify_model_adoption(path,root=R):
 # Every physical stage remains closed until the requested real artifacts are
 # adopted with ordinary source/parameter/report identities. Unit tests do not
 # create this production record.
 doc=json.load(open(path));assert doc.get('status')=='ADOPTED_HASH_VERIFIED' and doc.get('adopted') is True
 required={'model-search-20261028','greybox-baseline-audit-20261028','sequential-budget-audit-20261028'}
 assert required<=set(doc['references']) and doc['model_entrypoint'] in doc['files']
 for name in required:assert doc['references'][name]['report_path'] in doc['files']
 for p,h in doc['files'].items():assert sha(Path(root)/p)==h,'model adoption drift '+p
 return dict(path=str(path),sha256=sha(path),model_entrypoint=doc['model_entrypoint'],files_verified=len(doc['files']),content_digest=hashlib.sha256(json.dumps(doc,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest())

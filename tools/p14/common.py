"""Read-only historic inputs. No campaign/launcher import."""
import json
from pathlib import Path
import hashlib

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/p14-20261027'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for s in iter(lambda:f.read(4*1024*1024),b''):h.update(s)
 return h.hexdigest()
def write(p,x):
 import numpy as np
 def plain(v):
  if isinstance(v,dict):return {str(k):plain(w) for k,w in v.items()}
  if isinstance(v,(list,tuple)):return [plain(w) for w in v]
  if isinstance(v,np.ndarray):return plain(v.tolist())
  if isinstance(v,np.generic):return v.item()
  return v
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():raise FileExistsError(p)
 p.write_text(json.dumps(plain(x),indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def records():
 rows=[]
 for group in ['development','formal']:
  for tar in sorted((ROOT/f'data/p13-20261026-{group}').iterdir()):
   if not (tar/'run').is_dir():continue
   a=tar/'analysis-v1';pointer=tar/'analysis-pointer-v2.json'
   if pointer.exists():a=tar/json.load(open(pointer))['directory']
   p=a/'prediction';pack=a/'packed-physical'
   if not p.exists():
    p=ROOT/'data/p13-20261026-development-predictions-v1'/tar.name/'prediction';pack=p.parent/'packed'
   rows.append({'id':tar.name,'group':group,'target':tar,'analysis':a,'prediction':p,'packed':pack,'measured':a/'measured/measurement.json'})
 assert len(rows)==78 and sum(r['group']=='formal' for r in rows)==66
 return rows

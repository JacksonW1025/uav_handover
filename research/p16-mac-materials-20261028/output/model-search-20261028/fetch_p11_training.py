from pathlib import Path
import json,subprocess,base64,hashlib,concurrent.futures
from fetch_evidence import ROOT,fetch
OLD=ROOT.parent/'offline-adjoint-20261028';tree=json.loads((OLD/'p11formal_tree.json').read_text());tree=tree if isinstance(tree,list) else tree['tree'];index={x['path']:x for x in tree};fit=json.loads((ROOT/'upstream/data/p11-20261025-formal/models/fit.json').read_text())
def one(s):
 rel=s['path'].split('/data/p11-20261025-formal/',1)[1];full='data/p11-20261025-formal/'+rel;dest=ROOT/'upstream'/full;old=OLD/'upstream'/full
 if not dest.exists():
  if old.exists():dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(old.read_bytes())
  else:
   d=index[rel];p=subprocess.run(['gh','api',f"repos/JacksonW1025/uav_handover/git/blobs/{d['sha']}"],capture_output=True,check=True);b=base64.b64decode(json.loads(p.stdout)['content']);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(b)
 assert hashlib.sha256(dest.read_bytes()).hexdigest()==s['sha256']
 rid=rel.split('/')[0]
 for tail in ['packed/prediction-input.json','measured/measurement.json']:fetch('data/p11-20261025-formal/'+rid+'/'+tail)
 print(rid,'verified',flush=True);return dict(id=rid,path=str(dest),sha256=s['sha256'])
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:r=list(ex.map(one,fit['inputs']))
(ROOT/'p11_training_receipt.json').write_text(json.dumps(r,indent=2));print('DONE',len(r),flush=True)

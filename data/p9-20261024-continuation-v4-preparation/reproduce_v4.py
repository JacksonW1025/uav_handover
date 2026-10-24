"""Read-only archival reproduction, including after later publication commits."""
import argparse,json,hashlib,sys,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(HERE));sys.path.insert(0,str(ROOT/'tools'))
from p9_model import sha

def verify_archive(frozen):
 m=json.loads((frozen/'manifest.json').read_text());receipt=json.loads((frozen/'receipt.json').read_text());assert sha(frozen/'manifest.json')==receipt['manifest_sha256']
 for d,c in [(frozen,receipt['commit']),(ROOT/'data/p9-20261024-continuation-v3-freeze',m['previous_freeze_commit']),(ROOT/'data/p9-20261024-continuation-v2-freeze',m['v2_freeze_commit']),(ROOT/'data/p9-20261024-continuation-v1-freeze',m['v1_freeze_commit']),(ROOT/'data/p9-20261024-freeze',m['original_freeze_commit'])]:
  for p,h in json.loads((d/'manifest.json').read_text())['files'].items():assert sha(ROOT/p)==h and hashlib.sha256(subprocess.check_output(['git','show',c+':'+p],cwd=ROOT)).hexdigest()==h,p
 assert (ROOT/'data/p9-20261024-preparation/attempts.jsonl').read_bytes().startswith((frozen/'prior-ledger.jsonl').read_bytes())
 return m

def main():
 p=argparse.ArgumentParser();p.add_argument('--verify-only',action='store_true');p.add_argument('--output',type=Path);a=p.parse_args();verify_archive(ROOT/'data/p9-20261024-continuation-v4-freeze')
 if a.verify_only:print('ARCHIVE frozen bindings PASS, no flight');return
 if a.output is None:p.error('--output required')
 out=a.output.resolve();out.mkdir(exist_ok=False)
 import audit_v4
 audit_v4.verify_freeze=verify_archive
 if audit_v4.audit(ROOT/'data/p9-20261024-preparation',ROOT/'data/p9-20261024-continuation-v4-freeze',ROOT/'data/p9-20261024-continuation-v4-formal',out/'audit'):raise RuntimeError('v2 re-audit failed')
 subprocess.run([sys.executable,str(HERE/'report_v4.py'),'--output',str(out/'report')],cwd=ROOT,check=True)
 subprocess.run([sys.executable,str(HERE/'postanalysis_v4.py'),'--formal',str(out/'report/analysis-view'),'--report',str(out/'report'),'--audit',str(out/'audit'),'--output',str(out/'postanalysis')],cwd=ROOT,check=True)
 print('READ-ONLY REPRODUCTION COMPLETE; prior FAIL retained; no simulation')
if __name__=='__main__':main()

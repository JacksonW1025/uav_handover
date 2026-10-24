"""Read-only reproduction of v2 stopped evidence; no simulation or gate relaxation."""
import argparse,json,sys,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];PREP=ROOT/'data/p9-20261024-continuation-v2-preparation';sys.path.insert(0,str(PREP));sys.path.insert(0,str(ROOT/'tools'))
from reproduce_v2 import verify_archive

def main():
 p=argparse.ArgumentParser();p.add_argument('--verify-only',action='store_true');p.add_argument('--output',type=Path);a=p.parse_args();verify_archive(ROOT/'data/p9-20261024-continuation-v2-freeze')
 if a.verify_only:print('ARCHIVE v2 bindings PASS; no flight');return
 if a.output is None:p.error('--output required')
 out=a.output.resolve();out.mkdir(exist_ok=False)
 import audit_v2
 audit_v2.verify_freeze=verify_archive
 code=audit_v2.audit(ROOT/'data/p9-20261024-preparation',ROOT/'data/p9-20261024-continuation-v2-freeze',ROOT/'data/p9-20261024-continuation-v2-formal',out/'audit')
 au=json.loads((out/'audit/audit.json').read_text());assert code and au['status']=='FAIL' and len(au['runs'])==2 and [r['passed'] for r in au['runs']]==[True,False]
 subprocess.run([sys.executable,str(HERE/'report_stopped.py'),'--output',str(out/'report')],cwd=ROOT,check=True)
 subprocess.run([sys.executable,str(HERE/'postanalysis_stopped.py'),'--formal',str(out/'report/analysis-view'),'--report',str(out/'report'),'--audit',str(out/'audit'),'--output',str(out/'postanalysis')],cwd=ROOT,check=True)
 print('V2 STOPPED REPRODUCED: C PASS,R FAIL,whole FAIL; no additional flight')
if __name__=='__main__':main()

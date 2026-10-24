"""One-shot4-flight supervised pipeline; no Git action or retry."""
import sys,json,time,traceback,subprocess
from pathlib import Path
from datetime import datetime,timezone
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(HERE));sys.path.insert(0,str(ROOT/'tools'))
from run_v4 import campaign
from p9_model import write

def main():
 start=time.monotonic();stage='FORMAL_RUNNING';freeze=ROOT/'data/p9-20261024-continuation-v4-freeze';formal=ROOT/'data/p9-20261024-continuation-v4-formal';audit=ROOT/'data/p9-20261024-continuation-v4-audit';report=ROOT/'data/p9-20261024-continuation-v4-report'
 def status(s,**kw):write(HERE/'pipeline-state.json',{'checked_at':datetime.now(timezone.utc).isoformat(),'stage':s,'formal':str(formal.relative_to(ROOT)),'automatic_retry':False,**kw})
 try:
  status(stage);campaign(ROOT/'data/p9-20261024-preparation',freeze,formal)
  stage='AUDIT_RUNNING';status(stage)
  subprocess.run([sys.executable,str(HERE/'audit_v4.py'),str(ROOT/'data/p9-20261024-preparation'),'--frozen',str(freeze),'--formal',str(formal),'--output',str(audit)],cwd=ROOT,check=True)
  stage='REPORT_RUNNING';status(stage)
  subprocess.run([sys.executable,str(HERE/'report_v4.py'),'--output',str(report)],cwd=ROOT,check=True)
  stage='POSTANALYSIS_RUNNING';status(stage)
  subprocess.run([sys.executable,str(HERE/'postanalysis_v4.py'),'--formal',str(report/'analysis-view'),'--report',str(report),'--audit',str(audit),'--output',str(ROOT/'data/p9-20261024-continuation-v4-postanalysis')],cwd=ROOT,check=True)
  status('READY_FOR_MANUAL_REVIEW',elapsed_s=time.monotonic()-start,formal_started=173,original102_missing=True,original162_diagnostic_only=True,no_overall_acceptance_pass=True)
  print('READY FOR MANUAL REVIEW, no automatic Git',flush=True)
 except BaseException as exc:
  status('STOPPED_REQUIRES_INSPECTION',failed_stage=stage,error=repr(exc));traceback.print_exc();raise
if __name__=='__main__':main()

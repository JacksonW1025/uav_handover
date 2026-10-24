#!/usr/bin/env python3
"""One-shot bounded user-unit pipeline; no restart or automatic new epoch."""
import json,subprocess,sys,time,traceback
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(Path(__file__).resolve().parent))
from p9_model import write
from run_continuation import campaign


def main():
    prep=Path(__file__).resolve().parent;freeze=ROOT/'data/p9-20261024-continuation-v1-freeze'
    formal=ROOT/'data/p9-20261024-continuation-v1-formal';audit=ROOT/'data/p9-20261024-continuation-v1-audit'
    report=ROOT/'data/p9-20261024-continuation-v1-report';plots=ROOT/'data/p9-20261024-continuation-v1-postanalysis'
    state=prep/'pipeline-state.json';started=time.monotonic();stage='FORMAL_RUNNING'
    def status(stage,**extra):write(state,{'checked_at':datetime.now(timezone.utc).isoformat(),'stage':stage,'formal':str(formal.relative_to(ROOT)),'audit':str(audit.relative_to(ROOT)),'report':str(report.relative_to(ROOT)),'postanalysis':str(plots.relative_to(ROOT)),'automatic_retry':False,**extra})
    try:
        status(stage);campaign(ROOT/'data/p9-20261024-preparation',freeze,formal)
        stage='AUDIT_RUNNING';status(stage)
        r=subprocess.run([sys.executable,str(prep/'audit_continuation.py'),str(ROOT/'data/p9-20261024-preparation'),'--frozen',str(freeze),'--formal',str(formal),'--output',str(audit)],cwd=ROOT)
        stage='REPORT_RUNNING';status(stage,audit_exit=r.returncode)
        b=subprocess.run([sys.executable,str(prep/'build_combined_report.py'),'--formal',str(formal),'--audit',str(audit),'--output',str(report)],cwd=ROOT)
        if r.returncode or b.returncode:raise RuntimeError('audit/report requires inspection; no simulations retried')
        stage='POSTANALYSIS_RUNNING';status(stage)
        p=subprocess.run([sys.executable,str(prep/'postanalysis_continuation.py'),'--formal',str(report/'analysis-view'),'--report',str(report),'--audit',str(audit),'--output',str(plots)],cwd=ROOT)
        if p.returncode:raise RuntimeError('postanalysis requires inspection; outputs retained')
        status('READY_FOR_MANUAL_REVIEW',elapsed_s=time.monotonic()-started,formal_started_total=173,formal_measured_total=172,original_infra_missing=1,no_overall_acceptance_pass=True)
        print('PIPELINE READY FOR MANUAL REVIEW; no automatic Git action',flush=True)
    except BaseException as exc:
        status('STOPPED_REQUIRES_INSPECTION',failed_stage=stage,error=repr(exc),no_restart=True)
        traceback.print_exc();raise


if __name__=='__main__':main()

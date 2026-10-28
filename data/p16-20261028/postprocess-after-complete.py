"""Dependent postprocessor only; never imports/calls any flight launcher."""
import sys,subprocess,time,json,datetime,resource
from pathlib import Path
b=Path('data/p16-20261028');script=b/'analysis-source-v2';started=time.perf_counter();child0=resource.getrusage(resource.RUSAGE_CHILDREN)
for check in range(360):
 if (b/'execution-complete.json').exists():break
 time.sleep(30)
else:raise RuntimeError('no complete frozenphysicalpool within3h, preservecheckpoint, no automaticrestart')
ledger=[json.loads(l) for l in (b/'attempts.jsonl').read_text().splitlines()];ss=[x for x in ledger if x['event']=='START_INTENT'];assert len(ss)==32 and len({x['id'] for x in ss})==32
assert all(any(e.get('id')==x['id'] and e['event'] in ['FINISH','SCOPED_REVIEW_RESOLVED'] for e in ledger) for x in ss)
time.sleep(5)
for cmd in [[sys.executable,str(script/'report.py'),str(b/'analysis-v2-results')],[sys.executable,'-m','pytest','-q','tests/test_p16.py','tests/test_p16_workflow.py','tests/test_p16_material.py','tests/test_p15.py','tests/test_p15_final.py','tests/test_p14h.py','tests/test_p14g.py','tests/test_p14r.py','tests/test_p14_motion.py','tests/test_p14.py',str(script/'test_analysis.py')],[sys.executable,str(script/'final_audit.py'),str(b/'final-audit-v1')]]:
 print('POSTPROCESS',cmd,flush=True);subprocess.run(cmd,check=True)
a=resource.getrusage(resource.RUSAGE_CHILDREN);x=dict(time=datetime.datetime.now(datetime.timezone.utc).isoformat(),wall_including_external_wait_s=time.perf_counter()-started,children_CPU_s=a.ru_utime+a.ru_stime-child0.ru_utime-child0.ru_stime,scope='dependentreport/tests/readonlyaudit only, no flightlaunch; reportCPU nested component no doublecount',publication='PENDING modelreview/report/finalcommitpushCI',new_START=0);p=b/'postprocessing-complete.json';assert not p.exists();p.write_text(json.dumps(x,indent=2)+'\n');print('P16_POSTPROCESS_READY_FOR_REVIEW',flush=True)

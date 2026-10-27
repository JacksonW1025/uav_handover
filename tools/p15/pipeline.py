"""Persistent serial P15 queue. Every prior START skipped, pending dependencies stop.
No implicit replacement or automatic resolution of untrusted execution outcomes.
"""
import sys,json,subprocess,time,resource
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from p15.common import *

def main():
 plan=Path(sys.argv[1]);rows=json.load(open(plan))['rows'];out=register(sys.argv[2],'serial queue after each complete identity/raw/source review, original START never repeated');st=time.perf_counter();before=resource.getrusage(resource.RUSAGE_SELF)
 for r in rows:
  ledger=[json.loads(l) for l in (B/'attempts.jsonl').read_text().splitlines()] if (B/'attempts.jsonl').exists() else [];started=[x for x in ledger if x['event']=='START_INTENT'];done={x['id'] for x in ledger if x['event'] in ['FINISH','REVIEW_RESOLVED']};pending=[x['id'] for x in started if x['id'] not in done]
  if pending:write(out/'stop.json',dict(reason='previous outcome/review pending',ids=pending));return
  if any(x['id']==r['id'] for x in started):continue
  cmd=[str(PY),str(R/'tools/p15/campaign.py'),r['id'],str(plan)];code=subprocess.run(cmd).returncode
  now=[json.loads(l) for l in (B/'attempts.jsonl').read_text().splitlines()];valid=any(x['id']==r['id'] and x['event'] in ['FINISH','REVIEW_RESOLVED'] for x in now)
  if code or not valid:write(out/'stop.json',dict(reason='new outcome requires scoped review',id=r['id'],rc=code));return
 after=resource.getrusage(resource.RUSAGE_SELF);write(out/'complete.json',dict(planned=len(rows),wall_s=time.perf_counter()-st,CPU_s_manager=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,scope='queue manager only, children separately charged'))
if __name__=='__main__':main()

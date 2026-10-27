"""Persistent full frozen-input scoring. All36 cases, no result selection.
Only completed/review-resolved flights; CPU0-3, avoid M3decision windows.
"""
import sys,json,time,resource
from pathlib import Path
R=Path('/home/car/uav_handover');sys.path.insert(0,str(R/'tools'))
from p15.common import B,PY,sha,write,cost_run,append

def safe():
 records=[json.loads(l) for l in (B/'attempts.jsonl').read_text().splitlines()];done={r['id'] for r in records if r['event'] in ['FINISH','REVIEW_RESOLVED']};active=[r for r in records if r['event']=='START_INTENT' and r['id'] not in done]
 for r in active:
  target=B/'runs'/r['id'];plan=json.load(open(target/'plan.json'))
  if plan['method']!='M3':continue
  ev=[json.loads(l) for l in (target/'run/events.jsonl').read_text().splitlines()] if (target/'run/events.jsonl').exists() else [];anchor=next((e for e in ev if e['event']=='p12_confirmed_native_stream_anchor'),None)
  if anchor:
   profile=(time.monotonic_ns()-anchor['run_wall_ns'])/1e9
   if -2<=profile<=21:return False
  else:
   created=next((e for e in ev if e['event']=='created'),None)
   if created and (time.monotonic_ns()-created['monotonic_ns'])/1e9>30:return False
 return True

def main():
 out=B/'scoring-execution-v1';out.mkdir(exist_ok=False);plans=[json.load(open(B/x/'plan.json')) for x in ['search-freeze-v2','map-freeze-v2']];ids=[r['id'] for p in plans for r in p['rows']];write(out/'before.json',dict(ids=ids,source_sha256=sha(Path(__file__)),model_sha256=sha(R/'tools/p15/model.py'),role='all frozen model conditional full forecasts and separate future scoring, no parameterfit or experimentalchange',CPU_affinity='offlineworkers0-3; avoid liveM3modelcriticalwindow'));pending=set(ids);st=time.perf_counter();before=resource.getrusage(resource.RUSAGE_SELF);errors=[]
 while pending:
  records=[json.loads(l) for l in (B/'attempts.jsonl').read_text().splitlines()];done={r['id'] for r in records if r['event'] in ['FINISH','REVIEW_RESOLVED']};ready=[i for i in ids if i in pending and i in done]
  if not ready or not safe():time.sleep(1);continue
  ident=ready[0];target=B/'runs'/ident
  jobs=[('evaluation-processes',R/'tools/p15/evaluate.py',[target,B/'evaluation'/ident]),('tap-processes',B/'model-taps-v1/compute.py',[target/'run/p15-selection-input.json',target/'run/p15-selection.json',B/'taps'/ident]),('extra-metrics-processes',B/'final-analysis-v2-source/extra_metrics.py',[target,B/'taps'/ident,B/'extra-metrics'/ident])]
  for kind,script,args in jobs:
   while not safe():time.sleep(1)
   try:
    q=cost_run(['/usr/bin/taskset','-c','0-3',PY,script,*args],B/kind/ident,cpu=120,wall=180,scope='allcase frozen conditional scoring '+kind)
    if q['rc']:errors.append(dict(id=ident,kind=kind,rc=q['rc']));break
   except BaseException as e:errors.append(dict(id=ident,kind=kind,error=repr(e)));break
  pending.remove(ident);write(out/(ident+'.json'),dict(id=ident,done=True,errors=[e for e in errors if e['id']==ident]));print('SCORED',ident,flush=True)
 after=resource.getrusage(resource.RUSAGE_SELF);write(out/'complete.json',dict(N=len(ids),errors=errors,wall_s=time.perf_counter()-st,CPU_s_manager=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,all_future_measurements_scoring_only=True))
if __name__=='__main__':main()

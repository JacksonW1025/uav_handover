import sys,json,time,resource,importlib.util
from pathlib import Path
R=Path('/home/car/uav_handover');sys.path.insert(0,str(R/'tools'))
from p15.common import B,PY,write,cost_run
spec=importlib.util.spec_from_file_location('scoring_safe',B/'scoring-source-v1/run.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
out=B/'tap-repair-execution-v2';out.mkdir();ids=json.load(open(B/'tap-path-repair-before-v2.json'))['affected_completed_ids'];write(out/'before.json',dict(ids=ids,reason='sameinput path-only repair, never physical/fullforecast rerun'));errors=[];st=time.perf_counter();before=resource.getrusage(resource.RUSAGE_SELF)
for ident in ids:
 t=B/'runs'/ident
 for kind,script,args in [('tap-processes-v2',B/'model-taps-v1/compute.py',[t/'run/p15-selection-input.json',t/'run/p15-selection.json',B/'taps'/ident]),('extra-metrics-processes-v2',B/'final-analysis-v2-source/extra_metrics.py',[t,B/'taps'/ident,B/'extra-metrics'/ident])]:
  while not m.safe():time.sleep(1)
  q=cost_run(['/usr/bin/taskset','-c','0-3',PY,script,*args],B/kind/ident,cpu=120,wall=180,scope='path-only failedtap repair, exactfrozenmodel/inputs olderrorcostkept')
  if q['rc']:errors.append(dict(id=ident,kind=kind,rc=q['rc']));break
 write(out/(ident+'.json'),dict(id=ident,errors=[e for e in errors if e['id']==ident]));print('TAP_REPAIRED',ident,flush=True)
after=resource.getrusage(resource.RUSAGE_SELF);write(out/'complete.json',dict(N=len(ids),errors=errors,wall_s=time.perf_counter()-st,CPU_s_manager=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime))

"""One bounded correctness repair, no search/parameter retuning/new physics."""
import sys,json,time,resource,subprocess,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import psutil
from p14g.common import *

def main():
 out=Path(sys.argv[1]);register(out,'post-state adjoint indexing correction; old weightedH2invalid forrequestedobjective, restunchanged',group_CPU_ceiling=240,per_set_CPU=90,weights=2,weighted_cases=10,global_numeric_charge_with240andvalidation100=5032.712317427229+240+100,hardcap_certification='stillnotcertified legacy200allowance retained');CPU0=resource.getrusage(resource.RUSAGE_CHILDREN);own=time.process_time();rows=[]
 def used():
  r=resource.getrusage(resource.RUSAGE_CHILDREN);return r.ru_utime+r.ru_stime-CPU0.ru_utime-CPU0.ru_stime+time.process_time()-own
 def launch(cmd,log):
  before=used();t=time.perf_counter();reason=None
  with log.open('w') as f:
   p=subprocess.Popen([str(PY),*cmd],stdout=f,stderr=subprocess.STDOUT)
   while p.poll() is None:
    try:cc=psutil.Process(p.pid).cpu_times();live=cc.user+cc.system
    except psutil.Error:live=0
    if used()+live>=239:reason='GROUP_CPU_RESOURCE_STOP';p.kill();break
    if time.perf_counter()-t>110:reason='JOB_WALL_RESOURCE_STOP';p.kill();break
    time.sleep(.1)
   rc=p.wait()
  return {'command':cmd,'rc':rc,'reason':reason,'CPU_s':used()-before,'wall_s':time.perf_counter()-t}
 for fiber in ['d02','d03']:
  target=out/('weights-'+fiber);r=launch([str(R/'tools/p14g/weights.py'),str(target),fiber],out/('weights-'+fiber+'.log'));rows.append(r);write(out/('weights-'+fiber+'-execution.json'),r)
  if r['rc']!=0:write(out/'stopped.json',{'reason':'weights incomplete','rows':rows,'CPU_s':used()});return
 jobs=[j for j in json.load(open(B/'B-v2/before-compute.json'))['jobs'] if j['variant']=='weighted'];write(out/'jobs.json',jobs)
 for n,j in enumerate(jobs):
  if used()>=238:write(out/'unstarted.json',jobs[n:]);break
  target=out/f'{n:03d}';target.mkdir();j=dict(j,weights_path=str((out/('weights-'+j['fiber'])).resolve()));jf=target/'job.json';write(jf,j);r=launch([str(R/'tools/p14g/rich_sets.py'),'child',str(jf),str(target)],target/'compute.log');r.update(n=n,job=j);rows.append(r);write(out/f'execution-{n:03d}.json',r);print('WEIGHT_REPAIR',n,r['rc'],round(r['CPU_s'],2),flush=True)
  if r['reason']=='GROUP_CPU_RESOURCE_STOP':write(out/'unstarted.json',jobs[n+1:]);break
 write(out/'execution.json',{'rows':rows,'CPU_s_exact':used(),'group_ceiling':240,'global_numeric_charge_plus100validation':5032.712317427229+used()+100,'old_unmeasured_allowance_not_certified':True});assert used()<240.5
if __name__=='__main__':main()

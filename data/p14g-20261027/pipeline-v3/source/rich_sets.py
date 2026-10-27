"""Read-only metric repair: LP/COM separate all-prefix bounds and actualCPU.
All core propagation and domains stay unchanged; original attempts retained.
"""
import sys,json,time,resource,subprocess,os,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from p14g.common import *

def annotate(s,r):
 ctx=s['p'].ctx;n=ctx.n
 for stem,key,anchor,D in [('COM','p','H0','D'),('LP','lp','LP_H0','DLP')]:
  center=float(s[key].c[2]-s[anchor].c[0]);g=s[key].pad()[2]-s[anchor].pad()[0];rad=float(np.nextafter(np.sum(abs(g)),np.inf));r[stem+'_L_interval_m']=[center-rad,center+rad];r[stem+'_D_upper_m']=float(s[D].bounds()[1][0]);r[stem+'_D_lower_m']=float(s[D].bounds()[0][0])
 for key in ['q','att']:
  lo,hi=s[key].bounds();a=lo[1:3];b=hi[1:3];minsq=np.where((a<=0)&(b>=0),0,np.minimum(a*a,b*b));maxsq=np.maximum(a*a,b*b);r[key+'_tilt_interval_deg']=[float(np.degrees(np.arccos(np.clip(1-2*minsq.sum(),-1,1)))),float(np.degrees(np.arccos(np.clip(1-2*maxsq.sum(),-1,1))))]
 assert ctx.n==n # passive NumPy arithmetic cannot allocate hidden affine noise.
 return r

def entry(job,out):
 from p14g import tube
 from p14g.compress import SETTINGS
 old=tube.metrics;counts={}
 def rich(s,nom):
  r=old(s,nom);annotate(s,r);k=SETTINGS.get('call',0);counts[k]=counts.get(k,0)+1;r['call_hint']=k;r['metric_phase']='pre_reduce' if counts[k]%2 else 'post_reduce';return r
 tube.metrics=rich
 from p14g.batch_sets import execute
 execute(job,out)

def main():
 if sys.argv[1]=='child':entry(json.load(open(sys.argv[2])),Path(sys.argv[3]));return
 out=Path(sys.argv[1]);register(out,'independent deterministic metric repair across all64 fixed jobs; LPmissingnotpassed, no threshold/domain/candidate changes',scope='B40 + C24, preserve previous outputs, all costs count',per_job_CPU_s=90,global_CPU_s=5400,additional_CPU_ceiling_s=1800)
 monitor=B/'resource-monitor-v1/result.json'
 while not monitor.exists():time.sleep(.5)
 legacyB=json.load(open(monitor))['CPU_upper_s'];Crows=json.load(open(B/'C-v2/sets/execution.json'));Cpoint=json.load(open(B/'C-v2/isolation.json'));D=json.load(open(B/'D-v1/isolation.json'));oldB0=json.load(open(B/'B-v1/execution.json'))[0]['wall_s'];weights=sum(json.load(open(B/n/'result.json'))['elapsed_s'] for n in ['B-weights-v1','B-weights-d03-v1']);legacy={'Bv2_live_monitor_CPU_upper':legacyB,'Cpoint_CPU_cap':180,'Csets_exit_missing_CPU_upper_min_cap4CPUwall':sum(min(90,4*x['wall_s']) for x in Crows),'D_missing_CPU_upper_4CPUwall':min(450,4*D['wall_s']),'weights_missing_CPU_upper_4CPUwall':4*weights,'Bv1_completed_reused_missing_CPU_upper':min(90,4*oldB0)+90,'unmetered_prior_smallwork_allowance_not_measured':200};upper=sum(legacy.values());available=min(1800,5400-upper-100);assert available>=90;write(out/'resource-reservation.json',{'legacy_charged_upper_or_allowance':legacy,'legacy_CPU_not_replaced_by_wall_orzero':True,'new_CPU_ceiling':available,'future_validation_CPU_reserve':100,'global5400upper':upper+available+100,'legacy_CPU_exact_missing':'C/D/weights exited beforemonitor; cap/wall*4 conservativecharges, not measurements.200smallwork allowance is explicit unresolved metering scope, notretroactiveproof.','memory':'childRLIMIT_AS24GiB, futureoneheavyjobatonce; oldaggregatepeaknotrecorded','protocol_repair':'global5400unchanged; additional LPmetricrecheck isolatedanalysisresourceallocation beforestarts. No newscientificmodel/threshold.'})
 jobs=json.load(open(B/'B-v2/before-compute.json'))['jobs']+json.load(open(B/'C-v2/sets/jobs-before.json'));write(out/'jobs.json',jobs);rows=[];ownstart=time.process_time();CPU0=resource.getrusage(resource.RUSAGE_CHILDREN)
 for n,job in enumerate(jobs):
  CPU=resource.getrusage(resource.RUSAGE_CHILDREN);used=(CPU.ru_utime+CPU.ru_stime)-(CPU0.ru_utime+CPU0.ru_stime)+time.process_time()-ownstart
  if available-used<90:write(out/'unstarted.json',{'jobs':jobs[n:],'reason':'remaining certifiedreservation below90CPUperjob','not_scientific_failure':True});break
  target=out/f'{n:03d}';target.mkdir();jf=target/'job.json';write(jf,job);before=resource.getrusage(resource.RUSAGE_CHILDREN);t=time.perf_counter()
  with (target/'compute.log').open('w') as f:
   try:rc=subprocess.run([str(PY),str(Path(__file__)),'child',str(jf),str(target)],stdout=f,stderr=subprocess.STDOUT,timeout=110).returncode
   except subprocess.TimeoutExpired:rc='WALL_LIMIT'
  after=resource.getrusage(resource.RUSAGE_CHILDREN);row={'n':n,'job':job,'rc':rc,'wall_s':time.perf_counter()-t,'CPU_s_waited_child':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,'max_child_RSS_kib_cumulative_not_individual':after.ru_maxrss};rows.append(row);write(out/f'execution-{n:03d}.json',row);print('RICH',n,rc,round(row['CPU_s_waited_child'],2),flush=True)
 CPU=resource.getrusage(resource.RUSAGE_CHILDREN);used=(CPU.ru_utime+CPU.ru_stime)-(CPU0.ru_utime+CPU0.ru_stime)+time.process_time()-ownstart;write(out/'execution.json',{'rows':rows,'new_CPU_s_exact_parent_and_children':used,'global_charged_CPU_upper_plus_allowance':upper+used,'remaining_to5400':5400-upper-used,'full_expected_jobs':64,'completed_attempts':len(rows),'future_validation_reserve':100});assert upper+used+100<=5400
if __name__=='__main__':main()

"""All-start independent analysis revision, immutable old report/FAIL preserved."""
import sys,json,collections,runpy,numpy as np
from pathlib import Path
R=Path('/home/car/uav_handover');sys.path.insert(0,str(R/'tools'))
from p15.common import B,PY,write,sha

def resource(path):
 if not path.exists():return None
 return json.load(open(path))
def sum_cpu(rows):return sum(x.get('CPU_s',0) for x in rows if x)
def main():
 out=Path(sys.argv[1]);out.mkdir(exist_ok=False,parents=True);legacy=out/'physical-component-v1';saved=sys.argv;sys.argv=[str(R/'tools/p15/report.py'),str(legacy)];runpy.run_path(R/'tools/p15/report.py',run_name='__main__');sys.argv=saved
 rows=json.load(open(legacy/'all-starts.json'))
 for r in rows:
  alternate=B/'evaluation-LP-only-v2'/r['id']/'summary.json'
  if r['evaluation'] is None and alternate.exists():r['evaluation']=json.load(open(alternate));r['evaluation_scope']='controllerLP/task valid, physicalCOMmissing'
 costrecords=[json.loads(l) for l in (B/'costs.jsonl').read_text().splitlines() if json.loads(l)['event']=='END'];cost_byid={x['id']:x for x in costrecords};allocated_ids=set();methods={m:dict(search_N=0,qualified_task=0,full_platform_PASS=0,aux_tail_taskprefix_only=0,physical_invalid=0,task_invalid=0,invalid=0,FAIL=0,SUCCESS=0,UNKNOWN=0,physical_CPU_s=0.,physical_wall_s=0.,analysis_CPU_s=0.,analysis_wall_s=0.,manager_CPU_s=0.,evaluation_CPU_s=0.,evaluation_wall_s=0.,prefixes=collections.Counter(),family=collections.Counter(),information=collections.Counter(),Bplan_reached=0,prefix_already_failed=0) for m in ['M0','M1','M2','M3']};direct={};devmap=dict(physical_CPU_s=0.,physical_wall_s=0.,manager_CPU_s=0.,missing_manager=[])
 for r in rows:
  target=B/'runs'/r['id'];result=r['result'];valid=bool(result and (result['status'] in ['PASS','PASS_SCORED_TASK_PREFIX_AUX_TAIL_UNKNOWN'] or result.get('qualified_controller_task',False)));ex=r['execution'] or {};manager=resource(target/'manager-cost.json');mine=dict(physical_CPU_s=ex.get('CPU_s',0),physical_wall_s=ex.get('wall_s',0),analysis_CPU_s=0.,analysis_wall_s=0.,manager_CPU_s=(manager or {}).get('CPU_s',0),evaluation_CPU_s=0.,evaluation_wall_s=0.)
  for path in [target/'analysis-process/cost.json',target/'qualified-task-prefix-process-v2/cost.json']:
   q=resource(path)
   if q:mine['analysis_CPU_s']+=q['CPU_s'];mine['analysis_wall_s']+=q['wall_s'];allocated_ids.add(str(path.parent.relative_to(R)))
  if r['id']=='p15-e-b2-M1-t3-F4-B':
   q=resource(B/'analysis-qualification-v2/process-case2/cost.json')
   if q:mine['analysis_CPU_s']+=q['CPU_s'];mine['analysis_wall_s']+=q['wall_s'];allocated_ids.add(str((B/'analysis-qualification-v2/process-case2').relative_to(R)))
  for kind in ['evaluation-processes','evaluation-LP-only-process-v2']:
   q=resource(B/kind/r['id']/'cost.json')
   if q:mine['evaluation_CPU_s']+=q['CPU_s'];mine['evaluation_wall_s']+=q['wall_s'];allocated_ids.add(str((B/kind/r['id']).relative_to(R)))
  if r['id']=='p15-e-b2-M2-t3-F4-B':
   q=resource(B/'shutdown-recovery-v1/partial-record-process/cost.json')
   if q:mine['analysis_CPU_s']+=q['CPU_s'];mine['analysis_wall_s']+=q['wall_s'];allocated_ids.add(str((B/'shutdown-recovery-v1/partial-record-process').relative_to(R)))
  direct[r['id']]=mine
  if r['budget_class']!='search':
   for key in ['physical_CPU_s','physical_wall_s','manager_CPU_s']:devmap[key]+=mine[key]
   if manager is None:devmap['missing_manager'].append(r['id'])
   continue
  d=methods[r['method']];d['search_N']+=1;d['qualified_task']+=valid;d['full_platform_PASS']+=bool(result and result['status']=='PASS');d['aux_tail_taskprefix_only']+=bool(result and result['status']=='PASS_SCORED_TASK_PREFIX_AUX_TAIL_UNKNOWN');d['physical_invalid']+=bool(result and result.get('physical_record_status')=='INVALID_EMPTY_BUFFER');d['task_invalid']+=not valid;d['invalid']+=bool(not valid or result and result.get('physical_record_status')=='INVALID_EMPTY_BUFFER')
  if result:
   d[result['risks']['task']]+=1;d['Bplan_reached']+=result['B_plan_reached'];d['prefix_already_failed']+=result['prefix_failed_before_B']
  for k,v in mine.items():d[k]+=v
  d['prefixes'][r['prefix']]+=1;d['family'][r['family']]+=1;d['information'][r['information']]+=1
 # All offline events not assigned to a searchrecord are setup/map/revisions,
 # including every failed comparison. Do not drop tasks to improve costs.
 search_ids={r['id'] for r in rows if r['budget_class']=='search'};search_cost_ids={x for x in allocated_ids if any('/'+i+'/' in x or x.endswith('/'+i) for i in search_ids)};extra_case2=str((B/'analysis-qualification-v2/process-case2').relative_to(R));search_cost_ids.add(extra_case2);search_cost_ids.add(str((B/'shutdown-recovery-v1/partial-record-process').relative_to(R)))
 setup_records=[x for x in costrecords if x['id'] not in search_cost_ids];setup_CPU=sum_cpu(setup_records)+devmap['physical_CPU_s']+devmap['manager_CPU_s'];setup_wall=sum(x['wall_s'] for x in setup_records)+devmap['physical_wall_s'];queuefiles=list(B.glob('*execution*/complete.json'));queueCPU=sum(json.load(open(p)).get('CPU_s_manager',0) for p in queuefiles);curves={};total_eval=sum(d['evaluation_CPU_s'] for d in methods.values())
 for method,d in methods.items():
  ownCPU=d['physical_CPU_s']+d['analysis_CPU_s']+d['manager_CPU_s']+d['evaluation_CPU_s'];ownwall=d['physical_wall_s']+d['analysis_wall_s']+d['evaluation_wall_s'];d.update(canonical_total_CPU_s=ownCPU+setup_CPU*(method=='M3')+queueCPU/4,equalquarter_total_CPU_s=ownCPU+setup_CPU/4+queueCPU/4,canonical_total_wall_lower_s=ownwall+setup_wall*(method=='M3'),equalquarter_wall_lower_s=ownwall+setup_wall/4,allL15diagnostics_M3_conservative_CPU_s=ownCPU-d['evaluation_CPU_s']+total_eval*(method=='M3')+setup_CPU*(method=='M3')+queueCPU/4)
  rr=[r for r in rows if r['budget_class']=='search' and r['method']==method];cumu=setup_CPU*(method=='M3');cumwall=setup_wall*(method=='M3');failure=0;cc=[dict(start=0,total_CPU_s=cumu,total_wall_lower_s=cumwall,failures=0)]
  for k,r in enumerate(rr):
   mi=direct[r['id']];cumu+=sum(mi[x] for x in ['physical_CPU_s','analysis_CPU_s','manager_CPU_s','evaluation_CPU_s']);cumwall+=sum(mi[x] for x in ['physical_wall_s','analysis_wall_s','evaluation_wall_s']);failure+=bool(r['result'] and r['result']['risks']['task']=='FAIL');cc.append(dict(start=k+1,id=r['id'],total_CPU_s=cumu,total_wall_lower_s=cumwall,failures=failure))
  curves[method]=cc
 # Event reach is a mechanism result, never a selection filter or extra sample.
 mechanism=[];predcounts={c:dict(N=0,actual_FAIL=0,actual_SUCCESS=0,actual_UNKNOWN=0,nominal_miss=0,nominal_false_alarm=0,pred_UNKNOWN=0) for c in ['tilt','height','task']}
 for r in rows:
  ev=r['evaluation']
  if r['budget_class']!='search' or not ev:continue
  for c,d in predcounts.items():
   a=ev['actual'][c];p=ev['predicted'][c];d['N']+=1;d['actual_'+a]+=1;d['nominal_miss']+=a=='FAIL' and p=='SUCCESS';d['nominal_false_alarm']+=a=='SUCCESS' and p=='FAIL';d['pred_UNKNOWN']+=p=='UNKNOWN'
  mechanism.append(dict(id=r['id'],Bpre_errors=ev['Bpre_errors'],phases=ev['phases'],windows=ev['windows'],actual_events=ev['actual_events'],full_time_errors=ev['full_time_errors']))
 for d in predcounts.values():d.update(miss_denominator=d['actual_FAIL'],false_alarm_denominator=d['actual_SUCCESS'],known_actual_coverage=d['actual_FAIL']+d['actual_SUCCESS'])
 maprows=[]
 for r in rows:
  if r['budget_class']!='map':continue
  t=B/'runs'/r['id'];sel=resource(t/'run/p15-selection.json');u=resource(t/'run/p15-local-update.json') or resource(t/'run/p15-inherited-update.json');maprows.append(dict(id=r['id'],selection=(sel or {}).get('executed_candidate'),updated_ranking=(sel or {}).get('update_changed_choice'),no_update_selection=((sel or {}).get('no_update_ablation') or {}).get('selected'),local_update=u,result=r['result'],evaluation=r['evaluation'],role='own record update' if (t/'run/p15-local-update.json').exists() else 'independent newseed pastupdate validation'))
 write(out/'method-total-costs.json',methods);write(out/'total-cost-curves.json',curves);write(out/'classification.json',predcounts);write(out/'mechanism-time-errors.json',mechanism);write(out/'map-loop.json',maprows);write(out/'cost-allocation-audit.json',dict(setup_records=[x['id'] for x in setup_records],setup_CPU_s=setup_CPU,setup_wall_s=setup_wall,nonsearch_physical=devmap,shared_queue_CPU_s=queueCPU,rule='execution-enforcement-v2/cost-attribution-v1.json',rule_registered_after_two_START=True,curve_kind='allocated wholeprogramme cost including latermap/engineering, not chronologicalfirstfailure time',firstfailure_confirmation_cost='separate chronological supplement, excludes futurediagnostics/map',unmeasured_CPU='early directshell/baselinehash and d01manager plus finalI/Otails UNKNOWN; sums measuredcomponents, not fullhardcapcertification',unviewed_labels_independent_audit='UNAVAILABLE; authorstatement only',historical_training_CPU='UNKNOWN',manager_wall='UNKNOWN overhead, wallcurves lowerbound, CPUexplicit',setup_not_double_counted=True))
 write(out/'machine.json',dict(schema='P15-independent-analysis-v2',counts=json.load(open(legacy/'machine.json'))['counts'],methods=methods,classification=predcounts,map_records=len(maprows),limitations=['costcontract registered after2START; not fullyprospective forwholecoststudy','first2 fullcandidate/plan enforcement retroactivelyaudited, next30 beforeSTART','d01 preA choice40.431ms late, sourceinterfaceonly, not preAacceptance','fullactive auxiliaryOPtail FAIL retained with scoped taskprefix qualifications','frozen fullforecasts postflight from duringdecision input, not task0prospective','2 seedblocks do not support broad efficiency/lowmiss inference','COMphysicalnot online, LPoutput model no unconditional safetyguarantee'],historical_results_unchanged=True))
 import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
 fig,ax=plt.subplots(1,2,figsize=(11,4))
 for m,cc in curves.items():ax[0].step([x['start'] for x in cc],[x['failures'] for x in cc],where='post',label=m);ax[1].step([x['total_CPU_s'] for x in cc],[x['failures'] for x in cc],where='post',label=m)
 ax[0].set(xlabel='Counted starts',ylabel='Actual task-failure witnesses');ax[1].set(xlabel='Assigned total CPU seconds, conservative setup charge',ylabel='Actual task-failure witnesses');ax[0].legend();fig.tight_layout();fig.savefig(out/'total-cost-curves.png',dpi=160);plt.close(fig)
 print('P15 V2 ALL-COUNT COST/QUALIFICATION SYNTHESIS',len(rows))
if __name__=='__main__':main()

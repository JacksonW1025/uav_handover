"""Post-query scoring only. No selector imports full truth; never changes frozen maps."""
import sys,json,time,hashlib,csv,math
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'tools'))
from p16.common import R,B,sha,write,now
from p16.quality import evaluate,curve_key
from p16.baseline import replay as gridreplay
from p16.cheap import replay as cheapreplay
from p16.sequential import calibrated,model_map,next_query
from p16.reuse import apply,gate

def read(p):return json.load(open(p))
def cost(rid):
 p=B/'runs'/rid;e=read(p/'execution.json');m=read(p/'manager-cost.json') if (p/'manager-cost.json').exists() else {};rev=read(p/'review-cost.json') if (p/'review-cost.json').exists() else None
 # Old development manager wall includes everything. Formal overhead is explicit.
 wall=m.get('wall_s',e['wall_s']+(rev or {}).get('wall_s',0))
 cpu=e['CPU_s']+m.get('CPU_s',0)+(rev or {}).get('CPU_s',0)
 sim=None;simscope='UNKNOWN no valid physical duration';ph=p/'run/gz-motor/physics-p13-body.bin'
 if ph.exists():
  from p13.physics import read as physicalread,BODY
  try:
   a,header=physicalread(ph,BODY,b'P13BODY1');sim=float((int(a['sim_ns'][-1])-int(a['sim_ns'][0]))/1e9) if len(a) else None;simscope='direct physical first-to-last sample time, whole acquiredsim prefix; metadata validity separately'
  except (ValueError,IndexError):simscope='UNKNOWN physical record missing or invalid; no fabricatedtime'
 return dict(run_id=rid,physical_sim_s=sim,physical_sim_scope=simscope,wall_s=wall,physical_wall_s=e['wall_s'],CPU_measured_s=cpu,CPU_complete=rev is not None,unknown=['failed developer review CPU, shell/checkpack tails'] if rev is None else ['last write tail; unrecovered orchestration shell overhead'],review_wall_s=(rev or {}).get('wall_s'),manager=m,physical=e)

def persistent(series):
 return next((x['query'] for i,x in enumerate(series) if all(y['quality']['same_quality'] for y in series[i:])),None)

def scores(pool,truth,maps,knowncosts,setup_wall=0.,setup_cpu=0.):
 out=[]
 for m in maps:
  pred=m['prediction'];seen=m.get('seen_ids',[]);ids=[i for i in seen if i in knowncosts];rest=[c for c in pool if c['id'] not in seen];q=m['query'];s=evaluate(pool,truth,pred);u=evaluate(rest,truth,pred) if rest else None
  out.append(dict(query=q,seen_ids=seen,quality=s,unqueried_quality=u,query_wall_s=sum(knowncosts[i]['wall_s'] for i in ids),query_CPU_measured_s=sum(knowncosts[i]['CPU_measured_s'] for i in ids),model_CPU_replay_s=m.get('CPU_s_cumulative',0),total_incremental_wall_lower_s=sum(knowncosts[i]['wall_s'] for i in ids)+setup_wall,total_incremental_CPU_lower_s=sum(knowncosts[i]['CPU_measured_s'] for i in ids)+setup_cpu+m.get('CPU_s_cumulative',0),cost_scope='full standalonequery costs even shared actualrecords, setup explicit, initialmodelwall missing so wall lowerbound, missingtail notzero claim'))
 return dict(series=out,first_persistent_joint_quality=persistent(out),budget=max(x['query'] for x in out),final=out[-1]['quality'])

def load_truth(rows):
 out={};sources={}
 for c,row in rows.items():
  p=B/'runs'/row['id']/'analysis-v1/result.json'
  if p.exists():out[c]=read(p);sources[c]=dict(path=str(p.relative_to(R)),sha256=sha(p))
  else:out[c]=dict(valid=False,tilt='UNKNOWN',height='UNKNOWN',task='UNKNOWN',complete=False)
 return out,sources

def main(out):
 start=time.process_time();out=Path(out);out.mkdir(exist_ok=False,parents=True)
 pool=read(B/'frozen/pool.json');rows=read(B/'frozen/rows.json');initial=read(B/'frozen/initial-predictions.json');truth,sources=load_truth(rows);assert all(x['valid'] for x in truth.values()),'all24 complete reviews required'
 led=[json.loads(l) for l in (B/'attempts.jsonl').read_text().splitlines()];starts=[x for x in led if x['event']=='START_INTENT'];assert len({x['id'] for x in starts})==len(starts)<=32
 costs={c:cost(rows[c]['id']) for c in rows};actualcost=[dict(stage=x['stage'],role=x.get('role'),**cost(x['id'])) for x in starts];setupwall=sum(x['wall_s'] for x in actualcost if x['stage']=='development');setupcpu=sum(x['CPU_measured_s'] for x in actualcost if x['stage']=='development')
 # These blind replay algorithms only receive the selected oracle result.
 st=time.process_time();gm=gridreplay(pool,lambda c:truth[c]);gridcpu=time.process_time()-st
 st=time.process_time();cm,cheapmeta=cheapreplay(pool,lambda c:truth[c]);cheapcpu=time.process_time()-st
 write(out/'A_grid-maps.json',gm);write(out/'A_cheap-maps.json',cm);write(out/'A_cheap-history.json',cheapmeta)
 maps={'A_grid':gm,'A_cheap':cm};policy_cpu={};transfer=[];ablations={}
 for p in ['G','R']:
  maps[p]=[read(B/f'policies/{p}/maps/q{i:02d}.json') for i in range(9)];h={};timings=[]
  for q in range(9):
   st=time.process_time();recalculated,rr=model_map(pool,initial,h,p);assert recalculated==maps[p][q]['prediction'];elapsed=time.process_time()-st;timings.append(elapsed)
   if q<8:
    d=read(B/f'policies/{p}/queries/q{q+1:02d}/decision.json');st=time.process_time();s=next_query(pool,initial,h,p);assert s['selected']==d['cell'];elapsed=time.process_time()-st;timings[-1]+=elapsed;r=read(B/f'policies/{p}/queries/q{q+1:02d}/return.json');h[r['cell_id']]=r['record']
   if p=='R':
    for x in rr:
     a=dict(query=q,**x)
     if x['accepted']:
      dr=truth[x['donor']].get('capture_suffix');rc=truth[x['receiver']].get('capture_suffix');ok,why=gate((dr or {}).get('signature'),(rc or {}).get('signature'));a.update(actual_receiver_domain_pass=ok,actual_domain_detail=why,actual_receiver_complete=truth[x['receiver']]['complete'],actual_receiver_task=truth[x['receiver']]['task'])
      pred=recalculated[x['receiver']];a['frozen_danger_as_safe']=truth[x['receiver']]['task']=='FAIL' and pred['task']=='SUCCESS'
      if truth[x['receiver']]['complete']:
       a['whole_peak_interval_covered']=all(lo<=truth[x['receiver']][field]<=hi for field,(lo,hi) in [('peak_loss',x['interval']['height']),('peak_tilt',x['interval']['tilt'])] if lo is not None and hi is not None)
      a['conditional_interpretation']='RETRACT_ACTUAL_DOMAIN_REJECTED' if not ok else 'empiricaldomaincheckonly, not futurecertification'
     transfer.append(a)
   if p=='R':
    # Reconstruct history at the map's information time; h above includes nextquery,
    # so use immutable return sequence directly to prevent post-return leakage.
    hh={}
    for k in range(1,q+1):
     r=read(B/f'policies/R/queries/q{k:02d}/return.json');hh[r['cell_id']]=r['record']
    base=calibrated(pool,initial,hh)
    for name,kw in [('drop_state_timing',dict(drop_state=True)),('drop_L_D_prefixTilt',dict(drop_ledger=True))]:
     pp,xx=apply(pool,initial,hh,base,**kw);ablations.setdefault(name,[]).append(dict(query=q,prediction=pp,transfers=xx,quality=evaluate(pool,truth,pp)))
  policy_cpu[p]=dict(replay_map_choice_CPU_s=sum(timings),per_q=timings,scope='independent posthoc deterministic computation estimate, original manager CPU separately; not retroactively measured original selection')
 for name,ms in ablations.items():write(out/f'ablation-{name}.json',ms)
 write(out/'transfers.json',transfer);write(out/'truth.json',truth);write(out/'truth-sources.json',sources)
 # Freeze layers were not refit after labels. Runtime model prediction CPU recorded perinitial.
 initialcpu=sum(x.get('CPU_s',0) for x in initial.values());initialwall=0.;measured_initial=all('CPU_s' in x for x in initial.values())
 metrics={n:scores(pool,truth,ms,costs,setup_wall=0,setup_cpu=initialcpu if n in ['G','R'] else 0) for n,ms in maps.items()}
 for name,v in metrics.items():
  for point in v['series']:
   comp=policy_cpu[name]['replay_map_choice_CPU_s'] if name in policy_cpu else gridcpu if name=='A_grid' else cheapcpu
   fraction=(point['query']+1)/(len(v['series']))
   point['model_choice_replay_CPU_estimate_s']=comp*fraction
   point['R_extra_historical_calibration_CPU_s']=read(B/'reuse-calibration-history-v2/summary.json')['CPU_s'] if name=='R' else 0.
   point['CPU_accounted_lower_with_replay_estimate_s']=point['total_incremental_CPU_lower_s']+point['model_choice_replay_CPU_estimate_s']+point['R_extra_historical_calibration_CPU_s']
   point['CPU_replay_allocation']='linear perbudgetdisplay estimate only; whole exactreplaytotal and originalmanager aggregate separately, not originalperquery timing'
 # Pairwise half and standalone full prep views are both reported, never selected forfavor.
 for n,v in metrics.items():
  for s in v['series']:
   s['pairwise_half_prep_wall_lower_s']=s['query_wall_s']+setupwall/2+(initialwall if n in ['G','R'] else 0)
   s['standalone_full_prep_wall_lower_s']=s['query_wall_s']+setupwall+(initialwall if n in ['G','R'] else 0)
 comparison={}
 for a,b in [('A_grid','G'),('A_cheap','G'),('G','R')]:
  qa=metrics[a]['first_persistent_joint_quality'];qb=metrics[b]['first_persistent_joint_quality'];both=qa is not None and qb is not None
  comparison[f'{b}_vs_{a}']=dict(both_attained=both,baseline_query=qa,method_query=qb,query_saving=(qa-qb) if both else None,interpretation='observed samequality saving only' if both else 'NOT_ATTAINED no extrapolation',baseline_final=metrics[a]['final']['same_quality'],method_final=metrics[b]['final']['same_quality'])
 seedplan=read(B/'frozen/replication-plan.json');seedpred=read(B/'replication-forecast.json');seedtruth={};seedpool=[];seedmaps={p:{} for p in ['initial','G','R']}
 for r,x in zip(seedplan['rows'],seedpred['rows']):
  p=B/'runs'/r['id']/'analysis-v1/result.json';assert p.exists();tr=read(p);seedtruth[r['cell_id']]=tr;c=next(c for c in pool if c['id']==r['cell_id']);seedpool.append(c)
  for method in seedmaps:seedmaps[method][r['cell_id']]=x[method]
 seedquality={p:evaluate(seedpool,seedtruth,pr) for p,pr in seedmaps.items()}
 seedcomparison=[dict(id=r['id'],cell=r['cell_id'],role=r.get('replication_role',r.get('role')),main=truth[r['cell_id']]['task'],seed2=seedtruth[r['cell_id']]['task'],tilt_main=truth[r['cell_id']]['peak_tilt'],tilt_seed2=seedtruth[r['cell_id']]['peak_tilt'],loss_main=truth[r['cell_id']]['peak_loss'],loss_seed2=seedtruth[r['cell_id']]['peak_loss']) for r in seedplan['rows']]
 costsout=dict(actual_unique_START=len(starts),stage_counts={stage:sum(x['stage']==stage for x in starts) for stage in ['development','main','replication']},actual_records=actualcost,actual_wall_sum_s=sum(x['wall_s'] for x in actualcost),physical_sim_s_known=sum(x['physical_sim_s'] for x in actualcost if x['physical_sim_s'] is not None),physical_sim_unknown_runs=sum(x['physical_sim_s'] is None for x in actualcost),actual_CPU_measured_lower_s=sum(x['CPU_measured_s'] for x in actualcost),setup_development_wall_s=setupwall,setup_development_CPU_measured_lower_s=setupcpu,initial_forecast_CPU_s=initialcpu if measured_initial else None,initial_forecast_wall_s=None,posthoc_baseline_grid_CPU_s=gridcpu,posthoc_baseline_cheap_CPU_s=cheapcpu,posthoc_policy_replay_estimates=policy_cpu,source_reuse_calibration_CPU_s=read(B/'reuse-calibration-history-v2/summary.json')['CPU_s'],material_validation_wall_s=read(B/'material-acceptance-v1/full.json').get('elapsed_seconds'),history_acquisition=dict(EE_training_trajectories=18,cheap_old_B_AB=36,CPU_s=None,wall_s=None,reason='historical acquisition aggregate not independently recovered; UNKNOWN, no zerocharge claim'),orchestrator=read(B/'execution-complete.json') if (B/'execution-complete.json').exists() else None,unknown_costs=['unmeasured shell/receipt/serializationtails','developer2 initial failedanalysis CPU','historicalfromscratch acquisition aggregate','original initialforecast wall','humanmodeldevelopment time notinstrumented'],saving_quantified_only_with_four_quality=True)
 summary=dict(schema='P16-analysis-v1',time=now(),freeze=read(B/'freeze-receipt.json')['commit'],all_retrospective_scoring=True,new_query_process='prospectivelyfrozen beforelabels, independent mainseed fromhistorical fitting; developerinitialtemplates used',truth=dict(valid=sum(x['valid'] for x in truth.values()),complete=sum(x['complete'] for x in truth.values()),task={l:sum(x['task']==l for x in truth.values()) for l in ['SUCCESS','FAIL','UNKNOWN']},prefix_failed_before_B=sum(x['prefix_failed_before_B'] is True for x in truth.values()),not_reached_B=sum(not x['B_plan_reached'] for x in truth.values())),comparisons=comparison,methods=metrics,reuse=dict(transfer_attempts=len(transfer),accepted=sum(x['accepted'] for x in transfer),classification_changes=sum(x.get('classification_changed',False) for x in transfer),accepted_actual_domain_rejections=sum(x.get('actual_receiver_domain_pass') is False for x in transfer),interval_counterexamples=sum(x.get('whole_peak_interval_covered') is False for x in transfer),danger_as_safe=sum(x.get('frozen_danger_as_safe',False) for x in transfer)),seed2_quality=seedquality,seed2_comparison=seedcomparison,costs=costsout,analysis_CPU_s=time.process_time()-start,scientific_scope='finite24 grid one mainseed, secondseed6descriptive; no continuous or allseed guarantee; prefixfailure not new B effect')
 write(out/'delivery.json',summary);write(out/'costs.json',costsout);write(out/'seed2.json',dict(quality=seedquality,comparison=seedcomparison,truth=seedtruth));figures(out,pool,truth,maps,metrics);print(json.dumps(dict(comparisons=comparison,reuse=summary['reuse'],truth=summary['truth']),indent=2))

def figures(out,pool,truth,maps,metrics):
 import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
 fig,axs=plt.subplots(2,2,figsize=(12,8),sharex=True)
 for ax,curve in zip(axs.flat,sorted({curve_key(c) for c in pool})):
  cs=sorted([c for c in pool if curve_key(c)==curve],key=lambda c:c['G']);xs=[c['G'] for c in cs];ys=[truth[c['id']]['peak_loss'] for c in cs];ax.plot(xs,ys,'ko-',label='SITL LP loss')
  for method in ['G','R']:
   pp=maps[method][-1]['prediction'];ax.plot(xs,[pp[c['id']].get('peak_loss',float('nan')) for c in cs],'--',label=method+' q8')
  ax.axhline(1,color='r',lw=1);ax.set_title(curve);ax.set_ylabel('LP maximum loss (m)');ax.legend(fontsize=8);ax.grid(alpha=.25)
 fig.supxlabel('Recovery interval G (s)');fig.tight_layout();fig.savefig(out/'boundary-height.png',dpi=150);plt.close(fig)
 fig,axs=plt.subplots(2,2,figsize=(12,8))
 for n,x in metrics.items():
  ss=x['series'];q=[s['query'] for s in ss]
  for ax,k in zip(axs.flat,['accuracy','danger_as_safe','prediction_unknown','coverage']):ax.plot(q,[s['quality']['components']['task'][k] for s in ss],'-o',ms=3,label=n);ax.set_title(k);ax.set_xlabel('Own query count');ax.grid(alpha=.25)
 axs[0,0].axhline(.9,color='k',ls=':');axs[1,1].axhline(.9,color='k',ls=':');axs[0,0].legend();fig.tight_layout();fig.savefig(out/'quality-query.png',dpi=150);plt.close(fig)
 fig,ax=plt.subplots(figsize=(9,5))
 for n,x in metrics.items():ax.plot([s['pairwise_half_prep_wall_lower_s']/60 for s in x['series']],[s['quality']['components']['task']['accuracy'] for s in x['series']],'-o',ms=3,label=n)
 ax.axhline(.9,color='k',ls=':');ax.set_xlabel('Standalone full query + half common prep wall lower bound (min)');ax.set_ylabel('Task accuracy');ax.legend();ax.grid(alpha=.25);fig.tight_layout();fig.savefig(out/'quality-cost.png',dpi=150);plt.close(fig)
if __name__=='__main__':main(sys.argv[1])

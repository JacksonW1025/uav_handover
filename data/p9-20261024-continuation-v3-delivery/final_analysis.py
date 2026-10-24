"""Post-flight disclosure of170 main records and3 historical exceptions. No fit."""
import argparse,csv,json,sys
from pathlib import Path
import numpy as np
from pyulog import ULog
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT/'tools'))
from p9_model import write,sha
from p1_metrics import tilt_deg

def csvsave(path,rr):
 with path.open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve();out.mkdir(exist_ok=False)
 report=ROOT/'data/p9-20261024-continuation-v3-report';rp=report/'prediction-measurement-ledger.csv';rows=list(csv.DictReader(rp.open()));assert len(rows)==170
 byid={r['id']:r for r in rows};ledger=ROOT/'data/p9-20261024-preparation/attempts.jsonl';L=[json.loads(x) for x in ledger.read_text().splitlines()];starts=[x for x in L if x['event']=='START_INTENT'];ends={x['id']:x for x in L if x['event']=='FINISH'}
 inputs={};idx=[];cost=[];compute=0.
 for s in starts:
  end=ends.get(s['id']);cost.append({'id':s['id'],'budget_class':s['budget_class'],'attempt_number':s['attempt_number'],'start':s['time'],'finish':end.get('time') if end else None,'elapsed_s':end.get('elapsed_s') if end else None,'legacy_infrastructure_ok':end.get('infrastructure_ok') if end else None,'observed_flight_failure':end.get('observed_flight_failure',end.get('flight_failure')) if end else None,'admitted_v3':end.get('evidence_admissible_v3') if end else None})
  if s['budget_class']!='formal':continue
  before=ROOT/s['output']/'prediction-before-query.json';b=json.loads(before.read_text());compute+=b['row'].get('prediction_compute_s',0.);r=byid.get(s['id']);actual=json.loads((ROOT/s['output']/'result.json').read_text()) if (ROOT/s['output']/'result.json').exists() else None
  state=('MAIN_'+r['measurement_kind']) if r else {102:'ORIGINAL102_INFRA_MISSING',162:'OLD162_POSTFLIGHT_DIAGNOSTIC',164:'OLD164_P7_GATE_FAIL_POSTHOC_ONLY'}[s['attempt_number']]
  idx.append({'attempt_number':s['attempt_number'],'id':s['id'],'stage':s['stage'],'seed':s['seed'],'state':state,'point_tilt_deg':b['prediction']['point_tilt_deg'],'empirical_range_deg':json.dumps(b['prediction']['empirical_tilt_range_deg']),'predicted_height_m':None,'overall_skip':b['prediction']['overall_skip'],'overall_decision':b['prediction']['overall_decision'],'main_tilt_deg':r['observed_tilt_deg'] if r else None,'measurement_epoch':r['execution_epoch'] if r else None,'opportunity':actual.get('opportunity_v3',{}).get('state') if actual else None,'v3_exception':actual.get('admission_v3',{}).get('exception_not_reached') if actual else None,'prediction_sha256':sha(before),'before_path':str(before.relative_to(ROOT))});inputs[str(before.relative_to(ROOT))]=sha(before)
 assert len(idx)==173 and len(set(r['id'] for r in idx))==173
 csvsave(out/'all-173-starts.csv',idx);csvsave(out/'all-attempt-costs.csv',cost)
 dr=[];segments=[]
 for r in rows:
  if r['stage']!='D':continue
  run=ROOT/r['evidence_directory']/'run';metric=run/('p9-v2-metrics.json' if r['measurement_kind']=='OPEN_GAP_CENSORED' else 'p9-metrics.json');m=json.loads(metric.read_text());last=next((x for x in m['recoveries'] if x['index']==m['planned_interruptions']-1),{});cfg=json.loads((run/'config.json').read_text())
  dr.append({'id':r['id'],'arm':r['treatment'],'cluster':r['cluster'],'epoch':r['execution_epoch'],'measurement_kind':r['measurement_kind'],'complete_window':m['complete_window'],'max_tilt_deg':m['max_tilt_deg'],'max_altitude_loss_m':m['max_altitude_loss_m'],'max_lag_m':m['max_lag_m'],'max_horizontal_distance_m':m['max_horizontal_distance_m'],'integrated_abs_lag_m_s':m['integrated_abs_lag_m_s'],'primary_failure':r['primary_failure']=='True','tilt_failure':r['tilt_failure']=='True','altitude_failure':r['altitude_failure']=='True','task_outcome':m['task_outcome'],'final_resume_observed':bool(last),'final_catch_up_s':last.get('vehicle_catch_up_10s_s'),'final_lag_at_6s_m':last.get('lag_at_6s_m'),'catch_up_censored':last.get('vehicle_catch_up_censored',True),'cost_outcome':m['final_task_cost_outcome']})
  u=ULog(str(run/'flight.ulg'),['vehicle_local_position','vehicle_attitude']);T={x.name:x.data for x in u.data_list if x.multi_id==0};lp=T['vehicle_local_position'];att=T['vehicle_attitude'];t0=m['clock_origin_native_us'];lt=(lp['timestamp_sample'].astype(float)-t0)/1e6;at=(att['timestamp'].astype(float)-t0)/1e6;theta=tilt_deg(np.column_stack([att[f'q[{k}]'] for k in range(4)]));z0=np.interp(0.,lt,lp['z']);end=m['window_observed_s'][1];w=(at>=0)&(at<=min(16.,end));assert abs(float(theta[w].max())-m['max_tilt_deg'])<1e-6
  ws=cfg['p5_condition_spec']['gaps']['windows_s'];offset=cfg['p2_profile']['pre_gap_s']-1.
  for k,(a,b) in enumerate(ws):
   begin=offset+a;finish=offset+ws[k+1][0] if k+1<len(ws) else 16.;w=(at>=begin)&(at<min(finish,end));z=(lt>=begin)&(lt<min(finish,end));peak=float(theta[w].max()) if w.any() else None;loss=max(0.,float((lp['z'][z]-z0).max())) if z.any() else None
   segments.append({'id':r['id'],'arm':r['treatment'],'cluster':r['cluster'],'event_index':k,'planned_start_s':begin,'planned_end_s':finish,'observed':'NOT_REACHED' if end<begin else ('COMPLETE' if end>=finish-.02 else 'CENSORED'),'peak_tilt_deg':peak,'global_altitude_loss_m':loss,'observed_tilt_ge45':None if peak is None else peak>=45.,'observed_altitude_gt1':None if loss is None else loss>1.})
  for x in [run/'flight.ulg',metric,run/'config.json']:inputs[str(x.relative_to(ROOT))]=sha(x)
 assert len(dr)==34
 csvsave(out/'D34-main-task-costs.csv',dr);csvsave(out/'D-planned-segment-risks.csv',segments)
 arms={}
 for arm in ['P9-Z','P9-C','P9-R','P9-CR']:
  rr=[r for r in dr if r['arm']==arm];v={'n':len(rr),'complete_n':sum(r['complete_window'] for r in rr),'primary_failures':sum(r['primary_failure'] for r in rr),'tilt_failures':sum(r['tilt_failure'] for r in rr),'tilt_known_n':sum(r['complete_window'] or r['tilt_failure'] for r in rr),'height_failures':sum(r['altitude_failure'] for r in rr),'height_known_n':sum(r['complete_window'] or r['altitude_failure'] for r in rr),'task_failures':sum(r['task_outcome']=='FAILURE' for r in rr),'task_known_n':sum(r['task_outcome'] in ['SUCCESS','FAILURE'] for r in rr),'cost_outcomes':{s:sum(r['cost_outcome']==s for r in rr) for s in ['SUCCESS','FAILURE','CENSORED','UNOBSERVED_FINAL_RESUME']}}
  for key in ['max_tilt_deg','max_altitude_loss_m','max_lag_m','max_horizontal_distance_m','integrated_abs_lag_m_s','final_catch_up_s','final_lag_at_6s_m']:
   vals=[r[key] for r in rr if r[key] is not None];v[key]={'observed_n':len(vals),'range':[min(vals),max(vals)] if vals else None,'censored_extrema_are_lower_bounds':key.startswith('max_')}
  arms[arm]=v
 write(out/'D-arm-summary.json',arms)
 new=json.loads((ROOT/'data/p9-20261024-continuation-v3-formal/results.json').read_text())['runs'];assert len(new)==9 and all(r['admissible_v3'] for r in new)
 write(out/'final-accounting.json',{'formal_starts':173,'formal_FINISH':sum(s['budget_class']=='formal' and s['id'] in ends for s in starts),'development_starts':10,'main_measurements':170,'D_main':34,'D_arm_counts':{k:v['n'] for k,v in arms.items()},'D_complete_four_arm_clusters':8,'old102_missing':True,'old162_diagnostic_only':True,'old164_posthoc_only':True,'unused_search_slots':7,'NOT_RUN_static':0,'new_v3_n':9,'new_v3_legacy_P7_incomplete_n':sum(not r['checks']['p7_measured'] for r in new),'new_v3_exception_n':sum(r['admission_v3']['exception_not_reached'] for r in new),'new_v3_observed_flight_failure_n':sum(r['observed_flight_failure'] for r in new),'no_overall_acceptance_PASS':True})
 write(out/'cost-summary.json',{'all_FINISH_formal_elapsed_s':sum(r['elapsed_s'] or 0 for r in cost if r['budget_class']=='formal'),'main170_elapsed_s':sum(float(r['elapsed_s']) for r in rows),'new9_elapsed_s':sum(r['elapsed_s'] for r in new),'old164_elapsed_s_excluded_from_main':75.86688087892253,'old102_start_to_cleanup_s':421.028078,'old162_start_to_exception_s':74.193239,'development_elapsed_s':sum(r['elapsed_s'] or 0 for r in cost if r['budget_class']=='development'),'all173_prediction_compute_s':compute,'v3_final161_noflight_replay_s':json.loads((ROOT/'data/p9-20261024-continuation-v3-preparation/compatibility-161.json').read_text())['elapsed_s'],'v3_initial161_noflight_replay_s':json.loads((ROOT/'data/p9-20261024-continuation-v3-preparation/compatibility-161-initial.json').read_text())['elapsed_s'],'human_adaptation_hours':None,'new_identification_flights':0})
 # Eight full main clusters; D07 has only the two repair arms in the main set.
 import matplotlib
 matplotlib.use('Agg');import matplotlib.pyplot as plt
 al=['P9-Z','P9-C','P9-R','P9-CR'];fig,axes=plt.subplots(2,2,figsize=(11,7),layout='constrained')
 for ax,key,label,lim in [(axes[0,0],'max_tilt_deg','Peak tilt (deg)',45),(axes[0,1],'max_altitude_loss_m','Altitude loss (m)',1),(axes[1,0],'max_lag_m','Maximum lag (m)',4.5)]:
  for k,c in enumerate(sorted({r['cluster'] for r in dr})):
   rr=[r for r in dr if r['cluster']==c]
   if len(rr)==4:
    rr=[next(r for r in rr if r['arm']==a) for a in al];x=np.arange(4)+(k-4)*.014;y=[r[key] for r in rr];ax.plot(x,y,c='0.8',lw=.7)
    for xi,yi,r in zip(x,y,rr):ax.scatter(xi,yi,c=f'C{k}',marker='o' if r['complete_window'] else '^',s=23)
   else:
    for r in rr:ax.scatter(al.index(r['arm']),r[key],c='black',marker='D',s=36,label='Partial D07' if r['arm']=='P9-C' else None)
  ax.set(xticks=range(4),xticklabels=al,ylabel=label);ax.axhline(lim,c='black',lw=.7);ax.legend(fontsize=8)
 ax=axes[1,1];bottom=np.zeros(4)
 for status,label,c in [('SUCCESS','Cost success','#009E73'),('FAILURE','Cost failure','#D55E00'),('CENSORED','Censored','#E69F00'),('UNOBSERVED_FINAL_RESUME','Final resume unobserved','#999999')]:
  n=np.array([sum(r['arm']==a and r['cost_outcome']==status for r in dr) for a in al]);ax.bar(range(4),n,bottom=bottom,label=label,color=c);bottom+=n
 ax.set(xticks=range(4),xticklabels=al,ylabel='Main runs (Z/R=8; C/CR=9)');ax.legend(fontsize=8)
 fig.suptitle('D34 main measurements: eight complete clusters; partial D07 marked black\nOld162/Z07 and164/R07 disclosed separately; triangles are censored lower bounds',fontsize=11)
 fig.savefig(out/'D34-reviewed.png',dpi=180);fig.savefig(out/'D34-reviewed.pdf');plt.close(fig)
 for x in [ledger,rp,report/'results.json',Path(__file__).resolve()]:inputs[str(x.relative_to(ROOT))]=sha(x)
 write(out/'input-manifest.json',inputs);write(out/'output-manifest.json',{x.name:sha(x) for x in out.iterdir() if x.is_file() and x.name!='output-manifest.json'})
 print('FINAL analysis170 main,173 starts,D34; old exceptions separate')
if __name__=='__main__':main()

"""Post-flight all164 starts and compact D25 review, fresh output only."""
import argparse,csv,json,sys,hashlib
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT/'tools'))
from p9_model import write,sha

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve();out.mkdir(exist_ok=False)
 report=ROOT/'data/p9-20261024-continuation-v3-report-stopped-v2';rp=report/'prediction-measurement-ledger.csv';rows=list(csv.DictReader(rp.open()));byid={r['id']:r for r in rows};assert len(rows)==165
 lp=ROOT/'data/p9-20261024-preparation/attempts.jsonl';L=[json.loads(x) for x in lp.read_text().splitlines()];starts=[x for x in L if x['event']=='START_INTENT'];ends={x['id']:x for x in L if x['event']=='FINISH'}
 index=[];cost=[];inputs={};compute=0.
 for s in starts:
  e=ends.get(s['id']);cost.append({'id':s['id'],'budget_class':s['budget_class'],'attempt_number':s['attempt_number'],'start':s['time'],'finish':e.get('time') if e else None,'elapsed_s':e.get('elapsed_s') if e else None,'infrastructure_ok':e.get('infrastructure_ok') if e else None})
  if s['budget_class']!='formal':continue
  path=ROOT/s['output']/'prediction-before-query.json';b=json.loads(path.read_text());inputs[str(path.relative_to(ROOT))]=sha(path);compute+=b['row'].get('prediction_compute_s',0.);r=byid.get(s['id'])
  status='ADMITTED_ORIGINAL_COMPATIBLE' if r else {102:'ORIGINAL_INFRA_MISSING',162:'ORIGINAL_POSTFLIGHT_DIAGNOSTIC_ONLY',164:'V2_OPEN_GAP_MEASURED_P7_GATE_FAIL',169:'V3_UNPLANNED_RECOVERY_GATE_FAIL'}[s['attempt_number']]
  index.append({'attempt_number':s['attempt_number'],'id':s['id'],'seed':s['seed'],'stage':s['stage'],'state':status,'point_tilt_deg':b['prediction']['point_tilt_deg'],'empirical_range_deg':json.dumps(b['prediction']['empirical_tilt_range_deg']),'predicted_altitude_loss_m':None,'overall_skip':b['prediction']['overall_skip'],'overall_decision':b['prediction']['overall_decision'],'admitted_observed_tilt_deg':r['observed_tilt_deg'] if r else None,'prediction_sha256':sha(path),'before_path':str(path.relative_to(ROOT))})
 assert len(index)==169
 def csvsave(path,rr):
  with path.open('w') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
 csvsave(out/'all-169-starts.csv',index);csvsave(out/'all-attempt-costs.csv',cost)
 d=[]
 for r in rows:
  if r['stage']!='D':continue
  path=ROOT/r['evidence_directory']/'run/p9-metrics.json';m=json.loads(path.read_text());last=next((x for x in m['recoveries'] if x['index']==m['planned_interruptions']-1),{})
  d.append({'id':r['id'],'arm':r['treatment'],'cluster':r['cluster'],'complete_window':m['complete_window'],'max_tilt_deg':m['max_tilt_deg'],'max_altitude_loss_m':m['max_altitude_loss_m'],'max_lag_m':m['max_lag_m'],'max_horizontal_distance_m':m['max_horizontal_distance_m'],'integrated_abs_lag_m_s':m['integrated_abs_lag_m_s'],'task_outcome':m['task_outcome'],'final_catch_up_s':last.get('vehicle_catch_up_10s_s'),'final_lag_at_6s_m':last.get('lag_at_6s_m'),'cost_outcome':m['final_task_cost_outcome']});inputs[str(path.relative_to(ROOT))]=sha(path)
 assert len(d)==29
 csvsave(out/'D29-admitted-task-costs.csv',d)
 separate=[]
 for rid,path,scope in [('D-07-P9-Z',ROOT/'data/p9-20261024-continuation-v1-stopped-analysis/attempt162-diagnostic/p9-open-gap-diagnostic.json','ORIGINAL162_POSTFLIGHT_ONLY'),('D-07-P9-R',ROOT/'data/p9-20261024-continuation-v2-formal/D-07-P9-R/run/p9-v2-assessment.json','NEW164_FROZEN_V2_MEASUREMENT_P7_GATE_FAIL')]:
  doc=json.loads(path.read_text());m=doc.get('measurement',doc);separate.append({'id':rid,'scope':scope,'admitted':False,'observed_until_s':m['window_observed_s'][1],'max_tilt_deg':m['max_tilt_deg'],'max_altitude_loss_m':m['max_altitude_loss_m'],'altitude_full_window_known':m['complete_window'],'recoveries':m['recoveries'],'final_cost_outcome':m['final_task_cost_outcome']});inputs[str(path.relative_to(ROOT))]=sha(path)
 write(out/'D07-Z-R-separate-failures.json',{'rows':separate,'meaning':'both failed before first resume; no evidence of activated/completed rate-limited recovery; censored peaks are lower bounds, no admission into D25'})
 summary={'formal_starts':169,'formal_FINISH_records':sum(x['budget_class']=='formal' and x['id'] in ends for x in starts),'admitted_original_compatible_measurements':165,'original102_missing':True,'original162_postflight_only':True,'new164_open_gap_measured_but_P7_gate_fail':True,'new169_unplanned_recovery_gate_fail':True,'D_admitted':29,'D_started':32,'D_NOT_RUN':4,'D_complete_four_arm_clusters':6,'D_arm_counts':{arm:sum(x['arm']==arm for x in d) for arm in ['P9-Z','P9-C','P9-R','P9-CR']},'development_starts':10,'unused_search_slots':7,'approved_formal_cap':173,'recorded_formal_FINISH_elapsed_s_includes_failed164':sum(x['elapsed_s'] or 0 for x in cost if x['budget_class']=='formal'),'admitted165_elapsed_s':sum(float(r['elapsed_s']) for r in rows),'failed164_elapsed_s':75.86688087892253,'failed169_elapsed_s':107.27256065094844,'original102_start_to_cleanup_wall_s':421.028078,'original162_start_to_exception_wall_s':74.193239,'all169_before_prediction_compute_s':compute,'whole_acceptance':'NO_PASS','next_scope':'No automatic further batch or retry. Extra setup recovery in169 is not an approved exception; four D09 arms remain NOT_RUN; preserve169 P7 FAIL and all previous exceptions.'}
 write(out/'assessment.json',summary)
 import matplotlib
 matplotlib.use('Agg');import matplotlib.pyplot as plt
 arms=['P9-Z','P9-C','P9-R','P9-CR'];fig,axes=plt.subplots(2,2,figsize=(11,7),layout='constrained')
 for ax,key,label,lim in [(axes[0,0],'max_tilt_deg','Peak tilt (deg)',45),(axes[0,1],'max_altitude_loss_m','Altitude loss (m)',1),(axes[1,0],'max_lag_m','Maximum lag (m)',4.5)]:
  for k,c in enumerate(sorted({r['cluster'] for r in d})):
   rr=[r for r in d if r['cluster']==c]
   if len(rr)==4:
    rr=[next(r for r in rr if r['arm']==a) for a in arms];x=np.arange(4)+(k-2.5)*.018;y=[r[key] for r in rr];ax.plot(x,y,color='0.8',lw=.7)
    for xi,yi,r in zip(x,y,rr):ax.scatter(xi,yi,c=f'C{k}',marker='o' if r['complete_window'] else '^',s=25)
   else:
    for r in rr:ax.scatter(arms.index(r['arm']),r[key],c='black',marker='D',s=38,label='Partial D07/D08' if r['cluster']=='D-07' and r['arm']=='P9-C' else None)
  ax.set(xticks=range(4),xticklabels=arms,ylabel=label);ax.axhline(lim,c='black',lw=.7);ax.legend(fontsize=8)
 ax=axes[1,1];bottom=np.zeros(4)
 for outcome,label,color in [('SUCCESS','Cost success','#009E73'),('FAILURE','Cost failure','#D55E00'),('CENSORED','Censored','#E69F00'),('UNOBSERVED_FINAL_RESUME','Final resume unobserved','#999999')]:
  y=np.array([sum(r['arm']==a and r['cost_outcome']==outcome for r in d) for a in arms]);ax.bar(range(4),y,bottom=bottom,label=label,color=color);bottom+=y
 ax.set(xticks=range(4),xticklabels=arms,ylabel='Admitted runs (C=8; others=7)');ax.legend(fontsize=8)
 fig.suptitle('D partial: six complete clusters + partial D07/D08; four D09 arms not run\nOld Z07/R07 and new CR08 protocol exceptions are disclosed separately; triangles are censored',fontsize=10)
 fig.savefig(out/'D29-reviewed.png',dpi=180);fig.savefig(out/'D29-reviewed.pdf');plt.close(fig)
 for path in [lp,rp,Path(__file__).resolve()]:inputs[str(path.relative_to(ROOT))]=sha(path)
 write(out/'input-manifest.json',inputs);write(out/'output-manifest.json',{x.name:sha(x) for x in out.iterdir() if x.is_file() and x.name!='output-manifest.json'})
 print(json.dumps(summary))
if __name__=='__main__':main()

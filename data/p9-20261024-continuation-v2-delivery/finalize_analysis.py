#!/usr/bin/env python3
"""Post-flight disclosure only: all173 starts, D cost/diagnostic scopes, no fit."""
import argparse,csv,json,sys,hashlib
from pathlib import Path
from datetime import datetime
import numpy as np
from pyulog import ULog
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT/'tools'))
from p9_model import write,sha
from p1_metrics import tilt_deg

def savecsv(path,rows):
 with path.open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve();out.mkdir(exist_ok=False)
 report=ROOT/'data/p9-20261024-continuation-v2-report';results=json.loads((report/'results.json').read_text());assert results['attempts']=={'development':10,'formal':173} and results['formal_runs_with_results']==171
 rows=list(csv.DictReader((report/'prediction-measurement-ledger.csv').open()));byid={r['id']:r for r in rows}
 lp=ROOT/'data/p9-20261024-preparation/attempts.jsonl';L=[json.loads(x) for x in lp.read_text().splitlines()];starts=[r for r in L if r['event']=='START_INTENT'];ends={r['id']:r for r in L if r['event']=='FINISH'}
 index=[];compute=0.;inputs={};cost=[]
 for s in starts:
  end=ends.get(s['id']);cost.append({'id':s['id'],'budget_class':s['budget_class'],'attempt_number':s['attempt_number'],'started_at':s['time'],'finished_at':end.get('time') if end else None,'elapsed_s':end.get('elapsed_s') if end else None,'infrastructure_ok':end.get('infrastructure_ok') if end else None,'flight_failure':end.get('flight_failure') if end else None})
  if s['budget_class']!='formal':continue
  bpath=ROOT/s['output']/'prediction-before-query.json';b=json.loads(bpath.read_text());compute+=b['row'].get('prediction_compute_s',0.);inputs[str(bpath.relative_to(ROOT))]=sha(bpath)
  r=byid.get(s['id']);status='MEASURED_'+r['measurement_kind'] if r else ('ORIGINAL102_INFRA_MISSING' if s['attempt_number']==102 else 'ORIGINAL162_POSTFLIGHT_DIAGNOSTIC_ONLY')
  index.append({'attempt_number':s['attempt_number'],'id':s['id'],'seed':s['seed'],'stage':s['stage'],'state':status,'measurement_version':r['execution_epoch'] if r else None,'point_tilt_deg':b['prediction']['point_tilt_deg'],'empirical_range_deg':json.dumps(b['prediction']['empirical_tilt_range_deg']),'predicted_altitude_loss_m':None,'overall_skip':b['prediction']['overall_skip'],'overall_decision':b['prediction']['overall_decision'],'observed_tilt_deg':r['observed_tilt_deg'] if r else None,'primary_failure':r['primary_failure'] if r else (True if s['attempt_number']==162 else None),'prediction_sha256':sha(bpath),'before_path':str(bpath.relative_to(ROOT))})
 assert len(index)==173 and len({x['id'] for x in index})==173
 savecsv(out/'all-173-starts.csv',index);savecsv(out/'all-attempt-costs.csv',cost)
 drows=[];segments=[];main_d=[r for r in rows if r['stage']=='D'];assert len(main_d)==35
 diagpath=ROOT/'data/p9-20261024-continuation-v1-stopped-analysis/attempt162-diagnostic/p9-open-gap-diagnostic.json';diag=json.loads(diagpath.read_text())
 work=[(r,'MAIN_MEASUREMENT') for r in main_d]+[({'id':'D-07-P9-Z','treatment':'P9-Z','cluster':'D-07','evidence_directory':'data/p9-20261024-continuation-v1-formal/D-07-P9-Z','measurement_kind':'POSTFLIGHT_DIAGNOSTIC_ONLY'},'ORIGINAL162_DIAGNOSTIC_ONLY')]
 for r,scope in work:
  run=ROOT/r['evidence_directory']/'run';path=run/('p9-v2-metrics.json' if r.get('measurement_kind')=='OPEN_GAP_CENSORED' else 'p9-metrics.json');m=json.loads(path.read_text()) if scope=='MAIN_MEASUREMENT' else diag
  cfg=json.loads((run/'config.json').read_text());last=next((x for x in m['recoveries'] if x['index']==m['planned_interruptions']-1),{})
  drows.append({'id':r['id'],'arm':r['treatment'],'cluster':r['cluster'],'scope':scope,'measurement_kind':r['measurement_kind'],'complete_window':m['complete_window'],'observed_until_s':m['window_observed_s'][1],'max_tilt_deg':m['max_tilt_deg'],'max_altitude_loss_m':m['max_altitude_loss_m'],'max_lag_m':m['max_lag_m'],'max_horizontal_distance_m':m['max_horizontal_distance_m'],'integrated_abs_lag_m_s':m['integrated_abs_lag_m_s'],'frozen_primary_outcome':m['frozen_primary_outcome'],'task_outcome':m['task_outcome'],'final_resume_observed':bool(last),'catch_up_s':last.get('vehicle_catch_up_10s_s'),'catch_up_censored':last.get('vehicle_catch_up_censored',True),'lag_at_6s_m':last.get('lag_at_6s_m'),'cost_outcome':m['final_task_cost_outcome']})
  u=ULog(str(run/'flight.ulg'),['vehicle_local_position','vehicle_attitude']);T={x.name:x.data for x in u.data_list if x.multi_id==0};local=T['vehicle_local_position'];at=T['vehicle_attitude'];t0=m['clock_origin_native_us'];lt=(np.asarray(local['timestamp_sample'],float)-t0)/1e6;tt=(np.asarray(at['timestamp'],float)-t0)/1e6;z0=np.interp(0.,lt,local['z']);theta=tilt_deg(np.column_stack([at[f'q[{i}]'] for i in range(4)]));end=m['window_observed_s'][1]
  aw=(tt>=0)&(tt<=min(16.,end));assert abs(float(theta[aw].max())-m['max_tilt_deg'])<1e-6
  ws=cfg['p5_condition_spec']['gaps']['windows_s'];offset=float(cfg['p2_profile']['pre_gap_s'])-1.
  for k,(a,b) in enumerate(ws):
   start=offset+a;finish=offset+ws[k+1][0] if k+1<len(ws) else 16.;aw=(tt>=start)&(tt<min(end,finish));zw=(lt>=start)&(lt<min(end,finish));peak=float(theta[aw].max()) if aw.any() else None;loss=max(0.,float((local['z'][zw]-z0).max())) if zw.any() else None
   segments.append({'id':r['id'],'arm':r['treatment'],'cluster':r['cluster'],'scope':scope,'planned_event_index':k,'planned_start_s':start,'planned_end_s':finish,'observation':'NOT_REACHED' if end<start else ('COMPLETE' if end>=finish-.02 else 'CENSORED'),'peak_tilt_deg':peak,'global_baseline_altitude_loss_m':loss,'observed_tilt_ge45':None if peak is None else peak>=45.,'observed_height_gt1':None if loss is None else loss>1.})
  for x in [run/'flight.ulg',run/'config.json',path if scope=='MAIN_MEASUREMENT' else diagpath]:inputs[str(x.relative_to(ROOT))]=sha(x)
 savecsv(out/'D35-main-task-costs.csv',[r for r in drows if r['scope']=='MAIN_MEASUREMENT']);savecsv(out/'D07-with-separate-diagnostic.csv',[r for r in drows if r['cluster']=='D-07']);savecsv(out/'D-planned-segment-risks.csv',segments)
 arms={}
 for arm in ['P9-Z','P9-C','P9-R','P9-CR']:
  rr=[r for r in drows if r['arm']==arm and r['scope']=='MAIN_MEASUREMENT'];v={'n':len(rr),'complete_n':sum(r['complete_window'] for r in rr),'primary_failure_n':sum(r['frozen_primary_outcome']=='FAILURE' for r in rr),'task_failure_n':sum(r['task_outcome']=='FAILURE' for r in rr),'cost_outcomes':{x:sum(r['cost_outcome']==x for r in rr) for x in ['SUCCESS','FAILURE','CENSORED','UNOBSERVED_FINAL_RESUME']}}
  for key in ['max_tilt_deg','max_altitude_loss_m','max_lag_m','max_horizontal_distance_m','integrated_abs_lag_m_s','catch_up_s','lag_at_6s_m']:
   vals=[r[key] for r in rr if r[key] is not None];v[key]={'observed_n':len(vals),'range':[min(vals),max(vals)] if vals else None,'censored_extrema_are_lower_bounds':key.startswith('max_')}
  arms[arm]=v
 write(out/'D-arm-summary.json',arms)
 write(out/'cost-summary.json',{'completed_formal_elapsed_s':sum(r['elapsed_s'] or 0 for r in cost if r['budget_class']=='formal'),'completed_development_elapsed_s':sum(r['elapsed_s'] or 0 for r in cost if r['budget_class']=='development'),'all173_prediction_compute_s':compute,'original102_start_to_cleanup_wall_s':421.028078,'original162_start_to_exception_wall_s':74.193239,'unknown_original_FINISH_elapsed_not_zero':True,'human_adaptation_hours':None,'initial_fit_elapsed_s':None,'no_new_identification_flights':True,'measurement_v2_no_flight_compatibility160_s':json.loads((ROOT/'data/p9-20261024-continuation-v2-preparation/compatibility-160.json').read_text())['elapsed_s']})
 for x in [lp,report/'results.json',report/'prediction-measurement-ledger.csv',Path(__file__).resolve()]:inputs[str(x.relative_to(ROOT))]=sha(x)
 write(out/'input-manifest.json',inputs);write(out/'output-manifest.json',{x.name:sha(x) for x in out.iterdir() if x.is_file() and x.name!='output-manifest.json'})
 print('FINAL DISCLOSURE173 starts,171 main,162 separate; D35 main+1 diagnostic; no data selection')
if __name__=='__main__':main()

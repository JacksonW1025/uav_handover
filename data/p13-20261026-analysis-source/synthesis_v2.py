from analysis_paths_v1 import analysis_dir
"""Summarize assigned flights, component denominators and interval curves."""
import sys,json
from pathlib import Path
from collections import Counter
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'));sys.path.insert(0,str(Path(__file__).parent))
from p9_model import write,sha
from time_process_v2 import process

def describe(x):
 a=np.array([v for v in x if v is not None],dtype=float)
 return {'n':len(a),'mean':float(a.mean()),'min':float(a.min()),'max':float(a.max())} if len(a) else {'n':0}
def synth(aggregate,out):
 out.mkdir(parents=True,exist_ok=False);case_rows=json.load(open(aggregate/'cases.json'))['rows'];done=[r for r in case_rows if r['status']=='FINISH'];contrasts=json.load(open(aggregate/'contrasts.json'))['rows'];per=[];scores=[];models={n:{} for n in ['M3','M4','M5']}
 for row in done:
  ident=row['id'];tar=R/'data/p13-20261026-formal'/ident;ar=R/'data/p13-20261026-formal-analysis-v3'/ident;p=process(tar,ar,out/'records'/ident);s=json.load(open(analysis_dir(tar)/'score/score.json'));scores.append({'id':ident,'family':row['family'],'block':row['block'],'arm':row['arm'],'models':s['models']});per.append({'id':ident,'family':row['family'],'block':row['block'],'arm':row['arm'],'process':p})
 for name in models:
  comp={}
  for part,key in [('tilt','risk_comparison'),('height','height_risk_comparison'),('task','task_risk_comparison')]:
   count=Counter(x['models'][name][key] for x in scores);eligible=sum(bool(x['models'][name]['risk']['classification_eligible'][part]) for x in scores);comp[part]={'counts':dict(count),'all_assigned_finished_flights':len(done),'classification_eligible':eligible,'agreement_n':count['AGREEMENT'],'agreement_fraction_among_eligible':count['AGREEMENT']/eligible if eligible else None,'UNKNOWN_retained':sum(v for k,v in count.items() if k.startswith('UNKNOWN')),'denominator':'one flight, not model/window. Shared blocks remain correlated; UNKNOWN never counted as agreement'}
  windows={}
  for part,key in [('tilt','risk_comparison'),('height','height_risk_comparison'),('task','task_risk_comparison')]:
   cs=Counter(v[key] for x in scores for v in x['models'][name]['event_windows']);windows[part]={'counts':dict(cs),'window_count':sum(cs.values()),'not_independent_flights':True}
  pp=[x['process']['full_prefix'][name] for x in per];errkeys=sorted(set(k for x in pp for k in x['errors']));bkeys=sorted(set(k for x in pp for k in x['B_before'] if k not in ['status','planned_B_profile_s','evaluated_profile_s']));models[name]={'whole_or_valid_witness_classification':comp,'full_prediction_count':sum(x['models'][name]['full_prediction'] for x in scores),'full_observation_and_prediction_count':sum(x['models'][name]['risk']['prediction_complete'] and x['models'][name]['risk']['observation_complete'] for x in scores),'overlapping_event_windows':windows,'full_prefix_error_max_per_flight':{k:describe([x['errors'].get(k,{}).get('max_abs') if x['errors'].get(k) else None for x in pp]) for k in errkeys},'B_before_status':dict(Counter(x['B_before']['status'] for x in pp)),'B_before_absolute_errors':{k:describe([abs(x['B_before'][k]) for x in pp if k in x['B_before']]) for k in bkeys},'compute_s':describe([x['compute_s'] for x in pp])}
 group=[]
 for fam in ['F2','F4']:
  for arm in ['NORMAL','A','B-short','B-medium','B-long','AB-short','AB-medium','AB-long','REPAIR-short','REPAIR-medium','REPAIR-long']:
   rr=[x for x in done if x['family']==fam and x['arm']==arm];group.append({'family':fam,'arm':arm,'n':len(rr),'task_counts':dict(Counter(x['task'] for x in rr)),'primary_counts':dict(Counter(x['primary'] for x in rr)),'censored':sum(x['censored'] for x in rr),'LP_peak_deg':describe([x['LP_peak_tilt_deg'] for x in rr]),'LP_loss_m':describe([x['LP_max_loss_m'] for x in rr]),'physical_COM_D_m':describe([x['physical']['COM_D_m'] for x in rr]),'physical_origin_D_m':describe([x['physical']['origin_D_m'] for x in rr]),'B_event_status_counts':dict(Counter(e['status'] for x in rr for e in x['event_statuses'] if e['label']=='B'))})
 effects=[]
 for fam in ['F2','F4']:
  for gap in ['short','medium','long']:
   rows=[x for x in contrasts if x['family']==fam and x['gap_label']==gap];costkeys=['aerodynamic_command_TV_rad_s','LP_horizontal_tracking_integral_m_s'];z={'family':fam,'gap':gap,'independent_blocks':len(rows),'single_success_combo_failure_blocks':sum(x['single_success_combo_failure_pattern'] for x in rows),'AB_minus_B_before':{k:describe([x.get('AB_minus_B_before',{}).get(k) for x in rows]) for k in ['COM_W_m_s','origin_L_m','origin_D_m','body_tilt_deg','h_l2','previous_l2','history_mean_l2','filter_l2_rad_s']},'initial_difference_ranges':{k:describe([x['AB_B_initial_differences'][k] for x in rows]) for k in rows[0]['AB_B_initial_differences']} if rows else {}}
   z['REPAIR_minus_AB_common_cost']={k:describe([x['common_window_costs_v3']['REPAIR_minus_AB'][k] for x in rows]) for k in costkeys}
   for k in ['post_joint_squared_rad2_per_s','thrust_impulse_Ns']:
    z['REPAIR_minus_AB_common_cost'][k]={'lower':describe([x['common_window_costs_v3']['REPAIR_minus_AB'][k]['lower'] for x in rows]),'upper':describe([x['common_window_costs_v3']['REPAIR_minus_AB'][k]['upper'] for x in rows])}
   effects.append(z)
 initial=[]
 for fam in ['F2','F4']:
  rr=[x for x in done if x['family']==fam];v=[]
  for x in rr:
   i=x['initial'];v.append({'id':x['id'],'physical_COM_W':i['physical_COM_v'][2],'LP_W':i['velocity'][2],'physical_COM_H':-i['physical_COM_p'][2],'LP_H':-i['position'][2],'h_l2':float(np.linalg.norm(i['h'])),'history_count':i['history_count'],'call_index':i['call_index'],'physical_host_age_us':i['physical_host_age_us'],'sample_native_delta_us':i['sample_us']-i['native_us']})
  initial.append({'family':fam,'rows':v,'ranges':{k:describe([r[k] for r in v]) for k in v[0] if k!='id'} if v else {}})
 write(out/'prediction-summary.json',{'schema':'p13-model-summary-1','models':models,'formal_flights':len(done),'no_refit':True,'window_vs_flight_vs_cluster_denominators_separate':True});write(out/'group-results.json',{'schema':'p13-group-results-1','rows':group,'effect_summary':effects,'independent_unit':'3 prespecified seed blocks per condition, correlated11 flights perblock; partial snapshots explicitly n<3'});write(out/'initial-covariates.json',{'schema':'p13-initial-covariates-1','families':initial,'no_matching_exclusion_or_count_normalization':True});write(out/'receipt.json',{'schema':'p13-synthesis-receipt-1','aggregate_receipt_sha256':sha(aggregate/'receipt.json'),'source_sha256':sha(Path(__file__)),'records':len(done),'unchanged_frozen_scores':True,'new_SITL':0});print('SYNTHESIS',len(done),[(n,models[n]['whole_or_valid_witness_classification']['tilt']['counts']) for n in models])
 return models
if __name__=='__main__':synth(Path(sys.argv[1]),Path(sys.argv[2]))

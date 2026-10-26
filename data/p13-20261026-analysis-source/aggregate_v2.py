"""Frozen block/interval estimands and raw contrasts; no post-treatment selection."""
import sys,json,csv
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'));sys.path.insert(0,str(Path(__file__).parent))
from p9_model import write,sha
from p11.models import R as matrix
from hold_axes_v1 import create as hold
from mechanical_costs_v2 import pair as common_cost_pair,costs as own_costs

def norm(x):return float(np.linalg.norm(x))
def angle(A,B):return float(np.degrees(np.arccos(np.clip((np.trace(A.T@B)-1)/2,-1,1))))
def aggregate(out,analysis_root):
 out.mkdir(parents=True,exist_ok=False);design=json.load(open(R/'config/p13-formal.json'));ledger=[json.loads(s) for s in (R/'data/p13-20261026-preparation/attempts.jsonl').read_text().splitlines()];finished={x['id'] for x in ledger if x['event']=='FINISH' and x['budget_class']=='formal'};started={x['id'] for x in ledger if x['event']=='START_INTENT' and x['budget_class']=='formal'};cases={};case_rows=[]
 for row in design['rows']:
  ident=row['id'];target=R/'data/p13-20261026-formal'/ident;ar=analysis_root/ident
  if ident not in finished or not (ar/'receipt.json').exists():case_rows.append(dict(row,status='STARTED_PENDING_TERMINAL' if ident in started else 'NOT_STARTED',analysis_pending=ident in finished));continue
  e=json.load(open(ar/'events/event-states.json'));d=json.load(open(target/'analysis-v1/measured/measurement.json'));s=json.load(open(target/'analysis-v1/score/score.json'));init=json.load(open(target/'analysis-v1/packed-physical/prediction-input.json'))['initial'];pr=dict(np.load(ar/'events/physical-prefix.npz'));prefix=json.load(open(ar/'prediction-prefix.json'));domain=json.load(open(ar/'domain.json'));hc=hold(target,ar/'events/event-states.json',out/'holds'/ident)
  b_row=next(x for x in e['rows'] if x['label']=='B_before');a_row=next(x for x in e['rows'] if x['label']=='A_before');cases[ident]={'row':row,'target':target,'event':e,'measurement':d,'score':s,'initial':init,'physical':pr,'Bbefore':b_row,'Abefore':a_row,'prefix':prefix,'domain':domain,'hold':hc};case_rows.append(dict(row,status='FINISH',task=d['task_outcome'],primary=d['frozen_flight_outcome']['outcome'],censored=d['censored'],LP_peak_tilt_deg=d['whole']['max_tilt_deg'],LP_max_loss_m=d['whole']['max_altitude_loss_m'],physical=e['physical_full'],B_before=b_row,initial=init,event_statuses=e['events'],domain=domain['full_domain_membership'],prediction_summary={n:{'tilt':v['risk_comparison'],'height':v['height_risk_comparison'],'task':v['task_risk_comparison'],'full':v['full_prediction'],'tilt_time_error':v['tilt_error_deg']} for n,v in s['models'].items()}))
 blocks=[];contrasts=[];pairdetails=[]
 for fam in ['F2','F4']:
  for block in [1,2,3]:
   rr=[r for r in design['rows'] if r['family']==fam and r['block']==block];complete=all(r['id'] in cases for r in rr);summary={'family':fam,'block':block,'seed':rr[0]['sim_seed'],'assigned11':len(rr),'finished_analyzed':sum(r['id'] in cases for r in rr),'complete':complete,'rows':[{k:row[k] for k in ['id','arm','ordinal']} for row in rr]};blocks.append(summary)
   if not complete:continue
   byarm={r['arm']:cases[r['id']] for r in rr};N=byarm['NORMAL'];A=byarm['A']
   for label,gap in [('short',.55),('medium',1.2),('long',2.)]:
    BB=byarm['B-'+label];AB=byarm['AB-'+label];RP=byarm['REPAIR-'+label];tB=AB['Bbefore'].get('requested_profile_s',AB['Bbefore'].get('observed_profile_s'))
    def reached(c):return next(x for x in c['event']['events'] if x['label']=='B')['status']=='CAPTURE_REACHED'
    pattern=all(c['measurement']['task_outcome']=='SUCCESS' for c in [N,A,BB]) and AB['measurement']['task_outcome']=='FAILURE' and reached(AB)
    z={'family':fam,'block':block,'seed':rr[0]['sim_seed'],'gap_label':label,'planned_gap_s':gap,'NORMAL_task':N['measurement']['task_outcome'],'A_task':A['measurement']['task_outcome'],'B_task':BB['measurement']['task_outcome'],'AB_task':AB['measurement']['task_outcome'],'REPAIR_task':RP['measurement']['task_outcome'],'AB_B_capture_reached':reached(AB),'REPAIR_B_capture_reached':reached(RP),'single_success_combo_failure_pattern':pattern,'strict_same_initial_causal_proof':False,'actual_A_capture_resume':AB['event']['events'][0]}
    for key,c in [('B',BB),('AB',AB),('REPAIR',RP)]:
     r=c['Bbefore'];p=r.get('physical');z[key+'_before_status']=r['status'];z[key+'_B_before_physical']=p;z[key+'_LP_peak_deg']=c['measurement']['whole']['max_tilt_deg'];z[key+'_LP_loss_m']=c['measurement']['whole']['max_altitude_loss_m'];z[key+'_physical_D_m']=c['event']['physical_full']['origin_D_m'];z[key+'_censored']=c['measurement']['censored']
    if AB['Bbefore'].get('physical') and BB['Bbefore'].get('physical'):
     aa=AB['Bbefore']['physical'];bb=BB['Bbefore']['physical'];z['AB_minus_B_before']={k:aa[k]-bb[k] for k in ['COM_W_m_s','origin_W_m_s','origin_L_m','origin_D_m','COM_H_m','body_tilt_deg']};as0=AB['Bbefore'].get('state');bs0=BB['Bbefore'].get('state')
     if as0 and bs0:z['AB_minus_B_before'].update(h_l2=norm(np.array(as0['h_before'])-bs0['h_before']),previous_l2=norm(np.array(as0['previous_action_before'])-bs0['previous_action_before']),history_mean_l2=norm(np.array(as0['history_mean_before'])-bs0['history_mean_before']),filter_l2_rad_s=norm(np.array(as0['last_completed_filter_after_rad_s'])-bs0['last_completed_filter_after_rad_s']),count_difference=as0['history_count_before']-bs0['history_count_before'])
    common_end=min(AB['event']['valid_end_s'],RP['event']['valid_end_s']);z['AB_REPAIR_common_end_s']=common_end;z['AB_REPAIR_full_task_integrals_comparable']=not AB['event']['censored'] and not RP['event']['censored'];z['full_costs_own_only']={'AB':AB['event']['mechanical_proxies'],'REPAIR':RP['event']['mechanical_proxies']};z['common_window_costs_v2']=common_cost_pair(AB['target'],RP['target'],common_end);z['own_covered_costs_v2']={'AB':own_costs(AB['target'],0,AB['event']['valid_end_s']),'REPAIR':own_costs(RP['target'],0,RP['event']['valid_end_s'])}
    # Actual initial differences remain, no matching/exclusion/renormalization.
    iniA=AB['initial'];iniB=BB['initial'];z['AB_B_initial_differences']={k:norm(np.array(iniA[k])-iniB[k]) for k in ['position','velocity','h','previous','history','rotor_filter','physical_COM_p','physical_COM_v','physical_omega']};z['AB_B_initial_differences'].update(history_count_difference=iniA['history_count']-iniB['history_count'],call_index_difference=iniA['call_index']-iniB['call_index'],native_sample_phase_difference_us=(iniA['native_us']-iniA['sample_us'])-(iniB['native_us']-iniB['sample_us']))
    contrasts.append(z)
    # Common absolute time nonadditivity, ordered SO3; no peak/capture alignment.
    from p12c.features import load
    loaded={name:load(c['target']/'run',c['target']/'analysis-v1') for name,c in [('N',N),('A',A),('B',BB),('AB',AB)]};stop=min(c['event']['valid_end_s'] for c in [N,A,BB,AB]);start=N['event']['events'][0]['planned_window_profile_s'][0];grid=np.arange(start,stop+.00001,.004);mats={}
    for name,d in loaded.items():
     idx=np.searchsorted(d['t'],grid,side='right')-1;idx=np.clip(idx,0,len(d['t'])-1);mats[name]=np.array([matrix(q) for q in d['attitude'][idx]])
    DA=np.transpose(mats['N'],(0,2,1))@mats['A'];DB=np.transpose(mats['N'],(0,2,1))@mats['B'];composition=mats['N']@DA@DB;reverse=mats['N']@DB@DA;er=np.array([angle(x,y) for x,y in zip(composition,mats['AB'])]);erv=np.array([angle(x,y) for x,y in zip(reverse,mats['AB'])]);Li={}
    for name,c in [('N',N),('A',A),('B',BB),('AB',AB)]:Li[name]=np.interp(grid,c['physical']['profile_s'],c['physical']['L'])
    nl=Li['AB']-Li['A']-Li['B']+Li['N'];pairdetails.append({'family':fam,'block':block,'gap':label,'common_absolute_interval_s':[float(start),float(stop)],'rows':len(grid),'ordered_SO3_nonadditivity_max_deg':float(max(er)),'reverse_order_diagnostic_max_deg':float(max(erv)),'physical_L_nonadditivity_max_abs_m':float(max(abs(nl))),'interpretation':'raw blocked observational nonadditivity, initial/cache differences can contribute; no pure neural-memory causal claim'});np.savez_compressed(out/f'nonadditivity-{fam}-b{block}-{label}.npz',profile_s=grid,ordered_SO3_deg=er,reverse_order_SO3_deg=erv,L_nonadditivity=nl)
 counts={'formal_started':len(started),'formal_finished':len(finished),'analyzed':len(cases),'complete_blocks':sum(x['complete'] for x in blocks),'independent_seed_blocks_planned':6,'per_condition_blocks':{f:sum(x['complete'] and x['family']==f for x in blocks) for f in ['F2','F4']}}
 write(out/'cases.json',{'schema':'p13-cases-aggregate-1','rows':case_rows,'counts':counts});write(out/'blocks.json',{'schema':'p13-blocks-aggregate-1','blocks':blocks,'counts':counts});write(out/'contrasts.json',{'schema':'p13-interval-block-contrasts-2','rows':contrasts,'independence':'3 independent seed blocks per condition; shared NORMAL/A or multiple gaps/models do not add independent flights','thresholds_and_initials':'unchanged, no post-treatment selection','counts':counts});write(out/'nonadditivity.json',{'schema':'p13-ordered-nonadditivity-1','rows':pairdetails,'counting':'not independent samples, one common-time comparison per assigned contrast'});write(out/'receipt.json',{'schema':'p13-aggregate-receipt-1','source_sha256':sha(Path(__file__)),'frozen_plan_sha256':sha(R/'config/p13-formal.json'),'analysis_root':str(analysis_root.relative_to(R)),'counts':counts,'model_parameters_unchanged':True})
 print('AGGREGATE',counts);return counts
if __name__=='__main__':aggregate(Path(sys.argv[1]),R/'data/p13-20261026-formal-analysis-v2')

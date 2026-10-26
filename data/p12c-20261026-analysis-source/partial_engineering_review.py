#!/usr/bin/env python3
"""Stopped P12c three-gate review; strict original scales, plus witness completeness v2."""
import json,sys
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p12c_platform.accept import task_features,metrics,dynamic_pass
from p12c.features import compare
P=R/'data/p12c-20261026-preparation';D=R/'data/p12c-20261026-development'
def main(out):
 if out.exists():raise FileExistsError(out)
 protocol=json.load(open(P/'protocol.json'));spec=json.load(open(P/'noninterference-spec.json'));rows=protocol['rows'];hard={};data={};pending=[];candidates=[]
 for row in rows:
  parent=D/row['id']
  if not (parent/'result.json').exists():pending.append(row['id']);continue
  result=json.load(open(parent/'result.json'));eng=json.load(open(parent/'analysis/engineering.json'));hard[row['id']]=result['evidence_ok'] and eng['status']=='PASS';data[row['id']]=task_features(parent);candidates.append(json.load(open(parent/'candidate.json')))
 hard['same_candidate_completed']=bool(candidates) and all(c==candidates[0] for c in candidates);dynamic={};initial={};pairs=[];natural=[];coverage={}
 for cls in ['NORMAL','SAFE_EVENT','BOUNDARY']:
  rr=[r for r in rows if r['class']==cls]
  for block in [1,2]:
   group=[r for r in rr if r['block']==block];off=next(r for r in group if not r['observe']);on=next(r for r in group if r['observe']);key=f'{cls}-b{block}'
   if off['id'] not in data or on['id'] not in data:pairs.append({'class':cls,'block':block,'status':'NOT_STARTED_OR_NOT_COMPLETED','assigned_ids':[r['id'] for r in group]});continue
   a,plan,ma,ea=data[off['id']];b,_,mb,eb=data[on['id']];first=plan['common_first_gap_profile_s'];pre=compare(a,b,[first-.5,first]);common=metrics(a,b,max(0,float(a['t'][0]),float(b['t'][0])),min(ea,eb));c=pre['continuous'];s=spec['prestate_scales'];initial[key]=c['position']['max_l2']<=s['position_l2_m'] and c['velocity']['max_l2']<=s['velocity_l2_m_s'] and c['SO3_deg']['max']<=s['SO3_deg'] and c['h_before']['max_l2']<=s['hidden_l2'] and c['exec_filter_after']['max_l2']<=s['filter_l2_rad_s'] and c['absolute_world_height_m']['max']<=s['absolute_height_m'];dynamic[key]=dynamic_pass(common,spec['dynamic_scales']);pairs.append({'class':cls,'block':block,'status':'COMPARED_ALL_VALID','off':off['id'],'on':on['id'],'metrics':common,'prestate':pre,'initial_domain_pass':bool(initial[key]),'complete_both':not ma['censored'] and not mb['censored'],'scientific_outcomes_off_on':[ma['task_outcome'],mb['task_outcome']],'censored_off_on':[ma['censored'],mb['censored']],'full_task_comparison':'ELIGIBLE' if not ma['censored'] and not mb['censored'] else 'UNKNOWN_CENSORED_OR_PREFIX'})
  for on in [False,True]:
   aa=[r for r in rr if r['observe']==on and r['id'] in data]
   if len(aa)==2:
    a,_,_,ea=data[aa[0]['id']];b,_,_,eb=data[aa[1]['id']];natural.append({'class':cls,'on':on,'ids':[r['id'] for r in aa],'metrics':metrics(a,b,max(0,float(a['t'][0]),float(b['t'][0])),min(ea,eb)),'role':'natural repeat spread, never threshold expansion or regression correction'})
 led=[json.loads(x) for x in (P/'attempts.jsonl').read_text().splitlines()];starts=[x for x in led if x['event']=='START_INTENT'];hard['within_budget_unique']=len(starts)<=12 and len({x['id'] for x in starts})==len(starts);hard['no_critical_run_failure']=not any(x['event']=='STOP_CRITICAL' for x in led);witness=json.load(open(P/'completeness-final.json'));hard['complete_event_witnesses']=all(x['all_expected_witnesses'] for x in witness['records']);sufficient=not pending and all(initial.values()) and witness['status']=='PASS';fail=[k for k,v in dynamic.items() if not v]
 result={'schema':'p12c-stopped-engineering-review-2','engineering_status':'NOT_RELEASED','hard_semantics':'PASS' if all(hard.values()) else 'FAIL','dynamic_effect':'NOT_EQUIVALENT_WITHIN_FIXED_SCALES' if fail else 'PASS_ON_COMPLETED_PAIRS','evidence_sufficiency':'PASS' if sufficient else 'INSUFFICIENT_FULL_MATRIX_STOPPED','hard_tests':hard,'dynamic_tests':dynamic,'initial_domain_tests':initial,'pairs':pairs,'natural_variation':natural,'missing_preparation':pending,'new_starts':len(starts),'formal_starts':0,'cumulative_with_old56':56+len(starts),'failed_dynamic_pairs':fail,'no_causal_inference_from_failure':'fixed scale not established, not proof of logger effect; no posthoc fitting, phase realignment or selected prefix','original_seal_and_accept_source_unchanged':True,'completeness_v2':'independent mandatory witness check, no empty timing pass; original sealed accept.py not executed to fabricate a full12 verdict','theory_gate':{'status':'CONDITIONAL_WORKING_DOMAIN_RELATIONS_ONLY','experiment_stop':False},'formal':'STOP_BEFORE_FREEZE_ALL24_UNSTARTED','remaining_prep':'not transferred or replaced'}
 out.write_text(json.dumps(result,indent=2)+'\n');print({k:result[k] for k in ['engineering_status','hard_semantics','dynamic_effect','evidence_sufficiency','new_starts','formal_starts','failed_dynamic_pairs']});return result
if __name__=='__main__':main(Path(sys.argv[1]))

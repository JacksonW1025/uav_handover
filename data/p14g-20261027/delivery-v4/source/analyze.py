"""Whole affected set-table analysis, includes resource-censored prefixes.
No actual labels enter model selection or parameters. Actual-model coverage is
separately revoked where the premise audit fails; point scores stay visible.
"""
import sys,json,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from p14g.common import *
KEYS=['p_radius_m','v_radius_m_s','SO3_error_upper_deg','omega_radius_rad_s','action_width_max','h_radius_max','generators']

def records(folder,n):
 p=folder/f'{n:03d}';f=p/'result.json'
 if f.exists():return json.load(open(f))['rows'],json.load(open(f))
 f=p/'metric-prefix.jsonl'
 if not f.exists():return [],None
 z=[json.loads(l) for l in f.read_text().splitlines()];rows=[r for r in z if r.get('metric_phase')=='post_reduce'] if z and 'metric_phase' in z[0] else z[1::2]
 for k,r in enumerate(rows,1):r.setdefault('call',k)
 return rows,None

def main():
 out=Path(sys.argv[1]);register(out,'full rerun/old overlap verification andall64jobs whole-union analysis');rich=B/'rich-v3';execution=json.load(open(rich/'execution.json'));jobs=json.load(open(rich/'jobs.json'));rows=[];checks=[]
 for r in execution['rows']:
  n=r['n'];z,meta=records(rich,n);oldfolder=B/'B-v2' if n<40 else B/'C-v2/sets';oldn=n if n<40 else n-40
  if n<2:oldfolder=B/'B-v1'
  original,_=records(oldfolder,oldn);N=min(len(z),len(original));deltas=[abs(float(a[k])-float(b[k])) for a,b in zip(z[:N],original[:N]) for k in KEYS if k in a and k in b];check={'n':n,'common_calls':N,'core_metric_difference_max':max(deltas) if deltas else None,'read_only_annotation':True};checks.append(check);assert not deltas or max(deltas)<1e-12,check
  job=jobs[n];valid=z if meta else z[:-1]
  if meta and meta['first_domain_loss']:valid=[q for q in z if q.get('call',q.get('call_hint',0))<meta['first_domain_loss']['call']]
  info=meta['first_precision_loss']['call'] if meta and meta['first_precision_loss'] else next((k+1 for k,q in enumerate(z) if q['p_radius_m']>.1 or q['v_radius_m_s']>.15 or q['SO3_error_upper_deg']>2.5 or q['omega_radius_rad_s']>.1 or q['action_width_max']>.2),None)
  row={'n':n,'job':job,'status':'RESOURCE_LIMIT_PREFIX' if not meta else 'MODEL_DOMAIN_LOSS' if meta['first_domain_loss'] else 'REQUESTED_PREFIX_COMPLETED','observed_calls':len(z),'valid_prefix_calls':len(valid),'first_information_loss_call':info,'first_domain_loss_call':meta['first_domain_loss']['call'] if meta and meta['first_domain_loss'] else None,'information_right_censored':info is None and not meta,'complete_A_hold_resume':bool(meta and 'resume' in meta['regions']),'CPU_s':r['CPU_s_waited_child'],'wall_s':r['wall_s'],'peak_RSS_kib':meta.get('peak_rss_kib') if meta else None,'checkpoints':list(meta['regions']) if meta else [f.stem for f in (rich/f'{n:03d}/regions').glob('*.json')],'all_prefix_cache_tilt_upper':max(q['att_tilt_interval_deg'][1] for q in valid) if valid else None,'all_prefix_COM_D_upper':max(q['COM_D_upper_m'] for q in valid) if valid else None,'all_prefix_LP_D_upper':max(q['LP_D_upper_m'] for q in valid) if valid else None,'rows':z}
  rows.append(row);write(out/f'job-{n:03d}.json',{k:v for k,v in row.items() if k!='rows'})
 groups={}
 for panel in ['zero','small','joint']:
  for variant in ['default','none','relations','weighted']:
   rr=[r for r in rows if r['n']<40 and r['job']['panel']==panel and r['job']['variant']==variant];key=panel+'-'+variant
   groups[key]={'expected_domain_cells':8 if panel=='joint' else 1,'completed_attempts':len(rr),'horizon_s':.8 if panel=='joint' else .064,'min_information_gate_or_censored_prefix_calls':min((r['first_information_loss_call'] or r['valid_prefix_calls']+1)-1 for r in rr) if rr else None,'some_information_right_censored':any(r['information_right_censored'] for r in rr),'min_valid_prefix_calls':min(r['valid_prefix_calls'] for r in rr) if rr else None,'whole_union_A_hold_resume_completed':len(rr)==8 and all(r['complete_A_hold_resume'] for r in rr),'CPU_s':sum(r['CPU_s'] for r in rr),'wall_s':sum(r['wall_s'] for r in rr),'at_call48':{q['n']:{k:q['rows'][47][k] for k in ['action_width_max','tilt_upper_deg','COM_D_upper_m','LP_D_upper_m','att_tilt_interval_deg']} for q in rr if len(q['rows'])>=48}}
 Cgroups={}
 for dynamic,mode in [(False,'persistent'),(False,'per_fusion'),(True,'persistent')]:
  rr=[r for r in rows if r['n']>=40 and r['job']['dynamic']==dynamic and r['job']['innovation_budget']['mode']==mode];Cgroups[str(dynamic)+'-'+mode]={'cells':len(rr),'min_information_loss_call':min(r['first_information_loss_call'] or 99999 for r in rr) if rr else None,'min_valid_prefix_calls':min(r['valid_prefix_calls'] for r in rr) if rr else None,'whole_initial_union_covered':len(rr)==8,'CPU_s':sum(r['CPU_s'] for r in rr)}
 summary={'B_groups':groups,'C_groups':Cgroups,'same_core_metric_checks':checks,'max_core_metric_change':max(c['core_metric_difference_max'] or 0 for c in checks),'full_joint_initial_domain_complete_event_increment':0,'three_panel_warning':'zero/small onlyd02/64ms; realdomain bothfibers/fourquarters0.8s. Fourmethods fair within panel, notsame-domain-lengthcomparison acrosspanels.','resource_accounting':execution,'new_SITL':0,'actual_future_safety':'UNKNOWN_ALL_CASES; smallinnovationpremise rejectedbyall5actualrecords; conditionalreal-model bounds notwithdrawn asmath butnoactualguarantees maydependonthem.'};write(out/'summary.json',summary)
 # Global actual-coverage dependency ledger, never edits historical originals.
 audit=json.load(open(B/'C-innovation-audit-v1/summary.json'));withdraw=[]
 for r in audit['rows']:
  withdraw.append({'id':r['id'],'small_budget_held_first_rejected':r['models']['held']['first_outside'],'small_budget_fading_first_rejected':r['models']['fading']['first_outside'],'dependent_claims':['C-smallbudget actualwholeflightenclosure','B-heldtemplate asactualfutureguarantee','physicalsafe successor interpretedasactualEKFclosedloop'],'actual_safety_status':'UNKNOWN_PREMISE_REJECTED','point_scores_unchanged':'C-score-v1 still reportsallmisses,falsealarms,UNKNOWN; no masking','conditional_source_math':'remainsconditional, sourceFP/geodesy/solverassumptions separate','old_originals':'neverrewritten'})
 write(out/'withdrawal-ledger.json',withdraw)
 print('ANALYZED',len(rows),'maxmetricchange',summary['max_core_metric_change'])
if __name__=='__main__':main()

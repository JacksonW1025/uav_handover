"""Replace ONLY the intended-output weighted comparison after correctness fix.
Old wrong-stage results remain audit evidence, not a valid negative H2 test.
"""
import sys,json,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from p14g.common import *
def main():
 out=Path(sys.argv[1]);register(out,'post-state adjoint fix aggregation, same domain/tolerances/resources, no new models');old=json.load(open(B/'analysis-v1/summary.json'));summary=copy.deepcopy(old);execution=json.load(open(B/'weighted-v4/execution.json'));rr={r['n']:r for r in execution['rows'] if 'n' in r};jobs=json.load(open(B/'B-v2/before-compute.json'))['jobs'];locals_={logical:n for n,logical in enumerate(j for j,v in enumerate(jobs) if v['variant']=='weighted')};new=[]
 for logical in range(64):
  base=json.load(open(B/'analysis-v1'/f'job-{logical:03d}.json'));base['result_source']='rich-v3/'+f'{logical:03d}'
  if logical in locals_:
   n=locals_[logical];p=B/'weighted-v4'/f'{n:03d}/result.json'
   if p.exists():
    x=json.load(open(p));job=x['job'];assert {k:v for k,v in job.items() if k!='weights_path'}==jobs[logical];valid=[r for r in x['rows'] if x['first_domain_loss'] is None or r['call']<x['first_domain_loss']['call']];base.update(result_source='weighted-v4/'+f'{n:03d}',job=job,status='MODEL_DOMAIN_LOSS' if x['first_domain_loss'] else 'REQUESTED_PREFIX_COMPLETED',observed_calls=len(x['rows']),valid_prefix_calls=len(valid),first_information_loss_call=x['first_precision_loss']['call'] if x['first_precision_loss'] else None,first_domain_loss_call=x['first_domain_loss']['call'] if x['first_domain_loss'] else None,CPU_s=rr[n]['CPU_s'],wall_s=rr[n]['wall_s'],all_prefix_cache_tilt_upper=max(r['att_tilt_interval_deg'][1] for r in valid),all_prefix_COM_D_upper=max(r['COM_D_upper_m'] for r in valid),all_prefix_LP_D_upper=max(r['LP_D_upper_m'] for r in valid));new.append((base,x))
   else:base.update(status='CORRECTED_WEIGHTING_NOT_COMPLETED',result_source=None)
  write(out/f'job-{logical:03d}.json',base)
 for panel in ['zero','small','joint']:
  z=[(r,x) for r,x in new if r['job']['panel']==panel];g=summary['B_groups'][panel+'-weighted'];g.update(completed_attempts=len(z),min_information_gate_or_censored_prefix_calls=min((r['first_information_loss_call'] or r['valid_prefix_calls']+1)-1 for r,x in z) if z else None,min_valid_prefix_calls=min(r['valid_prefix_calls'] for r,x in z) if z else None,CPU_s=sum(r['CPU_s'] for r,x in z),wall_s=sum(r['wall_s'] for r,x in z),corrected_phase_semantics=True,at_call48={r['n']:{k:x['rows'][47][k] for k in ['action_width_max','tilt_upper_deg','COM_D_upper_m','LP_D_upper_m','att_tilt_interval_deg']} for r,x in z if len(x['rows'])>=48})
 summary.update(poststate_weighting_fix='Zpre=(Fpost+Znext)A; Wpost=Fcurrent+Zfuture. Priorweightedinvalidforthisobjective, retained.',weighted_fix_complete_jobs=len(new),weighted_fix_CPU_s_exact=execution['CPU_s_exact'],global_numeric_charge_plus100validation=execution['global_numeric_charge_plus100validation'],old_LP_annotation_metric_equality_scope='64oldvariantjobs only; correctedweightsintentionallydifferent, not subjecttooldmetriczeroassert');write(out/'summary.json',summary);write(out/'withdrawal-ledger.json',json.load(open(B/'analysis-v1/withdrawal-ledger.json')));print('CORRECTED_WEIGHTED_ANALYZED',len(new))
if __name__=='__main__':main()

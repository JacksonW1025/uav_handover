"""Read-only three-epoch descriptive report, two prior exceptions retained."""
import argparse,csv,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT/'tools'))
from p9_model import write,sha
from p9_report import report

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve();out.mkdir(exist_ok=False);view=out/'analysis-view';view.mkdir()
 epochs=['data/p9-20261024-formal','data/p9-20261024-continuation-v1-formal','data/p9-20261024-continuation-v2-formal'];rows=[];sources={};inputs={}
 for epoch in epochs:
  src=ROOT/epoch/'results.json';doc=json.loads(src.read_text());inputs[str(src.relative_to(ROOT))]=sha(src)
  for r in doc['runs']:
   if not r.get('p9') or not r.get('infrastructure_ok'):continue
   attempt=(ROOT/r['directory']).parent;target=view/r['id'];target.mkdir();pred=attempt/'prediction-before-query.json';(target/pred.name).write_bytes(pred.read_bytes())
   rows.append(dict(r,analysis_execution_epoch=epoch));sources[r['id']]={'attempt':str(attempt.relative_to(ROOT)),'epoch':epoch,'prediction_sha256':sha(pred),'result_sha256':sha(attempt/'result.json'),'measurement_kind':r.get('measurement_kind','ORIGINAL_COMPATIBLE')}
 oldaudit=ROOT/'data/p9-20261024-audit-interrupted-v1/audit.json';a1=ROOT/'data/p9-20261024-continuation-v1-audit-stopped-v1/audit.json';a2=ROOT/'data/p9-20261024-continuation-v2-audit-stopped-v1/audit.json'
 audits=[]
 for src in [oldaudit,a1,a2]:
  audit=json.loads(src.read_text());bad=[k for k,h in audit['input_hashes'].items() if sha(ROOT/k)!=h]
  audits.append({'path':str(src.relative_to(ROOT)),'whole_status':audit['status'],'individual_n':len(audit['runs']),'all_individual_pass':all(x['passed'] for x in audit['runs']),'input_drift':bad});inputs[str(src.relative_to(ROOT))]=sha(src)
 if len(rows)!=161 or any(x['input_drift'] for x in audits) or not all(x['all_individual_pass'] for x in audits[:2]) or audits[-1]['whole_status']!='FAIL':raise RuntimeError('partial measurements/audit require inspection')
 seal=ROOT/'data/p9-20261024-formal/searches-sealed-before-reference.json';searches=json.loads(seal.read_text())['searches'];inputs[str(seal.relative_to(ROOT))]=sha(seal)
 status='V2_STOPPED_P7_EVIDENCE_GATE_INCOMPLETE'
 write(view/'results.json',{'status':status,'runs':rows,'searches':searches,'original_missing_id':'C-CZ15-g0.1-reference-P9-Z','original162_diagnostic_only':True,'no_overall_acceptance_pass':True})
 write(view/'source-attempt-map.json',sources)
 baseline=out/'frozen-generator-output';report(ROOT/'data/p9-20261024-preparation',view,baseline)
 s=json.loads((baseline/'results.json').read_text());s.update(execution_status=status,overall_acceptance='NO_OVERALL_PASS_ORIGINAL102_MISSING_162_ANALYSIS_EXCEPTION_164_P7_EVIDENCE_GATE_FAIL',epoch_audits=audits,original102_missing=True,original162_diagnostic_only=True,formal_original_compatible_n=sum(x['measurement_kind']=='ORIGINAL_COMPATIBLE' for x in sources.values()),formal_new_censored_measurement_n=sum(x['measurement_kind']=='OPEN_GAP_CENSORED' for x in sources.values()),D_planned_clusters=9,D_complete_four_arm_measurement_clusters=6,no_refit=True)
 for x in s['searches']:
  missing=12-x['reference_grid_n'];x['reference_missing_n']=missing;x['reference_observed_unresolved_n']=x['reference_unresolved_n'];x['reference_unresolved_n']+=missing
  if missing:x['error_vs_unique_empirical_reference_s']=None
 s['cost']['original102_start_to_cleanup_wall_s']=421.028078;s['cost']['original162_start_to_exception_wall_s']=74.193239;s['cost']['new164_FINISH_elapsed_s_excluded_from_main_measured_sum']=75.86688087892253;s['new164_protocol_failed']=True;s['remaining_NOT_RUN']=9
 write(out/'results.json',s)
 rr=list(csv.DictReader((baseline/'prediction-measurement-ledger.csv').open()))
 for r in rr:r['evidence_directory']=sources[r['id']]['attempt'];r['execution_epoch']=sources[r['id']]['epoch'];r['measurement_kind']=sources[r['id']]['measurement_kind']
 with (out/'prediction-measurement-ledger.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
 # Every original planned slot, including original162, remains accounted separately.
 events=[json.loads(x) for x in (ROOT/'data/p9-20261024-preparation/attempts.jsonl').read_text().splitlines()];starts={x['id']:x for x in events if x['event']=='START_INTENT' and x['budget_class']=='formal'}
 plan=json.loads((ROOT/'data/p9-20261024-freeze/plan.json').read_text());account=[]
 for r in plan['runs']+plan['search_slots']:
  state='COMPLETED_MEASUREMENT' if r['id'] in sources else ('ORIGINAL102_MISSING' if r['id']=='C-CZ15-g0.1-reference-P9-Z' else ('ORIGINAL162_FLIGHT_FAILURE_ANALYSIS_EXCEPTION' if r['id']=='D-07-P9-Z' else ('NEW164_P7_EVIDENCE_GATE_FAIL' if r['id']=='D-07-P9-R' else ('NOT_RUN_AFTER_V2_STOP' if r['stage']!='C-search' else 'UNUSED_SEARCH_STOP'))))
  # Unstarted static rows are explicitly preserved after the v2 stop.
  account.append({'id':r['id'],'stage':r['stage'],'state':state,'attempt_number':starts.get(r['id'],{}).get('attempt_number')})
 write(out/'budget-accounting.json',{'formal_started':len(starts),'development_started':10,'original_cap':180,'approved_cap':173,'rows':account,'unused_search_slots':7,'no_overall_acceptance_pass':True})
 # Reference missing102 always null, no interpolation.
 grid=[]
 for r in plan['runs']:
  if r['stage']=='C-reference':
   actual=next((x for x in rows if x['id']==r['id']),None);grid.append({'id':r['id'],'family':r['family'],'phase_s':r['phase_s'],'seed':r['sim_seed'],'observed_tilt_deg':actual['p9']['max_tilt_deg'] if actual else None,'tilt_failure':actual['p9']['tilt_ge_45_failure'] if actual else None,'missing':actual is None})
 write(out/'reference-grid.json',{'rows':grid,'no_probability_truth':True})
 diag=ROOT/'data/p9-20261024-continuation-v1-stopped-analysis/attempt162-diagnostic/p9-open-gap-diagnostic.json'
 write(out/'original162-separate-diagnostic.json',{'scope':'postflight-only original162, excluded from171 measurements and main D paired analysis','diagnostic':json.loads(diag.read_text()),'D07_other_arms':[x for x in rr if x['cluster']=='D-07']});inputs[str(diag.relative_to(ROOT))]=sha(diag)
 for x in [Path(__file__).resolve(),ROOT/'data/p9-20261024-preparation/attempts.jsonl']:inputs[str(x.relative_to(ROOT))]=sha(x)
 write(out/'input-manifest.json',inputs);write(out/'output-manifest.json',{str(x.relative_to(out)):sha(x) for x in sorted(out.rglob('*')) if x.is_file() and x.name!='output-manifest.json'})
 print('REPORT161 admitted measurements;102/162/164 separate;9 static NOT_RUN',flush=True)
if __name__=='__main__':main()

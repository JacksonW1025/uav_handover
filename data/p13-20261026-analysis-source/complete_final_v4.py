"""Recover final reporting path lookup from START ledger, no experiment changes."""
import sys,json,subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[2];S=Path(__file__).parent;sys.path.insert(0,str(R/'tools'));from p9_model import write,sha
out=R/'data/p13-20261026-final-analysis-v4';out.mkdir(parents=True,exist_ok=False);L=[json.loads(s) for s in (R/'data/p13-20261026-preparation/attempts.jsonl').read_text().splitlines()];starts={x['id']:x for x in L if x['event']=='START_INTENT' and x['budget_class']=='formal'};finished=[x['id'] for x in L if x['event']=='FINISH' and x['budget_class']=='formal'];assert len(starts)==len(finished)==66;agg=R/'data/p13-20261026-results-v3';syn=R/'data/p13-20261026-synthesis-v3';assert json.load(open(agg/'receipt.json'))['counts']['analyzed']==66 and json.load(open(syn/'receipt.json'))['records']==66
py=str(R/'uav_lab/.local/venv/bin/python')
def run(n,*args):print('FINAL_REPAIR_PHASE',n,flush=True);subprocess.run([py,str(S/n),*map(str,args)],cwd=R,check=True)
for ident in finished:
 tar=R/starts[ident]['output'];run('phase_diagnostics_v2.py',tar,R/'data/p13-20261026-phase-v3'/ident);run('crossing_v2.py',tar,R/'data/p13-20261026-crossing-v3'/ident)
run('plot_results_v3.py',agg,syn,R/'docs/figures/p13');write(out/'receipt.json',{'schema':'p13-final-analysis-path-recovery-4','formal_finished':66,'old_failure':'final_pipeline_v3 looked foroutputinFINISH; field is carried bySTART_INTENT. Oldlogandcompletedaggregate/synthesis/covariates/clocks preserved. New completion joins exactid, never retriesflights.','sources':{n:sha(S/n) for n in ['complete_final_v4.py','phase_diagnostics_v2.py','crossing_v2.py','plot_results_v3.py']},'aggregate_sha256':sha(agg/'receipt.json'),'synthesis_sha256':sha(syn/'receipt.json'),'new_SITL':0});print('FINAL_ANALYSIS_COMPLETE66',flush=True)

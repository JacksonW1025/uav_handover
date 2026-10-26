from analysis_paths_v1 import analysis_dir
"""Wait on existing ledger only; analyze finished records, NEVER launch SITL."""
import sys,json,time,subprocess,os
from pathlib import Path
R=Path(__file__).resolve().parents[2];SRC=Path(__file__).parent;sys.path.insert(0,str(R/'tools'))
from p9_model import write,sha
P=R/'data/p13-20261026-preparation';out=R/'data/p13-20261026-final-analysis-v3';out.mkdir(parents=True,exist_ok=False)
sources=['aggregate_v5.py','mechanical_costs_v4.py','hold_axes_v3.py','synthesis_v2.py','time_process_v2.py','covariates_v2.py','clock_execution_v2.py','phase_diagnostics_v2.py','crossing_v2.py','plot_results_v3.py'];sealed={n:sha(SRC/n) for n in sources};write(out/'analysis-source-seal.json',sealed)
while True:
 ledger=[json.loads(s) for s in (P/'attempts.jsonl').read_text().splitlines()];finished=[x for x in ledger if x['budget_class']=='formal' and x['event']=='FINISH'];critical=[x for x in ledger if x['event']=='STOP_CRITICAL' and x.get('queue')=='formal'];allreviewed=all((R/'data/p13-20261026-formal-analysis-v3'/x['id']/'receipt.json').exists() for x in finished)
 if (len(finished)==66 or critical) and allreviewed:break
 if (R/'data/p13-20261026-formal-analysis-v3/analysis-error.json').exists():raise RuntimeError('retained independent analysis error, repair separately')
 time.sleep(10)
if sealed!={n:sha(SRC/n) for n in sources}:raise RuntimeError('analysis source seal changed; no experiment changed')
py=str(R/'uav_lab/.local/venv/bin/python');agg=R/'data/p13-20261026-results-v3';syn=R/'data/p13-20261026-synthesis-v3'
def run(name,*args):
 print('ANALYSIS_PHASE',name,flush=True);subprocess.run([py,str(SRC/name),*map(str,args)],cwd=R,check=True)
run('aggregate_v5.py',agg);run('synthesis_v2.py',agg,syn);run('covariates_v2.py',agg,R/'data/p13-20261026-covariates-v3');run('clock_execution_v2.py',agg,R/'data/p13-20261026-clocks-v3')
for row in finished:
 tar=R/row['output'];run('phase_diagnostics_v2.py',tar,R/'data/p13-20261026-phase-v3'/row['id']);run('crossing_v2.py',tar,R/'data/p13-20261026-crossing-v3'/row['id'])
run('plot_results_v3.py',agg,syn,R/'docs/figures/p13');write(out/'receipt.json',{'schema':'p13-final-analysis-pipeline-2','formal_finished':len(finished),'critical_queue_stop':critical,'analysis_sources_unchanged':True,'new_SITL':0,'artifacts':list(map(str,[agg.relative_to(R),syn.relative_to(R)]))});print('FINAL_ANALYSIS_COMPLETE',len(finished),flush=True)

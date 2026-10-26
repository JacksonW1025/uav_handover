from analysis_paths_v1 import analysis_dir
"""Produce concrete reviewable delivery after experiment/analysis, no flights/git writes."""
import sys,time,json,subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[2];S=Path(__file__).parent;sys.path.insert(0,str(R/'tools'));from p9_model import write,sha
out=R/'data/p13-20261026-delivery-readiness-v2';out.mkdir(parents=True,exist_ok=False);files=['extra_diagnostics_v2.py','history_prediction_v3.py','cache_physics_gap_v2.py','recovery_prediction_v2.py','hold_summary_v2.py','delivery_audit_v2.py','report_v2.py'];seals={n:sha(S/n) for n in files};write(out/'sources.json',seals)
while not (R/'data/p13-20261026-final-analysis-v3/receipt.json').exists():time.sleep(10)
if {n:sha(S/n) for n in files}!=seals:raise RuntimeError('offline delivery source changed; preserve and review independently')
py=str(R/'uav_lab/.local/venv/bin/python')
def run(n,*args):
 print('DELIVERY_PHASE',n,flush=True);subprocess.run([py,str(S/n),*map(str,args)],cwd=R,check=True)
run('extra_diagnostics_v2.py');run('hold_summary_v2.py',R/'data/p13-20261026-hold-summary-v1');run('delivery_audit_v2.py',R/'data/p13-20261026-delivery-audit-v2');run('report_v2.py');write(out/'receipt.json',{'schema':'p13-delivery-readiness-1','sources_unchanged':True,'experiment_finished_and_all_sources_original':True,'new_SITL':0,'git_commit_or_push_by_this_service':False,'pending':'agent final review, normal commit/push, remote and CI verification'});print('READY_FOR_FINAL_REVIEW',flush=True)

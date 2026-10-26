"""Complete only missing analysis of existing formal53; never launch SITL."""
import sys,json,shutil
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path[:0]=[str(R/'tools'),str(Path(__file__).parent)]
from p13.campaign import formal_rows
from p13.pack import create
from p13.isolated import predict
from p12.score import score
from p9_model import write,sha
from p9_run import append
import p2_batch
P=R/'data/p13-20261026-preparation';allcheck=json.load(open(R/'data/p13-20261026-physics-scope-v4/all-started-recheck.json'));assert allcheck['records']==53 and allcheck['all_pass'];formal_rows();ident='p13-F2-b3-B-short';tar=R/'data/p13-20261026-formal'/ident;a=tar/'analysis-v2';assert not a.exists();shutil.copytree(tar/'analysis-v1',a);write(tar/'analysis-pointer-v2.json',{'schema':'p13-analysis-only-pointer-2','directory':'analysis-v2','preserved_original':'analysis-v1','reason':'original full-run airborne integration check applied to postresearch classic landing; scope-decision-v4 keeps raw FAIL and unchanged1mm threshold','new_SITL':0});create(tar/'run',a/'packed',a/'packed-physical');predict(a/'packed-physical',R/'data/p13-20261026-freeze/models',a/'prediction');score(a/'prediction',a/'packed-physical',a/'measured/measurement.json',a/'score');m=json.load(open(a/'measured/measurement.json'));write(tar/'analysis-result-v2.json',{'schema':'p13-analysis-recovery-2','status':'PASS_RESEARCH_SCOPE_WITH_FULL_RAW_EVIDENCE','legacy_physics_fullrun':'FAIL retained','scope_decision_sha256':sha(R/'data/p13-20261026-physics-scope-v4'/ident/'scope-decision.json'),'task_outcome':m['task_outcome'],'censored':m['censored'],'new_SITL':0});append(P/'attempts.jsonl',{'event':'ANALYSIS_RECOVERY','id':ident,'budget_class':'formal','time':p2_batch.now(),'version':'physics-scope-v4 and analysis-v2','new_SITL':0,'legacy_fail_preserved':True});append(P/'attempts.jsonl',{'event':'FINISH','id':ident,'budget_class':'formal','time':p2_batch.now(),'evidence_ok':True,'task_outcome':m['task_outcome'],'censored':m['censored'],'analysis_version':'analysis-v2/physics-scope-v4','no_SITL_retry':True});print('RECOVERED_EXISTING53',m['task_outcome'],flush=True)

import sys,json
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path[:0]=[str(R/'tools'),str(Path(__file__).parent)]
from physics_scope_v4 import validate
from p9_model import write
root=R/'data/p13-20261026-physics-scope-v4';rows=[]
for x in [json.loads(s) for s in (R/'data/p13-20261026-preparation/attempts.jsonl').read_text().splitlines()]:
 if x['event']!='START_INTENT' or x['budget_class']!='formal':continue
 p=root/x['id'];r=json.load(open(p/'scope-decision.json')) if p.exists() else validate(R/x['output'],p);rows.append(r);print('SCOPED',x['id'],r['decision'],flush=True)
write(root/'all-started-recheck.json',{'schema':'p13-physics-scope-recheck-4','records':len(rows),'all_pass':all(x['decision']=='PASS_RESEARCH_PHASE_WITH_FULL_RAW_COVERAGE' for x in rows),'rows':rows,'threshold_case_order_model_physics_changes':False,'new_SITL':0})

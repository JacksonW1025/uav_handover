"""All assigned D36 raw labels, explicitly distinct from admitted main set."""
import argparse,json,csv,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT/'tools'))
from p9_model import write,sha
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(exist_ok=False)
plan=json.loads((ROOT/'data/p9-20261024-freeze/plan.json').read_text());L=[json.loads(x) for x in (ROOT/'data/p9-20261024-preparation/attempts.jsonl').read_text().splitlines()];starts={r['id']:r for r in L if r['event']=='START_INTENT'}
rows=[];inputs={}
for r in plan['runs']:
 if r['stage']!='D':continue
 s=starts[r['id']];attempt=ROOT/s['output'];path=attempt/'run/p7-metrics.json';m=json.loads(path.read_text());result=json.loads((attempt/'result.json').read_text()) if (attempt/'result.json').exists() else {};admitted=bool(result.get('admissible_v3',result.get('infrastructure_ok',False)))
 rows.append({'id':r['id'],'cluster':r['cluster'],'arm':r['treatment'],'seed':r['sim_seed'],'attempt_number':s['attempt_number'],'raw_P7_primary':m['flight_outcome']['outcome'],'raw_P7_task':m['p7']['task_outcome']['outcome'],'raw_P7_status':m['status'],'main_admitted':admitted,'scope':'MAIN' if admitted else {162:'POSTHOC_P9_DIAGNOSTIC_ONLY',164:'OLD_P7_EVIDENCE_FAIL',169:'UNPLANNED_RECOVERY_P7_FAIL'}[s['attempt_number']]});inputs[str(path.relative_to(ROOT))]=sha(path)
assert len(rows)==36
with (a.output/'D36-assigned-raw-labels.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
summary={}
for arm in ['P9-Z','P9-C','P9-R','P9-CR']:
 rr=[r for r in rows if r['arm']==arm];summary[arm]={'assigned_n':len(rr),'main_admitted_n':sum(r['main_admitted'] for r in rr),'raw_primary_failure_n':sum(r['raw_P7_primary']=='FAILURE' for r in rr),'raw_task_failure_n':sum(r['raw_P7_task']=='FAILURE' for r in rr)}
write(a.output/'summary.json',{'scope':'raw frozen P7 labels for all assigned D36; includes protocol failures; not a pooled acceptance or independent probability estimate; P9 main denominator stays separate','arms':summary})
for x in [ROOT/'data/p9-20261024-preparation/attempts.jsonl',Path(__file__).resolve()]:inputs[str(x.relative_to(ROOT))]=sha(x)
write(a.output/'input-manifest.json',inputs);write(a.output/'output-manifest.json',{x.name:sha(x) for x in a.output.iterdir() if x.is_file() and x.name!='output-manifest.json'})
print(summary)

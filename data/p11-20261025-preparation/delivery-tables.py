import sys,json,csv,hashlib
from pathlib import Path
sys.path.insert(0,'tools')
from p11.memory import compare
from p9_model import write
out=Path('data/p11-20261026-analysis');formal=Path('data/p11-20261025-formal');plan=json.loads(Path('config/p11.json').read_text());ledger=[json.loads(x) for x in Path('data/p11-20261025-preparation/attempts.jsonl').read_text().splitlines()];starts=[x for x in ledger if x['event']=='START_INTENT']
fields=['id','budget_class','ordinal','output','input_sha256','seed','terminal','evidence_ok','flight_outcome','task_outcome','censored']
with (out/'startup-ledger.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
 for s in starts:
  terminals=[x for x in ledger if x['id']==s['id'] and x['event'] in ['FINISH','STOP','EXCEPTION']];e=terminals[-1] if terminals else {};w.writerow({k:({'terminal':e.get('event')}|s|e).get(k) for k in fields})
rows=[]
for row in plan['rows']:
 p=formal/row['id'];result=p/'result.json';s=next((s for s in starts if s['id']==row['id']),None);r=json.loads(result.read_text()) if result.exists() else {}
 rows.append({**{k:row[k] for k in ['id','family','split','group','rep','branch','sim_seed','config','config_sha256']},'status':'VALID' if r.get('p11_valid_scientific_result') else ('OBSERVATION_STOP_INVALID' if s else 'PENDING_UNSTARTED'),'primary':r.get('p11_frozen_flight_outcome',{}).get('outcome'),'task':r.get('p11_task_outcome'),'censored':r.get('p11_censored'),'ordinal':s.get('ordinal') if s else None,'raw_path':str(p/'run/flight.ulg') if s else None})
write(out/'branch-pair-table.json',{'rows':rows,'immutable_plan_unchanged':True})
with (out/'branch-pair-table.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
for identity in ['F1-r1-AB','F3-r1-AB','F4-r1-AB','ANCHOR-D-09-r1-ORIGINAL']:
 compare(formal/identity/'observation/synchronized.npz',out/('memory-sensitivity-'+identity+'.json'))
print('startup',len(starts),'formal rows',len(rows),'memory4')

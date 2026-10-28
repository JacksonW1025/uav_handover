"""Main grid posthoc score after both query phases sealed. No model/seed2 updates."""
import sys,json,time
from pathlib import Path
sys.path.insert(0,'tools')
from p16.common import B,write,now,sha
from p16.quality import evaluate
from p16.baseline import replay as grid
from p16.cheap import replay as cheap
from p16.dual import both_terminal
st=time.perf_counter();cpu=time.process_time();out=Path(sys.argv[1]);out.mkdir(exist_ok=False,parents=True);sealed=both_terminal();pool=json.load(open(B/'frozen/pool.json'));rows=json.load(open(B/'frozen/rows.json'));ledger=[json.loads(l) for l in (B/'attempts.jsonl').read_text().splitlines()];truth={};src={}
for c in pool:
 row=rows[c['id']];assert any(x.get('id')==row['id'] and x['event'] in ['FINISH','SCOPED_REVIEW_RESOLVED'] for x in ledger);p=B/'runs'/row['id']/'analysis-v1/result.json';truth[c['id']]=json.load(open(p));src[c['id']]=sha(p)
maps={'A_grid':grid(pool,lambda k:truth[k]),'A_cheap':cheap(pool,lambda k:truth[k])[0]}
for p in ['G','R']:maps[p]=[json.load(open(B/f'policies/{p}/maps/q{q:02d}.json')) for q in range(9)]
metrics={}
for name,series in maps.items():
 e=[dict(query=x['query'],quality=evaluate(pool,truth,x['prediction'])) for x in series];persistent=next((x['query'] for i,x in enumerate(e) if all(z['quality']['same_quality'] for z in e[i:])),None);metrics[name]=dict(first_persistent_joint_quality=persistent,series=e)
write(out/'result.json',dict(time=now(),source_hashes=src,terminal=sealed,methods=metrics,CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-st,new_START=0,seed2_used=False,policy_updated=False,scope='frozen selection alreadyclosed, maintruth posthoc scoring only'))
print(json.dumps({n:dict(first_persistent=x['first_persistent_joint_quality'],final=x['series'][-1]['quality']['components']['task']) for n,x in metrics.items()},indent=2))

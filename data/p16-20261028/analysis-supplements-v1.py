"""Predeclared same-final-unqueried-set and deduplicated reuse accounting. No update."""
import sys,json
from pathlib import Path
sys.path.insert(0,'tools')
from p16.common import B,write,now
from p16.quality import evaluate
out=Path(sys.argv[1]);out.mkdir(exist_ok=False,parents=True);results=Path(sys.argv[2]);pool=json.load(open(B/'frozen/pool.json'));truth=json.load(open(results/'truth.json'));rows={}
for p in ['G','R']:
 a=json.load(open(B/f'policies/{p}/maps/q00.json'));z=json.load(open(B/f'policies/{p}/maps/q08.json'));remain=[c for c in pool if c['id'] not in z['seen_ids']];rows[p]=dict(final_unqueried_ids=[c['id'] for c in remain],initial_on_same_unqueried=evaluate(remain,truth,a['prediction']),updated_on_same_unqueried=evaluate(remain,truth,z['prediction']),scope='same finalunqueried set, excludes queriedtruth overrides, not independent extra flights')
trans=json.load(open(results/'transfers.json'));accepted=[x for x in trans if x['accepted']];pairs=sorted({(x['donor'],x['receiver']) for x in accepted});receivers=sorted({x['receiver'] for x in accepted});classes={}
for a,b in pairs:
 c=next(c for c in pool if c['id']==a);key=f"{c['family']}/G{c['G']:.3f}";classes.setdefault(key,set()).update([a,b])
choices={p:[json.load(open(B/f'policies/{p}/queries/q{q:02d}/decision.json'))['cell']['id'] for q in range(1,9)] for p in ['G','R']}
write(out/'supplement.json',dict(time=now(),common_final_unqueried=rows,reuse=dict(repeated_accepted_map_records=len(accepted),unique_donor_receiver_pairs=pairs,unique_receiver_ids=receivers,classes={k:sorted(v) for k,v in classes.items()},max_observed_class_size=max([len(v) for v in classes.values()],default=0),repeated_accepts_with_true_domain_rejected=sum(x.get('actual_receiver_domain_pass') is False for x in accepted),scope='q00-q08 are shared repeated maps, not independent cases; conditional gate is empirical incomplete scheduling state'),choices=choices,same_query_position=sum(a==b for a,b in zip(choices['G'],choices['R'])),true_unique_cells_selected=len(set(choices['G'])|set(choices['R'])),primary_flight={label:sum(x['original_flight']['outcome']==label for x in truth.values()) for label in ['SUCCESS','FAILURE']},new_START=0))

#!/usr/bin/env python3
"""Fixed model fitting/selection barrier between P11 training and heldout flights."""
import datetime
import json
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from p9_model import sha,write
from p11.campaign import verify,OUT,PREP
from p11.fit import create
from p11.isolated import predict
from p11.score import score


def main():
    verify();plan=json.loads((ROOT/'config/p11.json').read_text());rows=[r for r in plan['rows'] if r['split']=='development']
    ledger=[json.loads(x) for x in (PREP/'attempts.jsonl').read_text().splitlines()]
    starts=[x for x in ledger if x['event']=='START_INTENT' and x['budget_class']=='formal']
    if len(starts)!=38 or {x['id'] for x in starts}!={r['id'] for r in rows}:raise RuntimeError('must seal before any heldout START, after exactly38 planned training starts')
    for r in rows:
        result=json.loads((OUT/r['id']/'result.json').read_text())
        if not result['p11_valid_scientific_result']:raise RuntimeError('training evidence incomplete')
    models=OUT/'models';create([OUT/r['id']/'packed/measurement.npz' for r in rows],models,'formal development groups G15/G20 only; heldout not opened')
    groups={name:{} for name in ['M0','M1','M2']};details=[]
    for row in rows:
        case=OUT/row['id'];predict(case/'packed',models,case/'prediction')
        scored=score(case/'prediction',case/'packed',case/'measured/measurement.json',case/'score')
        for name,r in scored['models'].items():groups[name].setdefault(row['group'],[]).append(r['training_selection_score'])
        details.append({'id':row['id'],'group':row['group'],'score_sha256':sha(case/'score/score.json')})
        print('TRAIN_PREDICTION',row['id'],flush=True)
    scores={k:float(np.mean([np.mean(values) for values in g.values()])) for k,g in groups.items()}
    selected=min(scores,key=scores.get)
    seal={'schema':'p11-trained-model-seal-1','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'model_sha256':sha(models/'models.json'),'policy_arrays_sha256':sha(models/'policy.npz'),
        'fit_sha256':sha(models/'fit.json'),'selected_for_comparison':selected,'group_balanced_scores':scores,
        'grouping':groups,'details':details,'formal_starts_at_seal':38,'heldout_starts_at_seal':0,
        'theory_or_repair_admission':'NONE; selection is empirical model comparison, not a new scoring/testing method',
        'all_three_models_retained':True,'no_post_heldout_refit':True}
    write(models/'seal.json',seal);print(json.dumps(seal))


if __name__=='__main__':main()

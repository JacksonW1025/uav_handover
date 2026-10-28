#!/usr/bin/env python3
"""Create immutable P11 input manifest before commit. Never starts SITL."""
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import p2_batch
from p9_model import sha,write


def main():
    out=ROOT/'data/p11-20261025-freeze';out.mkdir(parents=True,exist_ok=False)
    accepted=ROOT/'data/p11-20261025-preparation/observation-acceptance.json'
    if json.loads(accepted.read_text())['status']!='PASS':raise RuntimeError('observation not accepted')
    plan=json.loads((ROOT/'config/p11.json').read_text())
    if len(plan['rows'])!=72 or len({r['id'] for r in plan['rows']})!=72:raise RuntimeError('row identity/budget mismatch')
    for row in plan['rows']:
        if sha(ROOT/row['config'])!=row['config_sha256']:raise RuntimeError('config drift '+row['id'])
        cfg=json.loads((ROOT/row['config']).read_text())
        if cfg['safety_tilt_deg']!=45 or row['kind']!='p5_gap':raise RuntimeError('protection/kind drift')
        if cfg['p5']['treatments'][row['treatment']]['rini']!=4:raise RuntimeError('memory baseline drift')
    write(out/'candidate.json',p2_batch.identity())
    paths=[p for folder in ['tools','research','config'] for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in str(p)]
    paths += [ROOT/'docs/THOR_P11_PLAN.md',ROOT/'docs/THOR_P11_INTERFACE.md',ROOT/'tests/test_p11.py',accepted,
        ROOT/'data/p11-20261025-preparation/history-before.json',out/'candidate.json',ROOT/'data/p9-20261024-freeze/model.json']
    paths += [p for p in (ROOT/'patches/p11-20261025-full-timing').rglob('*') if p.is_file()]
    write(out/'manifest.json',{'schema':'p11-input-freeze-1','status':'FROZEN_INPUTS_AWAIT_COMMIT_AND_REMOTE_RECEIPT',
        'files':{str(p.relative_to(ROOT)):sha(p) for p in sorted(set(paths))},'rows':72,
        'budgets':{'development_used':11,'formal_cap':72,'total_max_planned':83,'development_unused':1},
        'policy_sha256':p2_batch.identity()['policy_sha256'],
        'receipt':'receipt.json created only after normal commit/push and remote SHA readback; not a self-hash cycle',
        'model_freeze':'all algorithms/forms/selection/bounds frozen here; trained coefficients derive only from fixed development groups and are sealed before heldout',
        'formal_started':False})
    print('Frozen',len(paths),'inputs; commit+remote receipt still REQUIRED')


if __name__=='__main__':main()

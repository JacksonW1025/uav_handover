#!/usr/bin/env python3
"""Prepare a freeze ONLY after development, equivalence and determinism pass.

The user has already authorized commit/push; this tool does not perform Git
mutations. --receipt checks a separately saved commit and remote main readback.
"""
import argparse
import copy
import json
from pathlib import Path
import subprocess
from p9_model import ROOT, sha, write
from p9_run import budget_counts


def development_gate(preparation):
    items=[json.loads(x) for x in (preparation/'attempts.jsonl').read_text().splitlines()]
    starts=[x for x in items if x['event']=='START_INTENT' and x['budget_class']=='development']
    if not 10<=len(starts)<=12:raise RuntimeError('requires completed 6 technical + 4 equivalence attempts; cap12')
    results=[]
    for s in starts:
        p=ROOT/s['output']/'results.json'
        if not p.exists():raise RuntimeError('unresolved attempt '+s['id'])
        results.append(json.loads(p.read_text())['runs'][0])
    byid={r['id']:r for r in results}
    required=[f'p9-dev-arm-{i}' for i in range(1,5)]+[f'p9-dev-clock-{i}' for i in [1,2]]+[f'p9-equivalence-{i}' for i in range(1,5)]
    for name in required:
        if name not in byid or not byid[name].get('infrastructure_ok') or not byid[name].get('candidate_unchanged') or not byid[name].get('explicit_inputs_unchanged') or byid[name].get('remote_session_after'):
            raise RuntimeError('required development/equivalence evidence missing/failed: '+name)
    eq=[]
    for i in range(1,5):
        r=byid[f'p9-equivalence-{i}'];run=ROOT/r['directory']
        refname='p6-20261019-b1-v2.0-D0.3-A0-T0-1' if i<=2 else 'p6-20261019-b1-v2.0-D0.5-A0-T1a3-1'
        m=json.loads((run/'p6-metrics.json').read_text());reference=json.loads((ROOT/'data'/refname/'p6-metrics.json').read_text())
        a=m['whole']['max_tilt_deg'];b=reference['whole']['max_tilt_deg']
        if m['flight_outcome']['outcome']!=reference['flight_outcome']['outcome'] or abs(a-b)>2.5:
            raise RuntimeError('equivalence outcome/tilt mismatch: '+r['id'])
        from pyulog import ULog
        from p6_export import TOPICS, reconstruct
        u=ULog(str(run/'flight.ulg'),TOPICS+['research_recovery'])
        T={d.name:d.data for d in u.data_list if d.multi_id==0};rec=reconstruct(T)
        if rec['resid']['components_over_1e-4'] or 'research_recovery' in T:
            raise RuntimeError('equivalence RREC0 / policy-input reconstruction mismatch')
        eq.append({'id':r['id'],'reference':refname,'max_tilt_deg':a,'reference_tilt_deg':b,
                   'reconstruction':rec['resid'],'rrec_rows':0})
    return {'counts':budget_counts(items),'technical_required':6,'equivalence':eq,'status':'PASS'}


def prepare(preparation,selected,out):
    if out.exists():raise RuntimeError('freeze output exists; never replace')
    gate=development_gate(preparation)
    deterministic=json.loads((preparation/'determinism.json').read_text())
    if deterministic['status']!='PASS':raise RuntimeError('determinism not passed')
    cfg=json.loads((selected/'config-with-selected-repair.json').read_text())
    from p9_plan import DOMAIN
    cfg['p9']['domain']=DOMAIN
    cfg['p9']['storage_plan']=json.loads((preparation/'storage-plan.json').read_text())
    plan=json.loads((preparation/'design-v2/plan.json').read_text())
    cfg['p9']['status']='FROZEN_PENDING_COMMIT_RECEIPT';cfg['p9']['formal_freeze']=str(out.relative_to(ROOT))
    cfg['p9']['version']='p9-plan-v1-frozen-from-draft-v2'
    cfg['p9']['criteria']={'task':{'tilt_gt_deg':45.,'altitude_loss_gt_m':1.},'tilt_comparison_ge_deg':45.,
                          'fixed_window_s':[0.,16.],'max_lag_m':4.5,'abs_lag_6s_m':.5,'vehicle_catch_up_window_s':10.,
                          'vehicle_position_m':.2,'vehicle_velocity_m_s':.1,'vehicle_dwell_s':.5}
    cfg['p9']['search_feedback']='tilt>=45 only; primary/task retained separately'
    cfg['p7_note']='P9: p7 section supplies unchanged legacy recovery/lag measurement definitions only; this is not a P7 acceptance batch.'
    cfg['p7']={k:cfg['p7'][k] for k in ['recovery','lag','task_failure_criterion']}
    cfg['p7']['recovery']['rate_m_s2']=cfg['p5']['treatments']['P9-CR']['rrec']
    cfg['p4']['groups']={}
    cfg['p4']['purpose']='P9 uses explicit plan.json slots and own audit; old P7 batch groups do not apply.'
    plan['status']='FROZEN_PENDING_COMMIT_RECEIPT'
    out.mkdir(parents=True)
    for source,name in [(preparation/'model.json','model.json'),(selected/'predictions.json','predictions.json'),
                        (selected/'repair-selection.json','repair-selection.json')]:
        (out/name).write_bytes(source.read_bytes())
    predictions=json.loads((out/'predictions.json').read_text());predictions['status']='FROZEN_PRE_FLIGHT'
    write(out/'predictions.json',predictions)
    config=ROOT/'config/p9.json'
    if config.exists():raise RuntimeError('config/p9.json already exists; require new version')
    write(config,cfg);write(out/'plan.json',plan);write(out/'development-gate.json',gate)
    files=[config,ROOT/'docs/THOR_P9_PLAN.md',ROOT/'tools/run_experiment.py',*sorted((ROOT/'tools').glob('p9_*.py')),
           ROOT/'tests/test_p9.py',out/'model.json',out/'plan.json',out/'predictions.json',out/'repair-selection.json',
           preparation/'input-manifest.json',preparation/'development-evaluation.json',preparation/'determinism.json',
           preparation/'seed-audit.json',preparation/'cost-baseline.json',preparation/'environment-preflight.json',
           preparation/'search-exhaustive-test.json',preparation/'analysis-only-validation.json',preparation/'storage-plan.json']
    write(out/'manifest.json',{'version':'P9-v1','files':{str(p.relative_to(ROOT)):sha(p) for p in files},
                             'freeze_precedes_all_formal_starts':True,'development_gate':gate,
                             'raw_remote_complete':False})
    print('PREPARED; commit/push, then create receipt before any formal start')


def receipt(out):
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    remote=subprocess.check_output(['git','ls-remote','origin','refs/heads/main'],cwd=ROOT,text=True).split()[0]
    if head!=remote:raise RuntimeError('remote main does not match freeze commit')
    m=json.loads((out/'manifest.json').read_text())
    import hashlib
    for path,h in m['files'].items():
        data=subprocess.check_output(['git','show',head+':'+path],cwd=ROOT)
        if hashlib.sha256(data).hexdigest()!=h or sha(ROOT/path)!=h:raise RuntimeError('freeze uncommitted/drift: '+path)
    write(out/'receipt.json',{'commit':head,'remote_main':remote,'manifest_sha256':sha(out/'manifest.json'),
                             'CI':'no repository workflow found; not a claim that CI passed'})
    print('SEALED',head)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('preparation',type=Path);p.add_argument('--selected',type=Path)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--receipt',action='store_true');a=p.parse_args()
    if a.receipt:receipt(a.output.resolve())
    else:prepare(a.preparation.resolve(),a.selected.resolve(),a.output.resolve())


if __name__=='__main__':main()

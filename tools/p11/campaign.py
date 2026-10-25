#!/usr/bin/env python3
"""Frozen P11 execution; no retries, no analyzer overwrite, every start counted."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import p2_batch
from p9_run import append,host_gate
from p9_model import sha,write

PREP=ROOT/'data/p11-20261025-preparation'
FROZEN=ROOT/'data/p11-20261025-freeze'
OUT=ROOT/'data/p11-20261025-formal'
PY=ROOT/'uav_lab/.local/venv/bin/python'


def verify():
    manifest=json.loads((FROZEN/'manifest.json').read_text());receipt=json.loads((FROZEN/'receipt.json').read_text())
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if head!=receipt['commit'] or head!=receipt['remote_main'] or sha(FROZEN/'manifest.json')!=receipt['manifest_sha256']:
        raise RuntimeError('frozen commit / verified remote receipt mismatch')
    import hashlib
    committed_manifest=subprocess.check_output(['git','show',head+':'+str((FROZEN/'manifest.json').relative_to(ROOT))],cwd=ROOT)
    if hashlib.sha256(committed_manifest).hexdigest()!=receipt['manifest_sha256']:raise RuntimeError('manifest not in frozen commit')
    for path,h in manifest['files'].items():
        if sha(ROOT/path)!=h:raise RuntimeError('FROZEN_INPUT_DRIFT '+path)
    expected=json.loads((FROZEN/'candidate.json').read_text());expected['project_head']=head
    if p2_batch.identity()!=expected:raise RuntimeError('candidate identity drift')
    acceptance=json.loads((PREP/'observation-acceptance.json').read_text())
    if acceptance['status']!='PASS':raise RuntimeError('observation gate not accepted')
    return manifest,acceptance


def tool(script,args,log):
    with log.open('w') as f:
        r=subprocess.run(['taskset','-c','0-3',str(PY),str(ROOT/'tools/p11'/script),*map(str,args)],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
    if r.returncode:raise RuntimeError('analysis failure '+script+'; see '+str(log))


def execute(row,acceptance):
    verify();host=host_gate();ledger=PREP/'attempts.jsonl'
    plan=json.loads((ROOT/'config/p11.json').read_text())
    wanted=next((r for r in plan['rows'] if r['id']==row['id']),None)
    if wanted!=row:raise RuntimeError('row not identical to fixed frozen case')
    with (PREP/'attempts.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        items=[json.loads(x) for x in ledger.read_text().splitlines()]
        starts=[x for x in items if x['event']=='START_INTENT'];formal=[x for x in starts if x['budget_class']=='formal']
        if len(formal)>=72 or len(starts)>=84:raise RuntimeError('hard startup cap')
        if any(x['id']==row['id'] for x in starts):raise RuntimeError('already begun; never rerun in place')
        formal_ids={x['id'] for x in formal}
        if any(x['event'] in ['STOP','EXCEPTION'] and x['id'] in formal_ids for x in items):raise RuntimeError('prior formal error stops this batch')
        seal_hash=None
        if row['split']=='heldout':
            seal_path=OUT/'models/seal.json';seal=json.loads(seal_path.read_text());seal_hash=sha(seal_path)
            for file,key in [('models.json','model_sha256'),('policy.npz','policy_arrays_sha256'),('fit.json','fit_sha256')]:
                if sha(OUT/'models'/file)!=seal[key]:raise RuntimeError('trained model/weights/fit drift')
            prior=[x for x in formal if x.get('trained_model_seal_sha256')]
            if prior and any(x['trained_model_seal_sha256']!=seal_hash for x in prior):raise RuntimeError('model seal changed after heldout start')
        if sha(ROOT/row['config'])!=row['config_sha256']:raise RuntimeError('row config drift')
        remaining=72-len(formal);storage=acceptance['storage'];required=storage['reserve_bytes']+remaining*storage['per_future_attempt_bound_bytes']
        free=shutil.disk_usage(ROOT).free
        if free<required:raise RuntimeError(f'CAPACITY_BEFORE_START available={free} required={required}; no history deletion')
        attempt=OUT/row['id'];attempt.mkdir(parents=True,exist_ok=False)
        r=dict(row,directory=str((attempt/'run').relative_to(ROOT)),repetition=row['rep'],
            extra_args=['--sim-seed',str(row['sim_seed']),'--initial-yaw-deg','0'])
        write(attempt/'plan.json',r);write(attempt/'host-before.json',host)
        append(ledger,{'event':'START_INTENT','id':row['id'],'time':p2_batch.now(),'budget_class':'formal',
            'ordinal':len(formal)+1,'output':str(attempt.relative_to(ROOT)),'input_sha256':row['config_sha256'],
            'seed':row['sim_seed'],'frozen_manifest_sha256':sha(FROZEN/'manifest.json'),
            'trained_model_seal_sha256':seal_hash,
            'free_bytes':free,'required_remaining_bytes':required,'conservatively_counted':True})
        print('START',len(formal)+1,'/72',row['id'],flush=True);started=time.monotonic()
        try:
            p2_batch.run_one(r,attempt)
            # Preserve generic wrapper booleans exactly; dedicated P11 outcome has its own fields.
            write(attempt/'wrapper-result.json',r)
            tool('observe.py',[attempt/'run','--output',attempt/'observation'],attempt/'observation.log')
            tool('synchronize.py',[attempt/'run','--output',attempt/'synchronization'],attempt/'synchronization.log')
            tool('state.py',[attempt/'observation/synchronized.npz','--config',attempt/'run/config.json','--output',attempt/'target-replay'],attempt/'target-replay.log')
            tool('pack.py',['pack',attempt/'run','--sync',attempt/'observation/synchronized.npz','--output',attempt/'packed'],attempt/'packing.log')
            tool('pack.py',['measure',attempt/'run','--sync',attempt/'observation/synchronized.npz','--output',attempt/'measured'],attempt/'measurement.log')
            measured=json.loads((attempt/'measured/measurement.json').read_text())
            infra=all(v for k,v in r['checks'].items() if k not in ['execution','subject_measured'])
            infra=infra and measured['status']=='MEASURED'
            if not r['checks']['execution'] and not str(r.get('reason','')).startswith('safety:'):infra=False
            verify();after=host_gate();write(attempt/'host-after.json',after)
            r.update({'p11_evidence_status':'MEASURED' if infra else 'FAIL','p11_frozen_flight_outcome':measured['frozen_flight_outcome'],
                'p11_task_outcome':measured['task_outcome'],'p11_censored':measured['censored'],
                'p11_valid_scientific_result':infra,'elapsed_s':time.monotonic()-started,
                'generic_boolean_note':'original flight_failure/accepted are wrapper fields; dedicated P11 outcomes above are authoritative; early safety failures remain failures'})
            write(attempt/'result.json',r)
            append(ledger,{'event':'FINISH','id':row['id'],'budget_class':'formal','time':p2_batch.now(),
                'ordinal':len(formal)+1,'evidence_ok':infra,'flight_outcome':measured['frozen_flight_outcome']['outcome'],
                'task_outcome':measured['task_outcome'],'censored':measured['censored'],'elapsed_s':r['elapsed_s']})
            print('FINISH',row['id'],measured['frozen_flight_outcome']['outcome'],measured['task_outcome'],'censored',measured['censored'],flush=True)
            if not infra:raise RuntimeError('new infrastructure/evidence error; frozen batch stops')
            return r
        except BaseException as exc:
            append(ledger,{'event':'STOP','id':row['id'],'budget_class':'formal','time':p2_batch.now(),
                'reason':repr(exc),'type':'NEW_ERROR_REQUIRES_DIAGNOSIS','retry':'NONE; no new-version continuation to hide this error'})
            write(OUT/'diagnosis.json',{'id':row['id'],'reason':repr(exc),'status':'STOPPED','remaining':'PENDING_UNSTARTED',
                'same_semantics_infrastructure_resume':'only after a separate evidence audit; no implicit retry of this ID'})
            raise


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--stage',choices=['training','heldout'],required=True);a=p.parse_args()
    _,acceptance=verify();plan=json.loads((ROOT/'config/p11.json').read_text())
    OUT.mkdir(exist_ok=True)
    if a.stage=='heldout':
        seal=OUT/'models/seal.json'
        if not seal.exists():raise RuntimeError('training model seal required before heldout starts')
        s=json.loads(seal.read_text())
        if sha(OUT/'models/models.json')!=s['model_sha256']:raise RuntimeError('trained model drift')
        for row in plan['rows']:
            if row['split']=='development' and not (OUT/row['id']/'result.json').exists():raise RuntimeError('training rows incomplete')
    for block in plan['execution_blocks']:
        if (block['split']=='development')!=(a.stage=='training'):continue
        for identity in block['ids']:
            row=next(r for r in plan['rows'] if r['id']==identity)
            existing=OUT/identity/'result.json'
            if existing.exists():
                saved=json.loads(existing.read_text())
                if not saved.get('p11_valid_scientific_result'):raise RuntimeError('prior error prevents pending continuation')
                continue
            execute(row,acceptance)
        ledger=[json.loads(x) for x in (PREP/'attempts.jsonl').read_text().splitlines()]
        starts=[x for x in ledger if x['event']=='START_INTENT'];fin=[x for x in ledger if x['event']=='FINISH' and x.get('budget_class')=='formal']
        write(OUT/f'checkpoint-block-{block["index"]}.json',{'block':block['index'],'status':'COMPLETE','development_starts':sum(x['budget_class']=='development' for x in starts),
            'formal_starts':sum(x['budget_class']=='formal' for x in starts),'valid_results':sum(x.get('evidence_ok',False) for x in fin),
            'failure':sum(x.get('flight_outcome')=='FAILURE' for x in fin),'censored':sum(x.get('censored',False) for x in fin),
            'effective_pairs':'computed after all five branches in each cluster; partial clusters never counted complete'})
        print('BLOCK_COMPLETE',block['index'],len(fin),'formal finished',flush=True)


if __name__=='__main__':main()

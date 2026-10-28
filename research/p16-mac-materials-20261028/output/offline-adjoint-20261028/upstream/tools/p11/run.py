#!/usr/bin/env python3
"""One conservatively counted P11 SITL attempt. No implicit retries or data overwrite."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import p2_batch
from p9_run import append, host_gate
from p9_model import sha, write

PREP=ROOT/'data/p11-20261025-preparation'
CAP={'development':12,'formal':72}


def claim(items, identity, kind, development_revision=1):
    starts=[x for x in items if x['event']=='START_INTENT']
    if any(x['id']==identity for x in starts):
        raise RuntimeError('already attempted; inspect outcome, no implicit retry')
    if sum(x['budget_class']==kind for x in starts)>=CAP[kind] or len(starts)>=84:
        raise RuntimeError('P11 hard startup cap')
    errors=[x for x in items if x['event'] in ['EXCEPTION','STOP']]
    if errors:
        # Development observation repairs are explicitly authorized. Formal errors
        # can NEVER use this path. The saved diagnosis binds the failed attempt.
        diagnosis=PREP/f'development-revision-{development_revision}.json'
        if kind!='development' or development_revision<=1 or not diagnosis.exists():
            raise RuntimeError('prior error stops affected batch; inspect, no version bypass')
        repair=json.loads(diagnosis.read_text())
        if repair['resolved_failed_ids']!=sorted({x['id'] for x in errors}):
            raise RuntimeError('development diagnosis does not cover exactly recorded errors')
        for path,h in repair['fixed_inputs'].items():
            if sha(ROOT/path)!=h:raise RuntimeError('development repair input drift: '+path)
    return 1+sum(x['budget_class']==kind for x in starts)


def execute(a):
    PREP.mkdir(exist_ok=True)
    with (PREP/'attempts.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        ledger=PREP/'attempts.jsonl'
        items=[json.loads(x) for x in ledger.read_text().splitlines()] if ledger.exists() else []
        n=claim(items,a.id,a.budget_class,a.development_revision)
        host=host_gate()
        if shutil.disk_usage(ROOT).free<2_000_000_000+160_000_000:
            raise RuntimeError('storage gate, retain raw histories and 2GB reserve')
        cfg=ROOT/a.config
        if a.budget_class=='formal':
            raise RuntimeError('formal gate not yet implemented or observation accepted')
        out=ROOT/'data/p11-20261025-development'/a.id
        out.mkdir(parents=True,exist_ok=False)
        row={'id':a.id,'kind':'p5_gap','condition':a.condition,'treatment':a.treatment,'config':a.config,
             'directory':str((out/'run').relative_to(ROOT)),'sim_seed':a.seed,'initial_yaw_deg':0.,
             'repetition':1,'status':'NOT_RUN','extra_args':['--sim-seed',str(a.seed),'--initial-yaw-deg','0']}
        row['development_revision']=a.development_revision
        before=p2_batch.identity()
        write(out/'candidate.json',before);write(out/'host-before.json',host);write(out/'plan.json',row)
        append(ledger,{'event':'START_INTENT','id':a.id,'time':p2_batch.now(),'budget_class':a.budget_class,
            'ordinal':n,'input_sha256':sha(cfg),'output':str(out.relative_to(ROOT)),
            'seed':a.seed,'conservative_count':True})
        start=time.monotonic()
        print('START',a.id,n,'/',CAP[a.budget_class],flush=True)
        try:
            p2_batch.run_one(row,out)
            row['candidate_unchanged']=p2_batch.identity()==before
            row['host_after']=p2_batch.host_state();row['elapsed_s']=time.monotonic()-start
            row['infrastructure_ok']=row['infrastructure_ok'] and row['candidate_unchanged'] and not row['host_after']['remote_desktop_session_running']
            # Baseline analyzer execution failure is not automatically a measured flight failure.
            write(out/'result.json',row)
            append(ledger,{'event':'FINISH','id':a.id,'time':p2_batch.now(),'budget_class':a.budget_class,
                'ordinal':n,'infrastructure_ok':row['infrastructure_ok'],'execution':row['checks']['execution'],
                'elapsed_s':row['elapsed_s']})
            print('FINISH',a.id,row['status'],row['infrastructure_ok'],flush=True)
            if not row['infrastructure_ok']:
                append(ledger,{'event':'STOP','id':a.id,'reason':'infrastructure/evidence gate failed','time':p2_batch.now()})
                return 1
            return 0
        except BaseException as exc:
            append(ledger,{'event':'EXCEPTION','id':a.id,'reason':repr(exc),'time':p2_batch.now(),
                'outcome':'uncertain until directory/process audit; no automatic retry'})
            raise


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--id',required=True);p.add_argument('--config',required=True)
    p.add_argument('--condition',default='p9-dev-arm-1');p.add_argument('--treatment',default='P9-Z')
    p.add_argument('--seed',type=int,default=407598619)
    p.add_argument('--budget-class',choices=list(CAP),default='development')
    p.add_argument('--development-revision',type=int,default=1)
    return execute(p.parse_args())


if __name__=='__main__':raise SystemExit(main())

#!/usr/bin/env python3
"""Counted P12 development only. Formal is barred until all independent gates pass."""
import argparse,fcntl,json,shutil,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
import p2_batch
from p9_run import append,host_gate
from p9_model import sha,write
PREP=ROOT/'data/p12-20261026-preparation'
CAP={'development':12,'formal':48}


def claim(items,identity,kind):
    starts=[x for x in items if x['event']=='START_INTENT']
    if any(x['id']==identity for x in starts):raise RuntimeError('already started; never retry')
    if sum(x['budget_class']==kind for x in starts)>=CAP[kind] or len(starts)>=60:
        raise RuntimeError('P12 hard startup cap')
    if any(x['event'] in ['STOP','EXCEPTION','DESIGN_STOP'] for x in items):
        raise RuntimeError('prior error; affected development revision requires explicit diagnosis, no automatic continuation')
    return 1+sum(x['budget_class']==kind for x in starts)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--id',required=True)
    p.add_argument('--config',required=True);p.add_argument('--seed',type=int,default=1334270311)
    a=p.parse_args();PREP.mkdir(exist_ok=True)
    with (PREP/'attempts.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);ledger=PREP/'attempts.jsonl'
        items=[json.loads(s) for s in ledger.read_text().splitlines()] if ledger.exists() else []
        ordinal=claim(items,a.id,'development');host=host_gate()
        free=shutil.disk_usage(ROOT).free
        if free<2_000_000_000+200_000_000:raise RuntimeError('P12 per-development capacity gate')
        out=ROOT/'data/p12-20261026-development'/a.id;out.mkdir(parents=True,exist_ok=False)
        row={'id':a.id,'kind':'p5_gap','condition':'p11-case','treatment':'P11-Z','config':a.config,
            'directory':str((out/'run').relative_to(ROOT)),'sim_seed':a.seed,'initial_yaw_deg':0.,
            'repetition':1,'status':'NOT_RUN','extra_args':['--sim-seed',str(a.seed),'--initial-yaw-deg','0']}
        before=p2_batch.identity();write(out/'candidate.json',before);write(out/'host-before.json',host);write(out/'plan.json',row)
        append(ledger,{'event':'START_INTENT','id':a.id,'budget_class':'development','ordinal':ordinal,
            'time':p2_batch.now(),'input_sha256':sha(ROOT/a.config),'free_bytes':free,
            'candidate_sha256':sha(out/'candidate.json'),'output':str(out.relative_to(ROOT)),
            'count_rule':'conservative intent; failed/aborted/invalid included'})
        print('P12 START',ordinal,'/12',a.id,flush=True);started=time.monotonic()
        try:
            p2_batch.run_one(row,out)
            row['candidate_unchanged']=p2_batch.identity()==before;row['elapsed_s']=time.monotonic()-started
            after=host_gate();write(out/'host-after.json',after)
            row['infrastructure_ok']=row['infrastructure_ok'] and row['candidate_unchanged']
            write(out/'wrapper-result.json',row)
            append(ledger,{'event':'FINISH','id':a.id,'budget_class':'development','ordinal':ordinal,
                'time':p2_batch.now(),'infrastructure_ok':row['infrastructure_ok'],'reason':row.get('reason')})
            print('P12 FINISH',a.id,row['status'],row['infrastructure_ok'],flush=True)
            if not row['infrastructure_ok']:
                append(ledger,{'event':'STOP','id':a.id,'reason':'infrastructure gate failed','time':p2_batch.now()})
                return 1
        except BaseException as e:
            append(ledger,{'event':'EXCEPTION','id':a.id,'reason':repr(e),'time':p2_batch.now(),
                'outcome':'check processes and directory; no automatic retry'})
            raise
    return 0


if __name__=='__main__':raise SystemExit(main())

#!/usr/bin/env python3
"""One counted P9 development attempt through the existing SITL/evidence chain.

No background shell, no killing/adopting processes, no retries. A new directory
is required per attempt. Formal execution uses p9_campaign.py and its separate
development/equivalence and frozen-commit gates.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import time

import psutil
import p2_batch
import p7_batch
from p9_model import ROOT, sha, write


def budget_counts(items):
    starts=[x for x in items if x['event']=='START_INTENT']
    return {kind:sum(x['budget_class']==kind for x in starts) for kind in ['development','formal']}


def claim(items,row,kind):
    if kind not in ['development','formal']:raise ValueError('unknown budget class')
    counts=budget_counts(items);cap={'development':12,'formal':180}[kind]
    if counts[kind]>=cap:raise RuntimeError(kind+' hard cap reached')
    if any(x.get('id')==row['id'] and x['event']=='START_INTENT' for x in items):
        raise RuntimeError('already attempted: inspect outcome; never implicit retry')
    return counts[kind]+1


def host_gate():
    if len(list(Path('/proc').glob('[0-9]*'))) < 50:
        raise RuntimeError('host process namespace unavailable; cannot verify concurrent sessions')
    if subprocess.run(['pgrep','-x','ToDesk_Session'],capture_output=True).returncode==0:
        raise RuntimeError('WAIT_HOST: ToDesk_Session connected; do not stop it')
    active=[]
    for p in psutil.process_iter(['pid','name','cmdline']):
        try:
            name=p.info['name'] or '';args=p.info['cmdline'] or []
            if name in ['px4','MicroXRCEAgent'] or (name in ['gz','gz-sim-server'] and 'sim' in args):
                active.append({'pid':p.pid,'name':name})
        except psutil.Error:continue
    if active:raise RuntimeError('OTHER_SIMULATION_ACTIVE: '+str(active))
    for cpu in Path('/sys/devices/system/cpu').glob('cpu[0-9]*/cpufreq'):
        lo=int((cpu/'scaling_min_freq').read_text());hi=int((cpu/'scaling_max_freq').read_text())
        if lo!=2601000 or hi!=2601000:
            raise RuntimeError('clock gate: jetson_clocks must be verified after reboot')
    return p2_batch.host_state()


def append(path,item):
    with path.open('a') as f:
        f.write(json.dumps(item,ensure_ascii=False,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())


def run_development(preparation,design,index,output):
    preparation=preparation.resolve();design=design.resolve();output=output.resolve()
    config=design/'config.json';plan_path=design/'plan.json';plan=json.loads(plan_path.read_text())
    row=dict(plan['development'][index]);row['config']=row.get('config',str(config.relative_to(ROOT)))
    row.update(directory=str((output/'run').relative_to(ROOT)),repetition=1,initial_yaw_deg=0.,
               extra_args=['--sim-seed',str(row['sim_seed']),'--initial-yaw-deg','0'])
    actual_cfg=ROOT/row['config']
    if output.exists():raise RuntimeError('attempt output already exists; no overwrite or implicit rerun')
    ledger=preparation/'attempts.jsonl';budget_lock=preparation/'attempts.lock'
    with budget_lock.open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        old=[json.loads(x) for x in ledger.read_text().splitlines()] if ledger.exists() else []
        intents=[x for x in old if x['event']=='START_INTENT']
        dev=[x for x in intents if x['budget_class']=='development']
        claim(old,row,'development')
        try:host=host_gate()
        except Exception as exc:
            append(ledger,{'event':'BLOCKED_BEFORE_START','time':p2_batch.now(),'id':row['id'],'reason':str(exc),'counts_as_start':False})
            raise
        output.mkdir(parents=True,exist_ok=False)
        candidate=p2_batch.identity();write(output/'candidate.json',candidate);write(output/'host-before.json',host)
        fingerprint={str(x.relative_to(ROOT)):sha(x) for x in [actual_cfg,plan_path,preparation/'model.json']}
        write(output/'plan.json',{'row':row,'mode':'development','budget_class':'development','inputs':fingerprint,
                                'flight_failure_is_result':True,'formal_validation':False})
        append(ledger,{'event':'START_INTENT','time':p2_batch.now(),'id':row['id'],'budget_class':'development',
                       'attempt_number':len(dev)+1,'output':str(output.relative_to(ROOT)),'seed':row['sim_seed'],
                       'warning':'intent is conservatively counted even if subprocess fails to launch'})
        start=time.monotonic()
        try:
            print('START',row['id'],'development',len(dev)+1,'/12',flush=True)
            p7_batch.run_row(row,output)
            if 'p9' in json.loads(actual_cfg.read_text()) and (output/'run/p7-metrics.json').exists():
                from p9_metrics import analyze
                measured=analyze(output/'run');write(output/'run/p9-metrics.json',measured)
                row['p9_status']=measured['status']
                row['infrastructure_ok']=bool(row['infrastructure_ok'] and measured['status']=='MEASURED')
                import p7_export
                summary=p7_export.export_run(row['directory'],output/'export',str(output.relative_to(ROOT)),row,'p9-development')
                row['reconstruction']=summary['reconstruction']
                row['infrastructure_ok']=bool(row['infrastructure_ok'] and summary['reconstruction']['components_over_1e-4']==0)
            write(output/'host-after.json',p2_batch.host_state())
            row['candidate_unchanged']=p2_batch.identity()==candidate
            row['explicit_inputs_unchanged']=all(sha(ROOT/p)==h for p,h in fingerprint.items())
            row['remote_session_after']=p2_batch.host_state()['remote_desktop_session_running']
            row['elapsed_s']=time.monotonic()-start
            write(output/'results.json',{'status':'DEVELOPMENT','runs':[row],'formal_validation':False})
            append(ledger,{'event':'FINISH','time':p2_batch.now(),'id':row['id'],'elapsed_s':row['elapsed_s'],
                           'infrastructure_ok':row.get('infrastructure_ok'),'flight_failure':row.get('flight_failure'),
                           'candidate_unchanged':row['candidate_unchanged'],'status':row['status']})
            print('END',row['id'],row.get('flight_outcome'),row.get('infrastructure_ok'),flush=True)
            return 0 if row.get('infrastructure_ok') and row['candidate_unchanged'] and row['explicit_inputs_unchanged'] and not row['remote_session_after'] else 1
        except BaseException as exc:
            append(ledger,{'event':'INTERRUPTED_OR_EXCEPTION','time':p2_batch.now(),'id':row['id'],'error':repr(exc),
                           'outcome':'uncertain; inspect directory/processes before any retry'})
            raise


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('preparation',type=Path);p.add_argument('--design',type=Path,required=True)
    p.add_argument('--development-index',type=int,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();return run_development(a.preparation,a.design,a.development_index,a.output)


if __name__=='__main__':raise SystemExit(main())

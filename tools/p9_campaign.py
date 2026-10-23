#!/usr/bin/env python3
"""P9 formal execution. Requires committed, remote-verified freeze receipt.

Run in the session background mechanism, never `cmd &`. No automatic retries.
Formal results cannot modify a model, design, prediction or repair choice.
"""
import argparse
import fcntl
import json
from pathlib import Path
import subprocess
import time
import shutil
import math

import p2_batch
import p7_batch
import p7_export
from p9_model import ROOT, sha, write
from p9_metrics import analyze
from p9_predict import forecast
from p9_run import append, claim, host_gate, budget_counts
from p9_search import propose
from p9_plan import case_spec


def validate_row(plan,cfg,row):
    static=next((x for x in plan['runs'] if x['id']==row['id']),None)
    slot=next((x for x in plan['search_slots'] if x['id']==row['id']),None)
    wanted=static or slot
    if wanted is None:raise RuntimeError('unplanned formal id')
    keys=['stage','sim_seed','treatment']+(['kind','condition','case'] if static else ['family','method','query'])
    if any(row.get(k)!=wanted.get(k) for k in keys):raise RuntimeError('formal row differs from frozen slot')
    if slot and not any(c['family']==slot['family'] and c['case']==row['case'] and c['condition']==row['condition'] for c in plan['search_candidates']):
        raise RuntimeError('proposal outside frozen search family')
    spec=case_spec(cfg,row['case'])
    if spec!=cfg['p5']['conditions'][row['condition']]:raise RuntimeError('prediction / runner condition mismatch')


def storage_gate(cfg,items,available=None):
    rule=cfg['p9']['storage_plan'];remaining=cfg['p9']['budget']['formal_cap']-budget_counts(items)['formal']
    per=math.ceil(rule['max_pilot_allocated_bytes']*rule['per_attempt_multiplier'])
    required=rule['audit_and_system_reserve_bytes']+max(0,remaining)*per
    free=shutil.disk_usage(ROOT).free if available is None else available
    if free<required:raise RuntimeError(f'BLOCKED_STORAGE: available {free}, need {required}; preserve historical raw files')
    return {'available_bytes':free,'required_bytes':required,'remaining_max_starts':remaining,'status':'PASS'}


def verify_freeze(frozen):
    manifest=json.loads((frozen/'manifest.json').read_text());receipt=json.loads((frozen/'receipt.json').read_text())
    if sha(frozen/'manifest.json')!=receipt['manifest_sha256']:raise RuntimeError('freeze manifest/receipt hash mismatch')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if head!=receipt['commit'] or receipt.get('remote_main')!=head:raise RuntimeError('freeze HEAD / verified remote receipt mismatch')
    import hashlib
    saved=subprocess.check_output(['git','show',head+':'+str((frozen/'manifest.json').relative_to(ROOT))],cwd=ROOT)
    if hashlib.sha256(saved).hexdigest()!=receipt['manifest_sha256']:raise RuntimeError('manifest not saved in frozen commit')
    for path,h in manifest['files'].items():
        if sha(ROOT/path)!=h:raise RuntimeError('FROZEN_INPUT_DRIFT '+path)
        # Every frozen input must exist in the saved commit, not just in the working tree.
        blob=subprocess.check_output(['git','show',head+':'+path],cwd=ROOT)
        if hashlib.sha256(blob).hexdigest()!=h:raise RuntimeError('frozen file not committed: '+path)
    return manifest


def execute_one(row,cfg,model,preparation,out,candidate,frozen,history=None):
    verify_freeze(frozen)
    validate_row(json.loads((frozen/'plan.json').read_text()),cfg,row)
    if p2_batch.identity()!=candidate:raise RuntimeError('IDENTITY_DRIFT')
    host=host_gate()
    attempt=out/row['id']
    ledger=preparation/'attempts.jsonl'
    with (preparation/'attempts.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        items=[json.loads(x) for x in ledger.read_text().splitlines()] if ledger.exists() else []
        count=claim(items,row,'formal')
        host['storage']=storage_gate(cfg,items)
        if attempt.exists():raise RuntimeError('existing attempt must be inspected; never rerun in place')
        attempt.mkdir(parents=True,exist_ok=False)
        row=dict(row);row['config']='config/p9.json';row['directory']=str((attempt/'run').relative_to(ROOT));row['repetition']=1
        row['extra_args']=['--sim-seed',str(row['sim_seed']),'--initial-yaw-deg','0']
        # Query prediction and OWN prior history durable BEFORE any simulator start.
        compute_start=time.monotonic();prediction=forecast(model,row['case'],cfg['p5']['treatments'][row['treatment']])
        row['prediction_compute_s']=time.monotonic()-compute_start
        write(attempt/'prediction-before-query.json',{'row':row,'prediction':prediction,'own_history':history or [],
                                                     'model_sha256':sha(frozen/'model.json'),'frozen_manifest_sha256':sha(frozen/'manifest.json')})
        write(attempt/'host-before.json',host)
        append(ledger,{'event':'START_INTENT','time':p2_batch.now(),'id':row['id'],'budget_class':'formal',
                       'attempt_number':count,'output':str(attempt.relative_to(ROOT)),'stage':row['stage'],
                       'seed':row['sim_seed'],'prediction_sha256':sha(attempt/'prediction-before-query.json')})
        print('START',count,'/180',row['id'],flush=True);started=time.monotonic()
        try:
            p7_batch.run_row(row,attempt)
            if (attempt/'run/p7-metrics.json').exists():
                measured=analyze(attempt/'run');write(attempt/'run/p9-metrics.json',measured)
                row['p9']=measured
                row['checks']['p9_measured']=measured['status']=='MEASURED'
                # P7 exporter writes into this NEW attempt only, not export/manifest.json.
                summary=p7_export.export_run(row['directory'],attempt/'export',str(out.relative_to(ROOT)),row,'p9-'+row['stage'])
                row['reconstruction']=summary['reconstruction']
                row['checks']['p9_reconstruction']=summary['reconstruction']['components_over_1e-4']==0
            else:row['checks']['p9_measured']=False
            row['candidate_unchanged']=p2_batch.identity()==candidate
            row['host_after']=p2_batch.host_state();write(attempt/'host-after.json',row['host_after'])
            row['checks']['remote_disconnected']=not row['host_after']['remote_desktop_session_running']
            row['checks']['candidate_unchanged']=row['candidate_unchanged']
            infra=[k for k in row['checks'] if k not in ['execution','subject_measured']]
            row['infrastructure_ok']=all(row['checks'][k] for k in infra)
            row['flight_failure']=bool(row['infrastructure_ok'] and row.get('flight_outcome')=='FAILURE')
            row['accepted']=bool(row['infrastructure_ok'] and row.get('flight_outcome')=='SUCCESS')
            row['elapsed_s']=time.monotonic()-started
            write(attempt/'result.json',row)
            append(ledger,{'event':'FINISH','time':p2_batch.now(),'id':row['id'],'stage':row['stage'],
                           'infrastructure_ok':row['infrastructure_ok'],'flight_failure':row['flight_failure'],
                           'elapsed_s':row['elapsed_s'],'status':row['status']})
            print('END',count,row['id'],row['flight_outcome'],'infra',row['infrastructure_ok'],
                  'tilt',row.get('p9',{}).get('max_tilt_deg'),flush=True)
            if not row['infrastructure_ok']:raise RuntimeError('infrastructure/evidence failure; counted, no automatic retry')
            return row
        except BaseException as exc:
            append(ledger,{'event':'INTERRUPTED_OR_EXCEPTION','time':p2_batch.now(),'id':row['id'],'error':repr(exc),
                           'outcome':'inspect saved result/processes; do not automatically retry'})
            raise


def campaign(preparation,frozen,out):
    verify_freeze(frozen);cfg=json.loads((ROOT/'config/p9.json').read_text())
    model=json.loads((frozen/'model.json').read_text());plan=json.loads((frozen/'plan.json').read_text())
    out.mkdir(parents=True,exist_ok=True)
    if (out/'candidate.json').exists():candidate=json.loads((out/'candidate.json').read_text())
    else:candidate=p2_batch.identity();write(out/'candidate.json',candidate)
    results=[]
    def one(row,history=None):
        path=out/row['id']/'result.json'
        if path.exists():
            r=json.loads(path.read_text())
            if not r.get('infrastructure_ok'):raise RuntimeError('prior infrastructure failure blocks resume: '+row['id'])
        else:
            # A session reconnect blocks new launches; it is not a started attempt.
            while subprocess.run(['pgrep','-x','ToDesk_Session'],capture_output=True).returncode==0:
                print('WAIT_HOST ToDesk connected; no launch',p2_batch.now(),flush=True);time.sleep(30)
            try:r=execute_one(row,cfg,model,preparation,out,candidate,frozen,history)
            except BaseException as exc:
                saved=out/row['id']/'result.json'
                items=[json.loads(x) for x in (preparation/'attempts.jsonl').read_text().splitlines()]
                started=any(x['event']=='START_INTENT' and x['id']==row['id'] for x in items)
                if started:
                    failed=json.loads(saved.read_text()) if saved.exists() else dict(row,status='UNRESOLVED',infrastructure_ok=False)
                    results.append(failed)
                write(out/'results.json',{'status':'STOPPED' if started else 'BLOCKED_BEFORE_START','runs':results,'formal_cap':180,'reason':repr(exc)})
                write(out/'diagnosis.json',{'id':row['id'],'reason':repr(exc),'retry':'none; inspect outcome before any new version'})
                raise
        if not any(x['id']==r['id'] for x in results):results.append(r)
        write(out/'results.json',{'status':'RUNNING','runs':results,'formal_cap':180})
        return r
    for row in plan['runs']:
        if row['stage']=='B':one(row)
    searches=[]
    for family in sorted({r['family'] for r in plan['search_candidates']}):
        pool=sorted([r for r in plan['search_candidates'] if r['family']==family],key=lambda x:x['phase_s'])
        pool_start=time.monotonic()
        forecasts=[dict(forecast(model,r['case'],cfg['p5']['treatments'][r['treatment']]),phase_s=r['phase_s']) for r in pool]
        pool_compute=time.monotonic()-pool_start
        for method in ['ledger','replay']:
            history=[];trace=[]
            slots=[r for r in plan['search_slots'] if r['family']==family and r['method']==method]
            final=None
            for slot in slots:
                proposal=propose(method,forecasts,history);trace.append(proposal)
                if proposal['index'] is None:final=proposal;break
                i=proposal['index'];choice=pool[i]
                row=dict(slot,kind='p5_gap',condition=choice['condition'],case=choice['case'],phase_s=choice['phase_s'])
                r=one(row,history)
                measured=r['p9'];fail=measured['tilt_ge_45_failure']
                if fail is None:raise RuntimeError('no C tilt observation; cannot supply fabricated feedback')
                if measured['censored'] and not fail:
                    final={'status':'CENSORED_UNRESOLVED','index':None,'reason':'full-horizon tilt did not become observable before another abort',
                           'counted_queries':len(history)+1,'censored_query_id':r['id']}
                    break
                history.append({'id':r['id'],'index':i,'phase_s':choice['phase_s'],'failure':fail,
                                'tilt_deg':measured['max_tilt_deg'],'sim_seed':r['sim_seed']})
                write(out/f'search-{family}-{method}.json',{'family':family,'method':method,'history':history,'trace':trace})
            if final is None:final=propose(method,forecasts,history)
            summary={'family':family,'method':method,'history':history,'trace':trace,'final':final,
                     'query_cap':10,'target_precision_s':.05,'reference_results_accessed':False,
                     'shared_pool_compute_s':pool_compute,'cost_note':'same pool shared between both methods; count once per family'}
            searches.append(summary);write(out/f'search-{family}-{method}.json',summary)
    write(out/'searches-sealed-before-reference.json',{'searches':searches,'frozen_model_sha256':sha(frozen/'model.json')})
    for stage in ['C-reference','D']:
        for row in plan['runs']:
            if row['stage']==stage:one(row)
    write(out/'results.json',{'status':'COMPLETE','runs':results,'searches':searches,
                            'formal_cap':180,'unused_query_slots':180-len(results)})
    print('COMPLETE formal starts',len(results),'unused',180-len(results),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('preparation',type=Path);p.add_argument('--frozen',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();campaign(a.preparation.resolve(),a.frozen.resolve(),a.output.resolve())


if __name__=='__main__':main()

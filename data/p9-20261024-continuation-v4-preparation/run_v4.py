#!/usr/bin/env python3
"""P9 approved continuation v2: exactly11 never-started original rows and independent measurement adapter.

New frozen execution version, no replay of missing attempt102, no refit/search.
Existing original inputs remain immutable. Stop on first new infrastructure fault.
"""
import argparse,fcntl,json,subprocess,time,sys,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'data/p9-20261024-continuation-v3-preparation'))
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'data/p9-20261024-continuation-v2-preparation'))
import p2_batch,p7_batch,p7_export,psutil
from p9_model import ROOT,sha,write
from measurement_v2 import analyze as assess_measurement
from opportunity_v3 import assess as assess_opportunity,decide
from p9_predict import forecast
from p9_run import append,claim,host_gate as original_host_gate,budget_counts
from p9_campaign import validate_row,storage_gate


def host_gate():
    state=original_host_gate()
    extra=[]
    for proc in psutil.process_iter(['pid','name','cmdline']):
        try:
            name=proc.info['name'] or '';args=proc.info['cmdline'] or [];joined=' '.join(args)
            if name in ['ruby','gz','gz-sim-server'] and (joined.startswith('gz sim ') or name=='gz-sim-server'):
                extra.append({'pid':proc.pid,'name':name})
        except psutil.Error:pass
    if extra:raise RuntimeError('OTHER_GAZEBO_ACTIVE: '+str(extra))
    return state


def verify_freeze(frozen):
    m=json.loads((frozen/'manifest.json').read_text());r=json.loads((frozen/'receipt.json').read_text())
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if head!=r['commit'] or r['remote_main']!=head or sha(frozen/'manifest.json')!=r['manifest_sha256']:raise RuntimeError('v2 freeze/receipt/HEAD mismatch')
    chain=[(frozen,head),(ROOT/'data/p9-20261024-continuation-v3-freeze',m['previous_freeze_commit']),(ROOT/'data/p9-20261024-continuation-v2-freeze',m['v2_freeze_commit']),(ROOT/'data/p9-20261024-continuation-v1-freeze',m['v1_freeze_commit']),(ROOT/'data/p9-20261024-freeze',m['original_freeze_commit'])]
    for folder,commit in chain:
        mm=json.loads((folder/'manifest.json').read_text())
        for path,h in mm['files'].items():
            if sha(ROOT/path)!=h or hashlib.sha256(subprocess.check_output(['git','show',commit+':'+path],cwd=ROOT)).hexdigest()!=h:raise RuntimeError('FROZEN_DRIFT '+path)
    if not (ROOT/'data/p9-20261024-preparation/attempts.jsonl').read_bytes().startswith((frozen/'prior-ledger.jsonl').read_bytes()):raise RuntimeError('ledger prefix changed')
    if sha(ROOT/'data/p9-20261024-formal/searches-sealed-before-reference.json')!=m['sealed_searches_sha256']:raise RuntimeError('search seal changed')
    return m


def claim_continuation(items,row):
    counts=budget_counts(items)
    if counts['development']!=10 or not 169<=counts['formal']<173:
        raise RuntimeError('continuation requires dev10 and formal starts169..172')
    n=claim(items,row,'formal')
    allowed=json.loads((ROOT/'data/p9-20261024-continuation-v4-freeze/plan.json').read_text())['runs']
    if row['id'] not in {r['id'] for r in allowed}:raise RuntimeError('unplanned remaining ID')
    return n


def measure_row(row,attempt,out):
    if (attempt/'run/p7-metrics.json').exists():
        assessment=assess_measurement(attempt/'run');write(attempt/'run/p9-v2-assessment.json',assessment)
        row['measurement_version']='p9-open-gap-measurement-v2';row['measurement_kind']=assessment['kind']
        measured=assessment['measurement']
        if measured is None:raise RuntimeError('UNMEASURABLE: '+str(assessment.get('reason')))
        if assessment['kind']=='ORIGINAL_COMPATIBLE':write(attempt/'run/p9-metrics.json',measured)
        else:write(attempt/'run/p9-v2-metrics.json',measured)
        row['p9']=measured
        row['checks']['p9_measured']=measured['status']=='MEASURED'
        # P7 exporter writes into this NEW attempt only, not export/manifest.json.
        summary=p7_export.export_run(row['directory'],attempt/'export',str(out.relative_to(ROOT)),row,'p9-'+row['stage'])
        row['reconstruction']=summary['reconstruction']
        row['checks']['p9_reconstruction']=summary['reconstruction']['components_over_1e-4']==0
    else:row['checks']['p9_measured']=False
    opportunity=assess_opportunity(attempt/'run');write(attempt/'run/recovery-opportunity-v3.json',opportunity)
    row['opportunity_v3']=opportunity


def decide_row(row,attempt):
    assessment=json.loads((attempt/'run/p9-v2-assessment.json').read_text())
    p7=json.loads((attempt/'run/p7-metrics.json').read_text())
    gate=decide(row,assessment,row['opportunity_v3'],p7);row['admission_v3']=gate;row['admissible_v3']=gate['evidence_admissible'];row['observed_flight_failure']=gate['observed_flight_failure']
    write(attempt/'run/admission-v3.json',gate)
    return gate


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
        count=claim_continuation(items,row)
        host['storage']=storage_gate(cfg,items)
        if attempt.exists():raise RuntimeError('existing attempt must be inspected; never rerun in place')
        attempt.mkdir(parents=True,exist_ok=False)
        row=dict(row);row['config']='config/p9.json';row['directory']=str((attempt/'run').relative_to(ROOT));row['repetition']=1
        row['extra_args']=['--sim-seed',str(row['sim_seed']),'--initial-yaw-deg','0']
        # Query prediction and OWN prior history durable BEFORE any simulator start.
        compute_start=time.monotonic();prediction=forecast(model,row['case'],cfg['p5']['treatments'][row['treatment']])
        row['prediction_compute_s']=time.monotonic()-compute_start
        prior_rows=json.loads((ROOT/'data/p9-20261024-freeze/predictions.json').read_text())['predictions']
        expected=next(x for x in prior_rows if x['id']==row['id'])
        if any(prediction[k]!=expected[k] for k in prediction):raise RuntimeError('original forecast changed')
        row['execution_epoch']='continuation-v4'
        write(attempt/'prediction-before-query.json',{'row':row,'prediction':prediction,'own_history':history or [],
                                                     'model_sha256':sha(frozen/'model.json'),'frozen_manifest_sha256':sha(frozen/'manifest.json')})
        write(attempt/'host-before.json',host)
        append(ledger,{'event':'START_INTENT','time':p2_batch.now(),'id':row['id'],'budget_class':'formal',
                       'attempt_number':count,'output':str(attempt.relative_to(ROOT)),'stage':row['stage'],
                       'seed':row['sim_seed'],'prediction_sha256':sha(attempt/'prediction-before-query.json')})
        print('START',count,'/173',row['id'],flush=True);started=time.monotonic()
        try:
            p7_batch.run_row(row,attempt)
            measure_row(row,attempt,out)
            row['candidate_unchanged']=p2_batch.identity()==candidate
            row['host_after']=p2_batch.host_state();write(attempt/'host-after.json',row['host_after'])
            row['checks']['remote_disconnected']=not row['host_after']['remote_desktop_session_running']
            row['checks']['candidate_unchanged']=row['candidate_unchanged']
            infra=[k for k in row['checks'] if k not in ['execution','subject_measured']]
            row['infrastructure_ok']=all(row['checks'][k] for k in infra)
            row['flight_failure']=bool(row['infrastructure_ok'] and row.get('flight_outcome')=='FAILURE')
            row['accepted']=bool(row['infrastructure_ok'] and row.get('flight_outcome')=='SUCCESS')
            decide_row(row,attempt)
            row['elapsed_s']=time.monotonic()-started
            write(attempt/'result.json',row)
            append(ledger,{'event':'FINISH','time':p2_batch.now(),'id':row['id'],'stage':row['stage'],
                           'infrastructure_ok':row['infrastructure_ok'],'flight_failure':row['flight_failure'],
                           'observed_flight_failure':row['observed_flight_failure'],'evidence_admissible_v3':row['admissible_v3'],
                           'elapsed_s':row['elapsed_s'],'status':row['status']})
            print('END',count,row['id'],row['flight_outcome'],'infra',row['infrastructure_ok'],
                  'evidence_v3',row['admissible_v3'],'tilt',row.get('p9',{}).get('max_tilt_deg'),flush=True)
            if not row['admissible_v3']:raise RuntimeError('infrastructure/evidence failure; counted, no automatic retry')
            return row
        except BaseException as exc:
            append(ledger,{'event':'INTERRUPTED_OR_EXCEPTION','time':p2_batch.now(),'id':row['id'],'error':repr(exc),
                           'outcome':'inspect saved result/processes; do not automatically retry'})
            raise


def campaign(preparation,frozen,out):
    verify_freeze(frozen)
    if out.exists():raise RuntimeError('continuation output exists; no automatic resume/retry')
    cfg=json.loads((ROOT/'config/p9.json').read_text());plan=json.loads((frozen/'plan.json').read_text())
    model=json.loads((frozen/'model.json').read_text())
    items=[json.loads(x) for x in (preparation/'attempts.jsonl').read_text().splitlines()]
    if budget_counts(items)!={'development':10,'formal':169}:raise RuntimeError('unexpected pre-continuation budget')
    if len(plan['runs'])!=4 or any(r['stage']!='D' for r in plan['runs']):raise RuntimeError('invalid continuation rows')
    started={x['id'] for x in items if x['event']=='START_INTENT'}
    if any(r['id'] in started for r in plan['runs']):raise RuntimeError('plan attempts an already-started id')
    candidate=p2_batch.identity();old=json.loads((ROOT/'data/p9-20261024-formal/candidate.json').read_text())
    if {k:v for k,v in candidate.items() if k!='project_head'}!={k:v for k,v in old.items() if k!='project_head'}:
        raise RuntimeError('flight implementation/Lab/policy differs from original epoch')
    host_gate();out.mkdir(parents=True,exist_ok=False)
    (out/'searches-sealed-before-reference.json').write_bytes((ROOT/'data/p9-20261024-formal/searches-sealed-before-reference.json').read_bytes())
    write(out/'candidate.json',candidate);write(out/'candidate-equivalence.json',{'status':'PASS','only_project_head_differs':True,'old_head':old['project_head'],'new_head':candidate['project_head']})
    results=[]
    for planned in plan['runs']:
        row=dict(planned)
        while subprocess.run(['pgrep','-x','ToDesk_Session'],capture_output=True).returncode==0:
            print('WAIT_HOST ToDesk connected; no launch',p2_batch.now(),flush=True);time.sleep(30)
        try:
            r=execute_one(row,cfg,model,preparation,out,candidate,frozen)
            results.append(r)
            write(out/'results.json',{'status':'RUNNING','execution_epoch':'continuation-v4','runs':results,'original_interrupted_attempt_excluded':True,'total_start_cap':173})
        except BaseException as exc:
            saved=out/row['id']/'result.json'
            if saved.exists() and not any(x['id']==row['id'] for x in results):results.append(json.loads(saved.read_text()))
            write(out/'results.json',{'status':'STOPPED_INFRASTRUCTURE','runs':results,'reason':repr(exc),'retry':'NONE; new epoch stops, preserve partial outputs'})
            write(out/'diagnosis.json',{'id':row['id'],'reason':repr(exc),'no_automatic_retry':True})
            raise
    counts=budget_counts([json.loads(x) for x in (preparation/'attempts.jsonl').read_text().splitlines()])
    if counts!={'development':10,'formal':173}:raise RuntimeError('final count mismatch')
    write(out/'results.json',{'status':'COMPLETE','execution_epoch':'continuation-v4','runs':results,'new_runs':4,'total_start_counts':counts,
          'original_interrupted_attempt_excluded':True,'overall_observation':'173 starts; original102 missing, original162 postflight diagnostic; at most169 admitted measurements; old164 and169 remain excluded; no overall acceptance PASS'})
    print('CONTINUATION V4 COMPLETE4; total173 starts, original102 and162 retained separately',flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--freeze',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();campaign(ROOT/'data/p9-20261024-preparation',a.freeze.resolve(),a.output.resolve())


if __name__=='__main__':main()

#!/usr/bin/env python3
"""Independent read-only P9 audit from raw ULog and before-query records.

Writes fresh audit outputs only. Old run analyzers/results are never replaced.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from run_v2 import verify_freeze
import p7_metrics
import p7_export
import p2_batch
from pyulog import ULog
from p9_model import ROOT, sha, write
from measurement_v2 import analyze as assess
from p9_predict import forecast
from p9_run import budget_counts
from p9_search import propose


def audit(preparation,frozen,formal,out):
    out.mkdir(parents=True,exist_ok=False)
    verify_freeze(frozen)
    ledger=[json.loads(x) for x in (preparation/'attempts.jsonl').read_text().splitlines()]
    counts=budget_counts(ledger);errors=[]
    if counts['development']>12 or counts['formal']>180:errors.append('hard budget exceeded')
    starts=[r for r in ledger if r['event']=='START_INTENT'];ids=[r['id'] for r in starts]
    if len(ids)!=len(set(ids)):errors.append('duplicate started id')
    manifest=json.loads((frozen/'manifest.json').read_text());receipt=json.loads((frozen/'receipt.json').read_text())
    if sha(frozen/'manifest.json')!=receipt['manifest_sha256']:errors.append('frozen manifest changed')
    for path,h in manifest['files'].items():
        if sha(ROOT/path)!=h:errors.append('frozen input changed: '+path)
    cfg=json.loads((ROOT/'config/p9.json').read_text());model=json.loads((frozen/'model.json').read_text())
    plan=json.loads((frozen/'plan.json').read_text());doc=json.loads((formal/'results.json').read_text())
    planned={r['id']:r for r in plan['runs']+plan['search_slots']}
    inputs={};checked=[];histories={}
    if not (formal/'searches-sealed-before-reference.json').exists() and any(r['stage']=='C-reference' for r in doc['runs']):
        errors.append('reference executed without sealed searches')
    for r in doc['runs']:
        rid=r['id'];attempt=formal/rid;run=attempt/'run';errs=[]
        if rid not in planned:errs.append('unplanned id')
        elif r['sim_seed']!=planned[rid]['sim_seed']:errs.append('seed differs from frozen slot')
        start=next((s for s in starts if s['id']==rid),None)
        if start is None:errs.append('missing counted start')
        record=attempt/'prediction-before-query.json';prior=json.loads(record.read_text())
        if start and start['prediction_sha256']!=sha(record):errs.append('before-query record changed')
        if prior['model_sha256']!=sha(frozen/'model.json'):errs.append('model id differs')
        expected=forecast(model,r['case'],cfg['p5']['treatments'][r['treatment']])
        if expected!=prior['prediction']:errs.append('deterministic prediction mismatch')
        raw_meta=json.loads((run/'metadata.json').read_text())
        if raw_meta.get('ulog_sha256')!=sha(run/'flight.ulg'):errs.append('ULog hash mismatch')
        reassessment=assess(run);write(out/(rid+'-v2-assessment.json'),reassessment)
        remeasured=reassessment['measurement']
        if reassessment['kind']!=r['measurement_kind']:errs.append('measurement provenance differs')
        write(out/(rid+'-p9.json'),remeasured)
        if remeasured!=r['p9']:errs.append('fixed-window measurement differs from raw reconstruction')
        old=json.loads((run/'p7-metrics.json').read_text());rebuilt=p7_metrics.analyze(run)
        write(out/(rid+'-p7.json'),rebuilt)
        if old!=rebuilt:errs.append('frozen primary/recovery measurement differs')
        errors_chain,_=p2_batch.chain_errors(json.loads((run/'output-chain.json').read_text()),bool(old.get('aborted')))
        if errors_chain:errs.append('output-chain gate: '+str(errors_chain))
        topics=p7_export.TOPICS
        u=ULog(str(run/'flight.ulg'),topics);tables={d.name:d.data for d in u.data_list if d.multi_id==0}
        reconstruction=p7_export.reconstruct(tables)['resid']
        if reconstruction['components_over_1e-4'] or reconstruction['rows_unmatched']:errs.append('policy-input reconstruction')
        before=json.loads((attempt/'host-before.json').read_text());after=json.loads((attempt/'host-after.json').read_text())
        if before['remote_desktop_session_running'] or after['remote_desktop_session_running']:errs.append('ToDesk contamination')
        if not r.get('candidate_unchanged') or not r.get('infrastructure_ok'):errs.append('candidate/infra not accepted')
        if r['stage']=='C-search':
            key=(r['family'],r['method']);history=histories.setdefault(key,[])
            if prior['own_history']!=history:errs.append('search own-history mismatch / forbidden feedback')
            pool=sorted([c for c in plan['search_candidates'] if c['family']==r['family']],key=lambda c:c['phase_s'])
            fs=[dict(forecast(model,c['case'],cfg['p5']['treatments'][c['treatment']]),phase_s=c['phase_s']) for c in pool]
            prop=propose(r['method'],fs,history)
            i=prop['index']
            if i is None or r['case']!=pool[i]['case']:errs.append('search proposal differs from isolated replay')
            if i is not None and (not r['p9']['censored'] or r['p9']['tilt_ge_45_failure']):
                history.append({'id':rid,'index':i,'phase_s':pool[i]['phase_s'],'failure':r['p9']['tilt_ge_45_failure'],
                                'tilt_deg':r['p9']['max_tilt_deg'],'sim_seed':r['sim_seed']})
        for path in [record,attempt/'result.json',run/'flight.ulg',run/'config.json',run/'events.jsonl',run/'p7-metrics.json',run/('p9-metrics.json' if r['measurement_kind']=='ORIGINAL_COMPATIBLE' else 'p9-v2-metrics.json'),run/'p9-v2-assessment.json',run/'output-chain.json']:
            inputs[str(path.relative_to(ROOT))]=sha(path)
        checked.append({'id':rid,'errors':errs,'passed':not errs,'reconstruction':reconstruction})
        errors.extend(rid+': '+e for e in errs)
        print('AUDIT',len(checked),'/',len(doc['runs']),rid,'PASS' if not errs else errs,flush=True)
    formal_starts=[s for s in starts if s['budget_class']=='formal' and s['id'] in planned]
    if counts!={'development':10,'formal':173}:errors.append('total budget differs from10/173')
    if len(formal_starts)!=11:errors.append('continuation v2 starts not11')
    if sha(formal/'searches-sealed-before-reference.json')!=sha(ROOT/'data/p9-20261024-formal/searches-sealed-before-reference.json'):errors.append('sealed search copy changed')
    if len(formal_starts)!=len(doc['runs']):errors.append('started attempts missing from aggregate; inspect unfinished/failed attempt')
    result={'status':'PASS' if not errors else 'FAIL','execution_status':doc['status'],'counts':counts,
            'runs_checked':len(checked),'runs':checked,'errors':errors,'input_hashes':inputs,
            'raw_remote_complete':False,'freeze_commit':receipt['commit'],'execution_epoch':'continuation-v2','epoch_started':len(formal_starts),'original_infra_missing':1,'prior162_frozen_analysis_exception':1,'original_compatible_n':sum(r.get('measurement_kind')=='ORIGINAL_COMPATIBLE' for r in doc['runs']),'new_open_gap_censored_n':sum(r.get('measurement_kind')=='OPEN_GAP_CENSORED' for r in doc['runs']),'overall_acceptance':'NO_OVERALL_PASS; original epoch interrupted'}
    write(out/'audit.json',result);print(result['status'],counts,flush=True);return bool(errors)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('preparation',type=Path);p.add_argument('--frozen',type=Path,required=True)
    p.add_argument('--formal',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    return audit(a.preparation.resolve(),a.frozen.resolve(),a.formal.resolve(),a.output.resolve())


if __name__=='__main__':raise SystemExit(main())

#!/usr/bin/env python3
"""Finalize engineering observation gate. This is never a theory/model PASS."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import datetime

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from p9_model import sha,write


def main():
    root=ROOT/'data/p11-20261025-development';prep=ROOT/'data/p11-20261025-preparation'
    out=prep/'observation-acceptance.json'
    if out.exists():raise FileExistsError('acceptance receipt is immutable; create a separately versioned output if needed')
    read=lambda name,file:json.loads((root/name/file).read_text())
    off=read('dev10-complete-timing-off','observation/observation.json')
    on=read('dev11-complete-timing-on','observation/observation.json')
    sync=read('dev11-complete-timing-on','synchronization/synchronization.json')
    target=read('dev11-complete-timing-on','target-replay/target-replay.json')
    old=read('dev01-old-baseline','observation/observation.json');disabled=read('dev02-new-disabled','observation/observation.json')
    first=read('dev04-observe-anchor-v2','observation/observation.json')
    binary_off=read('dev10-complete-timing-off','run/metadata.json')['binary_sha256']
    binary_on=read('dev11-complete-timing-on','run/metadata.json')['binary_sha256']
    names=['dev09-final-protocol','dev10-complete-timing-off','dev11-complete-timing-on']
    allocation={name:int(subprocess.check_output(['du','-sB1',str(root/name)],text=True).split()[0]) for name in names}
    # Includes explicit extra allowance for synchronized data, model traces and score tables.
    per=int(max(allocation.values())*1.25)+10_000_000;reserve=2_000_000_000;free=shutil.disk_usage(ROOT).free
    ledger=[json.loads(x) for x in (prep/'attempts.jsonl').read_text().splitlines()]
    starts=[x for x in ledger if x['event']=='START_INTENT'];dev=sum(x['budget_class']=='development' for x in starts)
    gates={'budget':dev==11 and len(starts)==11,
        'same_binary_final_off_on':binary_off==binary_on,'all_observation_gates':on['status']=='PASS',
        'full_cycle_timing':on['baseline']['whole_observation_cycle_us']['p99']<2500 and off['baseline']['whole_observation_cycle_us']['p99']<2500,
        'whole_publication_measured':on['baseline']['p11_publication_ns']['max']>0,
        'sidecar_complete':sync['publish_plus_sidecar_us']['n']==sync['sends']-1,
        'send_read_intervals':sync['status']=='PASS' and sync['sends']==sync['matched_valid_reads'],
        'target_module_latest':target['status']=='PASS',
        'target_RTGT':read('dev06-long-capture','target-replay/target-replay.json')['status']=='PASS',
        'target_RREC':read('dev07-recovery','target-replay/target-replay.json')['status']=='PASS',
        'normal_path':read('dev08-normal','observation/observation.json')['status']=='PASS',
        'old_behavior_equivalence':abs(old['baseline']['max_tilt_deg_whole_log']-disabled['baseline']['max_tilt_deg_whole_log'])<=2.5 and abs(old['baseline']['max_tilt_deg_whole_log']-first['baseline']['max_tilt_deg_whole_log'])<=2.5,
        'current_off_on_equivalence':abs(on['baseline']['max_tilt_deg_whole_log']-off['baseline']['max_tilt_deg_whole_log'])<=2.5,
        'no_missed_duplicate_regressed':all(on['baseline'][k]==0 and off['baseline'][k]==0 for k in ['sample_missed_total','duplicate_total','regressed_total']),
        'capacity_72_with_reserve':free>=reserve+72*per}
    for name in names:
        run=root/name/'run';f=run/'flight.ulg';original=next(run.glob('rootfs/log/**/*.ulg'))
        gates[name+'_hardlink_preserved']=f.stat().st_ino==original.stat().st_ino and sha(f)==sha(original)
    report={'schema':'p11-observation-acceptance-1','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'status':'PASS' if all(gates.values()) else 'FAIL','gates':gates,'development_starts':dev,'formal_starts':0,
        'final_binary_sha256':binary_on,'observation':on,'off_baseline':off['baseline'],'synchronization':sync,
        'storage':{'measured_physical_allocated_bytes':allocation,'per_future_attempt_bound_bytes':per,'reserve_bytes':reserve,
            'available_bytes':free,'required_72_bytes':reserve+72*per,'check_before_every_attempt':True,
            'mechanism':'new hardlink AFTER every owned process exits; both raw paths survive; no historical files deleted/overwritten'},
        'failures_retained':{'dev03':'invalid JSON sidecar exception, pre-stream truncated, no task acceptance, counted',
            'dev05':'normal frozen safety-envelope abort; infra/output chain pass; counted censored flight failure, not protection anomaly'},
        'phase':'measured send/read and native query intervals retained; 2ms intent is not claimed exact phase; formal 0/2/6ms variants are evaluated by achieved distributions',
        'scope':'engineering observation gate on these development runs; finite overhead/equivalence evidence, not universal scheduling bound, model accuracy or theory admission',
        'no_more_development_planned':True,'remaining_development_cap':12-dev,'formal_plan_rows':72,
        'source_receipts':{str(p.relative_to(ROOT)):sha(p) for p in [root/'dev11-complete-timing-on/observation/observation.json',root/'dev11-complete-timing-on/synchronization/synchronization.json',root/'dev11-complete-timing-on/target-replay/target-replay.json']}}
    write(out,report);print(json.dumps({'status':report['status'],'gates':gates,'storage':report['storage']}))
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())

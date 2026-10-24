#!/usr/bin/env python3
"""Read-only diagnostic for attempt162, never replacement of its frozen failure.
Uses native last reception before the first timeout capture ONLY in this new
post-flight diagnostic. No flights, fitting, acceptance, or overwritten files.
"""
import json,sys,types
from pathlib import Path
import numpy as np
from pyulog import ULog
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from p9_model import sha,write
from p5_metrics import receptions
import p7_metrics,p7_export,p2_batch

def main():
    out=Path(__file__).resolve().parent/'attempt162-diagnostic'
    out.mkdir(exist_ok=False)
    run=ROOT/'data/p9-20261024-continuation-v1-formal/D-07-P9-Z/run'
    u=ULog(str(run/'flight.ulg'),list(set(p7_export.TOPICS+['research_target'])))
    tables={d.name:d.data for d in u.data_list if d.multi_id==0}
    cfg=json.loads((run/'config.json').read_text())
    ev=[json.loads(x) for x in (run/'events.jsonl').read_text().splitlines()]
    base=json.loads((run/'p7-metrics.json').read_text())
    rec=np.asarray(receptions(tables['raptor_status'],tables['trajectory_setpoint']))
    target=tables['research_target'];profile_start=base['times_px4_us']['profile_start']
    ix=np.flatnonzero((target['kind']==1)&(target['activation']==0)&(target['timestamp']>profile_start))
    # T_CAPTURE is imported from the exact frozen analyzer, not a guessed label.
    from p5_metrics import T_CAPTURE
    ix=np.flatnonzero((target['kind']==T_CAPTURE)&(target['activation']==0)&(target['timestamp']>profile_start))
    if len(ix)!=1:raise RuntimeError('expected exactly one first in-flight capture for this open-gap diagnostic')
    cap=int(target['timestamp'][ix[0]]);last=int(rec[rec<cap][-1]);after=rec[rec>last]
    if len(after):raise RuntimeError('open-gap claim contradicted by later reception')
    if not .2<=(cap-last)/1e6<=.216:raise RuntimeError('timeout semantics inconsistent')
    if not any(e['event']=='p5_gap_started' and e['index']==0 for e in ev):raise RuntimeError('first gap never started')
    source=ROOT/'tools/p9_metrics.py';s=source.read_text()
    old="if first is None:raise ValueError('no observed first interruption; fixed-window origin cannot be established')"
    if s.count(old)!=1:raise RuntimeError('frozen source anchor mismatch')
    module=types.ModuleType('postflight_open_gap_diagnostic');module.__file__=str(source)
    exec(compile(s.replace(old,'if first is None:first='+str(last)),str(source),'exec'),module.__dict__)
    numerical=module.analyze(run)
    numerical.update(status='POSTFLIGHT_DIAGNOSTIC_ONLY_NOT_FROZEN_ACCEPTANCE',open_gap=True,
        frozen_analyzer_outcome='EXCEPTION; original run files and aggregate unchanged',
        diagnostic_anchor={'last_external_reception_native_us':last,'timeout_capture_native_us':cap,'timeout_delay_s':(cap-last)/1e6},
        scope='new read-only diagnostic version; these values do not repair missing frozen P9 result or change validation denominators')
    write(out/'p9-open-gap-diagnostic.json',numerical)
    rebuilt=p7_metrics.analyze(run);write(out/'p7-remeasured.json',rebuilt)
    reconstruction=p7_export.reconstruct(tables)['resid'];write(out/'policy-reconstruction.json',reconstruction)
    chain_errors,_=p2_batch.chain_errors(json.loads((run/'output-chain.json').read_text()),True)
    meta=json.loads((run/'metadata.json').read_text())
    write(out/'assessment.json',{'frozen_primary_outcome':base['flight_outcome'],
        'p7_raw_remeasurement_identical':rebuilt==base,'raw_ulog_hash_matches_metadata':meta['ulog_sha256']==sha(run/'flight.ulg'),
        'policy_reconstruction':reconstruction,'output_chain_errors':chain_errors,
        'runtime_safety_abort':True,'closed_gaps':0,'first_gap_started':True,'normal_process_cleanup':{e['name']:e['exit_code'] for e in ev if e['event']=='process_stopped'},
        'frozen_p9_measurement_valid':False,'counts_as_started':True,'rerun':False,
        'limit':'missing post-run host and candidate records; this diagnostic is not a completed protocol/acceptance result'})
    files=[source,Path(__file__).resolve()]+[run/n for n in ['flight.ulg','events.jsonl','p7-metrics.json','config.json','metadata.json','output-chain.json']]
    write(out/'input-manifest.json',{str(p.relative_to(ROOT)):sha(p) for p in files})
    write(out/'output-manifest.json',{str(p.relative_to(out)):sha(p) for p in out.iterdir() if p.is_file() and p.name!='output-manifest.json'})
    print(json.dumps({'last':last,'capture':cap,'diagnostic_peak':numerical['max_tilt_deg'],'observed_until_s':numerical['window_observed_s'],'p7_identical':rebuilt==base,'reconstruction':reconstruction,'chain_errors':chain_errors}))
if __name__=='__main__':main()

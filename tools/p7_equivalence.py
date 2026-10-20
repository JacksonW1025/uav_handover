#!/usr/bin/env python3
"""Check a finished P7 equivalence batch (new candidate: MC_RAPTOR_RREC, default 0) against P6 B1 (criteria pre-registered
in config/p7.json p7.equivalence).

The P6 B1 cells p5_gap v2.0-D0.4-A0 T0 and v2.0-D0.7-A0 T1a3 are flown 2 times each with config/p6.json and analysed by
the frozen p6_metrics. A run is equivalent when the batch checks passed (accepted, or a pre-registered flight failure with
sound infrastructure and evidence), its flight outcome equals the B1 run, |max tilt - B1| <= 2.5 deg (whole window, as
P6), and RREC = 0 behaves as in P6: MC_RAPTOR_RREC = 0 in the log, no research_recovery row, and every policy_input
reconstructed with the P6 target rules (tools/p6_export.reconstruct) with 0 components > 1e-4. Writes equivalence.json
(and diagnosis.json when not equivalent, with the pre-registered decision).
"""
import argparse,json
from pathlib import Path
from pyulog import ULog
import p6_export
ROOT=Path(__file__).resolve().parents[1]

def identity_rrec0(run):
    u=ULog(str(run/'flight.ulg'),p6_export.TOPICS+['research_recovery']);T={d.name:d.data for d in u.data_list if d.multi_id==0}
    values=dict(u.initial_parameters)
    for stamp,name,value in sorted(u.changed_parameters,key=lambda x:x[0]):values[name]=value
    R=p6_export.reconstruct(T)
    return {'MC_RAPTOR_RREC':values.get('MC_RAPTOR_RREC'),'research_recovery_rows':0 if 'research_recovery' not in T else int(len(T['research_recovery']['timestamp'])),
            'p6_reconstruction':R['resid']}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('batch',type=Path);p.add_argument('--config',default='config/p7.json');a=p.parse_args()
    batch=a.batch.resolve();spec=json.loads((ROOT/a.config).read_text())['p7']['equivalence'];tol=float(spec['max_tilt_tolerance_deg'])
    results=json.loads((batch/'results.json').read_text());ok=results.get('status')=='PASS' and bool(results.get('complete'));out=[]
    for r in results['runs']:
        key=f"{r['condition']}:{r['treatment']}";ref_dir=ROOT/spec['reference'][key];run=ROOT/r['directory']
        ref=json.loads((ref_dir/'p6-metrics.json').read_text());row={'id':r['id'],'condition':r['condition'],'treatment':r['treatment'],'reference_run':spec['reference'][key],'problems':[]}
        if not (r.get('accepted') or r.get('flight_failure')):row['problems'].append('batch checks not passed')
        m=json.loads((run/'p6-metrics.json').read_text()) if (run/'p6-metrics.json').exists() else {}
        if m.get('status')!='MEASURED':row['problems'].append('p6_metrics not MEASURED')
        row['outcome']=(m.get('flight_outcome') or {}).get('outcome');row['reference_outcome']=ref['flight_outcome']['outcome']
        row['max_tilt_deg']=(m.get('whole') or {}).get('max_tilt_deg');row['reference_max_tilt_deg']=ref['whole']['max_tilt_deg']
        if row['outcome']!=row['reference_outcome']:row['problems'].append('flight outcome differs from P6 B1')
        if row['max_tilt_deg'] is None or abs(row['max_tilt_deg']-row['reference_max_tilt_deg'])>tol:row['problems'].append(f'max tilt differs from P6 B1 by more than {tol} deg')
        row['max_tilt_difference_deg']=None if row['max_tilt_deg'] is None else row['max_tilt_deg']-row['reference_max_tilt_deg']
        if (run/'flight.ulg').exists():
            idn=identity_rrec0(run);row['rrec0_identity']=idn
            if idn['MC_RAPTOR_RREC'] is None or abs(float(idn['MC_RAPTOR_RREC']))>1e-9:row['problems'].append('MC_RAPTOR_RREC not 0 in the log')
            if idn['research_recovery_rows']:row['problems'].append('research_recovery rows with RREC = 0')
            if idn['p6_reconstruction']['components_over_1e-4']:row['problems'].append('policy_input not reproduced by the P6 target rules')
        else:row['problems'].append('no flight log')
        row['equivalent']=not row['problems'];ok=ok and row['equivalent'];out.append(row)
    result={'batch':str(batch.relative_to(ROOT)),'criteria':spec,'runs':out,'equivalent':bool(ok)}
    if not ok:
        # Pre-registered decision (p7.equivalence.rule): only the outcome of the boundary cell T1a3 D0.7 differs, with its
        # max tilt inside the P6 B1/B3 range of that cell +- 2.5 deg -> continue, P7 results conditional on the user.
        b3=[44.9,45.1,46.4]
        only_cell=all(r['equivalent'] or (r['condition']=='v2.0-D0.7-A0' and r['treatment']=='T1a3' and r['problems']==['flight outcome differs from P6 B1']
                     and r['max_tilt_deg'] is not None and min(b3)-tol<=r['max_tilt_deg']<=max(b3)+tol) for r in out) and results.get('status')=='PASS'
        result['decision']=('CONTINUE_CONDITIONAL: only the outcome of the boundary cell T1a3 v2.0 D0.7 differs (P6 B1+B3 of this cell: F 46.4, S 44.9, F 45.1 deg); the formal P7 batches run and their results are conditional on the user accepting this equivalence'
                            if only_cell else 'STOP: a difference other than the pre-registered boundary-cell flip; P7 stops for diagnosis')
        (batch/'diagnosis.json').write_text(json.dumps({'equivalent':False,'decision':result['decision'],'runs':[{k:r[k] for k in ['id','outcome','reference_outcome','max_tilt_deg','reference_max_tilt_deg','problems']} for r in out]},indent=2,ensure_ascii=False)+'\n')
    (batch/'equivalence.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n');print('equivalent',ok,result.get('decision',''))
    for r in out:print(r['id'],r['equivalent'],r['outcome'],r['max_tilt_deg'],r['problems'])
    return 0 if ok else 1
if __name__=='__main__':raise SystemExit(main())

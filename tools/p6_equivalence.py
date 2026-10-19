#!/usr/bin/env python3
"""Check a finished P6 equivalence batch (new candidate: p6_ident, explicit windows, generated conditions; PX4 unchanged)
against P5 (criteria pre-registered in config/p6.json p6.equivalence).

The P5 conditions p5_gap D0.7-A0 T1 and D1.0-A0 T1a3 are flown 2 times each with config/p5.json and analysed by the frozen
p5_metrics. A run is equivalent when the batch checks passed (accepted, or a pre-registered flight failure with sound
infrastructure and evidence), its flight outcome equals the P5 batch-e2 run of the same condition and |whole-window max
tilt - P5| <= 2.5 deg. Reads run evidence only; writes equivalence.json (and diagnosis.json when not equivalent).
"""
import argparse,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('batch',type=Path);p.add_argument('--config',default='config/p6.json');a=p.parse_args()
    batch=a.batch.resolve();spec=json.loads((ROOT/a.config).read_text())['p6']['equivalence'];tol=float(spec['max_tilt_tolerance_deg'])
    results=json.loads((batch/'results.json').read_text());ok=results.get('status')=='PASS' and bool(results.get('complete'));out=[]
    for r in results['runs']:
        key=f"{r['condition']}:{r['treatment']}";ref_dir=ROOT/spec['reference'][key];run=ROOT/r['directory']
        ref=json.loads((ref_dir/'p5-metrics.json').read_text());row={'id':r['id'],'condition':r['condition'],'treatment':r['treatment'],'reference_run':spec['reference'][key],'problems':[]}
        if not (r.get('accepted') or r.get('flight_failure')):row['problems'].append('batch checks not passed')
        m=json.loads((run/'p5-metrics.json').read_text()) if (run/'p5-metrics.json').exists() else {}
        if m.get('status')!='MEASURED':row['problems'].append('p5_metrics not MEASURED')
        row['outcome']=(m.get('flight_outcome') or {}).get('outcome');row['reference_outcome']=ref['flight_outcome']['outcome']
        row['max_tilt_deg']=(m.get('whole') or {}).get('max_tilt_deg');row['reference_max_tilt_deg']=ref['whole']['max_tilt_deg']
        if row['outcome']!=row['reference_outcome']:row['problems'].append('flight outcome differs from P5')
        if row['max_tilt_deg'] is None or abs(row['max_tilt_deg']-row['reference_max_tilt_deg'])>tol:row['problems'].append(f'max tilt differs from P5 by more than {tol} deg')
        row['max_tilt_difference_deg']=None if row['max_tilt_deg'] is None else row['max_tilt_deg']-row['reference_max_tilt_deg']
        row['equivalent']=not row['problems'];ok=ok and row['equivalent'];out.append(row)
    result={'batch':str(batch.relative_to(ROOT)),'criteria':spec,'runs':out,'equivalent':bool(ok)}
    (batch/'equivalence.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n');print('equivalent',ok)
    for r in out:print(r['id'],r['equivalent'],r['outcome'],r['max_tilt_deg'],r['problems'])
    return 0 if ok else 1
if __name__=='__main__':raise SystemExit(main())

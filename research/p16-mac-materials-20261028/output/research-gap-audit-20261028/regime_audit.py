"""Retrospective stress test of a necessary regime condition, not a new-method win.

All choices use the prefix through capture 3. Capture 4 is outcome-only.
The 27 prefixes are treated as already available; this is not a flight-budget audit.
"""
from pathlib import Path
import csv, gzip, json
import numpy as np

ROOT = Path(__file__).resolve().parent

def main():
    rows = []
    prior = json.load(open(ROOT / 'cycle_audit.json'))
    measured = {r['id']: r for r in prior['rows']}
    for d in sorted((ROOT / 'upstream/export').glob('p7-20261020-a-q4-*')):
        summary = json.load(open(d / 'summary.json'))
        raw = list(csv.DictReader(gzip.open(d / 'trace.csv.gz', 'rt')))
        t = np.array([float(r['t_s']) for r in raw])
        z = np.array([float(r['ep_z']) for r in raw])
        mode = np.array([r['target_mode'] for r in raw])
        captures = [e for e in summary['events'] if e['event'] == 'capture' and 0 <= e['gap'] < 4]
        stats = []
        for i in range(3):
            external = (t >= captures[i]['t_s']) & (t < captures[i+1]['t_s']) & (mode == 'external')
            v = z[external]
            stats.append(dict(rows=len(v), min_error=float(v.min()) if len(v) else None,
                downward_saturated_fraction=float((v >= .5).mean()) if len(v) else None,
                all_downward_saturated=bool(len(v) and (v >= .5).all())))
        r = measured[d.name]
        rows.append(dict(id=d.name, condition=summary['condition'], treatment=summary['treatment'],
            cycles=stats, observed_previous_increment=r['cycles'][1]['loss'],
            outcome_next_increment=r['cycles'][2]['loss']))
    cheap = sorted(rows, key=lambda r: (-r['observed_previous_increment'], r['id']))[:3]
    gate = [r for r in rows if r['cycles'][1]['all_downward_saturated']]
    assert len(gate) == 3
    def score(selected):
        return dict(ids=[r['id'] for r in selected],
            positive_next_increment=sum(r['outcome_next_increment'] > 0 for r in selected),
            mean_next_increment=float(np.mean([r['outcome_next_increment'] for r in selected])))
    result = dict(sampled_external_branch_counts_by_cycle=[sum(r['cycles'][i]['all_downward_saturated'] for r in rows) for i in range(3)],
        total_sequences=len(rows), rows=rows,
        prefix_only_stress_probe=dict(cheap_previous_increment_top3=score(cheap), saturation_gate_three=score(gate),
            interpretation='Saturation is a necessary condition of the proposed invariance regime, not a sufficient recurrence/drift criterion. Using it alone does not improve continuation choice. This does not evaluate an implemented full cycle-closure method.'),
        limitations=['Retrospective analysis; all outcomes were inspected before this hypothesis.',
            '27 prefixes are assumed already available; this is not a total test-cost or original task-failure-yield comparison.',
            'Recorded export samples only; hidden execution and recurrent state missing.',
            'No comparison against full-information grey-box forecast is possible on these reduced P7 exports without reconstructing unavailable initial states.'],
        new_flights=0, new_SITL=0, Thor_used=False)
    (ROOT / 'source_regime_audit.json').write_text(json.dumps(result, indent=2))
    print(json.dumps({k:v for k,v in result.items() if k != 'rows'}, indent=2))

if __name__ == '__main__':
    main()

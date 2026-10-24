#!/usr/bin/env python3
"""Read existing P9 small evidence; never reanalyse/overwrite historical runs."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INPUTS = [
    'CLAUDE.md', 'tools/p9_model.py', 'tools/p9_predict.py',
    'tools/p9_search.py', 'tools/p9_plan.py', 'tools/p9_campaign.py',
    'tools/p9_run.py', 'tools/p9_metrics.py', 'tools/p9_audit.py',
    'tools/run_experiment.py', 'tools/apply_research.py',
    'research/state/TargetProfile.hpp', 'research/state/RecoveryTarget.hpp',
    'config/p9.json', 'docs/THOR_P9_PLAN.md', 'docs/THOR_P9_FINAL_REPORT.md',
    'data/p9-20261024-freeze/model.json', 'data/p9-20261024-freeze/manifest.json',
    'data/p9-20261024-continuation-v1-formal/diagnosis.json',
    'data/p9-20261024-continuation-v2-formal/diagnosis.json',
    'data/p9-20261024-continuation-v3-formal/diagnosis.json',
    'data/p9-20261024-continuation-v4-publication/execution-deviation-review.json',
    'data/p9-20261024-continuation-v4-report/prediction-measurement-ledger.csv',
    'data/p9-20261024-continuation-v4-report/reference-grid.json',
    'data/p9-20261024-continuation-v4-delivery/169-extra-replay.json',
    'data/p9-20261024-continuation-v4-postanalysis/event-diagnostics.csv',
    'data/p9-20261024-continuation-v4-postanalysis/C-condition-seed-variation.json',
    'data/p9-20261024-continuation-v4-delivery/final-disclosure/all-173-starts.csv',
]


def audit():
    def read(name):
        return ROOT/name
    # Select by explicit path to keep input ordering from silently changing data.
    ledger = list(csv.DictReader(read('data/p9-20261024-continuation-v4-report/prediction-measurement-ledger.csv').open()))
    b = [r for r in ledger if r['stage'] == 'B']
    dangerous = [r for r in b if r['danger_underestimated'] == 'True']
    events = list(csv.DictReader(read('data/p9-20261024-continuation-v4-postanalysis/event-diagnostics.csv').open()))
    flips = json.loads(read('data/p9-20261024-continuation-v4-postanalysis/C-condition-seed-variation.json').read_text())
    mixed = [r for r in flips['rows'] if r['mixed_known_binary_outcomes']]
    extra = json.loads(read('data/p9-20261024-continuation-v4-delivery/169-extra-replay.json').read_text())
    assert len(ledger) == 169 and len(b) == 48 and len(dangerous) == 6
    joins = []
    for row in dangerous:
        observed = [e for e in events if e['id'] == row['id']]
        joins.append({k: row[k] for k in ['id', 'sim_seed', 'predicted_tilt_deg',
                      'observed_tilt_deg', 'full_horizon_comparable', 'censored']} |
                     {'observed_event_diagnostics': observed,
                      'attribution': 'model/clock/seed confounded; no causal partition or strict error bound'})
    delays = [float(e['capture_delay_after_last_read_s']) for e in events
              if e['capture_delay_after_last_read_s']]
    return {'status': 'P9_SMALL_EVIDENCE_RECHECKED',
            'all_history_is_seen_development': True,
            'formal_starts': 173, 'main_measurements': len(ledger),
            'exceptions': {'102': 'PERMANENT_MISSING', '162': 'POSTHOC_DIAGNOSTIC_ONLY',
                           '164': 'ORIGINAL_EVIDENCE_REJECTED', '169': 'EXTRA_RECOVERY_REJECTED',
                           'v4': 'UNAPPROVED_POST_STOP_CONTINUATION_DEVIATION_RETAINED'},
            'B_n': len(b), 'B_dangerous_point_underestimates': joins,
            'mixed_seed_conditions': mixed,
            'capture_delay_after_last_read_s': {'n': len(delays), 'min': min(delays),
                                               'max': max(delays), 'counts': dict(Counter(delays))},
            'extra_recovery_169': extra,
            'extra_recovery_169_step_average_s': (extra['extra_end']-extra['extra_start'])/1e6/extra['extra_steps'],
            'causal_limits': [
                'q is a geometric attitude proxy; vdot=q omits thrust/drag/height/GRU',
                'nominal 8 ms/20 ms publication time is not measured native read/sample time',
                'actual runner uses elapsed monotonic time; native controller clocks read/capture',
                'seed variation includes changed scheduling and hidden state; not proven IID noise',
                '169 replay verifies extra target exposure, not the cause of its initial stale/fresh transition',
                'no post-hoc fit or residual is promoted to a universal envelope'],
            'inputs': {name: hashlib.sha256(read(name).read_bytes()).hexdigest() for name in INPUTS}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    out = parser.parse_args().output
    out.mkdir(parents=True, exist_ok=False)
    result = audit()
    (out/'historical-evidence.json').write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n')
    print(json.dumps({'status': result['status'], 'dangerous_B': len(result['B_dangerous_point_underestimates']),
                      'mixed_seed_conditions': len(result['mixed_seed_conditions'])}))

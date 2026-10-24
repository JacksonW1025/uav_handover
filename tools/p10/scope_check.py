#!/usr/bin/env python3
"""Necessary-domain check of already frozen P9 forecasts; no new prediction.

An outside result means UNKNOWN, never a failure label. Passing necessary
conditions is not an initial-history, prefix or error-envelope certificate.
"""
import argparse
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def check():
    source = ROOT/'data/p9-20261024-freeze/predictions.json'
    rows = json.loads(source.read_text(), parse_float=F)['predictions']
    result = []
    for row in rows:
        violations = []
        for e in row['events']:
            ep = [p-r for p, r in zip(e['position_flu_m'], e['target_position_flu_m'])]
            dv = [v-r for v, r in zip(e['velocity_flu_m_s'], e['target_velocity_flu_m_s'])]
            reasons = []
            if any(x*x > F(49, 2000) for x in ep):
                reasons.append('CURRENT_POSITION_EXCEEDS_NECESSARY_ELLIPSOID_BOUND')
            if any(x*x > F(1029, 10000) for x in dv):
                reasons.append('CURRENT_VELOCITY_EXCEEDS_NECESSARY_ELLIPSOID_BOUND')
            if sum(q*q for q in e['q_flu_m_s2']) > F(3283, 100):
                reasons.append('CURRENT_Q_EXCEEDS_NECESSARY_ELLIPSOID_BOUND')
            if reasons:
                violations.append({'event': e['event'], 't_s': str(e['t_s']), 'reasons': reasons})
        result.append({'id': row['id'], 'stage': row['stage'], 'treatment': row['treatment'],
                       'necessary_domain_violations': violations,
                       'decision': 'UNKNOWN_OUTSIDE_LOCAL_CERTIFICATE' if violations else
                                   'UNKNOWN_PREFIX_HISTORY_AND_ERROR_BOUNDS_UNVERIFIED'})
    return {'status': 'NECESSARY_SCOPE_ONLY_NO_SAFETY_CLASSIFICATION',
            'source': str(source.relative_to(ROOT)), 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
            'n_frozen_forecasts': len(rows),
            'n_with_necessary_violation': sum(bool(r['necessary_domain_violations']) for r in result),
            'n_real_safety_certified': 0, 'rows': result}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('output', type=Path)
    out = p.parse_args().output
    out.mkdir(parents=True, exist_ok=False)
    result = check()
    (out/'scope-check.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: result[k] for k in ['n_frozen_forecasts', 'n_with_necessary_violation', 'n_real_safety_certified']}))

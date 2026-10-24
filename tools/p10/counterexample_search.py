#!/usr/bin/env python3
"""Finite exact counterexample search. A found witness refutes a claim;
failure to find one is NEVER a region proof. No flight or historical rewrites.
"""
import argparse
from fractions import Fraction as F
import json
from pathlib import Path

from verify import N, ROOT, mv, quadratic, rho_bounds, transition


def search():
    cert = json.loads((ROOT/'data/p10-20261024-a/construction/certificate.json').read_text())
    model = json.loads((ROOT/'data/p9-20261024-freeze/model.json').read_text(), parse_float=F)
    p = [[F(x, cert['P_scale']) for x in row] for row in cert['axes'][0]['P_integer']]
    grid = [F(k, 10) for k in range(-2, 3)]
    found = []
    # Fixed target: E_dot = kp*clip(e)*d + d*q, with q a state.
    for d in grid:
        for q in grid:
            x = [F(0), d, q]+[F(0)]*(N-3)
            derivative = d*q
            if derivative > 0 and quadratic(p, x) < 49:
                found.append({'e': '0', 'd': str(d), 'q': str(q),
                              'V': str(quadratic(p, x)), 'P9_E_dot': str(derivative)})
    assert found
    a = transition(model['kp'][0], model['kv'][0], rho_bounds()[0])
    history = [F(0)]*N
    history[-2:] = [F(1, 10), F(1, 5)]
    assert quadratic(p, history) < 49
    difference = mv(a, history)[2]
    assert difference != 0
    # Fixed information/pre-state and finite target jump range: no outcomes.
    refused = []
    for i in range(101):
        alpha = F(i, 100)
        j = [-alpha/5, -alpha/5]+[F(0)]*(N-2)
        value = quadratic(p, j)
        if value >= (7-F(1, 10)-F(1, 20))**2:
            refused.append({'alpha': str(alpha), 'event_V': str(value),
                            'decision': 'UNKNOWN_TEST_REQUIRED_NOT_PROVEN_FAILURE'})
    return {'status': 'EXACT_WITNESSES_FOUND',
            'E_search_grid': 'e=0; d,q in {-0.2,-0.1,0,0.1,0.2}; require V<49',
            'E_candidates': 25, 'E_positive_inside_domain': found,
            'same_current_history_counterexample': {'history_V': str(quadratic(p, history)),
                 'history_oldest_e_d': ['1/10', '1/5'], 'next_q_difference': str(difference)},
            'jump_search': {'alpha_grid': '0:.01:1', 'n': 101,
                            'first_refused': refused[0], 'refused_n': len(refused)},
            'limit': 'finite search finds counterexamples only; NOT a regional proof, failure classifier or performance comparison'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    out = parser.parse_args().output
    out.mkdir(parents=True, exist_ok=False)
    result = search()
    (out/'counterexamples.json').write_text(json.dumps(result, indent=2)+'\n')
    print(result['status'])

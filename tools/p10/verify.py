#!/usr/bin/env python3
"""Independent exact-rational verifier; Python standard library ONLY.

Does not import the constructor, scipy, numpy, P9 prediction or any flight tool.
All proof decisions use Fraction / integers, no floating point eigenvalue tests.
Output must be new. An exception stops without retry or alternate acceptance.
"""
import argparse
from fractions import Fraction as F
import hashlib
import json
from math import factorial, lcm
from pathlib import Path
import time

if not __debug__:
    raise RuntimeError('Exact checker requires assertions enabled; do not use python -O')

ROOT = Path(__file__).resolve().parents[2]
N = 25
H = F(1, 125)


def zeros():
    return [[F(0) for _ in range(N)] for _ in range(N)]


def quadratic(p, x):
    return sum(x[i]*p[i][j]*x[j] for i in range(N) for j in range(N))


def mv(a, x):
    return [sum(v*z for v, z in zip(row, x)) for row in a]


def pd(a):
    """Sylvester criterion via fraction-free Bareiss, no pivot permutation.

    Every returned positive pivot is the corresponding leading principal
    determinant. Integer divisions are checked, so no roundoff is hidden.
    """
    assert all(a[i][j] == a[j][i] for i in range(N) for j in range(N))
    den = lcm(*(x.denominator for row in a for x in row))
    b = [[int(x*den) for x in row] for row in a]
    previous = 1
    signs = []
    for k in range(N):
        pivot = b[k][k]
        if pivot <= 0:
            raise ValueError(f'nonpositive leading determinant {k}')
        signs.append(True)
        if k == N-1:
            break
        for i in range(k+1, N):
            for j in range(k+1, N):
                val = b[i][j]*pivot-b[i][k]*b[k][j]
                if val % previous:
                    raise ValueError('non-exact Bareiss division')
                b[i][j] = val//previous
        previous = pivot
    return len(signs)


def transition(kp, kv, rho):
    # Re-derived directly from q+, v+ and p+ equations, not constructor code.
    a = zeros()
    for col in range(N):
        q1 = (rho if col == 2 else F(0))
        if col == 23:
            q1 -= (1-rho)*kp
        if col == 24:
            q1 -= (1-rho)*kv
        a[2][col] = q1
        qsum = q1+(1 if col == 2 else 0)
        a[1][col] = (1 if col == 1 else 0)+H*qsum/2
        a[0][col] = (1 if col == 0 else 0)+(H if col == 1 else 0)+H*H*qsum/4
    a[3][0] = a[4][1] = F(1)
    for row in range(5, N):
        a[row][row-2] = F(1)
    return a


def rho_bounds():
    # Alternating Taylor series for exp(-1/10), decreasing term magnitudes.
    lo = sum((-F(1, 10))**i/factorial(i) for i in range(20))
    hi = sum((-F(1, 10))**i/factorial(i) for i in range(21))
    assert 0 < lo < hi < 1
    return lo, hi


def residual_margin(p, a):
    # Sparse multiplication of A'PA; Gershgorin proves Q >= (1/2) I.
    cols = [[(i, a[i][j]) for i in range(N) if a[i][j]] for j in range(N)]
    q = [[p[i][j]-sum(u*p[k][l]*v for k, u in cols[i] for l, v in cols[j])
          for j in range(N)] for i in range(N)]
    margin = min(q[i][i]-F(1, 2)-sum(abs(q[i][j]) for j in range(N) if i != j)
                 for i in range(N))
    assert margin > 0, 'Lyapunov dissipation not verified'
    return margin


def target(k):
    # Independent rational transcription of TargetProfile RTGT2, RTDEC2.
    t = F(k, 125)
    if k < 5:
        return F(9, 5)*t-t*t, F(9, 5)-2*t
    return F(9, 5)*F((2*k)//5, 50), F(9, 5)


def verify(path):
    started = time.perf_counter()
    doc = json.loads(path.read_text())
    assert doc['schema'] == 'p10-a-local-delay-certificate-1'
    assert doc['P_scale'] == 10**10 and doc['state_scale'] == 10**12
    assert doc['initial_P_radius'] == '1/10'
    assert doc['per_step_disturbance_P_radius'] == '1/10000'
    assert doc['resume_disturbance_P_radius'] == '1/20'
    model_path = ROOT/'data/p9-20261024-freeze/model.json'
    assert doc['model_path'] == str(model_path.relative_to(ROOT))
    assert hashlib.sha256(model_path.read_bytes()).hexdigest() == doc['model_sha256']
    assert doc['model_sha256'] == '474509c9192ce270b897fdc1cbd69796be180c6a5a73b9f091678dbbca256b4a'
    model = json.loads(model_path.read_text(), parse_float=F)
    assert (model['delay_s'], model['tau_s']) == (F(11, 125), F(2, 25))
    assert model['position_clip_m'] == F(1, 2) and model['velocity_clip_m_s'] == 1
    rho = rho_bounds()
    evidence = []
    ps, aa, centers = [], [], []
    coord = [F(1, 2000), F(21, 10000), F(67, 100)]
    for axis, item in enumerate(doc['axes']):
        assert len(item['P_integer']) == N and all(len(r) == N for r in item['P_integer'])
        p = [[F(x, doc['P_scale']) for x in row] for row in item['P_integer']]
        lower = [row[:] for row in p]
        for i in range(N):
            lower[i][i] -= F(1, 2)
        pd(lower)  # (1/2)I < P
        upper = max(sum(abs(x) for x in row) for row in p)
        assert upper < 10000
        # Cauchy-Schwarz output constants are certified by rank-one LMIs.
        for i, c in enumerate(coord):
            rank = [row[:] for row in p]
            rank[i][i] -= 1/c
            pd(rank)  # P > e_i e_i' / c => |x_i|^2 < c V(x)
        a = [transition(model['kp'][axis], model['kv'][axis], r) for r in rho]
        margins = [residual_margin(p, x) for x in a]
        ps.append(p)
        aa.append(a)
        raw = item['center_integer']
        assert len(raw) == 251 and all(len(r) == N for r in raw)
        cc = [[F(x, doc['state_scale']) for x in row] for row in raw]
        assert all(x == 0 for x in cc[0])
        centers.append(cc)
        evidence.append({'axis': axis, 'positive_leading_minors_per_LMI': N,
                         'exact_LMIs_checked': 4, 'P_upper_row_sum': str(upper),
                         'dissipation_gershgorin_margins': [str(x) for x in margins]})
    assert len(ps) == 2
    max_v = F(0)
    max_round = F(0)
    minimum_slack = F(1000)
    # Radius covers every initial history in the 50-D P-ball, every bounded
    # additive model input at every tick, and uncertain resume input.
    radius = F(1, 10)
    for k in range(251):
        cv = sum(quadratic(p, cc[k]) for p, cc in zip(ps, centers))
        max_v = max(max_v, cv)
        slack = (7-radius)**2-cv  # sufficient sqrt(Vcenter)+radius <= 7
        assert slack > 0, f'prefix leaves certified domain at {k}'
        minimum_slack = min(minimum_slack, slack)
        if k == 250:
            break
        err_sq = [F(0), F(0)]
        for axis in range(2):
            rp, rv = target(k) if axis == 0 else (F(0), F(0))
            rn, vn = target(k+1) if axis == 0 else (F(0), F(0))
            b = [H*rv-rn+rp, rv-vn]+[F(0)]*(N-2)
            for endpoint in range(2):
                predicted = mv(aa[axis][endpoint], centers[axis][k])
                residual = [centers[axis][k+1][i]-predicted[i]-b[i] for i in range(N)]
                err_sq[axis] = max(err_sq[axis], sum(x*x for x in residual))
        # Convexity extends endpoint checks to every rho in its interval.
        residual_p_sq_upper = 10000*sum(err_sq)
        assert residual_p_sq_upper <= F(1, 10**12), 'center rounding exceeds 1e-6 P-norm'
        max_round = max(max_round, residual_p_sq_upper)
        radius += F(1, 1000000)+F(1, 10000)
        if k+1 == 5:
            radius += F(1, 20)
    # Initial history clipping: P > .5 I and radius .1 -> all coordinates < .15.
    assert 2*F(1, 10)**2 < F(1, 2)**2
    # Current bounds and tilt proxy between ALL samples, via exponential q arc.
    assert coord[0]*49 < F(1, 2)**2 and coord[1]*49 < 1
    assert coord[2]*49 < F('9.80665')**2
    # Constraint actually chooses a target-jump attenuation range, not ranking.
    jumps = []
    for alpha in [F(1, 10), F(1)]:
        j = [-alpha/5, -alpha/5]+[F(0)]*(N-2)
        v = quadratic(ps[0], j)
        admissible = v < (7-F(1, 10)-F(1, 20))**2
        jumps.append({'alpha': str(alpha), 'post_event_center_V': str(v),
                      'decision': 'PROXY_ADMISSIBLE' if admissible else 'UNKNOWN_TEST_REQUIRED'})
    assert jumps[0]['decision'] == 'PROXY_ADMISSIBLE'
    assert jumps[1]['decision'] == 'UNKNOWN_TEST_REQUIRED'
    # Deliberately different queue with the same current p/v/q: no reset allowed.
    x = [F(0)]*N
    x[-2], x[-1] = F(1, 10), F(1, 5)
    hist_next = mv(aa[0][0], x)[2]
    assert hist_next != 0
    # Dropping q from P9 E makes positive drift at e=0,dv=q=.1 explicit.
    counter = {'same_current_state_different_queue_qnext': str(hist_next),
               'zero_queue_qnext': '0', 'P9_E_positive_derivative': '1/100',
               'event_from_zero_deltaE_for_dr_0.2_dv_0.2': str(F(1, 2)*model['kp'][0]*F(1, 5)**2+F(1, 2)*F(1, 5)**2)}
    return {'status': 'EXACT_LOCAL_PROXY_CERTIFICATE_VERIFIED',
            'P10_A_operational_gate': 'NOT_PASSED',
            'reason': 'no justified real-model/timing bounds or runner-reachable initial tube; height absent',
            'disturbance_support': 'model input: current e,dv,q only; resume input: current e,dv only; histories always shift exactly',
            'model_sha256': doc['model_sha256'],
            'certificate_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'rho_interval': [str(x) for x in rho], 'matrix_evidence': evidence,
            'dimension': 50, 'history_samples_per_axis': 11,
            'domain': {'total_V_max': 49, 'e_square_bound': str(coord[0]*49),
                       'dv_square_bound': str(coord[1]*49), 'q_norm_square_bound': str(coord[2]*49),
                       'tilt_bound': 'atan(sqrt(3283/100)/9.80665); exponential proxy interpolation only',
                       'intersample_with_discrete_disturbance': 'q norm <= sqrt(.67*49)+sqrt(.67)*1e-4; actual continuous residual envelope not established',
                       'height': 'UNMODELLED_OVERALL_ABSTAIN'},
            'witness': {'prefixes_checked': 251, 'horizon_s': 2,
                        'actual_initial_speed_lower_m_s': '1.8 - sqrt(0.0021)*0.1 > 1.795',
                        'resume_s': '1/25', 'initial_P_radius': '1/10',
                        'disturbance_P_radius_per_step': '1/10000 (ASSUMED, NOT fitted)',
                        'event_uncertainty_P_radius': '1/20 (ASSUMED)',
                        'max_center_V': str(max_v), 'final_tube_radius': str(radius),
                        'minimum_prefix_slack': str(minimum_slack),
                        'max_center_residual_P_square_upper': str(max_round),
                        'history_origin': 'local admissible proxy history, not verified P9 timeout-reachable'},
            'jump_constraints': jumps, 'counterexamples': counter,
            'elapsed_s': time.perf_counter()-started}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('certificate', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    result = verify(args.certificate)
    (args.output/'audit.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: result[k] for k in ['status', 'P10_A_operational_gate', 'elapsed_s']}))

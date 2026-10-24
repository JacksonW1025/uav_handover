#!/usr/bin/env python3
"""Independent P10-A2 exact-rational checker (standard library only).

Does not import candidate construction or P9/P10-A prediction code. Outputs new.
The proof is for the declared discrete proxy/source-event class, not real SITL.
"""
import argparse
import csv
from fractions import Fraction as F
from functools import lru_cache
import gzip
import hashlib
import json
from math import factorial, lcm
from pathlib import Path
import time

if not __debug__:
    raise RuntimeError('Do not run the certificate checker with python -O')

ROOT = Path(__file__).resolve().parents[2]
N = 47
H = F(1, 250)
SCALE = 10**12
LP, LV, LQ = F(13, 1000), F(29, 1000), F(633, 1000)
EP, EV = F(1, 2**21)+F(1, 10**12), F(1, 2**23)+F(1, 10**12)


def up(x):
    """Outward radius rounding, never nearest rounding."""
    return F(-((-x*SCALE).numerator//(-x*SCALE).denominator), SCALE)


def pd(a):
    assert len(a) == N and all(len(row) == N for row in a)
    assert all(a[i][j] == a[j][i] for i in range(N) for j in range(N))
    den = lcm(*(x.denominator for row in a for x in row))
    b = [[int(x*den) for x in row] for row in a]
    previous = 1
    for k in range(N):
        pivot = b[k][k]
        if pivot <= 0:
            raise ValueError('nonpositive exact leading principal determinant')
        for i in range(k+1, N):
            for j in range(k+1, N):
                val = b[i][j]*pivot-b[i][k]*b[k][j]
                assert val % previous == 0
                b[i][j] = val//previous
        previous = pivot


def a_matrix(kp, kv, rho):
    a = [[F(0) for _ in range(N)] for _ in range(N)]
    for j in range(N):
        z = rho if j == 2 else F(0)
        if j == N-2:
            z -= (1-rho)*kp
        if j == N-1:
            z -= (1-rho)*kv
        a[2][j] = z
        qsum = z+(j == 2)
        a[1][j] = F(j == 1)+H*qsum/2
        a[0][j] = F(j == 0)+(H if j == 1 else 0)+H*H*qsum/4
    a[3][0] = a[4][1] = F(1)
    for i in range(5, N):
        a[i][i-2] = F(1)
    return a


@lru_cache(maxsize=4)
def check_p(raw, kp, kv):
    p = [[F(x, 10**10) for x in row] for row in raw]
    lower = [row[:] for row in p]
    for i in range(N):
        lower[i][i] -= F(1, 2)
    pd(lower)
    assert max(sum(abs(x) for x in row) for row in p) < 30000
    for i, c in enumerate([F(15, 100000), F(8, 10000), F(2, 5)]):
        r = [row[:] for row in p];r[i][i] -= 1/c;pd(r)
    assert LP*LP > F(15, 100000) and LV*LV > F(8, 10000) and LQ*LQ > F(2, 5)
    assert p[3][3] < F(27, 5)**2 and p[4][4] < 25
    rho = [sum((-F(1, 20))**j/factorial(j) for j in range(n)) for n in [20, 21]]
    assert 0 < rho[0] < rho[1] < 1
    margins = []
    for r in rho:
        a = a_matrix(kp, kv, r)
        cols = [[(i, a[i][j]) for i in range(N) if a[i][j]] for j in range(N)]
        q = [[p[i][j]-sum(u*p[k][l]*v for k, u in cols[i] for l, v in cols[j])
              for j in range(N)] for i in range(N)]
        margin = min(q[i][i]-F(1, 2)-sum(abs(q[i][j]) for j in range(N) if i != j) for i in range(N))
        assert margin > 0
        margins.append(margin)
    return rho, {'P_bounds': '.5 I < P < 30000 I', 'Q_lower': '1/2',
        'output_square_constants': ['3/20000', '1/1250', '2/5'],
        'rho_interval': [str(x) for x in rho], 'exact_Q_margins': [str(x) for x in margins],
        'rank_one_positive_LMIs': 3, 'dimension': N}


def reference(pub_us):
    t = F(pub_us, 10**6);speed = F(9, 5)
    if t < -2:
        return -F(27, 10), F(0)
    if t < -1:
        return -F(27, 10)+F(9, 10)*(t+2)**2, speed*(t+2)
    if t < F(23, 5):
        return speed*t, speed
    z = min(t-F(23, 5), F(9, 10))
    return F(207, 25)+speed*z-z*z, max(F(0), speed-2*z)


def initial_state():
    y = [[F(0) for _ in range(3)] for _ in range(N)]
    y[0] = [-F(27, 10), F(1, 100), F(0)]
    y[2][2] = F(1, 10)
    for j in range(1, 23):
        u = -F(j, 22);tau = F(11, 125)
        y[3+2*(j-1)][1] = F(1, 100)
        y[3+2*(j-1)][2] = F(1, 10)*tau*tau*(u**4/2+u**3+u*u/2)
        y[4+2*(j-1)][2] = F(1, 10)*tau*(2*u**3+3*u*u+u)
    return y


def require_unsaturated(ep_bound, dv_bound):
    if ep_bound >= F(1, 2) or dv_bound >= 1:
        raise ValueError('UNKNOWN_SATURATION_OR_MODE_CROSSING_NOT_CERTIFIED')


def cap_reference(cap, us):
    """Source RTGT2, 1-D. Copies are functions of captured body coordinates.

    cap carries the SAME captured uncertainty parameters, not a new reset ball.
    Its residual bounds enclose float32 observation/profile casts separately.
    """
    pc, vc, erp, erv, ct = cap
    dt = F(us-ct, 10**6)
    width = abs(vc[1])+abs(vc[2])+erv
    if dt == 0:
        return pc[:], vc[:], erp+EP, erv+EV, 'CAPTURE_COPY'
    if vc[0]-width >= 2*dt:
        rp = [pc[i]+dt*vc[i] for i in range(3)];rp[0] -= dt*dt
        rv = vc[:];rv[0] -= 2*dt
        return rp, rv, erp+dt*erv+EP, erv+EV, 'DECEL_POSITIVE'
    if -vc[0]-width >= 2*dt:
        rp = [pc[i]+dt*vc[i] for i in range(3)];rp[0] += dt*dt
        rv = vc[:];rv[0] += 2*dt
        return rp, rv, erp+dt*erv+EP, erv+EV, 'DECEL_NEGATIVE'
    if abs(vc[0])+width <= 2*dt:
        rp = [pc[i]+abs(vc[0])*vc[i]/2 for i in range(3)]
        rp[0] = pc[0]+vc[0]*abs(vc[0])/4
        # f(v)=v|v|/4 has globally 1/2-Lipschitz derivative.
        # Taylor remainder <= width²/4, including sign-crossing uncertainty.
        return rp, [F(0)]*3, erp+abs(vc[0])*erv/2+width*width/4+EP, EV, 'STOPPED_ALL_SET'
    raise ValueError('UNKNOWN_CAPTURE_STOP_GUARD_CROSSES_SET')


def verify(directory):
    started = time.perf_counter()
    directory = Path(directory)
    cert = json.loads((directory/'certificate.json').read_text())
    assert cert['schema'] == 'p10-a2-source-event-tube-1'
    expected = {'N': 47, 'delay_steps': 22, 'native_period_us': 4000,
        'publisher_period_us': 20000, 'publisher_phase_us': -2000,
        'recovery_sample_period_us': 4000, 'stale_operator': '>', 'timeout_us': 200000,
        'speed_m_s': '9/5', 'gap_windows_us': [[0, 500000]],
        'deceleration_start_us': 4600000, 'stream_end_us': 11500000,
        'observation_us': [-5000000, 16000000], 'rsh': 1, 'rtgt': 2, 'rtdec': 2, 'rrec': 0, 'rini': 4,
        'active_throughout': True, 'initial_capture_active': False,
        'initial_external_valid': True, 'binary32_RNE': True,
        'double_arithmetic_abs_envelope': '1/1000000000000',
        'w_support': 'current p,v,q only; lateral zero; no queue forcing',
        'initial_previous_stale': False, 'initial_recovery_armed': False,
        'initial_recovery_active': False, 'use_internal_reference': False,
        'history_reset_on_capture': False, 'finite_inputs': True, 'accepted_unique_samples': True,
        'axis': 'NED-x; target yaw=0; lateral state, reference and disturbance identically zero',
        'trace_scale': SCALE, 'P_scale': 10**10,
        'initial_position_generator_m': '1/100', 'initial_q_generator': '1/10',
        'initial_quantization_P_radius': '1/2000', 'per_step_current_state_w_P_radius': '1/10000000',
        'center_generator_rounding_P_budget_per_step': '1/100000000', 'output_q_limit': 6}
    assert set(cert) == set(expected)|{'schema','P_integer','model_sha256','stage','rounding_mode','proof_object'}, 'unknown or missing certificate input'
    for key, value in expected.items():
        assert cert[key] == value, f'not in certified input/clock class: {key}'
    model_path = ROOT/'data/p9-20261024-freeze/model.json'
    digest = hashlib.sha256(model_path.read_bytes()).hexdigest()
    assert cert['model_sha256'] == digest == '474509c9192ce270b897fdc1cbd69796be180c6a5a73b9f091678dbbca256b4a'
    model = json.loads(model_path.read_text(), parse_float=F)
    kp, kv = model['kp'][0], model['kv'][0]
    rho, matrix_evidence = check_p(tuple(tuple(r) for r in cert['P_integer']), kp, kv)
    with gzip.open(directory/'trace.csv.gz', 'rt') as f:
        trace = [[int(x) for x in row] for row in csv.reader(f)]
    assert len(trace) == 5251 and all(len(r) == 22 for r in trace)
    initial = initial_state()
    # Native input/target rounding in the constructive polynomial prehistory.
    assert 30000*(23*(EP+F(1, 20000000))**2+23*EV**2+F(1, 2**24)**2) < F(1, 2000)**2
    radius = F(1, 2000)
    # P > .5 I gives each residual coordinate < sqrt(2) R < 2R.
    # Check the full constructive history set before using clipped queue data.
    for i in range(3, N):
        limit = F(1, 2) if (i-3) % 2 == 0 else F(1)
        assert abs(initial[i][0])+abs(initial[i][1])+abs(initial[i][2])+2*radius < limit
    old_stale = False;last_slot = -1;last_pub = -5002000;last_read = -5000000
    cap = None;cap_row = -1;events = [];equal_guard = []
    max_ep = max_dv = max_q = max_round = F(0)
    first_old_domain = None
    history = initial[3:]
    for k, row in enumerate(trace):
        us = -5000000+4000*k
        assert row[0] == us, 'wrong native/gyro clock'
        y = [[F(row[1+3*c+i], SCALE) for c in range(3)] for i in range(3)]+history
        if k == 0:
            assert y[:3] == initial[:3]
        slot = (us+5002000)//20000
        if slot > last_slot:
            last_slot = slot;pub = -5002000+slot*20000
            if pub < 11500000 and not 0 <= pub < 500000:
                sp, sv = reference(pub);last_pub, last_read = pub, us
        age = us-last_read
        stale = age > 200000
        capture, resume = stale and not old_stale, old_stale and not stale
        if age == 200000:
            equal_guard.append({'native_us': us, 'stale': stale});assert not stale
        if capture:
            cap = (y[0][:], y[1][:], LP*radius+EP, LV*radius+EV, us)
            cap_row = k
            events.append({'kind': 'CAPTURE', 'native_us': us, 'age_us': age,
                'captured_velocity_center': str(y[1][0]),
                'captured_velocity_total_halfwidth': str(abs(y[1][1])+abs(y[1][2])+LV*radius+EV),
                'reset_relation': 'pcap=fl32(body_position),vcap=fl32(body_velocity); same captured variables retained'})
        if resume:
            events.append({'kind': 'RESUME', 'native_us': us, 'last_pub_us': last_pub,
                           'history_reset': False, 'profile_ended': True, 'recovery_start': False})
        assert row[16:] == [last_pub, last_read, int(stale), int(capture), int(resume), cap_row], 'guard/read/reset/event evidence mismatch'
        if stale:
            rp, rv, rp_err, rv_err, phase = cap_reference(cap, us)
        else:
            rp, rv, rp_err, rv_err = [sp, F(0), F(0)], [sv, F(0), F(0)], EP, EV
            phase = 'EXTERNAL_HELD'
        ce, cd = [y[0][i]-rp[i] for i in range(3)], [y[1][i]-rv[i] for i in range(3)]
        ep_err = abs(ce[1])+abs(ce[2])+LP*radius+rp_err
        dv_err = abs(cd[1])+abs(cd[2])+LV*radius+rv_err
        ep_bound, dv_bound = abs(ce[0])+ep_err, abs(cd[0])+dv_err
        require_unsaturated(ep_bound, dv_bound)
        qb = abs(y[2][0])+abs(y[2][1])+abs(y[2][2])+LQ*radius
        assert qb < 6, 'UNKNOWN_TILT_OUTPUT_BOUND_NOT_MET'
        # Bounds used in the independently stated binary32 cast envelopes.
        assert abs(y[0][0])+abs(y[0][1])+abs(y[0][2])+LP*radius < 16
        assert abs(y[1][0])+abs(y[1][1])+abs(y[1][2])+LV*radius < 4
        assert abs(rp[0])+abs(rp[1])+abs(rp[2])+rp_err < 16
        assert abs(rv[0])+abs(rv[1])+abs(rv[2])+rv_err < 4
        max_ep, max_dv, max_q = max(max_ep, ep_bound), max(max_dv, dv_bound), max(max_q, qb)
        if first_old_domain is None:
            lo_e, lo_d = max(F(0), abs(ce[0])-ep_err), max(F(0), abs(cd[0])-dv_err)
            if lo_e*lo_e > F(49, 2000) or lo_d*lo_d > F(1029, 10000):
                first_old_domain = {'native_us': us, 'e_abs_lower': str(lo_e), 'd_abs_lower': str(lo_d),
                    'scope': 'entire propagated set violates an original necessary raw-V<=49 coordinate bound'}
        clips = [[F(row[10+2*c+i], SCALE) for c in range(3)] for i in range(2)]
        if capture:
            assert ce == [F(0)]*3 and cd == [F(0)]*3, 'constrained reset nominal/generator copy lost'
        if k == 5250:
            break
        maxima = [F(0)]*3
        for c in range(3):
            for r in rho:
                qn = r*y[2][c]-(1-r)*(kp*y[-2][c]+kv*y[-1][c])
                vn = y[1][c]+H*(y[2][c]+qn)/2
                pn = y[0][c]+H*(y[1][c]+vn)/2
                residuals = [F(trace[k+1][1+3*c+i], SCALE)-val for i, val in enumerate([pn, vn, qn])]
                residuals += [clips[0][c]-ce[c], clips[1][c]-cd[c]]
                maxima[c] = max(maxima[c], *(abs(x) for x in residuals))
        # Each channel has at most 47 coordinates; sqrt(30000*47) < 2000.
        # Sum over center and both generators, covering every |z_i|<=1.
        round_p_upper = 2000*sum(maxima)
        assert round_p_upper <= F(1, 10**8), 'center/generator discrete residual too large'
        max_round = max(max_round, round_p_upper)
        radius = up(radius+F(27, 5)*rp_err+5*rv_err+F(1, 10**8)+F(1, 10**7))
        history = clips+history[:-2]
        old_stale = stale
    assert [(e['kind'], e['native_us']) for e in events] == [('CAPTURE',204000),('RESUME',520000),('CAPTURE',11704000)]
    assert first_old_domain is not None
    assert any(e['native_us'] == 200000 for e in equal_guard)
    assert (6+LQ*F(1, 10**7))**2 < F('9.80665')**2
    return {'status': 'VERIFIED_SOURCE_EVENT_DISCRETE_PROXY_CLASS',
        'gate': 'A2_DECLARED_PROXY_SUBCLASS_MEETS_REQUESTED_GATE_PENDING_PARENT_REVIEW',
        'B_C_D_authorized_or_started': False, 'new_flights': 0,
        'proof_object': '47-D one-axis physical-state/error tube; other axis exactly zero; source guard/reset clock machine; q interpolation only',
        'source_class_conditions': 'RSH1, active throughout, initially inactive capture/recovery and valid fresh stream; every unique gyro/read tick at 4 ms; publisher at -2 ms mod 20 ms; RREC0, RTGT2, RTDEC2; no invalid or missed samples',
        'events': events, 'strict_equality_guards_verified': equal_guard,
        'matrix_evidence': matrix_evidence, 'prefixes': len(trace),
        'initial_set': {'position_m': '[-.01,.01] offset', 'q': '[-.1,.1]',
            'history': 'kinematically consistent polynomial p,v prehistory; same two parameters; source float32 enclosures',
            'residual_P_radius': '1/2000', 'entire_initial_history_inside_clip_box': True},
        'max_abs_e_upper': str(max_ep), 'max_abs_d_upper': str(max_dv),
        'max_q_upper': str(max_q), 'certified_q_output_limit': 6,
        'tilt_bound': 'atan(6/9.80665) < 45 degrees for stipulated q interpolation',
        'intersample_residual_allowance': 'sqrt(.4)*1e-7 extra if discrete q residual applied at sample endpoint; still <45',
        'max_center_generator_rounding_P_upper': str(max_round), 'final_error_P_radius': str(radius),
        'old_raw_certificate_entire_set_counterexample': first_old_domain,
        'decision': 'ADMIT_DECLARED_COMPLETE_EVENT_SEQUENCE_FOR_PROXY_TILT; other inputs UNKNOWN; no overall safety or test-saving claim',
        'actual_SITL_claim': 'none; w<=1e-7 is a strict conditional input assumption, not an empirical residual guarantee',
        'float_scope': 'binary32 rounding within verified |position|<16, |velocity|<4 plus declared 1e-12 double-arithmetic envelope; actual machine conformance remains a condition',
        'height_and_task_cost': 'not certified; overall ABSTAIN',
        'certificate_sha256': hashlib.sha256((directory/'certificate.json').read_bytes()).hexdigest(),
        'trace_sha256': hashlib.sha256((directory/'trace.csv.gz').read_bytes()).hexdigest(),
        'elapsed_s': time.perf_counter()-started}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('input', type=Path);p.add_argument('--output', type=Path, required=True)
    args = p.parse_args();args.output.mkdir(parents=True, exist_ok=False)
    result = verify(args.input)
    (args.output/'audit.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: result[k] for k in ['status','gate','prefixes','elapsed_s']}))

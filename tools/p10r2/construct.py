#!/usr/bin/env python3
"""P10-A2 offline candidate generator. Acceptance is in the independent checker.

No simulator, ROS, subprocess, network or Lab writes. Original P10-A untouched.
"""
import argparse
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np
from scipy.linalg import solve_discrete_lyapunov

ROOT = Path(__file__).resolve().parents[2]
SCALE = 10**12
N = 47
H = .004


def ref(t, speed=1.8):
    if t < -2:
        return -1.5*speed, 0.
    if t < -1:
        return -1.5*speed+.5*speed*(t+2)**2, speed*(t+2)
    if t < 4.6:
        return speed*t, speed
    z = min(t-4.6, speed/2)
    return speed*4.6+speed*z-z*z, max(0., speed-2*z)


def matrix(kp, kv, rho):
    a = np.zeros((N, N))
    a[0, 0] = a[1, 1] = 1.
    a[0, 1] = H
    z = np.zeros(N)
    z[2] = rho
    z[-2:] = -(1-rho)*np.array([kp, kv])
    a[2] = z
    a[1] += H/2*(np.eye(N)[2]+z)
    a[0] += H*H/4*(np.eye(N)[2]+z)
    a[3, 0] = a[4, 1] = 1.
    for i in range(5, N):
        a[i, i-2] = 1.
    return a


def initial():
    y = np.zeros((N, 3))  # nominal, position generator, q generator
    y[0, 0] = -2.7
    y[0, 1] = .01
    y[2, 2] = .1
    # Kinematically consistent prehistory: p'=v, v'=q polynomial;
    # current p offset and q uncertain, current v=0. Reference held at -2.7.
    for j in range(1, 23):
        u = -j/22
        y[3+2*(j-1), 1] = .01
        y[3+2*(j-1), 2] = .1*.088**2*(.5*u**4+u**3+.5*u*u)
        y[4+2*(j-1), 2] = .1*.088*(2*u**3+3*u*u+u)
    return np.rint(y*SCALE).astype(np.int64).astype(float)/SCALE


def rollout(kp, kv, speed=1.8, duration=.5, rtgt=2, keep=False):
    rho = math.exp(-.05)
    y = initial()
    y[0, 0] = -1.5*speed
    pub_slot = -1
    last_pub = -5002000
    last_read = -5000000
    stale = False
    cap = None
    rows = []
    events = []
    max_e = max_d = max_q = 0.
    sat = 0
    first_old = None
    for k in range(5251):
        us = -5000000+4000*k
        slot = (us+5002000)//20000
        if slot > pub_slot:
            pub_slot = slot
            pub = -5002000+20000*slot
            pt = pub/1e6
            if pt < 4.6+speed/2+6 and not 0 <= pt < duration:
                sp, sv = ref(pt, speed)
                last_pub, last_read = pub, us
        now_stale = us-last_read > 200000
        capture, resume = now_stale and not stale, stale and not now_stale
        if capture:
            cap = (k, us, y[0].copy(), y[1].copy())
            events.append({'kind': 'CAPTURE', 'row': k, 'native_us': us,
                           'velocity_center': float(y[1, 0]),
                           'cause': 'gap' if us < 1000000 else 'stream_end'})
        if resume:
            events.append({'kind': 'RESUME', 'row': k, 'native_us': us})
        if now_stale:
            ci, ct, pc, vc = cap
            t = (us-ct)/1e6
            if rtgt == 0:
                rp, rv = pc.copy(), np.zeros(3)
            elif t == 0:
                rp, rv = pc.copy(), vc.copy()
            elif abs(vc[0]) > 2*t:
                sign = 1 if vc[0] > 0 else -1
                rp, rv = pc+t*vc, vc.copy()
                rp[0] -= sign*t*t
                rv[0] -= sign*2*t
            else:
                rp, rv = pc+abs(vc[0])/2*vc, np.zeros(3)
                rp[0] = pc[0]+vc[0]*abs(vc[0])/4
        else:
            rp, rv = np.array([sp, 0., 0.]), np.array([sv, 0., 0.])
        ce, cd = y[0]-rp, y[1]-rv
        max_e, max_d, max_q = max(max_e, abs(ce[0])), max(max_d, abs(cd[0])), max(max_q, abs(y[2, 0]))
        if first_old is None and (ce[0]**2 > .0245 or cd[0]**2 > .1029):
            first_old = {'native_us': us, 'e_center': float(ce[0]), 'd_center': float(cd[0])}
        if abs(ce[0]) > .5:
            ce = np.array([np.clip(ce[0], -.5, .5), 0., 0.]); sat += 1
        if abs(cd[0]) > 1:
            cd = np.array([np.clip(cd[0], -1, 1), 0., 0.]); sat += 1
        clips = np.rint(np.vstack([ce, cd])*SCALE).astype(np.int64)
        if keep:
            values = [us, *np.rint(y[:3].T.flatten()*SCALE).astype(np.int64).tolist(),
                      *clips.T.flatten().tolist(), last_pub, last_read, int(now_stale),
                      int(capture), int(resume), cap[0] if cap else -1]
            rows.append(values)
        qn = rho*y[2]-(1-rho)*(kp*y[-2]+kv*y[-1])
        vn = y[1]+H/2*(y[2]+qn)
        pn = y[0]+H/2*(y[1]+vn)
        y = np.vstack([pn, vn, qn, clips.astype(float)/SCALE, y[3:-2]])
        y = np.rint(y*SCALE).astype(np.int64).astype(float)/SCALE
        stale = now_stale
    return rows, {'speed_m_s': speed, 'duration_s': duration, 'rtgt': rtgt,
                  'nominal_peak_q': max_q, 'nominal_peak_tilt_deg': math.degrees(math.atan(max_q/9.80665)),
                  'nominal_max_e': max_e, 'nominal_max_d': max_d,
                  'nominal_saturated_samples': sat, 'old_domain_first_counterexample': first_old,
                  'events': events, 'claim': 'nominal diagnostic only; not a region proof'}


def build(out):
    started = time.perf_counter()
    out.mkdir(parents=True, exist_ok=False)
    model_file = ROOT/'data/p9-20261024-freeze/model.json'
    model = json.loads(model_file.read_text())
    kp, kv = model['kp'][0], model['kv'][0]
    a = matrix(kp, kv, math.exp(-.05))
    p = solve_discrete_lyapunov(a.T, np.eye(N))
    p = (p+p.T)/2
    cert = {'schema': 'p10-a2-source-event-tube-1',
            'model_sha256': hashlib.sha256(model_file.read_bytes()).hexdigest(),
            'P_scale': 10**10, 'P_integer': np.rint(p*10**10).astype(np.int64).tolist(),
            'trace_scale': SCALE, 'N': N, 'delay_steps': 22,
            'native_period_us': 4000, 'publisher_period_us': 20000,
            'publisher_phase_us': -2000, 'recovery_sample_period_us': 4000,
            'stale_operator': '>', 'timeout_us': 200000,
            'speed_m_s': '9/5', 'gap_windows_us': [[0, 500000]],
            'deceleration_start_us': 4600000, 'stream_end_us': 11500000,
            'observation_us': [-5000000, 16000000],
            'rsh': 1, 'rtgt': 2, 'rtdec': 2, 'rrec': 0, 'rini': 4,
            'active_throughout': True, 'initial_capture_active': False,
            'initial_external_valid': True, 'binary32_RNE': True,
            'double_arithmetic_abs_envelope': '1/1000000000000',
            'w_support': 'current p,v,q only; lateral zero; no queue forcing',
            'initial_previous_stale': False, 'initial_recovery_armed': False,
            'initial_recovery_active': False, 'use_internal_reference': False,
            'history_reset_on_capture': False, 'finite_inputs': True,
            'accepted_unique_samples': True,
            'axis': 'NED-x; target yaw=0; lateral state, reference and disturbance identically zero',
            'initial_position_generator_m': '1/100', 'initial_q_generator': '1/10',
            'initial_quantization_P_radius': '1/2000', 'per_step_current_state_w_P_radius': '1/10000000',
            'center_generator_rounding_P_budget_per_step': '1/100000000',
            'output_q_limit': 6, 'rounding_mode': 'binary32 RNE envelope + 1e-12 arithmetic envelope',
            'stage': 'OFFLINE_A2_ONLY_NO_B_C_D',
            'proof_object': 'new 4 ms discrete surrogate, source event clock machine, q output interpolation only'}
    (out/'certificate.json').write_text(json.dumps(cert, indent=2)+'\n')
    rows, nominal = rollout(kp, kv, keep=True)
    path = out/'trace.csv.gz'
    with gzip.GzipFile(filename=str(path), mode='wb', mtime=0) as f:
        import io
        txt = io.TextIOWrapper(f, encoding='utf-8', newline='')
        writer = csv.writer(txt);writer.writerows(rows);txt.flush();txt.detach()
    (out/'nominal.json').write_text(json.dumps(nominal, indent=2)+'\n')
    coverage = []
    for speed in [1.5, 1.8, 2.]:
        for rtgt in [0, 2]:
            for duration in [.3, .5, .65]:
                _, record = rollout(kp, kv, speed, duration, rtgt)
                coverage.append(record)
    (out/'coverage-candidates.json').write_text(json.dumps({'rows': coverage,
        'scope': '18 finite nominal counterexample searches; source-clock-aware; not a proof over the speed/duration domain',
        'old_P_scaled': False, 'prior_seen_frozen_diagnostic': '138/156 outside original necessary raw-state bounds'}, indent=2)+'\n')
    (out/'construction-cost.json').write_text(json.dumps({'elapsed_s': time.perf_counter()-started,
        'new_flights': 0, 'source_model_refitted': False}, indent=2)+'\n')
    print(json.dumps({'output': str(out), 'rows': len(rows), 'trace_bytes': path.stat().st_size}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('output', type=Path)
    build(p.parse_args().output)

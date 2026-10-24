#!/usr/bin/env python3
"""Offline candidate construction only. Acceptance belongs to verify.py.

No experiment runner, ROS, subprocess, Lab modification or network imports.
The frozen P9 model is an input, not re-fitted. Output must be new.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np
from scipy.linalg import solve_discrete_lyapunov

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / 'data/p9-20261024-freeze/model.json'
SCALE = 10**10
STATE_SCALE = 10**12
N = 25
H = .008


def matrix(kp, kv, rho):
    a = np.zeros((N, N))
    a[0, 0] = a[1, 1] = 1.
    a[0, 1] = H
    qnext = np.zeros(N)
    qnext[2] = rho
    qnext[-2:] = -(1-rho)*np.array([kp, kv])
    a[2] = qnext
    a[1] += H/2*(np.eye(N)[2]+qnext)
    a[0] += H*H/4*(np.eye(N)[2]+qnext)
    a[3, 0] = a[4, 1] = 1.
    for i in range(5, N):
        a[i, i-2] = 1.
    return a


def reference(k):
    # Local T1 capture -> external resume at 40 ms, then held moving line.
    t = k*H
    if k < 5:
        return 1.8*t-t*t, 1.8-2*t
    pub = (2*k//5)*.02
    return 1.8*pub, 1.8


def build(out):
    started = time.perf_counter()
    out.mkdir(parents=True, exist_ok=False)
    model = json.loads(MODEL.read_text())
    rho = np.exp(-.1)
    axes = []
    for axis, (kp, kv) in enumerate(zip(model['kp'], model['kv'])):
        a = matrix(kp, kv, rho)
        p = solve_discrete_lyapunov(a.T, np.eye(N))
        p = (p+p.T)/2
        pint = np.rint(p*SCALE).astype(np.int64)
        x = np.zeros(N)
        centers = [[0]*N]
        rp, rv = reference(0) if axis == 0 else (0., 0.)
        for k in range(250):
            np_, nv = reference(k+1) if axis == 0 else (0., 0.)
            b = np.zeros(N)
            b[0] = H*rv-(np_-rp)
            b[1] = rv-nv
            x = a@x+b
            xi = np.rint(x*STATE_SCALE).astype(np.int64)
            centers.append(xi.tolist())
            x = xi.astype(float)/STATE_SCALE
            rp, rv = np_, nv
        axes.append({'P_integer': pint.tolist(), 'center_integer': centers,
                     'diagnostic_spectral_radius': float(max(abs(np.linalg.eigvals(a))))})
    obj = {'schema': 'p10-a-local-delay-certificate-1',
           'model_path': str(MODEL.relative_to(ROOT)),
           'model_sha256': hashlib.sha256(MODEL.read_bytes()).hexdigest(),
           'P_scale': SCALE, 'state_scale': STATE_SCALE, 'axes': axes,
           'scope': 'local proxy theorem; full P10-A operational gate NOT_PASSED',
           'initial_P_radius': '1/10', 'per_step_disturbance_P_radius': '1/10000',
           'resume_disturbance_P_radius': '1/20',
           'initial_history_reachability': 'admissible proxy initial history; NOT proved runner-reachable',
           'construction_elapsed_s': time.perf_counter()-started}
    (out/'certificate.json').write_text(json.dumps(obj, indent=2)+'\n')
    print(json.dumps({'output': str(out), 'elapsed_s': obj['construction_elapsed_s']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    build(parser.parse_args().output)

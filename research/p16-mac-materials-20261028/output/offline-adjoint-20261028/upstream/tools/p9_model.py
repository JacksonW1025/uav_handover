#!/usr/bin/env python3
"""P9 horizontal surrogate v1. Rebuild from ordinary P6-A/P8-A only.

This is a new model, unrelated to the missing P8 frozen model. Height is
unmodelled: an overall-safety decision MUST abstain. No strict error guarantee.
"""
import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path

import numpy as np
from scipy.signal import lfilter

ROOT = Path(__file__).resolve().parents[1]
NAME = 'p9-horizontal-delay-v1'
DT = .02
G = 9.80665
COLS = ['t', 'pf', 'pl', 'vf', 'vl', 'qf', 'ql', 'tf', 'tl', 'tvf', 'tvl']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, obj):
    path=Path(path);tmp=path.with_name(path.name+f'.{os.getpid()}.tmp')
    with tmp.open('w') as f:
        f.write(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False)+'\n')
        f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)
    fd=os.open(path.parent,os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def prepare(out):
    """Derive portable attitude/target traces in NEW output, never rewrite old runs."""
    from pyulog import ULog
    from p6_export import TOPICS, reconstruct
    manifest = json.loads((ROOT/'export/manifest.json').read_text())
    names = sorted(n for n, r in manifest['runs'].items() if r['kind'] == 'p6_ident'
                   and r['batch'] in ['data/p6-20261019-batch-a', 'data/p8-20261021-batch-a'])
    if len(names) != 26:
        raise ValueError('Expected 18 P6-A + 8 P8-A ordinary identification runs')
    (out/'ident').mkdir()
    inputs, runs = {}, []
    for name in names:
        base = ROOT/'export'/name
        summary = json.loads((base/'summary.json').read_text())
        raw = ROOT/'data'/name/'flight.ulg'
        for path in [raw, base/'summary.json', base/'trace.csv.gz']:
            inputs[str(path.relative_to(ROOT))] = {'sha256':sha(path), 'bytes':path.stat().st_size}
        u = ULog(str(raw), TOPICS)
        tables = {d.name:d.data for d in u.data_list if d.multi_id == 0}
        rec = reconstruct(tables)
        if rec['resid']['components_over_1e-4'] or not rec['ok'].all():
            raise ValueError('Identification reconstruction mismatch: '+name)
        att = tables['vehicle_attitude']
        idx = np.maximum(np.searchsorted(att['timestamp'], rec['s'], side='right')-1, 0)
        qw, qx, qy, qz = [np.asarray(att[f'q[{i}]'], float)[idx] for i in range(4)]
        bz = np.column_stack([2*(qx*qz+qw*qy), 2*(qy*qz-qw*qx), 1-2*(qx*qx+qy*qy)])
        if np.any(bz[:,2] <= .1):
            raise ValueError('attitude proxy singular: '+name)
        force = -G*bz[:,:2]/bz[:,2,None]
        yaw = rec['yaw']; c, s = np.cos(yaw), np.sin(yaw)
        def rotate(x):
            return np.column_stack([c*x[:,0]+s*x[:,1], s*x[:,0]-c*x[:,1]])
        t0 = summary['time_origin']['px4_us']
        tt = (rec['s']-t0)/1e6
        # Include .5 s prehistory and the full identification manoeuvre/end hold.
        end = next((e['t_s'] for e in summary['events'] if e['event']=='stream_end'), float(tt[-1]))
        grid = np.arange(-.5, end, DT)
        pos, vel = rotate(rec['pos']), rotate(rec['vel'])
        target, tv = rotate(rec['pos']-rec['e']), rotate(rec['vel']-rec['ev'])
        values = np.column_stack([pos, vel, rotate(force), target, tv])
        arr = np.column_stack([grid, *[np.interp(grid, tt, values[:,j]) for j in range(values.shape[1])]])
        stream = io.StringIO(); np.savetxt(stream, arr, delimiter=',', header=','.join(COLS), comments='', fmt='%.9g')
        target_path = out/'ident'/f'{name}.csv.gz'
        target_path.write_bytes(gzip.compress(stream.getvalue().encode(), mtime=0))
        runs.append({'run':name, 'condition':summary['condition'], 'file':str(target_path.relative_to(out)),
                     'sha256':sha(target_path), 'rows':len(arr), 'kind':'ordinary_identification_development',
                     'sim_seed':summary['sim_seed'], 'family':summary['condition'].split('-')[0]})
    write(out/'input-manifest.json', {'model':NAME, 'runs':runs, 'inputs':inputs,
          'raw_remote_complete':False, 'source':'P6-A 18 + P8-A 8; no B/C failures or 24 exploration rows used to fit',
          'attitude_proxy':'q_xy=-g*R_body_z_xy/R_body_z_z, rotated to target yaw FLU; proxy assumes vertical thrust compensation',
          'sampling':'20 ms, linear interpolation of state and target; target discontinuities not smoothed in future rollout'})


def load_runs(out):
    m = json.loads((out/'input-manifest.json').read_text())
    runs = []
    for r in m['runs']:
        path = out/r['file']
        if sha(path) != r['sha256']:
            raise ValueError('input hash mismatch '+r['file'])
        with gzip.open(path, 'rt') as f:
            a = np.loadtxt(f, delimiter=',', skiprows=1)
        runs.append((r, a))
    return runs


def response_features(a, delay, tau):
    rho = math.exp(-DT/tau)
    p, v = a[:,1:3]-a[:,7:9], a[:,3:5]-a[:,9:11]
    p, v = np.clip(p,-.5,.5), np.clip(v,-1,1)
    t = a[:,0]
    x = np.stack([-np.column_stack([np.interp(t-delay,t,p[:,j]) for j in range(2)]),
                  -np.column_stack([np.interp(t-delay,t,v[:,j]) for j in range(2)])], axis=2)
    filt = lfilter([1-rho], [1,-rho], x, axis=0)
    initial = rho**(np.arange(len(a))+1)
    y = a[:,5:7]-initial[:,None]*a[0,5:7]
    return filt, y, initial


def fit(runs):
    """Equal run weighting; fit two yaw axes separately. Fixed 21 x 6 grid."""
    best = None
    for delay in np.arange(0,.16001,.008):
        for tau in [.04,.08,.12,.16,.24,.32]:
            xs, ys = [], []
            for _, a in runs:
                x, y, _ = response_features(a,float(delay),tau)
                xs.append(x/math.sqrt(len(a))); ys.append(y/math.sqrt(len(a)))
            x, y = np.concatenate(xs), np.concatenate(ys)
            coeff = np.array([np.linalg.lstsq(x[:,j],y[:,j],rcond=None)[0] for j in range(2)])
            if np.any(coeff <= 0):
                continue
            score = float(np.mean((np.einsum('naj,aj->na',x,coeff)-y)**2))
            key = (score,float(delay),tau)
            if best is None or key < best[0]:
                best = key, coeff
    if best is None:
        raise ValueError('no positive-gain surrogate candidate')
    (_, delay, tau), coeff = best
    return {'name':NAME, 'version':1, 'dt_s':DT, 'delay_s':delay, 'tau_s':tau,
            'kp':coeff[:,0].tolist(), 'kv':coeff[:,1].tolist(),
            'position_clip_m':.5, 'velocity_clip_m_s':1.,
            'command_limit_per_axis_m_s2':(coeff[:,0]*.5+coeff[:,1]).tolist(),
            'plant':'pdot=v; vdot=q (attitude force proxy); qdot=(-q-kp*clip(ep(t-delay)) -kv*clip(ev(t-delay)))/tau',
            'height_prediction':None, 'overall_safety':'ABSTAIN_HEIGHT_UNMODELLED',
            'strict_guarantee':False}


def integrate(model, a):
    """Free horizontal rollout against exogenous LOGGED identification targets."""
    p, v, q = a[0,1:3].copy(), a[0,3:5].copy(), a[0,5:7].copy()
    rho = math.exp(-DT/model['tau_s']); kp, kv = np.array(model['kp']),np.array(model['kv'])
    # fractional delay on the 20 ms integration grid
    d = model['delay_s']/DT; ep = []; ev = []; result = []
    for k, row in enumerate(a):
        result.append(np.r_[p,v,q])
        ep.append(np.clip(p-row[7:9],-.5,.5)); ev.append(np.clip(v-row[9:11],-1,1))
        j = max(0.,k-d); lo = int(math.floor(j)); hi = min(k,lo+1); w = j-lo
        u = -kp*((1-w)*ep[lo]+w*ep[hi])-kv*((1-w)*ev[lo]+w*ev[hi])
        qnext = rho*q+(1-rho)*u
        vnext = v+.5*DT*(q+qnext)
        p = p+.5*DT*(v+vnext); v = vnext; q = qnext
    return np.array(result)


def evaluate(model, a):
    r = integrate(model,a)
    measured = np.degrees(np.arctan(np.linalg.norm(a[:,5:7],axis=1)/G))
    pred = np.degrees(np.arctan(np.linalg.norm(r[:,4:6],axis=1)/G))
    window = a[:,0] >= 0
    return {'predicted_peak_tilt_deg':float(pred[window].max()),'observed_peak_tilt_deg':float(measured[window].max()),
            'peak_error_deg':float(pred[window].max()-measured[window].max()),
            'trajectory_tilt_rmse_deg':float(np.sqrt(np.mean((pred[window]-measured[window])**2))),
            'position_rmse_m':float(np.sqrt(np.mean((r[window,:2]-a[window,1:3])**2)))}


def rebuild(out):
    runs = load_runs(out); model = fit(runs)
    # Hold out all repetitions of one condition together; still development, not new validation.
    folds = {}
    for condition in sorted({r['condition'] for r,_ in runs}):
        folds[condition] = fit([(r,a) for r,a in runs if r['condition']!=condition])
    ledger = []
    for r, a in runs:
        m = folds[r['condition']]
        ledger.append({'run':r['run'],'condition':r['condition'], 'split':'leave_whole_condition_out_development',
                       **evaluate(m,a), 'fold_delay_s':m['delay_s'],'fold_tau_s':m['tau_s']})
    errors = [abs(x['peak_error_deg']) for x in ledger]
    model['error_rule'] = {'empirical_peak_abs_band_deg':max(errors), 'rule':'maximum absolute peak error in 26 grouped development predictions; no coverage claim',
          'calibration_n_runs':26,'calibration_n_groups':len(folds),'statistics':'related manoeuvres; no IID/conformal guarantee',
          'tilt_screen':'upper=point+band; tilt-only skip if upper<45 and domain supported; never global skip',
          'unvalidated_reset_sequences':'ABSTAIN_FOR_SAFETY; numerical forecasts allowed for independent testing'}
    model['fit_source_manifest_sha256'] = sha(out/'input-manifest.json')
    write(out/'model.json',model)
    write(out/'development-evaluation.json', {'rows':ledger,'fit_on_all':[{'run':r['run'],**evaluate(model,a)} for r,a in runs],
          'independent_validation_n':0, 'height':'not fitted; all overall-safety decisions abstain'})
    with (out/'development-evaluation.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(ledger[0]));w.writeheader();w.writerows(ledger)
    return model


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path)
    p.add_argument('--prepare',action='store_true');args=p.parse_args();out=args.output.resolve()
    if args.prepare:
        out.mkdir(parents=True,exist_ok=False);prepare(out)
    model = rebuild(out)
    print(json.dumps(model,ensure_ascii=False,indent=2))


if __name__=='__main__':main()

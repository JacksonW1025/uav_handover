#!/usr/bin/env python3
"""Direct P12 execution-state audit; known-command replay, not plant prediction."""
import argparse,json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p9_model import sha,write
from p11.observe import stats
from output_chain import read_trace

DTYPE=np.dtype([(k,'<u8') for k in ['sim_us','sample_us','consume_ns','filter_ns','end_ns']]+
    [(k,'<f8') for k in ['dt','command','filter_before','filter_after','joint','scaled_joint','thrust',
        'torque_x','torque_y','torque_z','tau_up','tau_down','slowdown','motor_constant']])
OLD=np.dtype([(k,'<u8') for k in ['sim_us','new_sample_us','applied_sample_us','wall_ns','arrival_ns']]+
    [('received','<u4'),('flags','<u4'),('command','<f8')])


def step(f,u,dt,up=.0125,down=.025):
    a=np.exp(-dt/np.where(u>f,up,down))
    return a*f+(1-a)*u


def bound(e,u,dt,up=.0125,down=.025):
    # Segment derivative alpha is in [rho_up,rho_down], including branch crossing.
    lo=np.exp(-dt/up);hi=np.exp(-dt/down)
    return np.maximum(lo*e+(1-lo)*u,hi*e+(1-hi)*u)


def audit(run,out):
    out.mkdir(parents=True,exist_ok=False);reports={};traces={}
    for i in range(4):
        path=run/f'gz-motor/execution-p12-{i}.bin';old=run/f'gz-motor/motor-{i}.bin'
        if not path.exists():raise FileNotFoundError(path)
        if path.stat().st_size%DTYPE.itemsize:raise RuntimeError('truncated execution row '+str(path))
        d=np.fromfile(path,dtype=DTYPE);motor,o,trailing=read_trace(old)
        if motor!=i or trailing:raise RuntimeError('legacy trace header/trailing bytes')
        if not len(d):raise RuntimeError('empty execution trace')
        one=step(d['filter_before'],d['command'],d['dt'],d['tau_up'],d['tau_down'])
        f=float(d['filter_before'][0]);rec=[]
        for r in d:
            f=step(f,r['command'],r['dt'],r['tau_up'],r['tau_down']);rec.append(f)
        j=np.searchsorted(o['sim_us'],d['sim_us']);covered=(j<len(o))
        same_old=bool(covered.all() and np.array_equal(o['sim_us'][j],d['sim_us']) and
            np.array_equal(o['applied_sample_us'][j],d['sample_us']) and np.array_equal(o['ref_motor_input'][j],d['command']))
        connection=float(np.max(abs(d['filter_before'][1:]-d['filter_after'][:-1])))
        error=np.abs(d['scaled_joint'])-d['filter_before']
        steady=np.abs(d['filter_before']-d['command'])
        reports[str(i)]={'rows':len(d),'raw_sha256':sha(path),'raw_bytes':path.stat().st_size,
            'initial_filter_direct_rad_s':float(d['filter_before'][0]),
            'initial_joint_direct_rad_s':float(d['joint'][0]),'single_max_rad_s':float(np.max(abs(one-d['filter_after']))),
            'continuous_max_rad_s':float(np.max(abs(np.array(rec)-d['filter_after']))),
            'state_connection_max_rad_s':connection,'non4ms_edges':int(np.sum(np.diff(d['sim_us'].astype(np.int64))!=4000)),
            'old_consumption_trace_match':same_old,'old_rows_without_execution':len(o)-len(d),
            'filter_vs_steady_command_rad_s':stats(steady),'joint_abs_minus_filter_before_rad_s':stats(error),
            'thrust_magnitude_formula_max_N':float(np.max(abs(abs(d['thrust'])-d['motor_constant']*d['scaled_joint']**2))),
            'consumption_to_filter_us':stats((d['filter_ns'].astype(np.int64)-d['consume_ns'].astype(np.int64))/1000),
            'filter_to_trace_end_us':stats((d['end_ns'].astype(np.int64)-d['filter_ns'].astype(np.int64))/1000),
            'finite':all(bool(np.isfinite(d[k]).all()) for k in DTYPE.names),
            'replay_scope':'all physical steps; initialize once from actual internal first filter-before; known commands/dt only'}
        traces['motor_'+str(i)]=d
    gates={i:bool(r['finite'] and r['single_max_rad_s']<1e-9 and r['continuous_max_rad_s']<1e-9 and
        r['state_connection_max_rad_s']<1e-12 and r['non4ms_edges']==0 and r['old_consumption_trace_match'] and
        r['old_rows_without_execution']==0 and r['thrust_magnitude_formula_max_N']<1e-9) for i,r in reports.items()}
    np.savez_compressed(out/'execution.npz',**traces)
    result={'schema':'p12-execution-audit-1','run':str(run),'status':'PASS' if all(gates.values()) else 'FAIL',
        'row_bytes':DTYPE.itemsize,'motors':reports,'gates':gates,'actual_joint_not_filter_setpoint':True,
        'force_order':'force and torque from current joint state BEFORE filter update and joint command',
        'future_bound':'only source filter relation proved; joint tracking residual is observed, no future hard bound supplied'}
    write(out/'execution.json',result);print(json.dumps({'status':result['status'],'motors':{i:{k:r[k] for k in ['rows','continuous_max_rad_s','old_rows_without_execution']} for i,r in reports.items()}}));return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=audit(a.run,a.output);raise SystemExit(r['status']!='PASS')

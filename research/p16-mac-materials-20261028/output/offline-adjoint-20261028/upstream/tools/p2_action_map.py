#!/usr/bin/env python3
"""Fit RAPTOR's action -> actuator_motors map from P1 RAPTOR baseline logs and check it against ActionMap.hpp.

Pairs research_timing.action (control steps that published under arbitration) with the actuator_motors row of the
same observation (timestamp_sample). For each motor, least squares over all four actions plus offset; the motor order
is the dominant coefficient. Writes action-map.json into a new output directory; never edits runs.
"""
import argparse,hashlib,json,re
from pathlib import Path
import numpy as np
from pyulog import ULog
ROOT=Path(__file__).resolve().parents[1]
HEADER=ROOT/'research/state/ActionMap.hpp'

def header_map(path=HEADER):
    """Constants used by the C++ conversion (single source of truth for Python checks)."""
    text=path.read_text()
    order=[int(x) for x in re.search(r'MOTOR_OF_ACTION\[4\]=\{([^}]*)\}',text).group(1).split(',')]
    scale=float(re.search(r'MOTOR_SCALE=([-0-9.e]+)f',text).group(1));offset=float(re.search(r'MOTOR_OFFSET=([-0-9.e]+)f',text).group(1))
    return {'motor_of_action':order,'scale':scale,'offset':offset}

def motor_to_action(motor,mapping=None):
    """Python mirror of handover_research::motor_to_action: (action[4] or None, clipped count)."""
    mapping=mapping or header_map();motor=np.asarray(motor,float)
    m=motor[mapping['motor_of_action']]
    if not np.all(np.isfinite(m)):return None,0
    a=(m-mapping['offset'])/mapping['scale'];clipped=int(np.sum((a>1)|(a<-1)))
    return np.clip(a,-1,1),clipped

def pairs(run):
    u=ULog(str(run/'flight.ulg'),['research_timing','actuator_motors'])
    t={d.name:d.data for d in u.data_list if d.multi_id==0}
    rt,am=t['research_timing'],t['actuator_motors']
    index={int(s):i for i,s in enumerate(am['timestamp_sample'])}
    published=rt['actuator_published'].astype(bool)&rt['control_step'].astype(bool)
    rows=[(i,index[int(s)]) for i,s in enumerate(rt['timestamp_sample']) if published[i] and int(s) in index]
    a=np.array([[rt[f'action[{k}]'][i] for k in range(4)] for i,_ in rows],float)
    m=np.array([[am[f'control[{k}]'][j] for k in range(4)] for _,j in rows],float)
    return a,m,int(published.sum())

def fit(runs):
    A=[];M=[];sources=[]
    for run in runs:
        a,m,n=pairs(run);A.append(a);M.append(m)
        sources.append({'run':str(run.relative_to(ROOT)),'published_steps':n,'paired':len(a),'ulog_sha256':hashlib.sha256((run/'flight.ulg').read_bytes()).hexdigest()})
    A=np.vstack(A);M=np.vstack(M);X=np.c_[A,np.ones(len(A))];motors=[]
    for j in range(4):
        c,*_=np.linalg.lstsq(X,M[:,j],rcond=None);k=int(np.argmax(np.abs(c[:4])))
        motors.append({'motor':j,'coefficients_action_0_3_offset':c.tolist(),'dominant_action':k,
            'max_abs_residual':float(np.max(np.abs(X@c-M[:,j]))),'off_diagonal_max_abs':float(np.max(np.abs(np.delete(c[:4],k))))})
    order=[None]*4
    for m in motors:order[m['dominant_action']]=m['motor']
    scale=float(np.mean([m['coefficients_action_0_3_offset'][m['dominant_action']] for m in motors]))
    offset=float(np.mean([m['coefficients_action_0_3_offset'][4] for m in motors]))
    return {'pairs':int(len(A)),'sources':sources,'per_motor':motors,'fitted':{'motor_of_action':order,'scale':scale,'offset':offset},
        'action_range_observed':[A.min(0).tolist(),A.max(0).tolist()],'motor_range_observed':[M.min(0).tolist(),M.max(0).tolist()]}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('runs',type=Path,nargs='+');a=p.parse_args()
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    result=fit([r.resolve() for r in a.runs]);header=header_map();f=result['fitted']
    result['header']={'path':str(HEADER.relative_to(ROOT)),'sha256':hashlib.sha256(HEADER.read_bytes()).hexdigest(),**header}
    result['header_matches_fit']=(f['motor_of_action']==header['motor_of_action'] and abs(f['scale']-header['scale'])<1e-5
        and abs(f['offset']-header['offset'])<1e-5 and all(m['max_abs_residual']<1e-5 and m['off_diagonal_max_abs']<1e-5 for m in result['per_motor']))
    result['inverse']='action[k] = (motor[motor_of_action[k]] - offset) / scale, clipped to [-1, 1] and counted (research/state/ActionMap.hpp)'
    result['tool_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (out/'action-map.json').write_text(json.dumps(result,indent=2)+'\n')
    print('pairs',result['pairs'],'fitted',f,'header_matches_fit',result['header_matches_fit'])
    return 0 if result['header_matches_fit'] else 1
if __name__=='__main__':raise SystemExit(main())

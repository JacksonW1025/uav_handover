#!/usr/bin/env python3
"""Independent exact reconstruction of the weight matrices, without theory.py."""
import argparse,json,sys
from pathlib import Path
from fractions import Fraction as Q
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p3_memory import load_policy
from p9_model import write,sha


def verify(path,out):
    doc=json.loads(path.read_text());p=load_policy();errors=[]
    # Dyadic32 weights are converted exactly; no float matrix product is trusted.
    absolute=lambda name:[[Q(float(abs(v))) for v in row] for row in p[name]]
    recurrent=absolute('Wh');incoming=absolute('Wi');dense=absolute('W0');output=absolute('W2')
    H=[[Q(0) for j in range(16)] for i in range(16)];X=[[Q(0) for j in range(22)] for i in range(16)]
    for i in range(16):
        candidate_bound=sum(recurrent[32+i])+Q(float(abs(p['bh'][32+i])))
        for j in range(16):
            H[i][j]=Q(i==j)+recurrent[32+i][j]+candidate_bound*recurrent[i][j]/4+recurrent[16+i][j]/2
        for j in range(22):
            X[i][j]=sum((incoming[32+i][k]+candidate_bound*incoming[i][k]/4+incoming[16+i][k]/2)*dense[k][j] for k in range(16))
    for key,value in [('H',H),('X',X),('A_abs',output)]:
        got=[[Q(v) for v in row] for row in doc[key]]
        if got!=value:errors.append(key)
    for key,matrix in [('action_H',H),('action_X',X)]:
        got=[[Q(v) for v in row] for row in doc[key]]
        expected=[[sum(output[i][k]*matrix[k][j] for k in range(16)) for j in range(len(matrix[0]))] for i in range(4)]
        if got!=expected:errors.append(key)
    if doc['policy_sha256']!=p['sha256']:errors.append('policy identity')
    result={'schema':'p12-independent-weight-audit-1','status':'PASS' if not errors else 'FAIL',
        'errors':errors,'input_sha256':sha(path),'policy_sha256':p['sha256'],
        'scope':'exact coefficient construction plus separately stated analytic proof; not complete feedback certificate'}
    if out.exists():raise FileExistsError(out)
    write(out,result);print(json.dumps(result));return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('matrices',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=verify(a.matrices,a.output);raise SystemExit(r['status']!='PASS')

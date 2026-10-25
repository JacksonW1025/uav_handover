#!/usr/bin/env python3
"""Re-extract all8 source logs, refit bounded candidates and check published cores.

Never overwrites evidence. Raw ULogs are local-only; missing sources fail loudly.
Full integer sequence audits can additionally be rerun with independent_audit.py.
"""
import argparse
import hashlib
import os
from fractions import Fraction as F
import json
from pathlib import Path
import subprocess
import time
from data import ROOT,extract,sha,write
from experiment import load_inputs,fit_models
from metric_audit import check
from contract_counterexample import calculate
from bench import load

BASE=ROOT/'data/p10-20261025-a4'

def main(out):
    out.mkdir(parents=True,exist_ok=False);start=time.perf_counter()
    extract(out/'inputs')
    files={p.name:sha(p) for p in (out/'inputs').iterdir() if p.is_file()}
    assert files=={p.name:sha(p) for p in (BASE/'inputs-interface').iterdir() if p.is_file()},'EXTRACTION_DIFFERENCE'
    runs=load_inputs(out/'inputs');models,trials=fit_models(runs)
    models={'models':models,'finite_q_trials':trials,'fit_runs':[r['run'] for r,a in runs if r['role']=='fit'],
        'check_runs':[r['run'] for r,a in runs if r['role']!='fit'],'prospective':False,'height_model':False}
    expected=json.loads((BASE/'model-comparison/models.json').read_text())
    # Fit output has no measured runtime fields; exact equality checks all12
    # trials, not only the winning model or a preselected PASS label.
    assert models==expected,'REFIT_DIFFERENCE'
    write(out/'models.json',models)
    metric=check(BASE/'structure/structure.json');assert metric==json.loads((BASE/'metric-audit/audit.json').read_text())
    write(out/'metric.json',metric)
    counter=calculate();assert counter==json.loads((BASE/'contract-counterexample-final/counterexample.json').read_text())
    write(out/'counterexample.json',counter)
    b=load();assert len(b['rows'])==7350
    comparisons=[]
    for name in ['T0','C04','CR06']:
        first=json.loads((BASE/f'audit-{name}/audit.json').read_text());last=json.loads((BASE/f'audits-final/{name}/audit.json').read_text())
        keys=set(first)-{'elapsed_s','verifier_sha256'}
        assert all(first[k]==last[k] for k in keys),'AUDIT_CORE_DIFFERENCE'
        r=last['first_capture_parameter_constraint'];L=F(r['velocity_norm_upper']);E=F(r['capture_velocity_vector_error_upper']);alpha=F(r['alpha_sufficient_lower'])
        assert (1-alpha)*L+alpha*E==1 and L>1 and 0<alpha<1
        comparisons.append({'case':name,'same_core_keys':sorted(keys),'first_audit_sha256':sha(BASE/f'audit-{name}/audit.json'),
            'final_audit_sha256':sha(BASE/f'audits-final/{name}/audit.json'),'alpha_identity_exact':True})
    # All tracked historical research evidence is compared against immutable
    # A3 main. New A4 files are intentionally absent from that baseline.
    baseline='5b6dc8c4aa021e06de5fcc853b734cf222d94cfd'
    tracked=subprocess.check_output(['git','ls-tree','-r',baseline],cwd=ROOT,text=True).splitlines()
    missing=[];changed=[]
    for line in tracked:
        info,path=line.split('\t',1);mode,kind,expected_blob=info.split()
        p=ROOT/path
        if not p.is_file() and not p.is_symlink():missing.append(path);continue
        content=os.readlink(p).encode() if mode=='120000' else p.read_bytes()
        current=hashlib.sha1(b'blob '+str(len(content)).encode()+b'\0'+content).hexdigest()
        if current!=expected_blob:changed.append(path)
    assert not missing and not changed,{'missing':missing,'changed':changed}
    write(out/'reproduction.json',{'schema':'p10-a4-reproduction-1','input_files_byte_identical':files,'refit_exact_equality':True,
        'metric_exact_equality':True,'counterexample_exact_equality':True,'two_independent_audit_execution_cores':comparisons,
        'historical_baseline':baseline,'tracked_historical_files_compared':len(tracked),'historical_missing':missing,'historical_changed':changed,
        'scope':'re-extraction/refit/exact metric/counter + comparison of two completed full sequence audits; does not claim a third full-audit run',
        'elapsed_s':time.perf_counter()-start,'new_SITL_starts':0})
    print(json.dumps({'input_files':len(files),'historical_files':len(tracked),'elapsed_s':time.perf_counter()-start}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);main(p.parse_args().output)

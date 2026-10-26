#!/usr/bin/env python3
"""P12: mount no future data into the predictor; copy only sanitized inputs and outputs."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from p9_model import sha,write


def predict(packed,models,out):
    if out.exists():raise FileExistsError(out)
    tmp=Path(tempfile.mkdtemp(prefix='p12-blind-'));inputs=tmp/'input';output=tmp/'output';inputs.mkdir();output.mkdir()
    doc=json.loads((packed/'prediction-input.json').read_text());fit=json.loads((models/'fit.json').read_text())
    if doc['policy_sha256']!=fit['policy_tar_sha256'] or sha(models/'policy.npz')!=fit['policy_arrays_sha256']:
        raise RuntimeError('policy identity mismatch')
    doc['model_sha256']=sha(models/'models.json');write(inputs/'input.json',doc)
    for name in ['models.json','policy.npz']:shutil.copy2(models/name,inputs/name)
    command=['bwrap','--ro-bind','/','/','--tmpfs',str(ROOT/'data'),'--tmpfs',str(ROOT/'export'),
        '--unshare-net','--unshare-pid','--proc','/proc','--bind',str(output),str(output),'--chdir',str(ROOT),
        'taskset','-c','0-3',str(ROOT/'uav_lab/.local/venv/bin/python'),str(ROOT/'tools/p12c/predict.py'),
        '--input',str(inputs/'input.json'),'--models',str(inputs/'models.json'),'--policy',str(inputs/'policy.npz'),
        '--output',str(output/'prediction')]
    started=time.monotonic()
    with (tmp/'child.log').open('w') as log:code=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT).returncode
    if code:
        out.mkdir(parents=True,exist_ok=False);shutil.copy2(tmp/'child.log',out/'child.log')
        write(out/'failure.json',{'code':code,'command':command,'temporary_evidence_retained':str(tmp)})
        raise RuntimeError('isolated predictor failed; preserve '+str(out))
    meta=json.loads((output/'prediction/prediction.json').read_text())
    if meta['filesystem_future_data_visible']:raise RuntimeError('future data visible')
    shutil.copytree(output/'prediction',out);shutil.copy2(inputs/'input.json',out/'sanitized-input.json');shutil.copy2(tmp/'child.log',out/'child.log')
    write(out/'isolation.json',{'schema':'p12-physical-isolation-1','command':command,'exit_code':code,
        'elapsed_s':time.monotonic()-started,'input_sha256':sha(inputs/'input.json'),
        'model_sha256':sha(inputs/'models.json'),'policy_arrays_sha256':sha(inputs/'policy.npz'),
        'future_data_hidden':True,'network_namespace':'isolated','pid_namespace':'isolated /proc, no parent-root access',
        'temporary_evidence_retained':str(tmp),'scoring_measurements_never_copied':True})
    return meta


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--packed',type=Path,required=True)
    p.add_argument('--models',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=predict(a.packed,a.models,a.output);print(json.dumps(r))

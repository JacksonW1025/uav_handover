#!/usr/bin/env python3
"""P12 no-flight reproduction into a NEW directory; requires retained local raw data."""
import argparse,json,subprocess,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
PY=ROOT/'uav_lab/.local/venv/bin/python'


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--compare',type=Path)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    def tool(script,arguments,name):
        with (a.output/(name+'.log')).open('w') as f:
            subprocess.run(['taskset','-c','0-3',str(PY),str(ROOT/'tools'/script),*map(str,arguments)],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True)
    sync=a.output/'observation/synchronized.npz'
    tool('p12/observe.py',[a.run,'--output',a.output/'observation'],'observation')
    tool('p12/audit.py',[a.run,'--output',a.output/'native'],'native')
    tool('p12/execution.py',[a.run,'--output',a.output/'execution'],'execution')
    tool('p12/target_replay.py',[sync,'--config',a.run/'config.json','--output',a.output/'target'],'target')
    tool('p11/synchronize.py',[a.run,'--output',a.output/'send-read'],'send-read')
    tool('p12/pack.py',[a.run,'--sync',sync,'--output',a.output/'packed'],'pack')
    tool('p11/pack.py',['measure',a.run,'--sync',sync,'--output',a.output/'measured'],'measure')
    tool('p12/isolated.py',['--packed',a.output/'packed','--models',ROOT/'data/p11-20261025-formal/models','--output',a.output/'prediction'],'prediction')
    tool('p11/score.py',['--predictions',a.output/'prediction','--packed',a.output/'packed','--measurement',a.output/'measured/measurement.json','--output',a.output/'score'],'score')
    comparison={}
    if a.compare:
        for path in (a.output/'prediction').glob('*.npz'):
            old=a.compare/path.name
            if not old.exists():raise FileNotFoundError(old)
            with np.load(path) as fresh,np.load(old) as prior:
                comparison[path.name]=set(fresh.files)==set(prior.files) and all(np.array_equal(fresh[k],prior[k],equal_nan=True) for k in fresh.files)
        if not all(comparison.values()):raise RuntimeError('reproduced numerical predictions differ')
    (a.output/'reproduction.json').write_text(json.dumps({'schema':'p12-reproduction-1','status':'PASS','run':str(a.run),
        'SITL_starts':0,'future_data_isolation':True,'array_comparisons':comparison,
        'scope':'known-input audits plus isolated autonomous candidate numerics; no full plant proof or formal acceptance'},indent=2)+'\n')
    print('PASS: offline reproduction; no SITL starts')


if __name__=='__main__':main()

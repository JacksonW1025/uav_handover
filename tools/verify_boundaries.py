#!/usr/bin/env python3
"""Check Git and active runtime boundaries without modifying the Lab."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args], text=True).strip()
assert not git('ls-files', 'uav_lab'), 'Lab must remain untracked'
for name in ['uav_lab/env.sh', 'data/boundary-probe/rootfs/file', 'data/boundary-probe/cli/px4-param']:
    assert git('check-ignore', name) == name
for name in ['tools/experiment', 'research/state/StateOps.hpp', 'data/final-raptor-hover/flight.ulg']:
    assert subprocess.run(['git','-C',str(ROOT),'check-ignore',name],capture_output=True).returncode == 1
for variant in ['classic','raptor']:
    result=subprocess.check_output(['bash','--noprofile','--norc','-c',
        f'set -u; source tools/lab-env.sh {variant}; env'],cwd=ROOT,text=True)
    for line in result.splitlines():
        if line.startswith(('PATH=','PYTHONPATH=','LD_LIBRARY_PATH=','AMENT_PREFIX_PATH=','CMAKE_PREFIX_PATH=','PX4_','GZ_')):
            assert not any(p in line for p in ['/home/car/uav_sf','/home/car/uav-lab','/home/car/uav3d']), line
print('PASS: Lab/runtime copies ignored; research and raw ULog retained; both overlays use current Lab')

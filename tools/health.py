#!/usr/bin/env python3
"""Read-only checks with command, exit status and evidence; no flight."""
import argparse
import datetime as dt
import importlib
import importlib.metadata as md
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / 'uav_lab'
MODULES = {'pyulog':'pyulog','pymavlink':'pymavlink','kconfiglib':'kconfiglib',
 'empy':'em','Jinja2':'jinja2','numpy':'numpy','PyYAML':'yaml','packaging':'packaging',
 'jsonschema':'jsonschema','typeguard':'typeguard','pandas':'pandas','scipy':'scipy',
 'matplotlib':'matplotlib','pytest':'pytest','psutil':'psutil','rclpy':'rclpy',
 'colcon-core':'colcon_core','pyros-genmsg':'genmsg','nunavut':'nunavut','px4_msgs':'px4_msgs'}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=ROOT/'data/environment-20261009/final-health')
    p.add_argument('--full',action='store_true')
    args = p.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True,exist_ok=True)
    result = {'timestamp': dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(),
              'python':sys.executable,'checks':[], 'dependencies':{}}
    commands = {
        'system':['uname','-a'], 'os':['cat','/etc/os-release'],
        'cpu':['lscpu'], 'memory':['free','-h'], 'disk':['df','-h',str(ROOT)],
        'gpu':['nvidia-smi'], 'cuda':['/usr/local/cuda/bin/nvcc','--version'],
        'l4t':['dpkg-query','-W','nvidia-l4t-core'],
        'compiler':['g++','--version'],'cmake':['cmake','--version'],
        'ninja':['ninja','--version'],'git':['git','--version'],
        'pip':['python','-m','pip','check'], 'gazebo':['gz','sim','--versions'],
        'ros':['ros2','pkg','list'],
        'lab':['python',str(LAB/'scripts/check_lab.py')] + (['--full'] if args.full else []),
        'tracked_lab':['git','-C',str(ROOT),'ls-files','uav_lab'],
        'ignore':['git','-C',str(ROOT),'check-ignore','uav_lab/env.sh'],
    }
    required = set(commands)-{'gpu','cuda'}
    for name, cmd in commands.items():
        try:
            proc = subprocess.run(cmd,capture_output=True,text=True,timeout=180)
            code, output = proc.returncode,proc.stdout+proc.stderr
        except (OSError,subprocess.TimeoutExpired) as e:
            code, output = -1,str(e)
        path=args.output/(name+'.log');path.write_text(output)
        passed=code==0 and not(name=='tracked_lab' and output.strip())
        result['checks'].append({'name':name,'command':cmd,'exit_code':code,
                                'status':'PASS' if passed else 'FAIL','log':str(path.relative_to(ROOT))})
        print(name, result['checks'][-1]['status'],flush=True)
    for dist, module in MODULES.items():
        try:
            obj=importlib.import_module(module)
            if module=='px4_msgs':
                expected=LAB/'workspaces'/os.environ['HANDOVER_VARIANT']/'install'
                if not Path(obj.__file__).resolve().is_relative_to(expected):raise RuntimeError('wrong px4_msgs overlay')
            try: version=md.version(dist)
            except md.PackageNotFoundError: version=getattr(obj,'__version__','ROS/system')
            result['dependencies'][dist]={'status':'PASS','version':version,'file':getattr(obj,'__file__','')}
        except Exception as e:
            result['dependencies'][dist]={'status':'FAIL','reason':str(e)}
    result['status']='PASS' if all(c['status']=='PASS' for c in result['checks'] if c['name'] in required) and all(d['status']=='PASS' for d in result['dependencies'].values()) else 'FAIL'
    (args.output/'result.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(result['status'])
    return 0 if result['status']=='PASS' else 1

if __name__=='__main__':sys.exit(main())

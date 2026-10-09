#!/usr/bin/env python3
"""Capture local source identities, modifications, submodules and installed versions."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1];LAB=ROOT/'uav_lab'
def command(args):
 p=subprocess.run(args,capture_output=True,text=True)
 return {'command':args,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 manifest=json.loads((LAB/'manifests/sources.json').read_text())
 result={'schema_version':1,'captured_at':dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(),
         'lab_root':str(LAB),'manifest':manifest,'python':sys.version,'python_executable':sys.executable,'sources':{},
         'pip':command([sys.executable,'-m','pip','list','--format=json']),
         'system_packages':command(['dpkg-query','-W','-f=${Package}\t${Version}\n','ros-jazzy-*','libgz-*','nvidia-l4t-core']),
         'build_commands':['source tools/lab-env.sh classic; make -C "$PX4_SOURCE_DIR" -j8 px4_sitl_default',
                           'source tools/lab-env.sh raptor; make -C "$PX4_SOURCE_DIR" -j8 px4_sitl_raptor',
                           'python -m colcon build --executor sequential --cmake-args -DCMAKE_BUILD_TYPE=Release -DPython3_EXECUTABLE="$VIRTUAL_ENV/bin/python"'],
         'tracked_environment_entry':'tools/lab-env.sh','runtime_config':'config/experiment.json'}
 result['tool_versions']={name:command(args) for name,args in {
     'gazebo':['gz','sim','--versions'],'compiler':['g++','--version'],
     'cmake':['cmake','--version'],'ninja':['ninja','--version'],
     'agent':['git','-C',str(LAB/'.local/checkouts/xrce-agent'),'rev-parse','HEAD']}.items()}
 result['source_manifest_sha256']=sha(LAB/'manifests/sources.json')
 result['snapshot_inventory_sha256']=sha(LAB/'manifests/snapshot-files.json')
 result['runtime_config_sha256']=sha(ROOT/'config/experiment.json')
 agent_binary=LAB/'.local/runtime/xrce-agent/bin/MicroXRCEAgent'
 result['agent_binary_sha256']=sha(agent_binary)
 for variant in ['classic','raptor']:
  p=LAB/'.local/checkouts'/('px4-'+variant)
  result['sources'][variant]={'head':command(['git','-C',str(p),'rev-parse','HEAD']),
      'origin':command(['git','-C',str(p),'remote','get-url','origin']),
      'status':command(['git','-C',str(p),'status','--short']),
      'submodules':command(['git','-C',str(p),'submodule','status','--recursive'])}
  target='px4_sitl_default' if variant=='classic' else 'px4_sitl_raptor';b=p/'build'/target
  result['sources'][variant]['binary_sha256']=sha(b/'bin/px4')
  result['sources'][variant]['boardconfig_sha256']=sha(b/'px4_boardconfig.h')
 policy=LAB/'.local/checkouts/px4-raptor/src/modules/mc_raptor/blob'
 result['policy_sha256']={p.name:sha(p) for p in [policy/'policy.h',policy/'policy.tar',policy/'benchmark.h']}
 result['policy_matches_snapshot']=all(sha(policy/name)==sha(LAB/'sources/px4-raptor/src/modules/mc_raptor/blob'/name) for name in result['policy_sha256'])
 result['patches']={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'patches').iterdir() if p.is_file()}
 (ROOT/'environment.lock').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
 print('environment.lock written; policy matches snapshot:',result['policy_matches_snapshot'])
if __name__=='__main__':main()

#!/usr/bin/env python3
"""Read-only local resource and relocation checks; never launches simulation."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

LAB = Path(__file__).resolve().parents[1] / 'uav_lab'


def run(argv, **kwargs):
    return subprocess.run(argv, capture_output=True, text=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full', action='store_true', help='Verify all vendored snapshot SHA-256 hashes')
    args = parser.parse_args()
    failures = []
    manifest = json.loads((LAB / 'manifests/sources.json').read_text())
    for entry in manifest['entries']:
        source = LAB / entry['snapshot']
        if not source.is_dir():
            failures.append('missing source: ' + entry['id'])
        if 'local_checkout' in entry:
            checkout = LAB / entry['local_checkout']
            result = run(['git', '-C', str(checkout), 'rev-parse', 'HEAD'])
            if result.returncode or result.stdout.strip() != entry['commit']:
                failures.append('missing/mismatched local Git checkout: ' + entry['id'])
            result = run(['git', '-C', str(checkout), 'submodule', 'status', '--recursive'])
            if result.returncode or any(line.startswith(('-', '+', 'U')) for line in result.stdout.splitlines()):
                failures.append('submodule mismatch: ' + entry['id'])
    for variant in ['classic', 'raptor']:
        for p in (LAB / 'workspaces' / variant / 'src').iterdir():
            if not p.exists() or not p.resolve().is_relative_to(LAB):
                failures.append('invalid ROS source link: ' + str(p.relative_to(LAB)))
        result = run(['bash', '--noprofile', '--norc', '-c',
                      'source "$1/env.sh" "$2"; /usr/bin/python3 -B -c '
                      "'import json,os; print(json.dumps(dict(os.environ)))'",
                      'lab-check', str(LAB), variant])
        if result.returncode:
            failures.append('environment load failed: ' + variant)
            continue
        environment = json.loads(result.stdout)
        for key in ['PX4_SOURCE_DIR', 'PX4_SNAPSHOT_DIR', 'PX4_RUNTIME_DIR', 'PX4_MSGS_DIR',
                    'XRCE_AGENT_SOURCE_DIR', 'RAPTOR_POLICY_DIR']:
            if not Path(environment[key]).exists() or not Path(environment[key]).resolve().is_relative_to(LAB):
                failures.append('invalid environment path: ' + key)
        banned = ['/home/car/uav-lab/', '/home/car/uav_sf/', '/home/car/px4_contract_gap/']
        for key in ['PATH', 'LD_LIBRARY_PATH', 'PYTHONPATH', 'AMENT_PREFIX_PATH',
                    'COLCON_PREFIX_PATH', 'CMAKE_PREFIX_PATH', 'GZ_SIM_RESOURCE_PATH',
                    'GZ_SIM_SYSTEM_PLUGIN_PATH']:
            if any(old in environment.get(key, '') for old in banned):
                failures.append('old repository in active environment: ' + key)
        binaries = [LAB / '.local/runtime/xrce-agent/bin/MicroXRCEAgent',
                    Path(environment['PX4_RUNTIME_DIR']) / 'bin/px4',
                    *sorted({p for directory in environment['GZ_SIM_SYSTEM_PLUGIN_PATH'].split(':') for p in Path(directory).glob('*.so')})]
        for binary in binaries:
            if not binary.exists():
                failures.append('missing runtime: ' + str(binary.relative_to(LAB)))
                continue
            dependencies = run(['ldd', str(binary)], env=environment)
            if dependencies.returncode or 'not found' in dependencies.stdout or any(
                    old in dependencies.stdout for old in banned):
                failures.append('runtime dependency failure: ' + str(binary.relative_to(LAB)))
        agent = run([str(LAB / 'scripts/MicroXRCEAgent'), 'udp4', '--help'], env=environment)
        if agent.returncode:
            failures.append('Agent help failed: ' + variant)
    if args.full:
        inventory = json.loads((LAB / 'manifests/snapshot-files.json').read_text())
        for item in inventory['files']:
            p = LAB / item['path']
            if 'link' in item:
                valid = p.is_symlink() and os.readlink(p) == item['link']
            elif p.is_file():
                digest = hashlib.sha256()
                with p.open('rb') as f:
                    for chunk in iter(lambda: f.read(1024 * 1024), b''):
                        digest.update(chunk)
                valid = digest.hexdigest() == item['sha256']
            else:
                valid = False
            if not valid:
                failures.append('snapshot mismatch: ' + item['path'])
        print('Snapshot files checked:', len(inventory['files']))
    for failure in failures:
        print('FAIL:', failure)
    if failures:
        return 1
    print('PASS: local sources, Git identities/submodules, ROS source links, environment paths, runtime library resolution, Agent help')
    print('NOT TESTED: build, Gazebo startup, PX4 flight, DDS transport, RAPTOR inference or handover')
    return 0


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""Export source-only changes, retaining the original modifications separately."""
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT=Path(__file__).resolve().parents[1]
PX=ROOT/'uav_lab/.local/checkouts/px4-raptor'
OUT=ROOT/'patches'
OUT.mkdir(exist_ok=True)
shutil.copy2(ROOT/'uav_lab/manifests/px4-ros2-interface.existing-changes.patch',OUT/'ros2-interface-existing.patch')
(OUT/'raptor-final.patch').write_bytes(subprocess.check_output(['git','-C',str(PX),'diff','--binary']))
names=subprocess.check_output(['git','-C',str(PX),'ls-files','--others','--exclude-standard','-z']).decode().strip('\0').split('\0')
with tarfile.open(OUT/'raptor-final-untracked.tar.gz','w:gz') as archive:
    for name in names:
        if not name:continue
        source=PX/name
        assert source.is_file() and source.stat().st_size<100000, name
        archive.add(source,arcname=name)
print('Exported final diff and',len(names),'small source files; existing patches retained')

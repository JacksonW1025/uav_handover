#!/usr/bin/env python3
"""Harmless managed-process liveness probe; no PX4/Gazebo/flight or budget start."""
import json,os,time
from pathlib import Path
from datetime import datetime,timezone

out=Path(__file__).resolve().parent/'liveness.jsonl'
for i in range(21):
    record={'checked_at':datetime.now(timezone.utc).isoformat(),'index':i,'pid':os.getpid(),
            'ppid':os.getppid(),'cgroup':Path('/proc/self/cgroup').read_text().strip(),
            'monotonic_s':time.monotonic(),'no_simulation':True}
    with out.open('a') as f:f.write(json.dumps(record)+'\n');f.flush();os.fsync(f.fileno())
    if i<20:time.sleep(5)
print('PROBE_COMPLETE no simulator or flight launched',flush=True)

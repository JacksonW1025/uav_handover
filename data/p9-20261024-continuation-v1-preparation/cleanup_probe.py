#!/usr/bin/env python3
"""Intentional non-flight process failure tests scoped child cleanup, not SITL."""
from pathlib import Path
from datetime import datetime,timezone
import sys,subprocess,time,os,signal,json

base=Path(__file__).resolve().parent
def record(name,**extra):
    with (base/'cleanup-probe.jsonl').open('a') as f:
        f.write(json.dumps({'event':name,'time':datetime.now(timezone.utc).isoformat(),'pid':os.getpid(),'ppid':os.getppid(),**extra})+'\n');f.flush();os.fsync(f.fileno())
if '--child' in sys.argv:
    def stop(signum,frame):
        record('CHILD_EXPECTED_SIGINT_EXIT',signal=signum);raise SystemExit(0)
    signal.signal(signal.SIGINT,stop);record('CHILD_START',cgroup=Path('/proc/self/cgroup').read_text().strip())
    for _ in range(100):time.sleep(.2)
    record('CHILD_TIMEOUT_WITHOUT_CLEANUP');raise SystemExit(3)
p=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--child'],start_new_session=True)
record('PARENT_START',child_pid=p.pid);time.sleep(2)
record('PARENT_INTENTIONAL_FAILURE_EXIT17');raise SystemExit(17)

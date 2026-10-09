#!/usr/bin/env python3
"""Read-only audit of the process identities recorded by our SITL runs."""
import json
from pathlib import Path
import socket
import psutil

ROOT=Path(__file__).resolve().parents[1]
checked=0
for path in (ROOT/'data').glob('*/metadata.json'):
    meta=json.loads(path.read_text())
    for item in meta.get('processes',[]):
        checked+=1
        try:
            process=psutil.Process(item['pid'])
            cmd=process.cmdline()
            # A later unrelated process may reuse the PID; compare identity.
            assert cmd!=item['command'], (path,item['name'],item['pid'],cmd)
        except psutil.NoSuchProcess:pass
for port in [18888,18591]:
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
        sock.bind(('127.0.0.1',port))
print('PASS:',checked,'recorded process identities exited; experiment UDP ports available')

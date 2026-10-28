#!/usr/bin/env python3
"""After normal push, independently bind every frozen input to committed bytes and remote main."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import datetime

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from p9_model import sha,write


def committed_files(head,files):
    names=list(files)
    raw=subprocess.check_output(['git','cat-file','--batch'],input=('\n'.join(head+':'+p for p in names)+'\n').encode(),cwd=ROOT)
    pos=0
    for name in names:
        end=raw.index(b'\n',pos);header=raw[pos:end].decode().split();pos=end+1
        if len(header)!=3 or header[1]!='blob':raise RuntimeError('not committed '+name)
        size=int(header[2]);body=raw[pos:pos+size];pos+=size+1
        if hashlib.sha256(body).hexdigest()!=files[name]:raise RuntimeError('committed input bytes mismatch '+name)
    if pos!=len(raw):raise RuntimeError('unexpected git batch output')
    return len(names)


def main():
    frozen=ROOT/'data/p11-20261025-freeze';path=frozen/'receipt.json'
    if path.exists():raise FileExistsError('never replace remote freeze receipt')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    remote=subprocess.check_output(['git','ls-remote','origin','refs/heads/main'],cwd=ROOT,text=True).split()[0]
    if head!=remote:raise RuntimeError('remote main differs; no formal launch')
    manifest=json.loads((frozen/'manifest.json').read_text())
    count=committed_files(head,{**manifest['files'],str((frozen/'manifest.json').relative_to(ROOT)):sha(frozen/'manifest.json')})
    r={'schema':'p11-remote-freeze-receipt-1','commit':head,'remote_main':remote,'manifest_sha256':sha(frozen/'manifest.json'),
        'committed_files_checked':count,'normal_push_required':True,'force_push_used':False,
        'checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'formal_starts_before_receipt':0,
        'CI':'separately queried; no local test result is called CI success'}
    write(path,r);print(json.dumps(r))


if __name__=='__main__':main()

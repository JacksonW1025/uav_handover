#!/usr/bin/env python3
"""Exactly one launch of the committed continuation user unit; never a retry."""
from pathlib import Path
from datetime import datetime,timezone
import json,subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(Path(__file__).resolve().parent))
from p9_model import write
from run_v4 import verify_freeze

def main():
    prep=Path(__file__).resolve().parent;freeze=ROOT/'data/p9-20261024-continuation-v4-freeze'
    verify_freeze(freeze)
    intent=prep/'launch-intent.json'
    if intent.exists() or (ROOT/'data/p9-20261024-continuation-v4-formal').exists():raise SystemExit('existing launch/output; inspect, never automatically relaunch')
    spec=json.loads((prep/'launch-spec.json').read_text())
    state=subprocess.check_output(['systemctl','--user','show',spec['unit'],'-p','LoadState'],text=True)
    if 'LoadState=not-found' not in state:raise SystemExit('unit name already exists; do not touch it')
    write(intent,{'time':datetime.now(timezone.utc).isoformat(),'unit':spec['unit'],'command':spec['command'],'warning':'launch intent, not a flight start; per-flight START_INTENT stays in original shared ledger'})
    r=subprocess.run(spec['command'],cwd=ROOT,capture_output=True,text=True)
    write(prep/'launch-result.json',{'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'no_retry':True})
    print(r.stdout,r.stderr,flush=True)
    if r.returncode:raise SystemExit(r.returncode)


if __name__=='__main__':main()

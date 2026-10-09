#!/usr/bin/env python3
"""Run one verification command and store its exit code and exact invocation."""
import argparse
import datetime as dt
import json
from pathlib import Path
import subprocess
import os
import signal
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--name',required=True);p.add_argument('--timeout',type=float,default=300)
 p.add_argument('--output',type=Path,default=ROOT/'data/environment-20261009/final-commands');p.add_argument('command',nargs=argparse.REMAINDER)
 a=p.parse_args();cmd=a.command[1:] if a.command and a.command[0]=='--' else a.command
 if not cmd:p.error('a command is required')
 a.output.mkdir(parents=True,exist_ok=True);start=time.monotonic();log=a.output/(a.name+'.log')
 with log.open('w') as f:
  try:
   proc=subprocess.Popen(cmd,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
   code=proc.wait(timeout=a.timeout)
  except subprocess.TimeoutExpired as ex:
   os.killpg(proc.pid,signal.SIGTERM)
   try:proc.wait(timeout=5)
   except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
   code=124;f.write(str(ex)+'\n')
 result={'name':a.name,'command':cmd,'exit_code':code,'status':'PASS' if code==0 else 'FAIL','elapsed_s':time.monotonic()-start,
         'finished_at':dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(),'log':str(log.relative_to(ROOT))}
 (a.output/(a.name+'.json')).write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n');print(json.dumps(result,ensure_ascii=False));return code
if __name__=='__main__':sys.exit(main())

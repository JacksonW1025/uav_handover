#!/usr/bin/env python3
"""Finite post-flight processing; no launches, fitting, commits or scheduling changes."""
import subprocess,time,json,sys
from pathlib import Path
R=Path(__file__).resolve().parents[2];S=Path(__file__).resolve().parent;PY=R/'uav_lab/.local/venv/bin/python';P=R/'data/p12-cont-20261026-preparation';OUT=R/'data/p12-cont-20261026-delivery-v2'
while True:
 state=subprocess.check_output(['systemctl','--user','show','p12-frozen-continuation.service','-p','ActiveState','-p','ExecMainStatus'],text=True)
 if 'ActiveState=active' not in state and 'ActiveState=activating' not in state:break
 time.sleep(30)
rows=[json.loads(s) for s in (P/'attempts.jsonl').read_text().splitlines()];starts=[s for s in rows if s['event']=='START_INTENT' and s['budget_class']=='formal'];finished=[s for s in rows if s['event']=='FINISH' and s['budget_class']=='formal']
if len(starts)!=48 or len(finished)!=48 or 'ExecMainStatus=0' not in state:
 (P/'postprocess-blocked.json').write_text(json.dumps({'status':'PARTIAL_OR_CRITICAL_STOP; no more starts from this script','formal_started':len(starts),'formal_finished':len(finished),'unit':state},indent=2)+'\n');raise SystemExit(2)
for cmd in [[str(PY),str(S/'world_height.py')],[str(PY),str(S/'analyze.py'),'--output',str(OUT)],[str(PY),str(S/'extra.py'),'--analysis',str(OUT)],[str(PY),str(S/'reproduce.py'),'--run',str(R/'data/p12-cont-20261026-formal/b2-ph1-AB/run'),'--output',str(R/'data/p12-cont-20261026-reproduction-final'),'--compare',str(R/'data/p12-cont-20261026-formal/b2-ph1-AB/analysis')],[str(PY),str(S/'raw_manifest.py'),str(OUT/'all-raw-derived-history-manifest.json')]]:
 subprocess.run(['taskset','-c','0-3',*cmd],cwd=R,check=True)
(P/'postprocess-complete.json').write_text(json.dumps({'status':'ANALYSIS_REPRODUCTION_HASHES_COMPLETE','formal_started':48,'new_SITL_starts':0,'output':str(OUT),'remaining':'human-readable report/figures/final audit and normal publication, no extra flights'},indent=2)+'\n')
print('POSTPROCESS_COMPLETE_NO_NEW_SITL',flush=True)

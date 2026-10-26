#!/usr/bin/env python3
"""Four remaining preparation starts, explicit window candidate, no retries."""
import subprocess,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p12c.workflow import process
PY=ROOT/'uav_lab/.local/venv/bin/python';PREP=ROOT/'data/p12-cont-20261026-preparation';A=ROOT/'data/p12-cont-20261026-analysis';D=ROOT/'data/p12-cont-20261026-development'
for name in ['window-09-single','window-10-single-repair','window-11-AB-repair-intermediate','window-12-AB-native']:
 subprocess.run([str(PY),'tools/p12c/run.py','--id',name,'--config',str((PREP/(name+'.json')).relative_to(ROOT))],cwd=ROOT,check=True)
 process(D/name/'run',A/name,ROOT/'data/p11-20261025-formal/models')
 gate=json.loads((A/name/'engineering.json').read_text());(PREP/('gate-'+name+'.json')).write_text(json.dumps(gate,indent=2)+'\n')
 if gate['engineering_status']!='PASS':raise RuntimeError('window candidate failed; no further starts')
 print('WINDOW_PREPARATION_PASS',name,flush=True)

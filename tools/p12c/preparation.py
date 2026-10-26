#!/usr/bin/env python3
"""Fixed remaining preparation sequence; no retries or uncounted SITL."""
import subprocess,sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];PY=ROOT/'uav_lab/.local/venv/bin/python';PREP=ROOT/'data/p12-cont-20261026-preparation';A=ROOT/'data/p12-cont-20261026-analysis';D=ROOT/'data/p12-cont-20261026-development'
ids=['f4-repeat-03','f4-repeat-04','f4-phase-05','f4-repair-06','f4-single-repair-07','f4-single-08']
for name in ids:
 if not (D/name/'wrapper-result.json').exists():
  subprocess.run([str(PY),'tools/p12c/run.py','--id',name,'--config',str((PREP/(name+'.json')).relative_to(ROOT))],cwd=ROOT,check=True)
 if not (A/name).exists():
  subprocess.run(['taskset','-c','0-3',str(PY),'tools/p12/reproduce.py','--run',str(D/name/'run'),'--output',str(A/name)],cwd=ROOT,check=True)
 gate=PREP/('gate-'+name+'.json')
 if not gate.exists():subprocess.run([str(PY),'tools/p12c/validate.py','--run',str(D/name/'run'),'--analysis',str(A/name),'--output',str(gate)],cwd=ROOT,check=True)
 if json.loads(gate.read_text())['engineering_status']!='PASS':raise RuntimeError('preparation observation error; stop affected design')
 print('PREPARATION_GATE_PASS',name,flush=True)

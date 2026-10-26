import subprocess,json,sys
from pathlib import Path
R=Path('/home/car/uav_handover');L=R/'data/p12b-20261026-preparation-v2/attempts.jsonl';PY=R/'uav_lab/.local/venv/bin/python'
for ordinal in range(4,9):
 rows=[json.loads(s) for s in L.read_text().splitlines()];plan=json.load(open(R/'data/p12b-20261026-preparation-v2/protocol.json'))['rows'][ordinal-3]
 if any(r['event']=='STOP_CRITICAL' for r in rows):raise RuntimeError('critical stop retained; do not continue')
 starts=[r for r in rows if r['event']=='START_INTENT' and r['id']==plan['id']]
 if starts:
  if any(r['event']=='FINISH' and r['id']==plan['id'] and r.get('evidence_ok') for r in rows):continue
  raise RuntimeError('already started without accepted completion; never retry')
 if not any(r['event']=='FINISH' and r.get('ordinal')==ordinal-1 and r.get('evidence_ok') for r in rows):raise RuntimeError('previous preparation not complete')
 subprocess.run([str(PY),'tools/p12b/campaign_v2.py','--prep',str(ordinal)],cwd=R,check=True)
print('P12B_PREPARATION_BUDGET8_SPENT; NO_FORMAL_AUTOSTART_FROM_THIS_UNIT',flush=True)

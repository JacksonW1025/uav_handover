"""All eight starts, separate analysis dirs; no launch and no result replacement."""
import json,sys,subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'));sys.path.insert(0,str(Path(__file__).parent))
from event_tables import create
P=R/'data/p12b-20261026-delivery';P.mkdir(exist_ok=False);E=P/'event-tables';E.mkdir()
rows=json.load(open(R/'data/p12b-20261026-preparation/protocol.json'))['rows'][:2]+json.load(open(R/'data/p12b-20261026-preparation-v2/protocol.json'))['rows'];manifest=[]
for row in rows:
 parent=R/('data/p12b-20261026-development-v2' if row['ordinal']>=3 else 'data/p12b-20261026-development')/row['id'];run=parent/'run';a=parent/'analysis';out=E/row['id']
 if not (a/'measured/measurement.json').exists():
  q=E/(row['id']+'-measurement')
  with (E/(row['id']+'-measurement.log')).open('w') as log:subprocess.run([str(R/'uav_lab/.local/venv/bin/python'),str(R/'tools/p11/pack.py'),'measure',str(run),'--sync',str(a/'observation/synchronized.npz'),'--output',str(q)],cwd=R,stdout=log,stderr=subprocess.STDOUT,check=True)
 create(run,a,out);manifest.append({'id':row['id'],'ordinal':row['ordinal'],'event_table':str((out/'event-states.json').relative_to(R)),'experiment_status':'NOT_PASSED_READ_CONTRACT' if row['ordinal']==2 else 'PREPARATION_RESULT_ONLY_NOT_FORMAL','formal_validation':False})
(P/'event-table-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print('ALL8_EVENT_TABLES_COMPLETE; no formal runs')

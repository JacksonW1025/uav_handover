import json,sys,hashlib
from pathlib import Path
import numpy as np
sys.path.insert(0,'/home/car/uav_handover/tools')
from output_chain import read_trace
root=Path('/home/car/uav_handover');out=Path('/tmp/handover3h-t3-20261116');j=json.loads((root/'data/handover-f1-sync-20261112-analysis-v1/f1-comparison.json').read_text()); result=[]
for r in j['rows']:
 if r['arm']=='E1':continue
 c=r['chain'];read=c['first_read_us'];run=root/'data/handover-f1-sync-20261112'/(r['case']+'-a1')/'flight'
 rec={'case':r['case'],'first_valid_read_us':read,'motors':[]}
 for path in sorted((run/'gz-motor').glob('motor-*.bin')):
  mid,m,tail=read_trace(path);assert tail==0
  exact=np.flatnonzero(m['applied_sample_us']==read);idx=int(exact[0]) if len(exact) else None
  rows=[]
  for row in m[(m['sim_us']>=read-8000)&(m['sim_us']<=read+12000)]:
   rows.append({name:float(row[name]) if name=='ref_motor_input' else int(row[name]) for name in ['sim_us','applied_sample_us','new_sample_us','received','flags','ref_motor_input']})
  rec['motors'].append({'motor':mid,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'first_exact_read_sample_application_us':int(m['sim_us'][idx]) if idx is not None else None,'delay_ms':(int(m['sim_us'][idx])-read)/1000 if idx is not None else None,'rows':rows})
 result.append(rec)
(out/'analysis/restore-application.json').write_text(json.dumps(result,indent=2)+'\n')
for r in result:print(r['case'],[x['delay_ms'] for x in r['motors']])

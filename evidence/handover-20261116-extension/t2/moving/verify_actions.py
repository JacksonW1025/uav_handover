import json
from pathlib import Path
import numpy as np
from pyulog import ULog
P=Path(__file__).resolve().parent;d=json.loads((P/'results.json').read_text());out=[]
for c in d['cases']:
 u=ULog(c['path']+'/flight.ulg',['research_timing','research_memory']);topics={v.name:v.data for v in u.data_list if v.multi_id==0};t=topics['research_timing'];m=topics['research_memory'];case={'case':c['name'],'frames':[]}
 for f in c['frames']:
  idx=np.where(t['timestamp']==f['time_us'])[0];all_err=[]
  for j in idx:
   a=np.array([t[f'action[{i}]'][j] for i in range(4)]);all_err.append(float(np.max(np.abs(a-np.clip(f['variants']['both']['raw_action'],-1,1)))))
  row={'time_us':f['time_us'],'candidate_rows':len(idx),'minimum_clipped_action_error':min(all_err) if all_err else None}
  if f['offset_s']==0:
   q=np.where((m['timestamp']<=f['time_us'])&(m['kind']==2))[0][-1];v=np.array([m[f'previous_action[{i}]'][q] for i in range(4)]);row['entry_input_max_error']=float(np.max(np.abs(v-f['previous_action_input'])));row['entry_mode']=int(m['entry_mode'][q]);row['entry_us']=int(m['timestamp'][q])
  case['frames'].append(row)
 out.append(case)
(P/'action-verification.json').write_text(json.dumps(out,indent=2)+'\n');err=[f['minimum_clipped_action_error'] for c in out for f in c['frames']];assert all(e is not None and e<1e-5 for e in err);print('36 sampled native actions verified; max error',max(err));print([(c['case'],c['frames'][0].get('entry_mode'),c['frames'][0].get('entry_input_max_error')) for c in out])

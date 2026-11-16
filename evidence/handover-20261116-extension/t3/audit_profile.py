from pyulog import ULog
from pathlib import Path
import json,numpy as np,csv
P=Path('/tmp/handover-t3-semantics-20261116/flight-analysis');j=json.loads((P/'summary.json').read_text());out=[]
for r in j['cases']:
 u=ULog(str(Path('/home/car/uav_handover')/r['execution']['flight']/'flight.ulg'),message_name_filter_list=['research_target','research_p11']);ds={d.name:d.data for d in u.data_list if d.multi_id==0};d=ds['research_target'];p=ds['research_p11'];a=r['activation_us'];b=r['first_valid_reference_read_us'];ix=np.flatnonzero((d['timestamp']>=a)&(d['timestamp']<=b+10000));fields=list(d)
 rows=[{k:d[k][i].item() for k in fields} for i in ix];end=[x for x in rows if x['kind']==3 and x['end_reason']==1];cap=[x for x in rows if x['kind']==1 and x['activation']]
 selected=np.flatnonzero((p['timestamp']>=a)&(p['timestamp']<=b+16000)&p['native_step'].astype(bool));csvkeys=['timestamp']+[f'{k}[{i}]' for k in ['network_target_position','network_target_velocity','position','velocity'] for i in range(3)]
 with (P/(r['case']+'-target-native.csv')).open('w') as f:
  w=csv.writer(f);w.writerow(csvkeys);w.writerows([[p[k][i].item() for k in csvkeys] for i in selected])
 after=np.flatnonzero((p['timestamp']>=r['first_neural_publication_us'])&(p['timestamp']<=r['first_neural_publication_us']+2000000)&p['native_step'].astype(bool))
 out.append({'case':r['case'],'capture_records':cap,'profile_end_external_records':end,'target_event_rows':rows,'first2s_vx_min':float(p['velocity[0]'][after].min()),'first2s_vx_max':float(p['velocity[0]'][after].max()),'mode':int(d['mode'][ix[0]])})
(P/'profile-audit.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps([{k:x[k] for k in ['case','mode','capture_records','profile_end_external_records','first2s_vx_min','first2s_vx_max']} for x in out],indent=2))

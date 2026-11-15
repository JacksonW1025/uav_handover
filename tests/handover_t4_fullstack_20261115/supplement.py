from pathlib import Path
import json,numpy as np
from pyulog import ULog
R=Path(__import__('os').environ['HANDOVER_RESEARCH_ROOT']);A=Path(__file__).parent;data=json.loads((A/'evidence.json').read_text())
for r in data:
 path=R/'data/handover-t4-fullstack-20261115'/r['case']/'flight';u=ULog(str(path/'flight.ulg'),message_name_filter_list=['vehicle_local_position','vehicle_attitude','vehicle_angular_velocity','research_p11','vehicle_status','vehicle_command_ack']);d={z.name:z.data for z in u.data_list if z.multi_id==0};t=r['first_N_publication'];snap={}
 for topic,fields in [('vehicle_local_position',['x','y','z','vx','vy','vz']),('vehicle_attitude',[f'q[{i}]' for i in range(4)]),('vehicle_angular_velocity',[f'xyz[{i}]' for i in range(3)])]:
  z=d[topic];i=int(np.searchsorted(z['timestamp'],t,side='right')-1);snap[topic]={'age_us':t-int(z['timestamp'][i]),**{k:float(z[k][i]) for k in fields}}
 p=d['research_p11'];ix=np.flatnonzero((p['timestamp']>=t-50000)&(p['timestamp']<=t+100000));r['entry']=snap;r['p11_entry']=[{k:float(v[i]) for k,v in p.items() if k in ['timestamp','active','external_valid','last_valid_read_us','activation'] or k.startswith(('network_target_velocity','network_target_position','gru_before','previous_action_before'))} for i in ix]
 s=d['vehicle_status'];ix=np.flatnonzero((s['timestamp']>=t-50000)&(s['timestamp']<=t+20000));r['nav_rows']=[{k:int(s[k][i]) for k in ['timestamp','nav_state','arming_state']} for i in ix];ak=d['vehicle_command_ack'];ix=np.flatnonzero((ak['timestamp']>=t-50000)&(ak['timestamp']<=t+20000));r['ack_rows']=[{k:int(ak[k][i]) for k in ['timestamp','command','result']} for i in ix]
(A/'evidence.json').write_text(json.dumps(data,indent=2)+'\n')

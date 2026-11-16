from pyulog import ULog
from pathlib import Path
import json,numpy as np,hashlib
D=Path('/tmp/handover3h-t3-20261116/flight-analysis');j=json.loads((D/'summary.json').read_text());out=[]
for row in j['cases']:
 path=Path('/home/car/uav_handover')/row['execution']['flight']/'flight.ulg';u=ULog(str(path),message_name_filter_list=['research_p11','trajectory_setpoint']);ds={d.name:d.data for d in u.data_list if d.multi_id==0};d=ds['research_p11'];s=ds['trajectory_setpoint'];ix=np.flatnonzero(d['timestamp']==row['first_valid_reference_read_us'])[0];ts=int(d['external_timestamp'][ix]);matches=np.flatnonzero(s['timestamp']==ts);assert len(matches)==1;mi=matches[0]
 fields=[f'position[{i}]' for i in range(3)]+[f'velocity[{i}]' for i in range(3)]+['yaw','yawspeed'];actual=np.array([s[k][mi] for k in fields],dtype=np.float32);send=row['first_send'];expected=np.array(send['position']+send['velocity']+[send['yaw'],send['yawspeed']],dtype=np.float32)
 assert np.array_equal(actual,expected)
 out.append({'case':row['case'],'read_native_us':row['first_valid_reference_read_us'],'source_message_timestamp_us':ts,'fields':fields,'accepted_payload':actual.tolist(),'sent_payload_float32':expected.tolist(),'accepted_matches_sent_exactly_float32':True,'float32_payload_sha256':hashlib.sha256(actual.tobytes()).hexdigest(),'validation':{'P11_external_valid':bool(d['external_valid'][ix]),'P11_subscription_updated':bool(d['subscription_updated'][ix]),'P11_network_position_velocity_yaw_matches':row['first_adopted_position_velocity_yaw_matches_plan_float32']}})
assert out[0]['float32_payload_sha256']==out[1]['float32_payload_sha256'];(D/'accepted-payload.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))

from pathlib import Path
import numpy as np,json
from pyulog import ULog
P=Path(__file__).resolve().parent;summary=json.loads((P/'feedforward-summary.json').read_text());out={}
for arm in ['FF','NOFF']:
 u=ULog('/tmp/handover3h-t1-feedforward-20261116/'+arm+'/flight/flight.ulg');d={z.name:z.data for z in u.data_list if z.multi_id==0};l=d['vehicle_local_position'];s=d['trajectory_setpoint'];st=summary[arm]['profile_lower_us'];phase=(l['timestamp'].astype(float)-st)/1e6/1.25;ix=np.searchsorted(s['timestamp'],l['timestamp'],side='right')-1;ix=np.maximum(ix,0)
 pos=np.array([l[k] for k in ['x','y','z']]).T;ref=np.array([s[f'position[{i}]'][ix] for i in range(3)]).T;v=np.array([l[k] for k in ['vx','vy','vz']]).T;vr=np.array([s[f'velocity[{i}]'][ix] for i in range(3)]).T;e=np.linalg.norm((pos-ref)[:,:2],axis=1);ve=np.linalg.norm((v-vr)[:,:2],axis=1);m=(phase>=4)&(phase<=7);stop=np.argmin(abs(phase-5));out[arm]={'horizontal_position_error_max_late':float(e[m].max()),'horizontal_velocity_error_max_late':float(ve[m].max()),'stop_position_error':float(e[stop]),'stop_horizontal_speed':float(np.linalg.norm(v[stop,:2]))}
 np.savetxt(P/(arm+'-tracking.csv'),np.column_stack([phase[m],e[m],ve[m]]),delimiter=',',header='normalized_phase,horizontal_position_error,horizontal_velocity_error',comments='')
(P/'feedforward-tracking.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))

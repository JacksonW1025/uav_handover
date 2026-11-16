from pathlib import Path
import json,hashlib
import numpy as np
from pyulog import ULog
P=Path(__file__).resolve().parent;u=ULog(str(P.parent/'t1-triplet/C2/flight/flight.ulg'));d={z.name:z.data for z in u.data_list if z.multi_id==0};start=49308000;lo=start+5380000;hi=start+5750000;s=d['trajectory_setpoint'];o=d['vehicle_local_position_setpoint'];c=d['vehicle_control_mode'];l=d['vehicle_land_detected'];summ={}
for name,z in [('received_reference',s),('classic_output',o)]:
 m=(z['timestamp']>=lo)&(z['timestamp']<=hi);a=np.array([z[f'acceleration[{i}]'][m] for i in range(3)]).T;ts=z['timestamp'][m];ci=np.maximum(np.searchsorted(c['timestamp'],ts,side='right')-1,0);li=np.maximum(np.searchsorted(l['timestamp'],ts,side='right')-1,0)
 summ[name]={'rows':len(ts),'all_acceleration_finite':bool(np.isfinite(a).all()),'acceleration_norm_max':float(np.max(np.linalg.norm(a,axis=1))),'multicopter_position_control_enabled_values':np.unique(c['flag_multicopter_position_control_enabled'][ci]).tolist(),'offboard_values':np.unique(c['flag_control_offboard_enabled'][ci]).tolist(),'landed_values':np.unique(l['landed'][li]).tolist(),'first_timestamp':int(ts[0]),'last_timestamp':int(ts[-1]),'example_acceleration':a[len(a)//2].tolist()}
(P/'classic-acceleration-consumption.json').write_text(json.dumps({'native_window_us':[lo,hi],'evidence':summ},indent=2));print(json.dumps(summ,indent=2))

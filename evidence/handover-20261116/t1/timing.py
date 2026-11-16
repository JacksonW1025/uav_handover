import json,sys
from pathlib import Path
import numpy as np
from pyulog import ULog
sys.path.insert(0,'/home/car/uav_handover/tools')
from output_chain import read_trace
P=Path(__file__).resolve().parent;B=Path('/tmp/handover3h-thor-20261116');R=json.loads((P/'results.json').read_text());out={}
for arm in ['N','PRE']:
 f=B/arm/'flight';u=ULog(str(f/'flight.ulg'));d={x.name:x.data for x in u.data_list if x.multi_id==0};p=d['research_p11'];o=d['research_actuator'];a=R['arms'][arm]
 i=np.flatnonzero((p['native_step']==1)&(p['active']==1))[0];oi=np.flatnonzero(o['owner']==1)[0]
 z={'first_active_native_us':int(p['timestamp'][i]),'first_neural_actuator_us':int(o['actuator_timestamp'][oi]),'profile_lower_us':a['profile_lower_us'],'marker_us':a['marker_us'],'first_four_motor_application_us':{}}
 for m in range(4):
  _,tr,_=read_trace(f/'gz-motor'/f'motor-{m}.bin');idx=np.searchsorted(o['actuator_timestamp'],tr['applied_sample_us'],side='right')-1;ok=(idx>=0)&(o['owner'][np.maximum(idx,0)]==1)&(o['actuator_timestamp'][np.maximum(idx,0)]==tr['applied_sample_us']);j=np.flatnonzero(ok)[0];z['first_four_motor_application_us'][m]=int(tr['sim_us'][j])
 z['first_active_profile_s']=(z['first_active_native_us']-a['profile_lower_us'])/1e6
 out[arm]=z
(P/'timing.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))

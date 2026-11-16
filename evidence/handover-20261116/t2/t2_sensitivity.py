#!/usr/bin/env python3
import sys,json
from pathlib import Path
import numpy as np
sys.path.insert(0,'/home/car/uav_handover/tools')
import p3_memory as r
out=Path('/tmp/handover3h-t2-20261116');P=r.load_policy();base=json.loads((out/'fixed-frame.json').read_text());rows=[]
for record in base['records']:
 x0=np.r_[record['input_physical_reference'],record['actual_action_input']];h0=np.array(record['prepared_gru']);prev=(x0[18:][[0,2,3,1]]+1)/2
 for hg in [0,.25,.5,.75,1]:
  for ag in [0,.25,.5,.75,1]:
   x=x0.copy();x[18:]*=ag;h=h0*hg
   encoded=np.maximum(0,x@P['W0'].T+P['b0']);gi=encoded@P['Wi'].T+P['bi'];gh=h@P['Wh'].T+P['bh'];sig=lambda z:1/(1+np.exp(-z));reset=sig(gi[:16]+gh[:16]);update=sig(gi[16:32]+gh[16:32]);candidate=np.tanh(gi[32:]+reset*gh[32:]);hn=(1-update)*candidate+update*h
   raw=hn@P['W2'].T+P['b2'];motor=(np.clip(raw,-1,1)[[0,2,3,1]]+1)/2
   rows.append({'run':record['run'],'gru_fraction':hg,'action_fraction':ag,'max_motor_delta':float(np.max(np.abs(motor-prev))),'mean_motor_delta':float(np.mean(motor-prev)),'encoded_relu':encoded.tolist(),'reset_gate':reset.tolist(),'update_gate':update.tolist(),'candidate_state':candidate.tolist(),'gru_next':hn.tolist(),'raw_action':raw.tolist()})
(out/'sensitivity.json').write_text(json.dumps({'kind':'fixed recorded inputs, synthetic memory interpolation, one step only','rows':rows},indent=2)+'\n')
for hg in [0,.25,.5,.75,1]:
 print(hg,[round(float(np.mean([v['max_motor_delta'] for v in rows if v['gru_fraction']==hg and v['action_fraction']==ag])),5) for ag in [0,.25,.5,.75,1]])
print('zero action with full GRU gate-change vs both')
for rec in base['records']:
 a=next(v for v in rows if v['run']==rec['run'] and v['gru_fraction']==1 and v['action_fraction']==0); b=next(v for v in rows if v['run']==rec['run'] and v['gru_fraction']==1 and v['action_fraction']==1)
 print(rec['run'],{k:float(np.linalg.norm(np.array(a[k])-b[k])) for k in ['encoded_relu','reset_gate','update_gate','gru_next']})

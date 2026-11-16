#!/usr/bin/env python3
"""Thor-only, read-only one-step GRU/previous-action ablation on recorded active entry.
No simulator, no parameters or source modified. Writes only requested output.
Use frozen p3_memory.py implementation and policy; all physical/reference inputs fixed.
"""
import argparse, hashlib, importlib.util, json, sys
from pathlib import Path
import numpy as np
from pyulog import ULog

ap=argparse.ArgumentParser()
ap.add_argument('--root',type=Path,required=True)
ap.add_argument('--policy',type=Path,required=True)
ap.add_argument('--output',type=Path,required=True)
ap.add_argument('runs',nargs='+',type=Path)
a=ap.parse_args()
sys.path.insert(0,str(a.root/'tools'))
import p3_memory as replay
P=replay.load_policy(a.policy)
example_error=float(replay.example_check(P))
if example_error>1e-5:raise RuntimeError('policy bundled-example mismatch')
records=[]
for run in a.runs:
    meta=json.loads((run/'metadata.json').read_text())
    if meta.get('policy_sha256')!=P['sha256']:raise RuntimeError('policy identity mismatch: '+str(run))
    u=ULog(str(run/'flight.ulg'),['research_memory','raptor_input','vehicle_status'])
    ts={d.name:d.data for d in u.data_list if d.multi_id==0}
    vs=ts['vehicle_status'];armed=vs['timestamp'][vs['arming_state']==2]
    seq=[s for s in replay.native_sequence(ts['research_memory'],ts['raptor_input']) if armed[0]<=s['t']<=armed[-1]]
    v=replay.validate(P,seq)
    if v['steps_over_1e-5']:raise RuntimeError('native baseline validation failed: '+str(run))
    candidates=[(i,s) for i,s in enumerate(seq) if s['active'] and s['entry'] is not None and s['x'] is not None]
    if len(candidates)<2:raise RuntimeError('expected a second prepared takeover: '+str(run))
    i,s=candidates[-1]
    x=np.asarray(s['x']).copy(); h=np.asarray(s['entry']).copy()
    if not s['source'].startswith('research_memory.policy_input'):raise RuntimeError('require exact policy input')
    result={'run':run.name,'policy_sha256':P['sha256'],'ulog_sha256':hashlib.sha256((run/'flight.ulg').read_bytes()).hexdigest(),
      'native_validation':v,'entry_us':s['t'],'entry_count':len(candidates),'input_physical_reference':x[:18].tolist(),
      'actual_action_input':x[18:].tolist(),'prepared_gru':h.tolist(),'logged_committed_gru':s['gru'].tolist(),'variants':{}}
    for label,keep_h,keep_action in [('reset',False,False),('action_only',False,True),('gru_only',True,False),('both',True,True)]:
        xx=x.copy();xx[18:]=x[18:] if keep_action else 0
        hh=h.copy() if keep_h else np.zeros_like(h)
        hn=replay.gru_step(P,hh,xx);raw=hn@P['W2'].T+P['b2'];clip=np.clip(raw,-1,1)
        # action order 0,1,2,3 maps to motors 0,3,1,2.
        motor=(clip[[0,2,3,1]]+1)/2
        previous_motor=(x[18:][[0,2,3,1]]+1)/2
        result['variants'][label]={'gru_after':hn.tolist(),'raw_action':raw.tolist(),'clipped_action':clip.tolist(),
           'motor_control':motor.tolist(),'action_clip_components':int(np.sum(raw!=clip)),
           'max_motor_change_from_logged_action_input':float(np.max(np.abs(motor-previous_motor))),
           'gru_delta_from_observed':float(np.linalg.norm(hn-s['gru']))}
    result['both_gru_max_error']=float(np.max(np.abs(np.asarray(result['variants']['both']['gru_after'])-s['gru'])))
    if result['both_gru_max_error']>1e-5:raise RuntimeError('prepared frame mismatch')
    records.append(result)
out={'kind':'new fixed-frame policy replay, not a flight','example_max_abs_error':example_error,'records':records,
 'interpretation':'First native inference, physical/reference input fixed. Motor change is relative to the exact averaged previous-action input, not a measured actuator-step counterfactual. No closed-loop trajectory is generated.'}
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'output':str(a.output),'frames':len(records),'variants_per_frame':4,'policy_sha256':P['sha256']}))


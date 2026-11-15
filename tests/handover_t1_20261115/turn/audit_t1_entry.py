import os
import sys,json,pathlib,numpy as np
from pyulog import ULog
ROOT=pathlib.Path(os.environ['HANDOVER_RESEARCH_ROOT']);sys.path.insert(0,str(ROOT/'tools'))
from output_chain import read_trace
from analyze import clean
base=ROOT/'data/handover-t1-turn-20261115-v1';f=base/'N/flight';u=ULog(str(f/'flight.ulg'));d={x.name:x.data for x in u.data_list if x.multi_id==0};p=d['research_p11'];o=d['research_actuator'];mem=d['research_memory'];sends=[json.loads(s) for s in (f/'explore-setpoints.jsonl').read_text().splitlines()];a=int(np.flatnonzero((p['timestamp']>52000000)&(p['activation']==1))[0]);pub=52564000;g=int(np.flatnonzero((p['timestamp']<=pub)&(p['native_step']==1))[-1]);m=int(np.flatnonzero((mem['timestamp']==p['timestamp'][a])&(mem['kind']==2))[0]);out={'activation_us':int(p['timestamp'][a]),'first_published_command_generated_at_us':int(p['timestamp'][g]),'first_generation_stale':int(p['stale'][g]),'first_generation_ref_age_us':int(p['timestamp'][g]-p['last_valid_read_us'][g]),'entry_gru_max_abs_difference':float(max(abs(mem[f'gru[{i}]'][m]-mem[f'gru_before_entry[{i}]'][m]) for i in range(16))),'entry_action':[float(mem[f'previous_action[{i}]'][m]) for i in range(4)],'entry_classic_action':[float(mem[f'classic_action[{i}]'][m]) for i in range(4)],'classic_action_publication_us':int(mem['classic_actuator_timestamp'][m]),'matching_sends':[],'late_window':{},'motors':{}}
payload=np.array([p[f'network_target_position[{j}]'][g] for j in range(3)]+[p[f'network_target_velocity[{j}]'][g] for j in range(3)],dtype=np.float32)
for s in sends:
 if np.array_equal(np.array(s['position']+s['velocity'],dtype=np.float32),payload):out['matching_sends'].append(s)
lo=53288000;hi=55288000;wm=(p['timestamp']>=lo)&(p['timestamp']<=hi);out['late_window']=dict(start_us=lo,end_us=hi,stale=int(p['stale'][wm].sum()),native_steps=int(p['native_step'][wm].sum()),activation=int(p['activation'][wm].sum()),max_reference_age_us=int((p['timestamp'][wm]-p['last_valid_read_us'][wm]).max()))
for j in range(4):
 mid,z,tail=read_trace(f/'gz-motor'/f'motor-{j}.bin');zz=z[(z['sim_us']>=lo)&(z['sim_us']<=hi)];ii=np.searchsorted(o['actuator_timestamp'],zz['applied_sample_us'],side='right')-1;at=z[np.searchsorted(z['sim_us'],p['timestamp'][a])];out['motors'][str(j)]=dict(late_max_age_us=int((zz['sim_us']-zz['applied_sample_us']).max()),late_max_gap_us=int(np.diff(zz['sim_us']).max()),late_owner_values=np.unique(o['owner'][ii]).tolist(),late_identity_match=bool(np.all(o['actuator_timestamp'][ii]==zz['applied_sample_us'])),sample_applied_at_activation_us=int(at['applied_sample_us']),tail_bytes=tail)
(base/'analysis-v1/entry-and-late-audit.json').write_text(json.dumps(clean(out),indent=2)+'\n');print(json.dumps(clean(out),indent=2))

import sys,json,hashlib
from pathlib import Path
import numpy as np
from pyulog import ULog
sys.path.insert(0,'tools')
from p11.observe import network
from p3_memory import load_policy
p=Path('data/p11-20261025-formal/F5-r2-NORMAL');d=dict(np.load(p/'observation/synchronized.npz'));P=load_policy();hh,raw,a=network(P,d['h_before'],d['input']);expected=np.where(d['committed'][:,None],hh,d['h_before'])
T={x.name:x.data for x in ULog(str(p/'run/flight.ulg'),['research_timing']).data_list};t=T['research_timing'];wanted=t['timestamp_sample'][t['active'].astype(bool)&t['control_step'].astype(bool)]
dt=np.diff(d['native_us'].astype(np.int64));wall=np.diff(d['run_wall_ns'].astype(np.int64));idx=np.flatnonzero(dt<=0)
r={'schema':'p11-stopped-observation-forensics-1','admitted_to_formal_results':False,'original_gate':'STOPPED; report JSON serialization failed, unchanged','rows':len(d['sample_us']),'sample_non4ms_edges':int(np.sum(np.diff(d['sample_us'].astype(np.int64))!=4000)),'missing_control_samples':len(set(wanted)-set(d['sample_us'])),'single_h_error':float(np.max(abs(expected-d['h_after']))),'single_action_error':float(np.max(abs(a-d['action']))),'continuous_h_error':float(np.max(abs(d['continuous_replayed'][:,:16]-d['h_after']))),'continuous_action_error':float(np.max(abs(d['continuous_replayed'][:,16:20]-d['action']))),'clock_nonpositive_native_edges':idx.tolist(),'clock_edges':[{'index':int(i),'native_us':d['native_us'][max(0,i-1):i+3].tolist(),'sample_us':d['sample_us'][max(0,i-1):i+3].tolist(),'run_wall_ns':d['run_wall_ns'][max(0,i-1):i+3].tolist()} for i in idx],'positive_native_wall_ratio_range':[float(np.min(wall[dt>0]/dt[dt>0]/1000)),float(np.max(wall[dt>0]/dt[dt>0]/1000))],'meaning':'one native hrt catch-up plateau, not lost 4ms sample calls. Existing diagnostic ratio is undefined at zero native delta; strict JSON refused inf. No tool/source/protocol update, no promotion to valid formal evidence and no pending restart.'}
Path('data/p11-20261025-preparation/stopped-observation-forensics.json').write_text(json.dumps(r,indent=2)+'\n');print(r)

import json,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,'tools')
from p12.execution import DTYPE
from p11.score import so3

def load(run,analysis):
 d=dict(np.load(analysis/'observation/synchronized.npz'))
 h=dict(np.load(analysis/'native/history.npz'))
 sends=[json.loads(s) for s in (run/'p11-sends.jsonl').read_text().splitlines()]
 t0=next(s['stream_t0_monotonic_s'] for s in sends if s['stream_t0_monotonic_s'] is not None)*1e9
 d['t']=(d['run_wall_ns'].astype(np.int64)-t0)/1e9
 d['mean']=h['history_before'];d['count']=h['count_before'];d['call_index']=h['call_before']
 for k in ['filter_after','scaled_joint','command','sample_us','end_ns']:
  a=[]
  for motor in range(4):
   e=np.fromfile(run/f'gz-motor/execution-p12-{motor}.bin',DTYPE)
   j=np.searchsorted(e['end_ns'],d['run_wall_ns'],side='right')-1
   if np.any(j<0):raise RuntimeError('no past execution')
   a.append(e[k][j])
  d['exec_'+k]=np.array(a).T
 return d

def compare(d,e,window):
 i=np.flatnonzero((d['t']>=window[0])&(d['t']<window[1]));j=np.searchsorted(e['t'],d['t'][i]);j=np.clip(j,1,len(e['t'])-1)
 j=np.where(abs(e['t'][j-1]-d['t'][i])<abs(e['t'][j]-d['t'][i]),j-1,j)
 out={'rows':len(i),'max_alignment_ms':float(max(abs(d['t'][i]-e['t'][j]))*1000),'continuous':{},'discrete':{}}
 for k in ['position','velocity','omega','h_before','previous','mean','exec_filter_after','exec_scaled_joint','exec_command']:
  x=d[k][i]-e[k][j];out['continuous'][k]={'max_l2':float(np.linalg.norm(x,axis=1).max()),'max_component':float(abs(x).max())}
 out['continuous']['SO3_deg']={'max':float(so3(d['attitude'][i],e['attitude'][j]).max())}
 out['continuous']['absolute_world_height_m']={'max':float(abs(d['truth_pv'][i,2]-e['truth_pv'][j,2]).max())}
 for k in ['count','committed','stale']:
  out['discrete'][k]=int(np.sum(d[k][i]!=e[k][j]))
 for k in ['lp_sample','att_sample','native_us']:
  out['discrete'][k+'_offset']=int(np.sum((d['sample_us'][i].astype(np.int64)-d[k][i].astype(np.int64))!=(e['sample_us'][j].astype(np.int64)-e[k][j].astype(np.int64))))
 return out

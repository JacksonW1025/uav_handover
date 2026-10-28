"""Actual prefix covariates, scoring-only. Never a model or selector input."""
import json,numpy as np
from pathlib import Path
from p16.common import B
from p12b.read_trace import load
from p12.execution import DTYPE

def extract(rid):
 t=B/'runs'/rid;run=t/'run';a=next(x for x in [t/'analysis-v2',t/'analysis-v1'] if (x/'result.json').exists() and json.load(open(x/'result.json'))['valid']);d=np.load(a/'observation/synchronized.npz');ev=[json.loads(x) for x in (run/'events.jsonl').read_text().splitlines()];epoch=next(x['run_wall_ns'] for x in ev if x['event']=='p12_confirmed_native_stream_anchor');ix=np.flatnonzero(d['read_wall_ns']<epoch);assert len(ix);i=int(ix[-1]);sample=int(d['sample_us'][i]);native=int(d['native_us'][i]);dr=load(run/'gz-motor/read-p12b.bin');matches=np.flatnonzero((dr['timestamp_sample']==sample)&(dr['timestamp']==native));assert len(matches)==1;j=int(matches[0]);filters=[];commands=[];ages=[]
 for rotor in range(4):
  a=np.fromfile(run/f'gz-motor/execution-p12-{rotor}.bin',DTYPE);js=np.flatnonzero(a['end_ns']<d['read_wall_ns'][i]);assert len(js);z=a[int(js[-1])];filters.append(float(z['filter_after']));commands.append(float(z['command']));ages.append((int(d['read_wall_ns'][i])-int(z['end_ns']))/1000)
 return dict(id=rid,LP_p=d['position'][i].tolist(),LP_v=d['velocity'][i].tolist(),estimated_q=d['attitude'][i].tolist(),gyro_cache=d['omega'][i].tolist(),h=d['h_after'][i].tolist(),previous=d['action'][i].tolist(),mean=d['input'][i,18:].tolist(),count=0 if d['committed'][i] else 1,call_index=int(dr['call_index_pre'][j])+1,target_p=d['target_p'][i].tolist(),target_v=d['target_v'][i].tolist(),stale=bool(d['stale'][i]),sample_us=sample,native_us=native,native_minus_sample_us=native-sample,LP_age_us=sample-int(d['lp_sample'][i]),att_age_us=sample-int(d['att_sample'][i]),last_valid_read_age_us=native-int(dr['last_valid_read_post'][j]),filter=filters,last_consumed_command=commands,execution_age_us=ages,profile_s=(int(d['run_wall_ns'][i])-epoch)/1e9,read_complete_before_epoch=bool(d['read_wall_ns'][i]<epoch),scope='actual completedprestream state, only posthoc score/initialdifference; not fed into autonomousforecast/query/update; LP/estimatedq not physicaltruth',exact_pending_transport=None)

def difference(a,b):
 out={k:float(np.linalg.norm(np.array(a[k])-b[k])) for k in ['LP_p','LP_v','gyro_cache','h','previous','mean','target_p','target_v']};qa=np.array(a['estimated_q']);qb=np.array(b['estimated_q']);out['estimated_SO3_deg']=float(np.degrees(2*np.arccos(np.clip(abs(qa@qb)/(np.linalg.norm(qa)*np.linalg.norm(qb)),-1,1))));out['filter_max_rad_s']=float(np.max(abs(np.array(a['filter'])-b['filter'])));out['call_index_difference']=a['call_index']-b['call_index'];out['discrete']={k:dict(first=a[k],second=b[k],equal=a[k]==b[k]) for k in ['count','stale','native_minus_sample_us','LP_age_us','att_age_us','last_valid_read_age_us']};return out

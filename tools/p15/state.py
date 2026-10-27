"""Decision-time completed controller row. Physical raw is buffered until exit,
therefore COM is NEVER used as a live ranking input on this platform.
"""
import re,os,time
import numpy as np
from p12b.read_trace import dtype
from p12.execution import DTYPE as EX
from p11.models import tilt,speeds
ARRAYS={'position':3,'velocity':3,'attitude':4,'angular_velocity':3,'network_target_position':3,'network_target_velocity':3,'gru_after':16,'previous_action_after':4,'policy_input':22,'executor_action':4}
INTS=['timestamp','timestamp_sample','sequence','run_wall_ns','read_wall_ns','last_valid_read_us','local_position_sample','attitude_sample']
BOOLS=['active','stale','gru_committed','external_valid','subscription_updated']

def parse(text):
 d={}
 for key,n in ARRAYS.items():
  m=re.search(r'^\s*'+key+r':\s*\[([^\]]+)\]',text,re.M)
  if not m:raise ValueError('missing live array '+key)
  a=np.array([float(x) for x in m.group(1).split(',')]);assert a.shape==(n,) and np.isfinite(a).all(),key;d[key]=a.tolist()
 for key in INTS:
  m=re.search(r'^\s*'+key+r':\s*(\d+)',text,re.M);assert m,key;d[key]=int(m[1])
 for key in BOOLS:
  m=re.search(r'^\s*'+key+r':\s*(True|False)',text,re.M);assert m,key;d[key]=m[1]=='True'
 m=re.search(r'^\s*target_yaw:\s*([^\s]+)',text,re.M);assert m;d['target_yaw']=float(m[1]);return d

def tail(path,dt,n=12):
 fd=os.open(path,os.O_RDONLY)
 try:
  k=os.fstat(fd).st_size//dt.itemsize;assert k>0
  return np.frombuffer(os.pread(fd,min(n,k)*dt.itemsize,(k-min(n,k))*dt.itemsize),dt).copy()
 finally:os.close(fd)

def capture(exp,label):
 lo=time.monotonic_ns();text=exp.command('listener','research_p11','-n','1',timeout=.1);hi=time.monotonic_ns();d=parse(text);assert d['active'];assert 0<=hi-d['run_wall_ns']<=40_000_000,'live completed row too old'
 rows=tail(exp.out/'gz-motor/read-p12b.bin',dtype(),32);r=rows[(rows['timestamp']==d['timestamp'])&(rows['timestamp_sample']==d['timestamp_sample'])];assert len(r)==1,'live P11/direct samecall not available';r=r[0];assert r['timing_initialized_pre'] and r['force_sync_initialized_pre'] and r['force_sync_pre']==2
 ex=[]
 for k in range(4):
  a=tail(exp.out/f'gz-motor/execution-p12-{k}.bin',EX,32);a=a[a['end_ns']<=hi];assert len(a);ex.append({key:float(a[-1][key]) if a.dtype[key].kind=='f' else int(a[-1][key]) for key in a.dtype.names})
 d.update(publisher_last_profile_s=exp.stream_state.get('last_t',None),label=label,query_before_ns=lo,available_by_ns=hi,profile_s=(d['run_wall_ns']/1e9-exp.stream_t0),call_index=int(r['call_index_pre'])+1,force_sync=2,history=d['policy_input'][18:22],history_count=0 if d['gru_committed'] else 1,direct={n:int(r[n]) for n in r.dtype.names},execution=ex,LP_H_m=-d['position'][2],LP_W_m_s=d['velocity'][2],tilt_deg=float(tilt(d['attitude'])),cache_age_us={'LP':d['timestamp_sample']-d['local_position_sample'],'attitude':d['timestamp_sample']-d['attitude_sample']},physical_online='UNAVAILABLE: P13 physical buffer flushed at process exit. No future COM used for ranking.',precision='listener float decimal5, direct identity exact; actual raw full precision retained for independent postflight verification',execution_age_ms=[(hi-x['end_ns'])/1e6 for x in ex],execution_timing='stdio execution flushed every25 steps (~100ms); stored states retain their actual ages, not asserted current filter',pending='transport pending identity UNKNOWN; latest NN action and last consumed command separate',source_interval='LP/att copy inside [run_wall_ns,read_wall_ns]; h/history/action available by query return, no instantaneous full state claim')
 return d

"""P14R raw passive records: valid committed prefixes, no missing-field zeros."""
import struct
from pathlib import Path
import numpy as np
HEAD=struct.Struct('<8s7Q')
CORE=np.dtype([(n,'<u8') for n in ['wall_ns','native_us','sample_us','kind','sequence']]+[('data','<f4',128),('ids','<u8',16),('geo','<f8',8)])
FUSION=np.dtype([('core',CORE),('time','<u8',64),('vertical_time','<u8',64),('state','<f4',(64,10)),('vertical','<f4',(64,3))])
assert CORE.itemsize==744 and FUSION.itemsize==5096
def read(path,dtype,magic,allow_incomplete=False):
 path=Path(path)
 with path.open('rb') as f:h=f.read(HEAD.size)
 if len(h)!=HEAD.size:raise ValueError('short header '+str(path))
 v=HEAD.unpack(h);head=dict(zip(['magic','version','bytes','capacity','count','dropped','errors','complete'],v))
 if v[0]!=magic or head['version']!=1 or head['bytes']!=dtype.itemsize:raise ValueError('schema '+str(path))
 if head['errors'] or head['count']>head['capacity']:raise ValueError('record write/count failure '+str(path))
 if not allow_incomplete and not head['complete']:raise ValueError('incomplete file; explicit prefix mode required')
 need=HEAD.size+head['count']*dtype.itemsize
 if path.stat().st_size<need:raise ValueError('committed prefix truncated')
 a=np.fromfile(path,dtype,offset=HEAD.size,count=head['count']);seq=a['core']['sequence'] if dtype==FUSION else a['sequence']
 if not np.array_equal(seq,np.arange(len(a))):raise ValueError('sequence/committed-prefix mismatch')
 head['magic']=head['magic'].decode();head['file_bytes']=path.stat().st_size;head['committed_bytes']=need
 return a,head

def audit(run,out):
 import json,sys
 sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
 from p14.common import write,sha
 run=Path(run);out=Path(out);out.mkdir(parents=True,exist_ok=False)
 core,ch=read(run/'gz-motor/observer-core.bin',CORE,b'P14RCORE',True);fusion,fh=read(run/'gz-motor/observer-fusion.bin',FUSION,b'P14RFUS1',True);gyro,gh=read(run/'gz-motor/observer-gyro.bin',CORE,b'P14RGYRO',True)
 pre=core[core['kind']==1];post=core[core['kind']==2];fpre=fusion[fusion['core']['kind']==3];fpost=fusion[fusion['core']['kind']==4]
 gates={'complete_or_committed_prefix':all(h['count']>0 and h['errors']==h['dropped']==0 for h in [ch,fh,gh]),'single_output_owner':len(np.unique(core['ids'][:,13]))==1,'single_gyro_owner':len(np.unique(gyro['ids'][:,1]))==1,'propagation_pairs':len(pre)==len(post) and np.array_equal(pre['sample_us'],post['sample_us']),'fusion_pairs':len(fpre)==len(fpost) and np.array_equal(fpre['core']['sample_us'],fpost['core']['sample_us']),'full_ring_capacity':bool(np.max(fusion['core']['ids'][:,2])<=64 and np.max(fusion['core']['ids'][:,6])<=64 and not np.any(fusion['core']['ids'][:,12])),'post_sample_identity':np.array_equal(post['sample_us'],post['ids'][:,10]),'core_finite':bool(np.isfinite(core['data']).all()),'gyro_finite':bool(np.isfinite(gyro['data']).all()),'fusion_finite':bool(np.isfinite(fusion['state']).all() and np.isfinite(fusion['vertical']).all()),'native_monotone':bool(np.all(np.diff(core['native_us'].astype(np.int64))>=0))}
 # Do not demand complete=1 to discard otherwise committed abnormal prefix.
 # Full-event coverage is checked independently against actual task timestamps.
 summary={'schema':'p14r-observer-audit-1','status':'PASS' if all(gates.values()) else 'DATA_QUARANTINE','gates':gates,'headers':[ch,fh,gh],'propagation_pairs':len(post),'fusion_pairs':len(fpost),'gyro_rows':len(gyro),'reset_align_kinds':dict(zip(*[x.tolist() for x in np.unique(core['kind'],return_counts=True)])),'ring_lengths':np.unique(fusion['core']['ids'][:,2]).tolist(),'sample_range_us':[int(post['sample_us'][0]),int(post['sample_us'][-1])],'files':{str(p):sha(p) for p in (run/'gz-motor').glob('observer-*.bin')},'full_EKF_covariance':'not recorded; OutputPredictor state is a separate scoped interface','no_future_bound_from_residual':True}
 write(out/'audit.json',summary)
 if not all(gates.values()):raise RuntimeError('observer record gates '+str([k for k,v in gates.items() if not v]))
 return summary

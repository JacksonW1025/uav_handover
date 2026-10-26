"""P12b direct-v2 native records. Never reconstruct absent old fields."""
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2]
TYPES={'uint64':'<u8','uint32':'<u4','int32':'<i4','bool':'u1'}
def dtype():
 fields=[('magic','<u4'),('version','<u4'),('sequence','<u8'),('prior_write_failures','<u8')]
 for line in (R/'research/state/ResearchP12b.msg').read_text().splitlines():
  if not line or line.startswith('#') or '=' in line:continue
  t,n=line.split();fields.append((n,TYPES[t]))
 return np.dtype(fields,align=False)
def load(path):
 dt=dtype()
 if path.stat().st_size%dt.itemsize:raise RuntimeError('partial direct read trace row')
 a=np.fromfile(path,dt)
 if not len(a) or not np.all(a['magic']==0x42325250) or not np.all(a['version']==2):raise RuntimeError('direct read trace header/schema')
 if not np.array_equal(a['sequence'],np.arange(len(a))) or np.any(a['prior_write_failures']):raise RuntimeError('direct read trace sequence/write failure')
 return {k:a[k] for k in a.dtype.names}

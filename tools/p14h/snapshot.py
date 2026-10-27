"""Full crossP passive rows. Header complete0 is a committed-prefix contract."""
import struct,numpy as np
from pathlib import Path
HEAD=struct.Struct('<8s7Q');ROW=np.dtype([(n,'<u8') for n in ['sequence','wall_ns','native_us','delayed_us','latest_us','flags','nstate','ndof']]+[('state','<f4',32),('covariance','<f4',(32,32)),('imu','<f4',8)])
assert ROW.itemsize==4320

def read(path):
 path=Path(path)
 with path.open('rb') as f:h=HEAD.unpack(f.read(64))
 d=dict(zip(['magic','version','bytes','capacity','count','dropped','errors','complete'],h));assert h[0]==b'P14HEKF1' and d['bytes']==ROW.itemsize and d['count']<=d['capacity'];assert path.stat().st_size>=64+d['count']*ROW.itemsize
 a=np.memmap(path,dtype=ROW,mode='r',offset=64,shape=(d['count'],));assert np.array_equal(a['sequence'],np.arange(len(a)));d['magic']=d['magic'].decode();return a,d

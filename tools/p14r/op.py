"""Actual source OutputPredictor via isolated ABI, no log access in this class."""
import ctypes as C,base64
import numpy as np
F=C.POINTER(C.c_float);D=C.POINTER(C.c_double)
def fp(x):return np.ascontiguousarray(x,dtype=np.float32)
def dp(x):return np.ascontiguousarray(x,dtype=np.float64)
class Op:
 def __init__(self,library,initial):
  self.lib=C.CDLL(str(library));L=self.lib
  L.p14r_create.argtypes=[C.c_void_p];L.p14r_create.restype=C.c_void_p;L.p14r_free.argtypes=[C.c_void_p]
  L.p14r_advance.argtypes=[C.c_void_p,C.c_uint64,F,F,C.c_float];L.p14r_fuse.argtypes=[C.c_void_p,C.c_uint64,F,F,D,F,F];L.p14r_outputs.argtypes=[C.c_void_p,F,F,D,F];L.p14r_fields.argtypes=[C.c_void_p,F]
  L.p14r_snapshot.argtypes=[C.c_void_p,C.c_void_p]
  L.p14r_add_ned.argtypes=[D,F,D];L.p14r_sub_geo.argtypes=[D,D,F];L.p14r_project.argtypes=[D,D,F]
  blob=base64.b64decode(initial['fusion_base64']);assert len(blob)==5096;b=C.create_string_buffer(blob);self.pointer=L.p14r_create(C.cast(b,C.c_void_p));assert self.pointer
  for row in initial['past_operations']:
   if row['kind']==1:self.advance(row['sample_us'],row['delta_angle'],row['delta_velocity'],row['dt'])
   elif row['kind']==3:self.fuse(row['sample_us'],row['q'],row['v'],row['geo'],row['bg'],row['ba'])
 def advance(self,sample,da,dv,dt=.004):
  a,b=fp(da),fp(dv);self.lib.p14r_advance(self.pointer,int(sample),a.ctypes.data_as(F),b.ctypes.data_as(F),float(dt))
 def fuse(self,sample,q,v,geo,bg,ba):
  q,v,g,bg,ba=fp(q),fp(v),dp(geo),fp(bg),fp(ba);self.lib.p14r_fuse(self.pointer,int(sample),q.ctypes.data_as(F),v.ctypes.data_as(F),g.ctypes.data_as(D),bg.ctypes.data_as(F),ba.ctypes.data_as(F))
 def outputs(self):
  q,v,g,c=fp(np.zeros(4)),fp(np.zeros(3)),dp(np.zeros(3)),fp(np.zeros(3));self.lib.p14r_outputs(self.pointer,q.ctypes.data_as(F),v.ctypes.data_as(F),g.ctypes.data_as(D),c.ctypes.data_as(F));return q,v,g,c
 def fields(self):
  x=fp(np.zeros(31));self.lib.p14r_fields(self.pointer,x.ctypes.data_as(F));return x
 def add(self,g,d):
  g,d,out=dp(g),fp(d),dp(np.zeros(3));self.lib.p14r_add_ned(g.ctypes.data_as(D),d.ctypes.data_as(F),out.ctypes.data_as(D));return out
 def sub(self,g,anchor):
  g,a,out=dp(g),dp(anchor),fp(np.zeros(3));self.lib.p14r_sub_geo(g.ctypes.data_as(D),a.ctypes.data_as(D),out.ctypes.data_as(F));return out
 def project(self,g,anchor):
  g,a,out=dp(g),dp(anchor),fp(np.zeros(3));self.lib.p14r_project(g.ctypes.data_as(D),a.ctypes.data_as(D),out.ctypes.data_as(F));return out
 def snapshot(self):
  b=C.create_string_buffer(5096);self.lib.p14r_snapshot(self.pointer,C.cast(b,C.c_void_p));return b.raw
 def close(self):
  if self.pointer:self.lib.p14r_free(self.pointer);self.pointer=None

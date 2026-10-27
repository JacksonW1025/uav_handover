"""Exact finite float decision-state projection, separate fromfull EKF state."""
import ctypes as C
class State(C.Structure):_fields_=[('avg',C.c_float),('acc',C.c_float),('target',C.c_float),('minimum',C.c_float),('count',C.c_int32),('required',C.c_int32),('processed',C.c_uint64)]
class Cadence:
 def __init__(self,path,target_us=10000,state=None):
  self.lib=C.CDLL(str(path));self.lib.p14h_init.argtypes=[C.POINTER(State),C.c_int];self.lib.p14h_push.argtypes=[C.POINTER(State),C.c_float,C.c_int];self.lib.p14h_push.restype=C.c_int;self.target_us=target_us;self.state=State();self.lib.p14h_init(C.byref(self.state),target_us)
  if state:
   for k,_ in State._fields_:setattr(self.state,k,state[k])
 def push(self,dt):return bool(self.lib.p14h_push(C.byref(self.state),float(dt),self.target_us))
 def dump(self):return {k:getattr(self.state,k) for k,_ in State._fields_}

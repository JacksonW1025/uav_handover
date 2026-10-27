"""Independent SITL runner entry: passive P snapshot + bounded resume release.
Real source timeout/read/control branch remains; no forged sample/native stamp.
"""
import sys,time,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import run_experiment as base
from p12b.read_trace import dtype
DTYPE=dtype()
def choose_boundary(wall,now,index,side):
 target=wall+8_000_000;steps=1
 while target-4_000_000<now+500_000:target+=8_000_000;steps+=1
 return target,index+2*steps,target-4_000_000 if side=='BEFORE' else target+300_000

class Experiment(base.Experiment):
 def __init__(self,args):
  super().__init__(args);self.env['HANDOVER_P14H_TRACE_DIR']=str(self.out/'gz-motor');self.h_gates={};self.h_gate_fd=None
 def latest_allowed(self):
  path=self.out/'gz-motor/read-p12b.bin'
  if self.h_gate_fd is None:
   if not path.exists():return None
   self.h_gate_fd=os.open(path,os.O_RDONLY)
  size=os.fstat(self.h_gate_fd).st_size;n=size//DTYPE.itemsize
  if not n:return None
  raw=os.pread(self.h_gate_fd,min(n,8)*DTYPE.itemsize,(n-min(n,8))*DTYPE.itemsize);a=np.frombuffer(raw,DTYPE)
  good=a[(a['active']!=0)&(a['gate_permit']!=0)&(a['timing_initialized_pre']!=0)]
  return None if not len(good) else good[-1]
 def start_stream(self,*args,**kw):
  super().start_stream(*args,**kw);original=self.stream;gaps=kw.get('gaps',());side=self.cfg.get('p14h',{}).get('resume_side')
  if side is None:return
  def publish():
   if self.stream_t0 is None:return original()
   now=time.monotonic();t=now-self.stream_t0;k=self.stream_state['gap']
   if k is None or t<gaps[k][1] or k!=0:return original()
   row=self.latest_allowed()
   if row is None:
    if t>gaps[k][1]+.04:raise RuntimeError('P14H_RESUME_GATE_MISSING_LIVE_SOURCE_ROW')
    return
   ns=time.monotonic_ns();wall=int(row['pre_read_wall_ns']);index=int(row['call_index_pre'])
   if k not in self.h_gates:
    target,target_index,release=choose_boundary(wall,ns,index,side)
    self.h_gates[k]={'source_read_wall_ns':wall,'source_index':index,'target_index':target_index,'target_intent_wall_ns':target,'release_intent_wall_ns':release,'side':side,'planned_gap_end_s':gaps[k][1]};self.event('p14h_resume_gate_armed',**self.h_gates[k])
   gate=self.h_gates[k]
   if side=='AFTER':
    if index<gate['target_index']:return
    gate.setdefault('actual_target_read_wall_ns',wall);due=gate['actual_target_read_wall_ns']+300_000
   else:due=gate['release_intent_wall_ns']
   if ns<due:return
   if t>gaps[k][1]+.04:raise RuntimeError('P14H_RESUME_GATE_WAIT_LIMIT')
   self.event('p14h_resume_gate_release',**gate,actual_release_before_ns=ns,last_observed_index=index,last_observed_read_wall_ns=wall,scope='message release treatment; actual arrival/readverified offline; no capture/time forcing');return original()
  self.stream=publish
 def pump(self,seconds=.1):
  old=self.rclpy.spin_once
  def spin(node,timeout_sec):
   tight=False
   if self.stream_t0 is not None and self.stream:
    t=time.monotonic()-self.stream_t0
    for a,b in self.p5_gap_windows():
     if b-.03<=t<=b+.05:tight=True
   return old(node,timeout_sec=min(timeout_sec,.00025) if tight else timeout_sec)
  self.rclpy.spin_once=spin
  try:return super().pump(seconds)
  finally:self.rclpy.spin_once=old
base.Experiment=Experiment
if __name__=='__main__':raise SystemExit(base.main())

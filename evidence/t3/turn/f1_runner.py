"""F1 first-reference scheduling only, normal mode command/ACK/nav unchanged.
E1 keeps classic; E2 release after mode(); E3 release after fresh active AND
neural publisher ownership plus a native-clock margin. Physical ownership is
independently audited from four motor traces after flight. No target compensation.
"""
import argparse,json,sys,time,re,hashlib
from pathlib import Path
ROOT=Path('/home/car/uav_handover');sys.path.insert(0,str(ROOT/'tools'))
from handover_lyapunov.runner import Experiment as Existing
import handover_100.runner as old
class Experiment(Existing):
 def publish(self):
  pending=getattr(self,'f1_pending',False)
  if pending:
   if self.spec['f1_arm']=='E2':return
   if not(self.cn_active_gate and self.latest['raptor_status'].active):return
   now=time.monotonic()
   if now-getattr(self,'f1_gate_check_last',0)<.01:return
   self.f1_gate_check_last=now
   if not getattr(self,'f1_owner_evidence',None):
    txt=self.command('listener','research_actuator','-n','1',timeout=.25)
    owner=re.search(r'\bowner:\s*(\d+)',txt);stamp=re.search(r'\bactuator_timestamp:\s*(\d+)',txt)
    if not owner or not stamp or int(owner.group(1))!=1:return
    self.f1_owner_evidence={'owner':1,'actuator_timestamp_us':int(stamp.group(1)),'listener_output':txt}
   tick=self.native_phase_end_bound()
   if tick<self.f1_owner_evidence['actuator_timestamp_us']+8000:return
   self.f1_pending=False;self.cn_waiting_first=False
   self.event('f1_reference_release_gate',arm='E3',fresh_active=self.cn_active_gate,owner=self.f1_owner_evidence,native_clock_us=tick,requirement='neural publisher observed, native clock >= publication+8ms; four actual motor application audited postflight')
  count=getattr(self,'send_count',0);super().publish()
  if getattr(self,'f1_need_first',False) and self.send_count>count:
   self.f1_need_first=False;self.event('f1_first_postrequest_publish',arm=self.spec['f1_arm'],monotonic_after_ns=time.monotonic_ns(),profile_s=time.monotonic()-self.stream_profile_t0,send_count=self.send_count,mode_wait_complete=getattr(self,'f1_mode_done',False))
 def switch(self,current,target,iteration):
  arm=self.spec['f1_arm']
  bound=self.native_bound_streaming();l=self.latest['vehicle_local_position'];att=self.latest['vehicle_attitude']
  self.event('explore_pre_switch',iteration=iteration,position=[float(l.x),float(l.y),float(l.z)],velocity=[float(l.vx),float(l.vy),float(l.vz)],quaternion=list(map(float,att.q)),nav_state=int(self.latest['vehicle_status'].nav_state),reference_count=self.send_count)
  if arm=='E1':
   self.event('f1_classic_continues',end_bound_px4_us=bound,arm=arm,profile_s=time.monotonic()-self.stream_profile_t0);return
  rs=self.latest['raptor_status']
  if rs.active:raise RuntimeError('expected inactive RAPTOR before unique request')
  self.cn_previous_timestamp=int(rs.timestamp);self.cn_request_ns=time.monotonic_ns();self.cn_active_gate=None;self.cn_waiting_first=(arm=='E3')
  self.f1_pending=True;self.f1_need_first=True;self.f1_mode_done=False;self.f1_owner_evidence=None
  self.event('handover_requested',end_bound_px4_us=bound,from_controller='C',to_controller='N',iteration=iteration,subject=True)
  self.event('f1_reference_wait_started',arm=arm,profile_s=time.monotonic()-self.stream_profile_t0,last_send_profile_s=self.send_last-self.stream_profile_t0,absolute_profile_clock_preserved=True)
  self.mode(self.neural_mode) # normal command, ACK validation and coarse nav confirmation
  self.f1_mode_done=True
  if arm=='E2':self.f1_pending=False;self.event('f1_reference_release_gate',arm='E2',reason='mode command ACK and nav confirmation returned');self.publish()
  self.wait(lambda:self.latest.get('raptor_status') and self.latest['raptor_status'].active,5,'RAPTOR active')
  if arm=='E3':self.wait(lambda:not self.f1_pending,2,'F1 owner-safe reference release')
  self.event('explore_switch_confirmed',iteration=iteration,to_controller='N',end_bound_px4_us=self.native_bound_streaming())
old.Experiment=Experiment
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--case',required=True);p.add_argument('--attempt',default='a1');p.add_argument('--execute',action='store_true',required=True);a=p.parse_args();plan=json.loads(Path(a.plan).read_text());s=plan['cases'][a.case];old.CASES={a.case:s};old.SEED=s['seed'];old.EVIDENCE=ROOT/plan['batch'];raise SystemExit(old.run(a.case,a.attempt))

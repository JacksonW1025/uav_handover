"""T3 scoped civilian SITL: common mild prefix/payload; owner-safe +0/+60ms release.
All mode commands, ACK checks, protections and cleanup are inherited unchanged.
"""
import argparse,json,sys,time,re,math
from pathlib import Path
ROOT=Path('/home/car/uav_handover');sys.path.insert(0,str(ROOT/'tools'))
from handover_lyapunov.runner import Experiment as Existing
import handover_100.runner as old
from handover_100.design import evaluate
class Experiment(Existing):
 def publish(self):
  if not self.reference_enabled:return
  if not getattr(self,'t3_anchor_set',False):
   self.event('t3_common_reference_anchor',original_classic_origin=self.origin,original_classic_yaw=self.yaw,planned_origin=self.spec['fixed_reference_origin_ned'],planned_yaw=self.spec['fixed_reference_yaw_rad'])
   self.origin=list(self.spec['fixed_reference_origin_ned']);self.yaw=float(self.spec['fixed_reference_yaw_rad']);self.t3_anchor_set=True
  if getattr(self,'f1_pending',False):
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
   safe_tick=self.f1_owner_evidence['actuator_timestamp_us']+8000
   if tick<safe_tick+int(self.spec['extra_reference_delay_ms']*1000):return
   self.f1_pending=False;self.cn_waiting_first=False
   self.t3_release_ready=True
   self.event('f1_reference_release_gate',arm=self.spec['f1_arm'],fresh_active=self.cn_active_gate,owner=self.f1_owner_evidence,native_clock_us=tick,safe_tick_us=safe_tick,extra_delay_ms=self.spec['extra_reference_delay_ms'],requirement='fresh active, neural publication observed, clock>=publication+8ms+declared extra delay; physical ownership audited after flight')
  now=time.monotonic()
  if now-self.send_last<.02:return
  phase=0. if self.stream_hold or self.stream_profile_t0 is None else now-self.stream_profile_t0
  if getattr(self,'t3_release_ready',False):
   if not hasattr(self,'t3_release_host'):self.t3_release_host=now;phase=float(self.spec['fixed_release_phase_s'])
   else:phase=float(self.spec['fixed_release_phase_s'])+now-self.t3_release_host
  p,v,a,y,yr=evaluate(self.spec,phase,self.origin,self.yaw,self.initial_velocity)
  msg=self.msgs.TrajectorySetpoint();stamp=int(time.time()*1e6);msg.timestamp=stamp
  msg.position=p;msg.velocity=v;msg.acceleration=a;msg.yaw=y;msg.yawspeed=yr
  off=self.msgs.OffboardControlMode();off.timestamp=stamp;off.position=True;self.offpub.publish(off)
  before=time.monotonic_ns();self.trajpub.publish(msg);after=time.monotonic_ns()
  self.send_count+=1;self.send_last=now
  self.sends.write(json.dumps(dict(id=self.send_count,profile_s=phase,before_ns=before,after_ns=after,position=p,velocity=v,acceleration=a,yaw=y,yawspeed=yr))+'\n');self.sends.flush()
  if self.send_count==1:self.event('explore_first_publish',before_ns=before,after_ns=after,profile_s=phase)
  if getattr(self,'f1_need_first',False):
   self.f1_need_first=False
   self.event('f1_first_postrequest_publish',arm=self.spec['f1_arm'],monotonic_after_ns=after,profile_s=phase,send_count=self.send_count,mode_wait_complete=getattr(self,'f1_mode_done',False),payload=dict(position=p,velocity=v,acceleration=a,yaw=y,yawspeed=yr))
 def switch(self,current,target,iteration):
  if (current,target)!=('C','N'):raise RuntimeError('Only unique C-to-N subject supported')
  bound=self.native_bound_streaming();l=self.latest['vehicle_local_position'];att=self.latest['vehicle_attitude']
  self.event('explore_pre_switch',iteration=iteration,position=[float(l.x),float(l.y),float(l.z)],velocity=[float(l.vx),float(l.vy),float(l.vz)],quaternion=list(map(float,att.q)),nav_state=int(self.latest['vehicle_status'].nav_state),reference_count=self.send_count)
  rs=self.latest['raptor_status']
  if rs.active:raise RuntimeError('expected inactive RAPTOR before unique request')
  self.cn_previous_timestamp=int(rs.timestamp);self.cn_request_ns=time.monotonic_ns();self.cn_active_gate=None;self.cn_waiting_first=True
  self.f1_pending=True;self.f1_need_first=True;self.f1_mode_done=False;self.f1_owner_evidence=None
  self.event('handover_requested',end_bound_px4_us=bound,from_controller='C',to_controller='N',iteration=iteration,subject=True)
  self.event('f1_reference_wait_started',arm=self.spec['f1_arm'],profile_s=time.monotonic()-self.stream_profile_t0,last_send_profile_s=self.send_last-self.stream_profile_t0,absolute_profile_clock_preserved=False,fixed_release_phase_s=self.spec['fixed_release_phase_s'])
  self.mode(self.neural_mode)
  self.f1_mode_done=True
  self.wait(lambda:self.latest.get('raptor_status') and self.latest['raptor_status'].active,5,'RAPTOR active')
  self.wait(lambda:not self.f1_pending,2,'T3 owner-safe reference release')
  self.event('explore_switch_confirmed',iteration=iteration,to_controller='N',end_bound_px4_us=self.native_bound_streaming())
old.Experiment=Experiment
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--case',required=True);p.add_argument('--attempt',default='a1');p.add_argument('--execute',action='store_true',required=True);a=p.parse_args();plan=json.loads(Path(a.plan).read_text());s=plan['cases'][a.case]
 if a.attempt!='a1':raise RuntimeError('This two-start plan permits only a1; no retries')
 evidence=ROOT/plan['batch'];ledger=evidence/'attempts.jsonl'
 rows=[json.loads(l) for l in ledger.read_text().splitlines()] if ledger.exists() else []
 starts=[r for r in rows if r['event']=='START_INTENT']
 ends={r['attempt_id'] for r in rows if r['event']=='PHYSICAL_END'}
 if len(starts)>=int(plan['maximum_starts']):raise RuntimeError('Two physical starts already consumed')
 if any(r.get('case')==a.case for r in starts):raise RuntimeError('Case already started; no retry')
 if any(r['attempt_id'] not in ends for r in starts):raise RuntimeError('Prior physical lifecycle unresolved')
 if any(r['event']=='END' and (r.get('execution_status')!='PASS' or r.get('cleanup_error')) for r in rows):raise RuntimeError('Prior attempt did not complete normally; remaining launch stopped')
 old.CASES={a.case:s};old.SEED=s['seed'];old.EVIDENCE=evidence;raise SystemExit(old.run(a.case,a.attempt))

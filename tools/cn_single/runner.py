"""Single counted SITL case. No implicit retry; no host-gate or safety bypass."""
import argparse
import fcntl
import json
import math
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
import traceback
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))
import run_experiment as base
from cn_single.design import SEED, MISSION_NED, GAP, DURATION, trajectory, global_waypoint, in_gap, budget
from p9_run import host_gate
from preparation_batch import identity

EVIDENCE = ROOT/'data/cn-single-20261109'
CONFIG = ROOT/'config/cn_single/single.json'
EXTRA_TOPICS = ['register_ext_component_request', 'register_ext_component_reply',
                'arming_check_request', 'arming_check_reply', 'health_report',
                'failsafe_flags', 'mission', 'mission_result', 'setpoint_config']


def upload_packet_valid(msg, system):
    """Only the owned autopilot, addressed to this GCS, for normal mission type."""
    return (msg.get_srcSystem()==system and msg.get_srcComponent()==1
            and getattr(msg,"target_system",245) in (0,245)
            and getattr(msg,"target_component",191) in (0,191)
            and getattr(msg,"mission_type",0)==0)


def require_neural(latest, mode):
    if latest["vehicle_status"].nav_state!=mode or not latest["raptor_status"].active:
        raise RuntimeError("unexpected neural authority or mode loss")


def claim(old,repair=False):
    starts=[x for x in old if x['event']=='START_INTENT']
    if not starts:
        if repair:raise RuntimeError('no prior failed attempt to repair')
        return
    if not repair:raise RuntimeError('one-case budget already spent; no implicit retry')
    if len(starts)!=1 or not any(x['event']=='END' for x in old):
        raise RuntimeError('repair requires exactly one terminated previous attempt')
    original=ROOT/'data/cn-single-20261109-flight'
    measured=json.loads((original/'cn-measurement.json').read_text())
    if (measured['subject_requests'] or measured.get('actual_neural_entries')!=0
            or measured['flight_execution'].get('reason')!="RuntimeError('owned SITL mission connection not verified')"):
        raise RuntimeError('repair is scoped only to the proven pre-subject MAVLink failure')



def close_experiment(e):
    """Retain terminal failure even if owned-process cleanup itself fails."""
    if e is None:return None
    try:
        e.stream=None;e.cleanup();return None
    except BaseException as exc:
        traceback.print_exc();return repr(exc)


def append(path, value):
    with path.open('a') as f:
        f.write(json.dumps(value, allow_nan=False)+'\n'); f.flush(); os.fsync(f.fileno())


class Experiment(base.Experiment):
    def state_contract(self):
        # Unlike the generic diagnostics, do not inject/reset controller memories.
        self.capture_states('disarmed_read_only')
        for name, value in [('MC_RAPTOR_RINI', 0), ('MC_RAPTOR_RTGT', 0), ('MC_RAPTOR_RREC', 0), ('MC_RAPTOR_NCO', 0)]:
            self.command('param', 'set', name, str(value))
            self.command('param', 'show', name)
        self.command('param', 'set', 'MPC_XY_CRUISE', '1.2')
        self.checks['state_contract'] = 'NOT_APPLIED_READ_ONLY_CASE'

    def spawn(self, name, argv, cwd=None):
        if name == 'agent':
            p = self.rootfs/'etc/logging/logger_topics.txt'
            with p.open('a') as f:
                f.write(''.join(n+' 0 0\n' for n in EXTRA_TOPICS))
        return super().spawn(name, argv, cwd)

    def pump(self,seconds=.1):
        mav=getattr(self,'cn_mavlink',None)
        if mav is not None and time.monotonic()-getattr(self,'cn_heartbeat',0.)>=1.:
            from pymavlink import mavutil
            mav.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_GCS,mavutil.mavlink.MAV_AUTOPILOT_INVALID,0,0,0)
            self.cn_heartbeat=time.monotonic()
        return super().pump(seconds)

    def cleanup(self):
        mav=getattr(self,'cn_mavlink',None)
        try:return super().cleanup()
        finally:
            if mav is not None:mav.close();self.cn_mavlink=None

    def mav_open(self):
        from pymavlink import mavutil
        mav=getattr(self,'cn_mavlink',None)
        if mav is None:raise RuntimeError('verified persistent MAVLink connection unavailable')
        # Discard buffered telemetry, then demand a new heartbeat from this peer.
        drained=0;end=time.monotonic()+1.
        while time.monotonic()<end:
            if mav.recv_match(blocking=False) is None:break
            drained+=1
        self.event('cn_mavlink_reused',local_endpoint=list(mav.port.getsockname()),drained=drained)
        mav.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_GCS,mavutil.mavlink.MAV_AUTOPILOT_INVALID,0,0,0)
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            self.pump(.01);hb=mav.recv_match(type='HEARTBEAT',blocking=False)
            if hb is not None and hb.get_srcSystem()==self.instance+1 and hb.autopilot==mavutil.mavlink.MAV_AUTOPILOT_PX4:
                self.event('cn_mavlink_identity_verified',system_id=hb.get_srcSystem(),component_id=hb.get_srcComponent())
                return mav
        raise RuntimeError('owned SITL persistent mission heartbeat not verified')

    def upload_mission(self, mav):
        from pymavlink import mavutil
        local = self.latest['vehicle_local_position']
        if not (local.xy_global and local.z_global):
            raise RuntimeError('mission needs valid global local-position reference')
        points = [global_waypoint(p, local.ref_lat, local.ref_lon, local.ref_alt) for p in MISSION_NED]
        self.event('cn_mission_upload_started',ned=MISSION_NED, global_int_msl=points)
        mav.mav.mission_count_send(self.instance+1, 1, len(points))
        sent = set(); end = time.monotonic()+15
        while time.monotonic()<end:
            self.pump(.01)
            msg = mav.recv_match(blocking=False)
            if msg is None: continue
            if not upload_packet_valid(msg,self.instance+1): continue
            typ = msg.get_type()
            if typ in ('MISSION_REQUEST', 'MISSION_REQUEST_INT'):
                seq = int(msg.seq)
                if not 0<=seq<len(points): raise RuntimeError('mission request sequence outside uploaded route')
                lat, lon, alt = points[seq]
                common = [self.instance+1, 1, seq]
                rest = [mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, int(seq==0), 1, 0., .5, 0., float('nan')]
                if typ == 'MISSION_REQUEST_INT':
                    mav.mav.mission_item_int_send(*common, mavutil.mavlink.MAV_FRAME_GLOBAL_INT, *rest, lat, lon, alt)
                else:
                    mav.mav.mission_item_send(*common, mavutil.mavlink.MAV_FRAME_GLOBAL, *rest, lat/1e7, lon/1e7, alt)
                sent.add(seq); self.event('cn_mission_item_sent',sequence=seq,request_type=typ)
            elif typ == 'MISSION_ACK':
                self.event('cn_mission_ack',result=int(msg.type),sent=sorted(sent))
                if msg.type != mavutil.mavlink.MAV_MISSION_ACCEPTED or sent != set(range(len(points))):
                    raise RuntimeError('mission not fully accepted')
                return
        raise TimeoutError('mission upload acknowledgement')

    def p1_flight(self, mode):
        mav = self.mav_open()
        try:
            self.upload_mission(mav)
            self.command('listener', 'mission_result', '-n', '1')
            self.mode(self.msgs.VehicleStatus.NAVIGATION_STATE_AUTO_MISSION)
            start = time.monotonic(); current = None; dwell = None
            while time.monotonic()-start < 25:
                self.pump(.02)
                while True:
                    msg = mav.recv_match(type=['MISSION_CURRENT', 'MISSION_ITEM_REACHED'],blocking=False)
                    if msg is None: break
                    if msg.get_srcSystem()!=self.instance+1: continue
                    self.event('cn_mission_progress',type=msg.get_type(),sequence=int(msg.seq))
                    if msg.get_type()=='MISSION_CURRENT': current = int(msg.seq)
                l = self.latest['vehicle_local_position']
                eligible = current==1 and math.hypot(l.vx,l.vy)>=.6 and math.hypot(l.x-3.,l.y-3.)>.75
                if eligible:
                    if dwell is None: dwell=time.monotonic()
                    if time.monotonic()-dwell>=.2: break
                else: dwell=None
            else: raise TimeoutError('predeclared moving Mission second-leg trigger')
        finally:
            mav.close();self.cn_mavlink=None
        l = self.latest['vehicle_local_position']
        origin=[float(l.x),float(l.y),float(l.z)]; velocity=[float(l.vx),float(l.vy),float(l.vz)]; yaw=float(l.heading)
        b=budget(origin,velocity,yaw); self.event('cn_path_budget',**b)
        if not b['inside']: raise RuntimeError('neural reference path exceeds preregistered budget')
        self.event('cn_trigger_state',origin=origin,velocity=velocity,yaw=yaw,mission_current=current)
        self.event('handover_requested',end_bound_px4_us=self.native_phase_end_bound(),from_controller='C',to_controller='N',iteration=0,subject=True)
        self.mode(mode)
        # No runner setpoint while Mission owns the classic controller. The first
        # post-confirmation publish is observable; do not assume first NN capture.
        t0=time.monotonic(); last=-1.; count=0; gap=False
        sends=(self.out/'cn-setpoints.jsonl').open('w');self.files.append(sends)
        def publish():
            nonlocal last,count,gap
            now=time.monotonic();t=now-t0
            if self.latest['vehicle_status'].nav_state!=mode:return
            if in_gap(t):
                if not gap:self.event('cn_gap_started',profile_s=t,last_publish_s=last);gap=True
                return
            if gap:self.event('cn_gap_ended',profile_s=t);gap=False
            if t-last<.02:return
            p,v,a,y,yr=trajectory(t,origin,velocity,yaw)
            msg=self.msgs.TrajectorySetpoint();msg.timestamp=int(time.time()*1e6)
            msg.position=p;msg.velocity=v;msg.acceleration=a;msg.yaw=y;msg.yawspeed=yr
            before=time.monotonic_ns();self.trajpub.publish(msg);after=time.monotonic_ns()
            count+=1;last=t
            sends.write(json.dumps(dict(id=count,profile_s=t,before_ns=before,after_ns=after,position=p,velocity=v,acceleration=a,yaw=y,yawspeed=yr))+'\n');sends.flush()
            if count==1:self.event('cn_first_external_publish',before_ns=before,after_ns=after,profile_s=t)
        self.stream=publish;publish()
        self.wait(lambda:self.latest.get('raptor_status') and self.latest['raptor_status'].active,5,'RAPTOR active')
        while time.monotonic()-t0<DURATION:
            self.pump(.02);require_neural(self.latest,mode)
        self.event('cn_reference_finished',published=count,profile_s=time.monotonic()-t0)
        # Only one subject C->N. A separate N->C recovery is necessary for classic landing.
        self.event('handover_requested',end_bound_px4_us=self.native_bound_streaming(),from_controller='N',to_controller='C',iteration=0,subject=False,purpose='landing recovery')
        self.mode(self.msgs.VehicleStatus.NAVIGATION_STATE_AUTO_LOITER)
        self.stream=None
        self.hover(4.,'landing_recovery',prefix='p1_phase')
        self.checks['cn_case']='COMPLETE'


def run(repair=False):
    evidence=ROOT/'data/cn-single-20261109-repair' if repair else EVIDENCE
    config=ROOT/'config/cn_single/repair.json' if repair else CONFIG
    evidence.mkdir(exist_ok=True)
    with (EVIDENCE/'attempts.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        ledger=EVIDENCE/'attempts.jsonl'
        old=[json.loads(x) for x in ledger.read_text().splitlines()] if ledger.exists() else []
        claim(old,repair)
        try:host=host_gate()
        except Exception as exc:
            append(ledger,dict(event='BLOCKED_BEFORE_START',time_ns=time.time_ns(),reason=str(exc),counts_as_start=False))
            raise
        base.write(evidence/'host-before.json',host)
        candidate=identity();base.write(evidence/'candidate-before.json',candidate)
        out=ROOT/('data/cn-single-20261109-repair-flight' if repair else 'data/cn-single-20261109-flight')
        if out.exists():raise RuntimeError('flight output exists; inspect rather than overwrite')
        args=SimpleNamespace(kind='p1_c_to_n',config=config,condition='single',treatment=None,output=out,
                             startup_only=False,capture_raw_sensors=False,hover_s=None,sim_seed=SEED,initial_yaw_deg=0.)
        append(ledger,dict(event='START_INTENT',time_ns=time.time_ns(),seed=SEED,budget=1,attempt=2 if repair else 1,infrastructure_repair=repair,output=str(out)))
        st=time.monotonic();cpu=resource.getrusage(resource.RUSAGE_CHILDREN);selfcpu=time.process_time()
        e=None;status='FAIL';reason=None
        try:
            e=Experiment(args);e.metadata['scenario']='cn_single_mission_3d_gap';e.execute();status='PASS'
        except BaseException as exc:
            reason=repr(exc);traceback.print_exc()
            if e:e.event('failure',reason=reason)
        finally:
            cleanup_error=close_experiment(e)
            if cleanup_error:status='FAIL'
            if e:
                base.write(out/'validation.json',dict(status=status,execution_status=status,reason=reason,cleanup_error=cleanup_error,checks=e.checks))
            try:
                after=identity();base.write(evidence/'candidate-after.json',after);unchanged=after==candidate
            except BaseException as exc:
                unchanged=False;reason=(reason or '')+'; identity audit: '+repr(exc)
            end=resource.getrusage(resource.RUSAGE_CHILDREN)
            base.write(evidence/'execution.json',dict(execution_status=status,reason=reason,cleanup_error=cleanup_error,wall_s=time.monotonic()-st,
                 cpu_s=time.process_time()-selfcpu+end.ru_utime+end.ru_stime-cpu.ru_utime-cpu.ru_stime,candidate_unchanged=unchanged))
            append(ledger,dict(event='PHYSICAL_END' if not cleanup_error else 'PHYSICAL_UNCERTAIN',time_ns=time.time_ns(),status=status,reason=reason,cleanup_error=cleanup_error))
        # Analysis remains separate from execution and all outcomes, including aborts,
        # are retained. The historical analyzer verdict is descriptive for this moving case.
        analysis={};analysis_start=time.monotonic();c0=resource.getrusage(resource.RUSAGE_CHILDREN)
        if e and (out/'flight.ulg').exists():
            commands=[('historical',[sys.executable,str(ROOT/'tools/analyze.py'),str(out)]),
                      ('output_chain',[sys.executable,str(ROOT/'tools/output_chain.py'),str(out)]),
                      ('single_case',[sys.executable,str(ROOT/'tools/cn_single/analyze.py'),str(out),'--output',str(out/'cn-measurement.json')])]
            for name,command in commands:
                with (out/'logs'/('cn-analysis-'+name+'.log')).open('w') as log:
                    analysis[name]=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT).returncode
        c1=resource.getrusage(resource.RUSAGE_CHILDREN)
        analysis.update(wall_s=time.monotonic()-analysis_start,cpu_s=c1.ru_utime+c1.ru_stime-c0.ru_utime-c0.ru_stime)
        base.write(evidence/'analysis-execution.json',analysis)
        complete=bool(status=='PASS' and unchanged and analysis.get('single_case')==0 and analysis.get('output_chain')==0)
        if complete:
            measured=json.loads((out/'cn-measurement.json').read_text());chain=json.loads((out/'output-chain.json').read_text())
            from p1_batch import chain_gate
            errors=chain_gate(chain);analysis['output_chain_errors']=errors
            completion=measured['completion']
            complete=(not errors and measured['status']=='MEASURED' and not measured['missing_topics']
                      and all(completion[k] for k in ['exactly_one_subject_C_to_N','reference_completed','landing_requested','disarmed_observed'])
                      and not completion['failures'] and completion['px4_exit_codes']==[0]
                      and measured.get('actual_neural_entries')==1 and measured.get('actual_neural_owner_entries')==1)
        base.write(evidence/'result.json',dict(status='COMPLETE' if complete else 'INCOMPLETE',execution_status=status,analysis=analysis,candidate_unchanged=unchanged,
                                              flight_outcomes_path=str(out/'cn-measurement.json'),note='completion is evidence/workflow completion, not a safe-flight claim'))
        append(ledger,dict(event='END',time_ns=time.time_ns(),status='COMPLETE' if complete else 'INCOMPLETE'))
        return 0 if complete else 1



if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true',required=True);p.add_argument('--repair-mavlink',action='store_true')
    args=p.parse_args();raise SystemExit(run(args.repair_mavlink))

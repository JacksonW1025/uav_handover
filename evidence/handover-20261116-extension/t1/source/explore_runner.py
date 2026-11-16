"""Normal-use exploratory SITL; fresh attempts, retained failures, real switches."""
import argparse,fcntl,json,math,os,resource,shutil,subprocess,sys,time,traceback
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import run_experiment as base
from cn_single import runner as original
from cn_reference.runner import Experiment as MissionExperiment,fresh_active
from cn_reference.mission_ready import wait_mission_ready,mission_sequence
from handover_explore.design import CASES,SEED,evaluate,geometry
from preparation_batch import identity
from p9_run import host_gate
EVIDENCE=ROOT/'data/handover-explore-20261110'

class Experiment(MissionExperiment):
    def p1_flight(self,mode):
        self.spec=self.cfg['explore'];self.neural_mode=mode;self.stream_profile_t0=None;self.send_count=0
        self.send_last=-1.;self.stream_hold=True;self.reference_enabled=True;self.cn_waiting_first=False
        self.sends=(self.out/'explore-setpoints.jsonl').open('w');self.files.append(self.sends)
        if self.spec['source']=='mission':return self.mission_flight(mode)
        self.origin,self.yaw,_=self.classic_target();self.initial_velocity=[0.,0.,0.]
        self.event('explore_reference_geometry',**geometry(self.spec,self.origin,self.yaw))
        self.stream=self.publish;self.pump(1.2)
        self.mode(self.msgs.VehicleStatus.NAVIGATION_STATE_OFFBOARD)
        current='C'
        if self.spec.get('neural_before_profile'):
            self.switch('C','N',0);current='N';self.pump(3.)
        native_profile_lower=self.native_bound_streaming()
        self.stream_profile_t0=time.monotonic();self.stream_hold=False
        self.event('explore_profile_started',origin=self.origin,yaw=self.yaw,profile_t0_monotonic_s=self.stream_profile_t0,source='raptor_prestabilized' if current=='N' else 'classic_OFFBOARD',shared_continuous_reference=True,native_start_lower_us=native_profile_lower)
        for i,(at,target) in enumerate(self.spec['switches']):
            while time.monotonic()-self.stream_profile_t0<float(at):self.pump(.01)
            self.switch(current,target,i);current=target
        while time.monotonic()-self.stream_profile_t0<self.spec['duration_s']:self.pump(.02)
        self.finish_subject(current)

    def publish(self):
        if not self.reference_enabled:return
        now=time.monotonic()
        if now-self.send_last<.02:return
        if self.spec['source']=='mission':
            if self.cn_active_gate is None:return
            if not self.latest['raptor_status'].active:return
            if self.stream_profile_t0 is None:
                self.stream_profile_t0=now
                self.event('explore_profile_started',origin=self.origin,yaw=self.yaw,profile_t0_monotonic_s=now,source='Mission_after_fresh_active',shared_continuous_reference=False)
        t=0. if self.stream_hold or self.stream_profile_t0 is None else now-self.stream_profile_t0
        p,v,a,y,yr=evaluate(self.spec,t,self.origin,self.yaw,self.initial_velocity)
        msg=self.msgs.TrajectorySetpoint();stamp=int(time.time()*1e6);msg.timestamp=stamp
        msg.position=p;msg.velocity=v;msg.acceleration=a;msg.yaw=y;msg.yawspeed=yr
        if self.spec['source']=='offboard':
            off=self.msgs.OffboardControlMode();off.timestamp=stamp;off.position=True;self.offpub.publish(off)
        before=time.monotonic_ns();self.trajpub.publish(msg);after=time.monotonic_ns()
        self.send_count+=1;self.send_last=now
        self.sends.write(json.dumps(dict(id=self.send_count,profile_s=t,before_ns=before,after_ns=after,position=p,velocity=v,acceleration=a,yaw=y,yawspeed=yr))+'\n');self.sends.flush()
        if self.send_count==1:self.event('explore_first_publish',before_ns=before,after_ns=after,profile_s=t)

    def switch(self,current,target,iteration):
        l=self.latest['vehicle_local_position'];att=self.latest['vehicle_attitude']
        bound=self.native_bound_streaming()
        self.event('explore_pre_switch',iteration=iteration,position=[float(l.x),float(l.y),float(l.z)],velocity=[float(l.vx),float(l.vy),float(l.vz)],quaternion=list(map(float,att.q)),nav_state=int(self.latest['vehicle_status'].nav_state),reference_count=self.send_count)
        self.event('handover_requested',end_bound_px4_us=bound,from_controller=current,to_controller=target,iteration=iteration,subject=True)
        if self.spec['source']=='mission' and target=='N' and self.spec['reference_kind']=='external_brake':
            rs=self.latest['raptor_status'];self.cn_previous_timestamp=int(rs.timestamp);self.cn_request_ns=time.monotonic_ns()
            self.cn_active_gate=None;self.cn_waiting_first=True;self.stream=self.publish
        self.mode(self.neural_mode if target=='N' else self.msgs.VehicleStatus.NAVIGATION_STATE_OFFBOARD)
        if target=='N':self.wait(lambda:self.latest.get('raptor_status') and self.latest['raptor_status'].active,5,'RAPTOR active')
        self.event('explore_switch_confirmed',iteration=iteration,to_controller=target,end_bound_px4_us=self.native_bound_streaming())

    def mission_flight(self,mode):
        mav=self.mav_open()
        try:
            self.upload_mission(mav);wait_mission_ready(self)
            self.mode(self.msgs.VehicleStatus.NAVIGATION_STATE_AUTO_MISSION)
            start=time.monotonic();dwell=None
            while time.monotonic()-start<25.:
                self.pump(.02);seq=mission_sequence(self)['seq_current'];l=self.latest['vehicle_local_position']
                eligible=(seq==1 and math.hypot(l.vx,l.vy)>=.6 and math.hypot(l.x-3.,l.y-3.)>.75)
                if self.spec.get('trigger_vertical')=='descending':
                    eligible=(0<=seq<5 and math.hypot(l.vx,l.vy)>=.6 and l.vz>=.5)
                if eligible:
                    if dwell is None:dwell=time.monotonic()
                    if time.monotonic()-dwell>=.2:break
                else:dwell=None
            else:raise TimeoutError('moving Mission second-leg trigger')
        finally:mav.close();self.cn_mavlink=None
        l=self.latest['vehicle_local_position'];self.origin=[float(l.x),float(l.y),float(l.z)]
        self.initial_velocity=[float(l.vx),float(l.vy),float(l.vz)];self.yaw=float(l.heading);self.stream_hold=False
        self.event('explore_reference_geometry',screen='record only, real-time physical envelope retained',**geometry(self.spec,self.origin,self.yaw,self.initial_velocity))
        self.switch('C','N',0)
        if self.spec['reference_kind']=='native_capture':
            self.stream_profile_t0=time.monotonic()
            self.event('explore_profile_started',origin=self.origin,yaw=self.yaw,profile_t0_monotonic_s=self.stream_profile_t0,source='native_capture_no_external_reference',shared_continuous_reference=False)
        if self.stream_profile_t0 is None:raise RuntimeError('Mission reference not started')
        while time.monotonic()-self.stream_profile_t0<self.spec['duration_s']:
            self.pump(.02);original.require_neural(self.latest,mode)
        self.finish_subject('N')

    def finish_subject(self,current):
        self.event('explore_subject_finished',end_bound_px4_us=self.native_bound_streaming(),published=self.send_count)
        self.event('handover_requested',end_bound_px4_us=self.native_bound_streaming(),from_controller=current,to_controller='C',iteration=99,subject=False,purpose='landing recovery')
        self.mode(self.msgs.VehicleStatus.NAVIGATION_STATE_AUTO_LOITER);self.stream=None
        self.hover(4.,'landing_recovery',prefix='p1_phase');self.checks['explore_case']='COMPLETE'

    def emergency_land(self):
        """Normal LAND request after a failure, retaining the original failure outcome."""
        if not self.safe:return
        self.stream=None;self.alt_floor=None
        self.event('explore_emergency_landing_requested',reason='attempt failed; normal LAND and observed cleanup, no forced mode or arm')
        try:
            self.ros_command(21)
            self.wait(lambda:self.latest.get('vehicle_land_detected') and self.latest['vehicle_land_detected'].landed,60.,'emergency landing')
            self.safe=False;self.wait(lambda:self.latest['vehicle_status'].arming_state!=2,15.,'emergency disarmed')
            self.event('explore_emergency_landing_completed')
        except BaseException as exc:self.event('explore_emergency_landing_incomplete',reason=repr(exc))

def run(case,attempt):
    EVIDENCE.mkdir(exist_ok=True)
    with (EVIDENCE/'attempts.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        ledger=EVIDENCE/'attempts.jsonl';outbase=EVIDENCE/(case+'-'+attempt)
        if outbase.exists():raise RuntimeError('attempt exists; never overwrite')
        rows=[json.loads(s) for s in ledger.read_text().splitlines()] if ledger.exists() else []
        starts={r['attempt_id'] for r in rows if r['event']=='START_INTENT'}
        ended={r['attempt_id'] for r in rows if r['event']=='PHYSICAL_END'}
        if starts-ended:raise RuntimeError('prior physical lifecycle unresolved: '+str(starts-ended))
        host=host_gate()
        if shutil.disk_usage(ROOT).free<5_000_000_000:raise RuntimeError('less than5GB free; preserve prior data')
        outbase.mkdir();base.write(outbase/'host-before.json',host)
        candidate=identity();base.write(outbase/'candidate-before.json',candidate)
        cfg=json.loads((ROOT/'config/cn_reference/quickcheck.json').read_text());cfg.pop('cn_reference',None)
        cfg['seed']=SEED;cfg['explore']=CASES[case]
        cfg['cn_single']['seed']=SEED
        cfg['cn_single']['classic_prefix']='AUTO_TAKEOFF 3m, AUTO_LOITER10s, then '+CASES[case]['source']
        cfg['cn_single']['trigger']='profile-time switches' if CASES[case]['source']=='offboard' else 'Mission index1 speed>=0.6m/s, distance>0.75m, dwell0.2s'
        if CASES[case].get('trigger_vertical')=='descending':cfg['cn_single']['trigger']='Any valid current Mission leg, horizontal speed>=0.6m/s and NED vz>=0.5m/s for0.2s'
        cfg['cn_single'].pop('repair_note',None)
        if CASES[case]['source']=='offboard':cfg['cn_single'].pop('mission_ned_m',None)
        cfg['cn_single']['startup_budget']=None;cfg['cn_single']['gap_profile_s']=None
        cfg['cn_single']['subject']='normal-use exploratory handover, no deliberate setpoint gap'
        cfg['cn_single']['external_reference']=CASES[case]['reference_kind'];cfg['cn_single']['memory']='original reset, no intervention'
        config=outbase/'config.json';base.write(config,cfg)
        flight=outbase/'flight';args=SimpleNamespace(kind='p1_c_to_n',config=config,condition='single',treatment=None,output=flight,startup_only=False,capture_raw_sensors=False,hover_s=None,sim_seed=SEED,initial_yaw_deg=0.)
        original.append(ledger,dict(event='START_INTENT',attempt_id=outbase.name,time_ns=time.time_ns(),case=case,seed=SEED,output=str(flight.relative_to(ROOT))))
        st=time.monotonic();sc=time.process_time();cpu=resource.getrusage(resource.RUSAGE_CHILDREN);e=None;status='FAIL';reason=None;cleanup_error=None
        try:
            e=Experiment(args);e.metadata['scenario']='handover_explore_'+case;e.execute();status='PASS'
        except BaseException as exc:
            reason=repr(exc);traceback.print_exc()
            if e:e.event('failure',reason=reason);e.emergency_land()
        finally:
            cleanup_error=original.close_experiment(e)
            if cleanup_error:status='FAIL'
            if e:base.write(flight/'validation.json',dict(status=status,execution_status=status,reason=reason,cleanup_error=cleanup_error,checks=e.checks))
            cpu1=resource.getrusage(resource.RUSAGE_CHILDREN);cost=dict(wall_s=time.monotonic()-st,cpu_s=time.process_time()-sc+cpu1.ru_utime+cpu1.ru_stime-cpu.ru_utime-cpu.ru_stime)
            original.append(ledger,dict(event='PHYSICAL_END' if not cleanup_error else 'PHYSICAL_UNCERTAIN',attempt_id=outbase.name,time_ns=time.time_ns(),execution_status=status,reason=reason,cleanup_error=cleanup_error,**cost))
        after=identity();base.write(outbase/'candidate-after.json',after)
        result=dict(case=case,label=CASES[case]['label'],attempt=attempt,execution_status=status,reason=reason,cleanup_error=cleanup_error,candidate_unchanged=after==candidate,execution_cost=cost,flight=str(flight.relative_to(ROOT)),note='execution completion is not flight safety or evidence acceptance')
        base.write(outbase/'result.json',result);original.append(ledger,dict(event='END',attempt_id=outbase.name,**result))
        print('EXPLORE_RESULT',json.dumps(result,ensure_ascii=False),flush=True)
        return 0 if not cleanup_error else 2

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',choices=list(CASES),required=True);p.add_argument('--attempt',default='a1');p.add_argument('--execute',action='store_true',required=True)
    a=p.parse_args();raise SystemExit(run(a.case,a.attempt))

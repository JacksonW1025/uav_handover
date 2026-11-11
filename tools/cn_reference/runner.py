"""Headless reference-handoff arms, with immutable attempts and explicit continuation."""
import argparse
import fcntl
import json
import math
import os
from pathlib import Path
import resource
import sys
import time
import traceback
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from cn_single import runner as original
from cn_reference.mission_ready import wait_mission_ready, mission_sequence
from cn_single.design import SEED, DURATION, MISSION_NED, global_waypoint, trajectory, in_gap, budget
from p9_run import host_gate
from preparation_batch import identity
from p1_batch import chain_gate
from p0_closure import GATE
from output_chain import analyze as output_analysis, read_trace, step_summary
import run_experiment as base

EVIDENCE=ROOT/'data/cn-reference-20261110'
CONFIG=ROOT/'config/cn_reference/quickcheck.json'
ARMS=('A','B','C')


def claim(rows,arm,continue_after_ack=False):
    if arm not in ARMS:raise ValueError('unknown arm')
    starts=[r for r in rows if r['event']=='START_INTENT']
    if len(starts)>=3:raise RuntimeError('three-start hard cap exhausted')
    if any(r['arm']==arm for r in starts):raise RuntimeError('arm already attempted; no repair or automatic retry')
    if [r['arm'] for r in starts]!=list(ARMS[:ARMS.index(arm)]):raise RuntimeError('arms must run once in A/B/C order')
    if continue_after_ack and (arm!='C' or [r['arm'] for r in starts]!=['A','B']):
        raise RuntimeError('continuation is only the remaining C start after A and B')
    for prior in starts:
        ends=[r for r in rows if r['event']=='END' and r['arm']==prior['arm']]
        if len(ends)!=1:raise RuntimeError('prior launch not unambiguously terminated')
        if not ends[0].get('infrastructure_ok') and not (continue_after_ack and prior['arm']=='B'):
            raise RuntimeError('prior infrastructure/evidence failure; remaining starts stopped')



def verify_ack_continuation(candidate):
    """A later user instruction allows only the already-budgeted C, not B retry."""
    b=EVIDENCE/'B';result=json.loads((b/'result.json').read_text())
    measured=json.loads((b/'flight/cn-reference-measurement.json').read_text())
    full=measured.get('full_neural_analysis',{})
    if (result.get('reason')!="TimeoutError('mission upload acknowledgement')"
        or result.get('cleanup_error') is not None or not result.get('candidate_unchanged')
        or measured.get('subject_requests') or full.get('actual_neural_entries')!=0):
        raise RuntimeError('continuation restricted to the known terminated pre-subject Mission ACK failure')
    old=json.loads((b/'candidate-before.json').read_text())
    for key in ['lab','policy_sha256','gz_research_plugin_sha256']:
        if candidate.get(key)!=old.get(key):raise RuntimeError('Lab/policy/plugin changed; continuation not allowed')
    changed=sorted(k for k in set(old['files'])|set(candidate['files']) if old['files'].get(k)!=candidate['files'].get(k))
    if set(changed)-{'tools/cn_reference/runner.py','tools/cn_reference/audit.py'}:
        raise RuntimeError('unexpected scientific/config changes: '+str(changed))
    return dict(previous_failure=result['reason'],changed_files=changed,
        original_budget=3,remaining_start='C only',no_B_retry=True,
        previous_candidates_unchanged=True,lab_policy_plugin_unchanged=True,
        reason='later user instruction prioritizes completing the intended switch; no expansion beyond original three starts',
        comparison_limit='C has infrastructure receive-loop repair and a later candidate; B never reached takeover, so no B/C causal comparison')


def claim_resume(rows,arm,attempt):
    """Later explicit user instruction supersedes the initial numerical cap.

    Each invocation still runs exactly one independently named attempt. Nothing
    retries automatically; all prior process lifecycles must be resolved first.
    """
    import re
    if arm not in ARMS or not re.fullmatch(arm+r'(?:[2-9]|[1-9][0-9]+)',attempt or ''):
        raise ValueError('resumed attempt must be named by arm and suffix >=2')
    starts=[r for r in rows if r['event']=='START_INTENT']
    key=lambda r:r.get('attempt',r['arm'])
    if any(key(r)==attempt for r in starts):raise RuntimeError('attempt already used; preserve its record')
    for prior in starts:
        ends=[r for r in rows if r['event']=='END' and key(r)==key(prior)]
        physical=[r for r in rows if r['event'] in ('PHYSICAL_END','PHYSICAL_UNCERTAIN') and key(r)==key(prior)]
        if len(ends)!=1 or len(physical)!=1 or physical[0]['event']!='PHYSICAL_END' or physical[0].get('cleanup_error'):
            raise RuntimeError('prior physical attempt not unambiguously terminated')
    return dict(reason='User explicitly removed launch cap and requested continued work toward a valuable switching result',
        original_budget_superseded=True,physical_start_cap=None,attempt=attempt,
        automatic_retry=False,prior_physical_starts=len(starts),scope='same seed, arms, safety, normal ACK and actual mode checks; no PX4 changes')


def reference_budget(origin,velocity,yaw,safety_altitude_m):
    """Same trajectory; replace old extra 5m ceiling with 1m physical margin.

    Original min-height and radial screen stay unchanged. Real-time physical
    limits are unchanged. Record both decisions instead of hiding rejected C2.
    """
    out=budget(origin,velocity,yaw)
    out['original_5m_screen_inside']=out['inside']
    out['reference_altitude_ceiling_m']=float(safety_altitude_m)-out['reserve_m']
    out['inside']=(out['max_reference_radius_m']+1.<=8.
        and out['min_reference_altitude_m']>=2.
        and out['max_reference_altitude_m']<=out['reference_altitude_ceiling_m'])
    out['screen_revision']='Only auxiliary reference ceiling: physical altitude limit minus existing 1m reserve; trajectory and real-time safety unchanged'
    return out


def fresh_active(msg,received_ns,request_ns,previous_timestamp):
    return bool(request_ns is not None and received_ns>=request_ns and msg.active
                and int(msg.exit_reason)==0 and int(msg.timestamp)>previous_timestamp)


class Experiment(original.Experiment):
    def upload_mission(self,mav):
        # Original protocol and deadline; service the receive queue instead of
        # sleeping 10ms for each unrelated telemetry packet. B stored all five
        # items in PX4 but did not observe the acceptance ACK before its timeout.
        from pymavlink import mavutil
        local=self.latest['vehicle_local_position']
        if not (local.xy_global and local.z_global):raise RuntimeError('mission needs valid global local-position reference')
        points=[global_waypoint(p,local.ref_lat,local.ref_lon,local.ref_alt) for p in MISSION_NED]
        self.event('cn_mission_upload_started',ned=MISSION_NED,global_int_msl=points,receive_loop='bounded drain 256 messages or 2ms after each safety pump')
        mav.mav.mission_count_send(self.instance+1,1,len(points))
        sent=set();end=time.monotonic()+15;packets=0;bursts=0;max_burst=0
        while time.monotonic()<end:
            self.pump(.01);burst_end=min(end,time.monotonic()+.002);n=0;bursts+=1
            while n<256 and time.monotonic()<burst_end:
                msg=mav.recv_match(blocking=False)
                if msg is None:break
                packets+=1;n+=1;max_burst=max(max_burst,n)
                if not original.upload_packet_valid(msg,self.instance+1):continue
                typ=msg.get_type()
                if typ in ('MISSION_REQUEST','MISSION_REQUEST_INT'):
                    seq=int(msg.seq)
                    if not 0<=seq<len(points):raise RuntimeError('mission request sequence outside uploaded route')
                    lat,lon,alt=points[seq];common=[self.instance+1,1,seq]
                    rest=[mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,int(seq==0),1,0.,.5,0.,float('nan')]
                    if typ=='MISSION_REQUEST_INT':mav.mav.mission_item_int_send(*common,mavutil.mavlink.MAV_FRAME_GLOBAL_INT,*rest,lat,lon,alt)
                    else:mav.mav.mission_item_send(*common,mavutil.mavlink.MAV_FRAME_GLOBAL,*rest,lat/1e7,lon/1e7,alt)
                    sent.add(seq);self.event('cn_mission_item_sent',sequence=seq,request_type=typ)
                elif typ=='MISSION_ACK':
                    self.event('cn_mission_ack',result=int(msg.type),sent=sorted(sent),received_packets=packets,receive_bursts=bursts,max_burst=max_burst)
                    if msg.type!=mavutil.mavlink.MAV_MISSION_ACCEPTED or sent!=set(range(len(points))):raise RuntimeError('mission not fully accepted')
                    return
        self.event('cn_mission_receive_timeout',received_packets=packets,receive_bursts=bursts,max_burst=max_burst,sent=sorted(sent))
        raise TimeoutError('mission upload acknowledgement')

    def receive(self,name,msg):
        super().receive(name,msg)
        if name=='raptor_status' and getattr(self,'cn_waiting_first',False):
            now=time.monotonic_ns()
            if fresh_active(msg,now,self.cn_request_ns,self.cn_previous_timestamp):
                if self.cn_active_gate is None:
                    self.cn_active_gate=dict(received_ns=now,timestamp=int(msg.timestamp),timestamp_sample=int(msg.timestamp_sample),
                        active=bool(msg.active),exit_reason=int(msg.exit_reason),latest_dds_nav=int(self.latest['vehicle_status'].nav_state))
                    self.event('cn_fresh_active_gate',**self.cn_active_gate,
                               semantics='native active implies CONFIGURED and native nav_state equals registered RAPTOR; DDS nav is only 5 Hz')

    def p1_flight(self,mode):
        arm=self.cfg['cn_reference']['arm']
        # Same Mission route, eligibility and dwell; native sequence avoids delayed
        # 1Hz MAVLink progress while upload retains its verified persistent link.
        mav=self.mav_open()
        try:
            self.upload_mission(mav)
            wait_mission_ready(self)
            self.mode(self.msgs.VehicleStatus.NAVIGATION_STATE_AUTO_MISSION)
            start=time.monotonic();current=None;dwell=None
            while time.monotonic()-start<25:
                self.pump(.02)
                current=mission_sequence(self)['seq_current']
                l=self.latest['vehicle_local_position']
                eligible=current==1 and math.hypot(l.vx,l.vy)>=.6 and math.hypot(l.x-3.,l.y-3.)>.75
                if eligible:
                    if dwell is None:dwell=time.monotonic()
                    if time.monotonic()-dwell>=.2:break
                else:dwell=None
            else:raise TimeoutError('predeclared moving Mission second-leg trigger')
        finally:
            mav.close();self.cn_mavlink=None
        l=self.latest['vehicle_local_position']
        origin=[float(l.x),float(l.y),float(l.z)];velocity=[float(l.vx),float(l.vy),float(l.vz)];yaw=float(l.heading)
        b=reference_budget(origin,velocity,yaw,self.cfg['safety_altitude_m']);self.event('cn_path_budget',**b)
        if arm!='A' and not b['inside']:raise RuntimeError('neural reference path exceeds physical-margin budget')
        self.event('cn_trigger_state',origin=origin,velocity=velocity,yaw=yaw,mission_current=current,arm=arm)
        bound=self.native_phase_end_bound()
        self.event('cn_control_trigger',end_bound_px4_us=bound,arm=arm)
        if arm=='A':
            # No external stream, no neural tail, same Mission producer retains authority.
            start=bound;end=bound;deadline=time.monotonic()+20
            while end-start<2_200_000:
                if time.monotonic()>deadline:raise TimeoutError('2.2s native classic control observation')
                self.pump(.02)
                if self.latest['vehicle_status'].nav_state!=self.msgs.VehicleStatus.NAVIGATION_STATE_AUTO_MISSION:
                    raise RuntimeError('classic control unexpectedly left Mission')
                end=self.native_phase_end_bound()
            self.event('cn_classic_control_finished',start_px4_us=start,end_px4_us=end,duration_s=(end-start)/1e6)
            self.mode(self.msgs.VehicleStatus.NAVIGATION_STATE_AUTO_LOITER)
            self.hover(4.,'landing_recovery',prefix='p1_phase');self.checks['cn_case']='COMPLETE';return

        sends=(self.out/'cn-setpoints.jsonl').open('w');self.files.append(sends)
        t0=None;last=-1.;count=0;gap=False;mode_confirmed=False
        self.cn_waiting_first=(arm=='C');self.cn_request_ns=None;self.cn_active_gate=None
        rs=self.latest.get('raptor_status')
        if rs is None or rs.active:raise RuntimeError('fresh inactive RAPTOR required before unique subject request')
        self.cn_previous_timestamp=int(rs.timestamp)

        def publish():
            nonlocal t0,last,count,gap
            # During C's confirmation wait the fresh controller-owned active flag
            # is native-mode proof. After mode() returns both arms use the original
            # nav_state guard, 50 Hz rule and time-parameterized trajectory/gap.
            early=(arm=='C' and not mode_confirmed and self.cn_active_gate is not None
                   and self.latest['raptor_status'].active)
            if not early and self.latest['vehicle_status'].nav_state!=mode:return
            if count==0 and arm=='C' and self.cn_active_gate is None:return
            now=time.monotonic()
            if t0 is None:t0=now;t=0.
            else:t=now-t0
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
            if count==1:
                self.cn_waiting_first=False
                self.event('cn_first_external_publish',before_ns=before,after_ns=after,profile_s=t,arm=arm,
                           mode_confirmed=mode_confirmed,active_gate=self.cn_active_gate)

        self.event('handover_requested',end_bound_px4_us=bound,from_controller='C',to_controller='N',iteration=0,subject=True)
        self.cn_request_ns=time.monotonic_ns()
        if arm=='C':self.stream=publish
        self.mode(mode) # Unmodified normal command, ACK validation, nav confirmation.
        mode_confirmed=True
        if arm=='B':self.stream=publish;publish()
        self.wait(lambda:self.latest.get('raptor_status') and self.latest['raptor_status'].active,5,'RAPTOR active')
        if t0 is None:raise RuntimeError('first reference was not released')
        while time.monotonic()-t0<DURATION:
            self.pump(.02);original.require_neural(self.latest,mode)
        self.event('cn_reference_finished',published=count,profile_s=time.monotonic()-t0)
        self.event('handover_requested',end_bound_px4_us=self.native_bound_streaming(),from_controller='N',to_controller='C',iteration=0,subject=False,purpose='landing recovery')
        self.mode(self.msgs.VehicleStatus.NAVIGATION_STATE_AUTO_LOITER)
        self.stream=None
        self.hover(4.,'landing_recovery',prefix='p1_phase');self.checks['cn_case']='COMPLETE'


def classic_chain_gate(out,chain):
    import numpy as np
    errors=[];local={}
    if set(chain.get('motors',{}))!={'0','1','2','3'}:errors.append('four motors missing')
    if set(chain.get('partial_tail_bytes',{}))!={'0','1','2','3'} or any(chain.get('partial_tail_bytes',{}).values()):errors.append('incomplete traces')
    if chain.get('motors_disagree_steps')!=0:errors.append('four motor samples disagree')
    ev=[json.loads(s) for s in (out/'events.jsonl').read_text().splitlines()]
    tr=next((e for e in ev if e['event']=='cn_control_trigger'),None)
    end=next((e for e in ev if e['event']=='cn_classic_control_finished'),None)
    if tr is None or end is None:return ['classic control boundaries missing'],local
    for path in sorted((out/'gz-motor').glob('motor-*.bin')):
        k,rows,tail=read_trace(path)
        mask=(rows['sim_us']>=tr['end_bound_px4_us'])&(rows['sim_us']<=end['end_px4_us'])
        s=step_summary(rows,mask);local[str(k)]=s;age=s['applied_age_us'] or {}
        if not s['steps'] or age.get('count')!=s['steps'] or s['negative_age_steps']:errors.append(f'{k}: missing/invalid samples')
        if age.get('p99') is None or age['p99']>GATE['p99_us'] or age.get('max',float('inf'))>GATE['max_us']:errors.append(f'{k}: age gate')
        if s['longest_over_target_steps']>GATE['longest_over_target_steps']:errors.append(f'{k}: consecutive age gate')
        if mask.sum()>1 and np.max(np.diff(rows['sim_us'][mask]))>4000:errors.append(f'{k}: missing physical steps')
    return errors,local


def run(arm,continue_after_ack=False,attempt=None,continue_until_result=False):
    EVIDENCE.mkdir(exist_ok=True)
    ledger=EVIDENCE/'attempts.jsonl'
    with (EVIDENCE/'attempts.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        rows=[json.loads(s) for s in ledger.read_text().splitlines()] if ledger.exists() else []
        if continue_until_result:
            if continue_after_ack:raise ValueError("choose one continuation mode")
            continuation=claim_resume(rows,arm,attempt)
        else:
            if attempt:raise ValueError("named repeat requires explicit user-directed continuation")
            claim(rows,arm,continue_after_ack);continuation=None
        attempt=attempt or arm
        try:host=host_gate()
        except Exception as exc:
            original.append(ledger,dict(event='BLOCKED_BEFORE_START',arm=arm,time_ns=time.time_ns(),reason=str(exc),counts_as_start=False));raise
        candidate=identity()
        if continue_after_ack:continuation=verify_ack_continuation(candidate)
        if continue_until_result:
            old=json.loads((EVIDENCE/'C/candidate-before.json').read_text())
            for key in ['lab','policy_sha256','gz_research_plugin_sha256']:
                if candidate.get(key)!=old.get(key):raise RuntimeError('Lab/policy/plugin changed outside continuation scope')
        evidence=EVIDENCE/attempt;evidence.mkdir(exist_ok=False)
        base.write(evidence/'candidate-before.json',candidate);base.write(evidence/'host-before.json',host)
        if continuation:
            base.write(evidence/'continuation.json',continuation)
            original.append(ledger,dict(event='USER_DIRECTED_CONTINUATION',arm=arm,time_ns=time.time_ns(),counts_as_start=False,**continuation))
        prior=[EVIDENCE/a/'candidate-before.json' for a in ARMS[:ARMS.index(arm)]]
        if not continuation and any(json.loads(p.read_text())!=candidate for p in prior):raise RuntimeError('candidate changed between arms')
        cfg=json.loads(CONFIG.read_text());cfg['cn_reference']['arm']=arm
        if continuation:cfg['cn_reference']['user_directed_continuation']=continuation
        if continue_until_result:
            cfg['cn_reference'].update(physical_start_cap=None,one_per_arm=False,order=None,attempt=attempt,
                stop_rule='Each failed attempt stops for diagnosis; user removed numerical cap; no automatic retry')
        config=evidence/'config.json';base.write(config,cfg)
        out=evidence/'flight'
        args=SimpleNamespace(kind='p1_c_to_n',config=config,condition='single',treatment=None,output=out,startup_only=False,capture_raw_sensors=False,hover_s=None,sim_seed=SEED,initial_yaw_deg=0.)
        original.append(ledger,dict(event='START_INTENT',arm=arm,attempt=attempt,time_ns=time.time_ns(),seed=SEED,start_number=1+sum(r['event']=='START_INTENT' for r in rows),budget=None if continue_until_result else 3,output=str(out.relative_to(ROOT))))
        st=time.monotonic();cpu=resource.getrusage(resource.RUSAGE_CHILDREN);sc=time.process_time()
        e=None;status='FAIL';reason=None;cleanup_error=None
        try:
            e=Experiment(args);e.metadata['scenario']='cn_reference_handoff_'+arm;e.execute();status='PASS'
        except BaseException as exc:
            reason=repr(exc);traceback.print_exc()
            if e:e.event('failure',reason=reason)
        finally:
            cleanup_error=original.close_experiment(e)
            if cleanup_error:status='FAIL'
            if e:base.write(out/'validation.json',dict(status=status,execution_status=status,reason=reason,cleanup_error=cleanup_error,checks=e.checks))
            end=resource.getrusage(resource.RUSAGE_CHILDREN)
            cost=dict(wall_s=time.monotonic()-st,cpu_s=time.process_time()-sc+end.ru_utime+end.ru_stime-cpu.ru_utime-cpu.ru_stime)
            original.append(ledger,dict(event='PHYSICAL_END' if not cleanup_error else 'PHYSICAL_UNCERTAIN',arm=arm,attempt=attempt,time_ns=time.time_ns(),status=status,reason=reason,cleanup_error=cleanup_error,**cost))
        analysis={};errors=[];at=time.monotonic();ac=resource.getrusage(resource.RUSAGE_CHILDREN);asc=time.process_time()
        try:
            import subprocess
            if not e or not (out/'flight.ulg').exists():raise RuntimeError('raw ULog missing')
            with (out/'logs/analysis-historical.log').open('w') as log:
                analysis['historical_exit']=subprocess.run([sys.executable,str(ROOT/'tools/analyze.py'),str(out)],stdout=log,stderr=subprocess.STDOUT).returncode
            chain=output_analysis(out);base.write(out/'output-chain.json',chain)
            if arm=='A':
                ce,local=classic_chain_gate(out,chain);analysis['classic_local_chain']=local
            else:ce=chain_gate(chain)
            errors.extend(ce);analysis['output_chain_errors']=ce
            from cn_reference.analyze import analyze
            measured=analyze(out,arm);base.write(out/'cn-reference-measurement.json',measured)
            analysis['measurement']=measured.get('evidence_completion')
            gate=measured.get('evidence_completion',{})
            if not gate.get('complete'):errors.append('measurement evidence incomplete: '+str(gate))
        except BaseException as exc:
            traceback.print_exc();errors.append('analysis: '+repr(exc))
        after=identity();base.write(evidence/'candidate-after.json',after)
        if after!=candidate:errors.append('candidate identity changed')
        try:base.write(evidence/'host-after.json',host_gate())
        except Exception as exc:errors.append('host-after: '+repr(exc))
        ac1=resource.getrusage(resource.RUSAGE_CHILDREN)
        analysis['wall_s']=time.monotonic()-at;analysis['cpu_s']=time.process_time()-asc+ac1.ru_utime+ac1.ru_stime-ac.ru_utime-ac.ru_stime
        # Any execution failure ends this attempt, even if a physical safety
        # outcome. Later explicitly authorized attempts are separately recorded.
        ok=status=='PASS' and cleanup_error is None and not errors
        result=dict(arm=arm,attempt=attempt,status='COMPLETE' if ok else 'STOPPED',execution_status=status,reason=reason,cleanup_error=cleanup_error,
                    infrastructure_ok=ok,errors=errors,execution_cost=cost,analysis=analysis,candidate_unchanged=after==candidate)
        base.write(evidence/'result.json',result)
        original.append(ledger,dict(event='END',arm=arm,attempt=attempt,time_ns=time.time_ns(),infrastructure_ok=ok,status=result['status'],errors=errors))
        return 0 if ok else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--arm',choices=ARMS,required=True);parser.add_argument('--execute',required=True,action='store_true')
    parser.add_argument('--continue-after-mission-ack',action='store_true',help='Later user-directed continuation: only the unspent C start after the exact B pre-subject ACK failure')
    parser.add_argument('--attempt',help='Independent attempt ID, e.g. C2; never overwrites earlier evidence')
    parser.add_argument('--continue-until-result',action='store_true',help='Later explicit user authorization removes initial launch cap; still exactly one attempt per invocation')
    args=parser.parse_args();raise SystemExit(run(args.arm,args.continue_after_mission_ack,args.attempt,args.continue_until_result))

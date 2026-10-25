"""Offline isolation of actual runner/native reference sources. No SITL imports."""
import ast
import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
CFG = ROOT/'data/p9-20261024-dev-01/run/config.json'
NATIVE = ROOT/'uav_lab/.local/checkouts/px4-raptor/src/modules/mc_raptor/mc_raptor.cpp'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def block(text, start):
    begin = text.index('{', start);depth = 1;i = begin+1
    while depth:
        depth += (text[i] == '{')-(text[i] == '}');i += 1
    return text[start:i]


def snapshot():
    native = NATIVE.read_text()
    header=NATIVE.with_suffix('.hpp').read_text()
    assert 'NUM_TRAJECTORY_SETPOINT_DTS = 100;' in header
    assert 'TRAJECTORY_SETPOINT_TIMEOUT = 200 * 1000;' in header
    assert 'TRAJECTORY_SETPOINT_INVALID_COUNT_WARNING_INTERVAL = 100;' in header
    read = block(native, native.index('if (status.subscription_update_trajectory_setpoint)'))
    guard = block(native, native.index('if (!timestamp_last_trajectory_setpoint_set || use_internal_reference'))
    # Include the matching else of the stale test.
    start=native.index(guard)
    else_start=native.index('else {',start+len(guard))
    end=else_start+len(block(native,else_start))
    guard = native[start:end]
    assert 'previous_trajectory_setpoint_stale = false;' in guard
    methods = {name: block(native, native.index('void Raptor::'+name+'('))
               for name in ['research_target_capture', 'research_target_step', 'research_recovery_transition']}
    order = native[native.index('research_target_step(next_active, status.trajectory_setpoint_stale);'):]
    assert order.index('research_recovery_transition') < order.index('_sample_clock.accept')
    assert '(current_time - timestamp_last_trajectory_setpoint) > TRAJECTORY_SETPOINT_TIMEOUT' in guard
    return {'native_sha256': sha(NATIVE), 'native_path': str(NATIVE.relative_to(ROOT)),
            'native_header_sha256':sha(NATIVE.with_suffix('.hpp')),
            'checked_source_constants':{'read_interval_ring_size':100,'invalid_warning_interval':100,'timeout_us':200000},
            'runner_sha256': sha(ROOT/'tools/run_experiment.py'), 'read': read, 'guard': guard,
            'methods': methods, 'transition_before_clock_rejection': True}


class Clock:
    us = 0
    epoch = 1000.
    def monotonic(self):return self.epoch+self.us/1e6
    def time(self):return self.monotonic()
    def monotonic_ns(self):return int(self.monotonic()*1e9)


class Message:
    pass


class Publisher:
    def __init__(self):self.messages=[]
    def publish(self, message):self.messages.append(copy.deepcopy(message))


def runner(startup=None):
    text = (ROOT/'tools/run_experiment.py').read_text()
    cls = next(n for n in ast.parse(text).body if isinstance(n, ast.ClassDef) and n.name == 'Experiment')
    names = {'profile_cfg','reposition','profile_duration','p1_profile','p5_gap_windows','start_stream'}
    methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert len(methods) == len(names)
    tree = ast.fix_missing_locations(ast.Module(body=[ast.ClassDef(name='Experiment', bases=[], keywords=[],
                                body=methods, decorator_list=[])], type_ignores=[]))
    clock = Clock();env = {'time':clock,'__name__':'pure_runner_isolation'}
    exec(compile(tree, 'actual_runner_pure_methods', 'exec'), env)
    cfg = json.loads(CFG.read_text());obj = env['Experiment'].__new__(env['Experiment'])
    obj.cfg=cfg;obj.pcfg=cfg['p2_profile'];obj.trajpub=Publisher();obj.offpub=Publisher()
    obj.msgs=SimpleNamespace(TrajectorySetpoint=Message, OffboardControlMode=Message)
    obj.events=[];obj.event=lambda name,**kw:obj.events.append({'event':name,**kw})
    windows=obj.p5_gap_windows()
    origin=startup['origin_event']['origin_ned_m'] if startup else [0.,0.,-3.]
    yaw=startup['origin_event']['yaw_rad'] if startup else 0.
    obj.start_stream(origin,yaw,False,gaps=windows)
    obj.stream_t0=clock.monotonic()
    return obj, clock


def cpp_source(snap, context=None):
    # Stubs provide transport/parameter/publication dependencies only. Read,
    # stale capture and module transitions below are copied byte-for-byte.
    pre = r'''
#define __PX4_POSIX 1
#include <cmath>
#include <cstdint>
#include <iostream>
#include <iomanip>
#include <string>
#include "research/state/TargetProfile.hpp"
#include "research/state/RecoveryTarget.hpp"
#include "research/state/SampleClock.hpp"
#define PX4_WARN(...) ((void)0)
#define PX4_INFO(...) ((void)0)
#define PX4_ERR(...) ((void)0)
#define PX4_ISFINITE(x) std::isfinite(x)
using TI=int;using param_t=int;
uint64_t now_us=0;
uint64_t hrt_absolute_time(){return now_us;}
param_t param_find(const char* s){return std::string(s)=="MC_RAPTOR_RSH"?1:std::string(s)=="MC_RAPTOR_RTGT"?2:std::string(s)=="MC_RAPTOR_RTDEC"?3:4;}
int32_t rtgt=0;float rrec=0;
void param_get(param_t p,int32_t* v){*v=p==1?1:rtgt;}
void param_get(param_t p,float* v){*v=p==3?2.f:rrec;}
struct research_target_s {enum {KIND_END=1,KIND_CAPTURE=2,KIND_PROFILE=3,END_RECAPTURE=4,END_EXTERNAL_SETPOINT=5,END_INACTIVE=6};};
struct research_recovery_s {enum {KIND_END=1,KIND_START=2,END_INACTIVE=3,END_STALE=4};};
struct trajectory_setpoint_s {float position[3]{},velocity[3]{},yaw{0},yawspeed{0};};
struct Raptor {
 trajectory_setpoint_s _trajectory_setpoint{};
 float position[3]{},linear_velocity[3]{};
 struct {float q[4]{1,0,0,0};} _vehicle_attitude;
 struct {uint64_t timestamp_sample=0;} _vehicle_angular_velocity,_vehicle_local_position;
 handover_research::TargetProfile _research_target{};
 int32_t _research_target_mode=0;float _research_target_decel=0;
 bool _research_target_activation=false;uint64_t _research_target_capture_time=0,_research_target_capture_sample=0,_research_target_local_sample=0;
 float _research_target_vehicle_position[3]{},_research_target_vehicle_velocity[3]{};uint8_t _research_target_phase=0;
 handover_research::RecoveryTarget _research_recovery{};handover_research::RecoveryStep _research_recovery_last{};
 bool _research_recovery_previous_stale=false,_research_recovery_armed=false;
 float _research_recovery_vehicle_position[3]{},_research_recovery_vehicle_velocity[3]{};
 int capture=0,rec_start=0;
 void research_target_publish(uint8_t k,uint8_t){if(k==research_target_s::KIND_CAPTURE)capture++;}
 void research_recovery_publish(uint8_t k,uint8_t){if(k==research_recovery_s::KIND_START)rec_start++;}
 void research_target_capture(bool,bool);void research_target_step(bool,bool);void research_recovery_transition(bool,bool,bool);
 uint64_t timestamp_last_trajectory_setpoint=0;bool timestamp_last_trajectory_setpoint_set=false;
 bool previous_trajectory_setpoint_stale=false,previous_active=false;
 handover_research::SampleClock sample_clock{};
 static constexpr uint64_t TRAJECTORY_SETPOINT_TIMEOUT=200000;
 static constexpr unsigned NUM_TRAJECTORY_SETPOINT_DTS=100,TRAJECTORY_SETPOINT_INVALID_COUNT_WARNING_INTERVAL=100;
 int32_t trajectory_setpoint_dts[100]{};unsigned trajectory_setpoint_dt_index=0,trajectory_setpoint_invalid_count=0;bool trajectory_setpoint_dts_full=false;
 void tick(uint64_t current_time,uint64_t sample,bool updated,bool next_active,trajectory_setpoint_s temp_trajectory_setpoint){
  now_us=current_time;_vehicle_angular_velocity.timestamp_sample=sample;_vehicle_local_position.timestamp_sample=sample;
  bool use_internal_reference=false;
  struct {bool subscription_update_trajectory_setpoint,trajectory_setpoint_stale;uint64_t timestamp_last_trajectory_setpoint;} status{};
  status.subscription_update_trajectory_setpoint=updated;
  capture=0;rec_start=0;
'''
    post = r'''
  research_target_step(next_active,status.trajectory_setpoint_stale);
  research_recovery_transition(next_active,status.trajectory_setpoint_stale,!previous_active&&next_active);
  unsigned skipped=sample_clock.accept(sample);
  previous_active=next_active;
  std::cout<<std::setprecision(17)<<status.trajectory_setpoint_stale<<' '<<capture<<' '<<rec_start<<' '<<skipped<<' '
   <<timestamp_last_trajectory_setpoint<<' '<<_research_recovery_armed<<' '<<_research_target.active;
  for(int i=0;i<2;i++)std::cout<<' '<<_trajectory_setpoint.position[i]<<' '<<_trajectory_setpoint.velocity[i];
  std::cout<<std::endl;
 }
};
'''
    main = r'''
float read_float(){std::string token;std::cin>>token;return std::stof(token);}
int main(){Raptor r;uint64_t us,sample;int update,active;
 while(std::cin>>us>>sample>>update>>active>>rtgt>>rrec){trajectory_setpoint_s sp;
  for(int i=0;i<2;i++){r.position[i]=read_float();r.linear_velocity[i]=read_float();}
  r.position[2]=-3.f;
  for(int i=0;i<2;i++){sp.position[i]=read_float();sp.velocity[i]=read_float();}sp.position[2]=-3.f;
  r.tick(us,sample,update,active,sp);
 }
}
'''
    if context:
        assign=''.join('r._vehicle_attitude.q[%d]=float(%r);'%(i,x) for i,x in enumerate(context['quaternion']))
        main=main.replace('Raptor r;', 'Raptor r;'+assign)
        main=main.replace('r.position[2]=-3.f;', 'r.position[2]=float(%r);'%context['position_ned'][2])
        main=main.replace('sp.position[2]=-3.f;', 'sp.position[2]=float(%r);sp.yaw=float(%r);'%(context['origin_event']['origin_ned_m'][2],context['origin_event']['yaw_rad']))
        main=main.replace('r.tick(us,sample,update,active,sp);','for(int j=0;j<4;j++)r._vehicle_attitude.q[j]=read_float();r.tick(us,sample,update,active,sp);')
        post=post.replace('std::cout<<std::endl;', "std::cout<<' '<<_trajectory_setpoint.yaw<<std::endl;")
    return pre+snap['read']+'\n'+snap['guard']+'\n'+post+'\n'+'\n'.join(snap['methods'].values())+'\n'+main


class Oracle:
    def __init__(self, snapshot_value=None, context=None):
        self.temp=tempfile.TemporaryDirectory(prefix='p10a3-oracle-')
        self.context=context
        p=Path(self.temp.name);self.source=cpp_source(snapshot_value or snapshot(),context);(p/'oracle.cpp').write_text(self.source)
        subprocess.run(['g++','-std=c++17','-O2','-Wall','-Wextra','-I',str(ROOT),str(p/'oracle.cpp'),'-o',str(p/'oracle')],check=True,capture_output=True,text=True)
        self.process=subprocess.Popen([str(p/'oracle')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
    def tick(self, row):
        self.process.stdin.write(' '.join(str(int(x)) if isinstance(x,bool) else str(x) for x in row)+'\n');self.process.stdin.flush()
        values=self.process.stdout.readline().split()
        if len(values)!=(12 if self.context else 11):raise RuntimeError('offline oracle output failure')
        return [int(x) for x in values[:7]]+[float(x) for x in values[7:]]
    def close(self):
        self.process.stdin.close();self.process.wait(timeout=10)
        if self.process.returncode:raise RuntimeError('offline oracle failed')
        self.temp.cleanup()


def startup_observation():
    import sys
    import numpy as np
    from pyulog import ULog
    sys.path.insert(0,str(ROOT/'tools'))
    from p6_export import TOPICS,reconstruct
    run=CFG.parent
    ev=[json.loads(l) for l in (run/'events.jsonl').read_text().splitlines()]
    origin=next(e for e in ev if e['event']=='p1_reference_origin')
    boundary=next(e['px4_bound_us'] for e in ev if e['event']=='p1_profile_started')
    u=ULog(str(run/'flight.ulg'),TOPICS);t={d.name:d.data for d in u.data_list if d.multi_id==0};rec=reconstruct(t)
    status=t['raptor_status'];st=np.asarray(status['timestamp'],np.int64)
    last=np.asarray(status['timestamp_last_trajectory_setpoint'],np.int64)
    read=np.asarray(status['subscription_update_trajectory_setpoint']).astype(bool)&(last==st)&(last>0)
    nearby=np.flatnonzero(read&(st>=boundary-20000)&(st<=boundary+4000))
    assert len(nearby)>0
    first_read=int(st[nearby[0]])
    k=int(np.searchsorted(rec['s'],first_read))-1;assert k>=0 and rec['ok'][k]
    before=int(np.searchsorted(st,rec['s'][k],side='right'))-1
    assert status['active'][before] and status['trajectory_setpoint_stale'][before]
    tm=t['research_timing'];i=int(np.flatnonzero((tm['timestamp_sample']==rec['s'][k])&tm['executor_called'].astype(bool))[0])
    at=t['vehicle_attitude'];a=int(np.flatnonzero(at['timestamp_sample']==tm['attitude_sample'][i])[0])
    quat=[float(at[f'q[{j}]'][a]) for j in range(4)]
    w,x,y,z=quat;bz=[2*(x*z+w*y),2*(y*z-w*x),1-2*(x*x+y*y)]
    yaw=origin['yaw_rad'];c,s=math.cos(yaw),math.sin(yaw)
    pos=rec['pos'][k].tolist();vel=rec['vel'][k].tolist();o=origin['origin_ned_m']
    def rotate(v):return [c*v[0]+s*v[1],s*v[0]-c*v[1]]
    return {'origin_event':origin,'profile_native_bound_us':boundary,'first_confirmed_stream_read_us':first_read,'state_sample_us':int(rec['s'][k]),
        'prestream_status':{key:int(status[key][before]) for key in ['timestamp','timestamp_sample','active','trajectory_setpoint_stale','subscription_update_trajectory_setpoint']},
        'local_position_sample_us':int(tm['local_position_sample'][i]),'attitude_sample_us':int(tm['attitude_sample'][i]),
        'position_ned':pos,'velocity_ned':vel,'quaternion':quat,
        'relative_position_flu':rotate([pos[0]-o[0],pos[1]-o[1]]),'velocity_flu':rotate(vel),
        'q_flu':rotate([-9.80665*bz[0]/bz[2],-9.80665*bz[1]/bz[2]]),
        'timing_scope':'actual named sensor/module values at LAST inference before first confirmed stream read. Source-allowed callback class starts from this declared pre-read state; profile native bound is later, not substituted for exact monotonic start. This is not an exact historic clock replay',
        'inputs':{str(p.relative_to(ROOT)):sha(p) for p in [run/'flight.ulg',run/'events.jsonl',run/'config.json']}}


def lift_attitude(q,yaw):
    # A valid body-z lift for the fixed-yaw q output; actual native float casts
    # are retained, not asserted to preserve the geometric output exactly.
    f,l=map(float,q);norm=math.sqrt(1+(f/9.80665)**2+(l/9.80665)**2)
    roll=-math.asin((l/9.80665)/norm);pitch=math.atan2(-f/9.80665,1.)
    cy,sy=math.cos(yaw/2),math.sin(yaw/2);cp,sp=math.cos(pitch/2),math.sin(pitch/2);cr,sr=math.cos(roll/2),math.sin(roll/2)
    return [cy*cp*cr+sy*sp*sr,cy*cp*sr-sy*sp*cr,cy*sp*cr+sy*cp*sr,sy*cp*cr-cy*sp*sr]

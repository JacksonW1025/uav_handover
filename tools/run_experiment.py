#!/usr/bin/env python3
"""Isolated headless SITL runner. Owns only the processes it starts."""
import argparse
import datetime as dt
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import traceback
import uuid
import resource
from readiness import Readiness
import p6_conditions
import p8_conditions
import psutil

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT/'uav_lab'
TYPES = ['classic_hover','raptor_hover','handover_c_to_n','handover_n_to_c',
         'handover_c_n_c','repeated_handover','state_reset','state_hold','state_restore','state_injection',
         'p1_c_to_n','p1_n_to_c','p1_baseline_classic','p1_baseline_raptor',
         'p2_c_to_n','p2_n_to_c','p2_baseline_classic','p2_baseline_raptor','p2_crash_probe',
         'p3_sequence','p3_baseline_raptor','p5_gap','p6_ident']
# P2 reuses the P1 flight sequence; only the treatment parameters and the condition profile differ.
# P4-01c: T0/T1 are N2 memory (RINI=4) with the original zero-velocity takeover target or the speed-matched one.
P2_TREATMENT_KINDS={'p2_c_to_n':['N0','N1','N2g','N2','N2s','Nstar','T0','T1'],'p2_n_to_c':['C0','C2'],'p2_baseline_classic':['B'],'p2_baseline_raptor':['B']}
# P3: C->N (N0), RAPTOR hover, N->C, classic deactivation, second C->N with a memory treatment; or the RAPTOR baseline.
P3_TREATMENT_KINDS={'p3_sequence':['N0','N3','N2s','N2'],'p3_baseline_raptor':['B']}
# P5: RAPTOR tracks a runner-published line; the stream pauses for D s and resumes on the same line (E2 once, E3 repeated).
P5_TREATMENT_KINDS={'p5_gap':['T0','T1','T1a1','T1a3']}
# P6: two more T1 decelerations for p5_gap (config/p6.json p5.treatments) and the identification flights (RAPTOR follows a
# runner-published step / chase / brake / capture profile through its external setpoint input).
P6_GAP_TREATMENTS=['T1a0.75','T1a1.5']
P6_TREATMENT_KINDS={'p6_ident':['T0']}
# P7: rate-limited recovery treatment for p5_gap (config/p7.json p5.treatments: T1a3 capture with MC_RAPTOR_RREC 2.0).
P7_GAP_TREATMENTS=['T1a3r2']
# P9 factorial controls use existing RTGT/RTDEC/RREC parameters, with explicit
# names and a P9-only config gate. No PX4/policy/safety-threshold change.
P9_GAP_TREATMENTS=['P9-Z','P9-C','P9-R','P9-CR']
P11_GAP_TREATMENTS=['P11-Z','P11-C']

def p5_profile(p5,spec):
    """P5 gap runs: merged reference profile (pure function of the config). Cruise = pre_gap_s + count*D +
    (count-1)*recover + post_gap_s; the line (ramp, cruise, deceleration to rest) is centred on RAPTOR's hover capture
    by a start offset of -L/2 along the axis, reached by the reposition trapezoid before the hold."""
    p={**p5['profile'],**{k:v for k,v in spec.items() if k in p5['profile_overrides']}}
    if 'windows_s' in spec['gaps']:return p6_windows_profile(spec,p)
    g=spec['gaps'];v=float(spec['speed_m_s']);n,D,r=int(g['count']),float(g['duration_s']),float(g['recover_s'])
    p['cruise_s']=round(float(p['pre_gap_s'])+n*D+(n-1)*r+float(p['post_gap_s']),9)
    length=.5*v*float(p['accel_s'])+v*p['cruise_s']+v*v/(2*float(p['decel_m_s2']))
    p['start_offset_m']=-round(length/2,6);p['path_length_m']=length;p['gaps']={'count':n,'duration_s':D,'recover_s':r}
    return p

def p6_windows_profile(spec,p):
    """P6 C2: explicit interruption windows [start, end) in s after the first interruption start (unequal lengths and
    recoveries). Cruise = pre_gap_s + end of the last window + post_gap_s; the line is centred as in p5_profile."""
    w=[[float(a),float(b)] for a,b in spec['gaps']['windows_s']];v=float(spec['speed_m_s'])
    if w[0][0]!=0. or any(b<=a for a,b in w) or any(w[k+1][0]<=w[k][1] for k in range(len(w)-1)):raise RuntimeError('invalid interruption windows')
    p['cruise_s']=round(float(p['pre_gap_s'])+w[-1][1]+float(p['post_gap_s']),9)
    length=.5*v*float(p['accel_s'])+v*p['cruise_s']+v*v/(2*float(p['decel_m_s2']))
    p['start_offset_m']=-round(length/2,6);p['path_length_m']=length;p['gaps']={'windows_s':w,'count':len(w)}
    return p

def cpu_affinity():
    # Optional host pinning, e.g. HANDOVER_CPU_AFFINITY='px4=8-11;gazebo=12-13;agent=6-7;runner=4-5'.
    text=os.environ.get('HANDOVER_CPU_AFFINITY','');out={}
    for item in filter(None,text.split(';')):
        name,_,cores=item.partition('=');out[name.strip()]=cores.strip()
    return out

def write(path, value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

class Experiment:
    def __init__(self,args):
        self.args=args
        self.startup_only=args.startup_only
        self.cfg=json.loads(args.config.read_text())
        if args.hover_s is not None:self.cfg['hover_s']=args.hover_s
        self.pcfg=None
        if args.kind.startswith('p1_'):
            # P1 condition is part of the recorded run configuration.
            if 'p1' not in self.cfg or args.condition not in self.cfg['p1']['conditions']:raise RuntimeError('P1 kinds need --condition from config p1.conditions')
            self.cfg['p1_condition']=args.condition;self.cfg['p1_speed_m_s']=float(self.cfg['p1']['conditions'][args.condition]['speed_m_s'])
            if args.treatment:raise RuntimeError('--treatment applies only to P2 kinds')
        elif args.kind in P2_TREATMENT_KINDS:
            # Condition, treatment and the merged reference profile are part of the recorded run configuration.
            p2=self.cfg.get('p2',{})
            if args.condition not in p2.get('conditions',{}):raise RuntimeError('P2 kinds need --condition from config p2.conditions')
            if args.treatment not in P2_TREATMENT_KINDS[args.kind] or args.treatment not in p2['treatments']:raise RuntimeError(f'{args.kind} needs --treatment in {P2_TREATMENT_KINDS[args.kind]}')
            condition=p2['conditions'][args.condition]
            self.pcfg={k:v for k,v in p2.items() if k not in ['conditions','treatments']};self.pcfg.update({k:v for k,v in condition.items() if k in p2['profile_overrides']})
            speed=condition.get('raptor_baseline_speed_m_s',condition['speed_m_s']) if args.kind=='p2_baseline_raptor' else condition['speed_m_s']
            self.cfg['p1_condition']=args.condition;self.cfg['p1_speed_m_s']=float(speed)
            self.cfg['p2_treatment']=args.treatment;self.cfg['p2_treatment_parameters']=p2['treatments'][args.treatment];self.cfg['p2_profile']=self.pcfg
        elif args.kind in P3_TREATMENT_KINDS:
            p3=self.cfg.get('p3',{});spec=p3.get('conditions',{}).get(args.condition)
            if spec is None:raise RuntimeError('P3 kinds need --condition from config p3.conditions')
            if bool(spec.get('baseline_only'))!=(args.kind=='p3_baseline_raptor'):raise RuntimeError('p3_baseline_raptor runs condition R only; p3_sequence runs the deactivation conditions')
            if args.treatment not in P3_TREATMENT_KINDS[args.kind]:raise RuntimeError(f'{args.kind} needs --treatment in {P3_TREATMENT_KINDS[args.kind]}')
            self.cfg['p3_condition']=args.condition;self.cfg['p3_condition_spec']=spec
            self.cfg['p3_treatment']=args.treatment;self.cfg['p3_treatment_parameters']=p3['treatments'][args.treatment]
        elif args.kind in P5_TREATMENT_KINDS:
            p5=self.cfg.get('p5',{});spec=p5.get('conditions',{}).get(args.condition)
            # P6: B/C conditions are generated from the pre-registered rule (config p5.condition_rule) by name.
            if spec is None and args.condition:spec=p6_conditions.gap_spec(self.cfg,args.condition)
            # P8-B: cases of the frozen P8 test space (any heading, 2-4 windows), generated by the same rule (p8_conditions).
            if spec is None and args.condition and 'p8' in self.cfg:spec=p8_conditions.case_spec(self.cfg,args.condition)
            if spec is None:raise RuntimeError('p5_gap needs --condition from config p5.conditions')
            if spec.get('cancelled'):raise RuntimeError('condition cancelled by the pre-registered safety budget: '+args.condition)
            allowed=P5_TREATMENT_KINDS[args.kind]+P6_GAP_TREATMENTS+P7_GAP_TREATMENTS
            if 'p9' in self.cfg:allowed=allowed+P9_GAP_TREATMENTS
            if 'p11' in self.cfg:allowed=allowed+P11_GAP_TREATMENTS
            if args.treatment not in allowed or args.treatment not in p5['treatments']:raise RuntimeError(f'p5_gap needs --treatment in {allowed}')
            # The P2 treatment and profile keys are reused so apply_treatment, the stream and the analyzers work unchanged.
            self.pcfg=p5_profile(p5,spec);self.cfg['p1_condition']=args.condition;self.cfg['p1_speed_m_s']=float(spec['speed_m_s'])
            self.cfg['p2_treatment']=args.treatment;self.cfg['p2_treatment_parameters']=p5['treatments'][args.treatment];self.cfg['p2_profile']=self.pcfg
            self.cfg['p5_condition_spec']=spec
        elif args.kind in P6_TREATMENT_KINDS:
            p6=self.cfg.get('p6',{}).get('ident',{})
            if args.condition not in p6.get('conditions',{}):raise RuntimeError('p6_ident needs --condition from config p6.ident.conditions')
            if args.treatment not in P6_TREATMENT_KINDS[args.kind] or args.treatment not in p6['treatments']:raise RuntimeError(f'p6_ident needs --treatment in {P6_TREATMENT_KINDS[args.kind]}')
            # P8-A (config with a p8 section): the same kind with the jump family (p8_conditions; other families delegate to
            # the unchanged p6_conditions).
            self.ident=p8_conditions if 'p8' in self.cfg else p6_conditions
            if p6['conditions'][args.condition].get('cancelled'):raise RuntimeError('condition cancelled by the pre-registered safety budget: '+args.condition)
            self.pcfg=self.ident.ident_cfg(self.cfg,args.condition);self.cfg['p1_condition']=args.condition;self.cfg['p1_speed_m_s']=float(self.pcfg.get('speed_m_s',0.))
            self.cfg['p2_treatment']=args.treatment;self.cfg['p2_treatment_parameters']=p6['treatments'][args.treatment];self.cfg['p2_profile']=self.pcfg
            self.cfg['p6_condition_spec']=p6['conditions'][args.condition]
            # Identification flights measure the saturated region: for this kind only the runner tilt abort is raised and an
            # altitude-loss abort is added (all other envelope limits unchanged).
            self.cfg['safety_tilt_deg']=float(p6['safety_tilt_deg']);self.cfg['p6_altitude_loss_abort_m']=float(p6['altitude_loss_abort_m'])
        elif args.condition or args.treatment:raise RuntimeError('--condition/--treatment apply only to P1/P2/P3/P5 flight kinds')
        # P4 independent run conditions: Gazebo seed and initial heading, pre-registered by the batch and recorded.
        self.sim_seed=args.sim_seed;self.initial_yaw_deg=args.initial_yaw_deg
        if self.sim_seed is not None or self.initial_yaw_deg is not None:
            self.cfg['p4_independence']={'sim_seed':self.sim_seed,'initial_yaw_deg':self.initial_yaw_deg}
        self.variant='classic' if args.kind=='classic_hover' else 'raptor'
        if os.environ.get('HANDOVER_VARIANT')!=self.variant:raise RuntimeError('use tools/experiment to select the correct overlay')
        self.out=(args.output or ROOT/'data'/(dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).strftime('%Y%m%dT%H%M%S')+'-'+args.kind+'-'+uuid.uuid4().hex[:6])).resolve()
        self.out.mkdir(parents=True,exist_ok=False)
        (self.out/'logs').mkdir();(self.out/'rootfs').mkdir();(self.out/'cli').mkdir()
        write(self.out/'config.json',self.cfg)
        self.events=(self.out/'events.jsonl').open('w')
        self.procs=[];self.files=[];self.latest={};self.received={};self.acks=[];self.expected_stopped=set()
        self.node=None;self.rclpy=None;self.safe=False;self.checks={};self.last_sample=0
        self.stream=None;self.stream_t0=None;self.stream_state=None;self.listener_durations=[];self.p3_motion_t0=None
        self.alt_floor=None;self.p6_switch_s=None
        self.samples=(self.out/'telemetry.jsonl').open('w')
        # P11 opt-in sidecar: serial ids and publish-call intervals, no message changes.
        self.p11_sends=(self.out/'p11-sends.jsonl').open('w') if self.cfg.get('p11',{}).get('runner_trace') else None
        if getattr(self,'p11_sends',None):self.files.append(self.p11_sends)
        self.resources=(self.out/'resources.jsonl').open('w');self.last_resource=0
        self.rootfs=self.out/'rootfs'
        self.source=LAB/'.local/checkouts'/('px4-'+self.variant)
        built=self.source/('build/px4_sitl_default' if self.variant=='classic' else 'build/px4_sitl_raptor')
        self.runtime=built if (built/'bin/px4').exists() else LAB/'.local/runtime/px4-classic'
        self.binary=Path(os.environ.get('HANDOVER_PX4_BINARY',str(self.runtime/'bin/px4'))).resolve()
        self.instance=self.cfg['instance']
        self.env=dict(os.environ,GZ_IP='127.0.0.1',GZ_PARTITION='handover-'+uuid.uuid4().hex,HEADLESS='1',
                      PX4_GZ_STANDALONE='1',PX4_SYS_AUTOSTART='4001',PX4_SIM_MODEL='gz_x500',PX4_GZ_WORLD='default',
                      PX4_GZ_MODELS=str(self.source/'Tools/simulation/gz/models'),
                      PX4_GZ_WORLDS=str(self.source/'Tools/simulation/gz/worlds'),
                      GZ_SIM_SERVER_CONFIG_PATH=str(self.source/'Tools/simulation/gz/server.config'),
                      PX4_GZ_MODEL_POSE='0,0,0,0,0,'+(f'{math.radians(self.initial_yaw_deg):.9f}' if self.initial_yaw_deg is not None else '0'),PX4_UXRCE_DDS_NS='',
                      ROS_DOMAIN_ID=str(self.cfg['ros_domain_id']),PX4_UXRCE_DDS_PORT=str(self.cfg['agent_port']),
                      PX4_PARAM_NAV_DLL_ACT='0',PX4_PARAM_COM_RC_IN_MODE='4',
                      PX4_PARAM_MIS_TAKEOFF_ALT=str(self.cfg['altitude_m']),
                      PX4_PARAM_IMU_GYRO_RATEMAX='250',PX4_PARAM_SDLOG_MODE='1',
                      PX4_PARAM_MC_RAPTOR_ENABLE='1' if self.variant=='raptor' else '0',
                      PX4_PARAM_MC_RAPTOR_OFFB='0')
        self.env['GZ_SIM_RESOURCE_PATH']=self.env['PX4_GZ_MODELS']+':'+self.env['PX4_GZ_WORLDS']+':/opt/ros/jazzy/share'
        # RAPTOR output-chain measurement: x500 copy whose motor plugin traces each physics step.
        research_models=self.source/'Tools/simulation/research_models'
        if self.variant=='raptor' and (research_models/'x500/model.sdf').exists():
            self.env['GZ_SIM_RESOURCE_PATH']=str(research_models)+':'+self.env['GZ_SIM_RESOURCE_PATH']
            self.env['PX4_GZ_MODELS']=str(research_models)
            self.env['HANDOVER_GZ_MOTOR_TRACE']=str(self.out/'gz-motor');(self.out/'gz-motor').mkdir()
            if self.cfg.get('p12',{}).get('observe'):self.env['HANDOVER_P12_TRACE']='1'
        plugins=self.runtime/'src/modules/simulation/gz_plugins' if (self.runtime/'src').exists() else self.runtime/'plugins'
        plugin_paths=str(plugins)+(':'+str(plugins/'optical_flow') if (plugins/'optical_flow').is_dir() else '')
        self.env['GZ_SIM_SYSTEM_PLUGIN_PATH']=plugin_paths
        if self.cfg.get('p12b',{}).get('read_trace_schema')=='direct-v2':self.env['HANDOVER_P12B_READ_TRACE']=str(self.out/'gz-motor/read-p12b.bin')
        self.env['LD_LIBRARY_PATH']=plugin_paths+':'+self.env.get('LD_LIBRARY_PATH','')
        if self.variant=='classic':
            self.env.pop('PX4_PARAM_MC_RAPTOR_ENABLE',None)
            self.env.pop('PX4_PARAM_MC_RAPTOR_OFFB',None)
        # ROS middleware reads the domain at context initialization in this process.
        os.environ['ROS_DOMAIN_ID']=self.env['ROS_DOMAIN_ID']
        # Hash every untracked source addition too: git diff alone omits research headers/messages.
        source_extra=subprocess.check_output(['git','-C',str(self.source),'ls-files','--others','--exclude-standard','-z']).decode().strip('\0').split('\0')
        self.source_extra_hashes={name:digest(self.source/name) for name in source_extra if name and (self.source/name).is_file()}
        self.metadata={'experiment_type':args.kind,'startup_only':self.startup_only,'capture_raw_sensors':args.capture_raw_sensors,'variant':self.variant,'created_at':dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(),
                       'seed':self.cfg['seed'],'seed_scope':'recorded; Gazebo/PX4 do not expose a verified universal seed',
                       'initial_pose':self.env['PX4_GZ_MODEL_POSE'],'sim_seed':self.sim_seed,'initial_yaw_deg':self.initial_yaw_deg,'source_commit':subprocess.check_output(['git','-C',str(self.source),'rev-parse','HEAD'],text=True).strip(),
                       'project_commit':subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip(),
                       'experiment_code_sha256':{str(p.relative_to(ROOT)):digest(p) for p in sorted((ROOT/'tools').glob('*.py'))},
                       'config_sha256':digest(self.out/'config.json'),
                       'source_untracked_sha256':self.source_extra_hashes,
                       'source_diff_sha256':hashlib.sha256(subprocess.check_output(['git','-C',str(self.source),'diff','--binary'])).hexdigest(),
                       'binary':str(self.binary),'binary_sha256':digest(self.binary),
                       'gz_research_plugin_sha256':digest(plugins/'libResearchMulticopterMotorModel.so') if 'HANDOVER_GZ_MOTOR_TRACE' in self.env else None,
                       'environment':{k:v for k,v in self.env.items() if k.startswith(('PX4_','GZ_','ROS_DOMAIN','HANDOVER_GZ','HANDOVER_CPU'))},'processes':[]}
        self.affinity=cpu_affinity()
        if self.affinity:
            # The runner (and listener/CLI children it starts) runs on its own cores; spawned processes via taskset.
            if 'runner' in self.affinity:os.sched_setaffinity(0,{c for part in self.affinity['runner'].split(',') for c in (range(int(part.split('-')[0]),int(part.split('-')[-1])+1))})
            self.metadata['cpu_affinity']={'requested':self.affinity,'runner_actual':sorted(os.sched_getaffinity(0))}
        self.event('created',thresholds=self.cfg)

    def event(self,event_name,**values):
        item={'event':event_name,'monotonic_ns':time.monotonic_ns(),'wall_time_ns':time.time_ns(),**values}
        self.events.write(json.dumps(item,allow_nan=False)+'\n');self.events.flush()
        print(event_name,values,flush=True)

    def spawn(self,name,argv,cwd=None):
        if name=='gazebo' and self.cfg.get('p12b',{}).get('solver_observe'):
            lib=ROOT/self.cfg['p12b']['solver_library']
            if not lib.is_file():raise RuntimeError('P12b solver observer missing')
            argv=['env','LD_PRELOAD='+str(lib),'HANDOVER_P12B_SOLVER_TRACE='+str(self.out/'gz-motor')]+list(argv)
            self.metadata['p12b_solver_observer']={'path':str(lib),'sha256':digest(lib),'semantics':'passive installed DART symbol interposition, solver arguments unchanged'}
        cores=self.affinity.get(name.split('-')[0]) if getattr(self,'affinity',None) else None
        if cores:argv=['taskset','-c',cores]+list(argv)  # taskset execs the target: same pid
        log=(self.out/'logs'/(name+'.log')).open('w');self.files.append(log)
        p=subprocess.Popen(argv,cwd=cwd,env=self.env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        self.procs.append((name,p));self.metadata['processes'].append({'name':name,'pid':p.pid,'command':argv})
        self.event('process_started',name=name,pid=p.pid,command=argv)
        return p

    def command(self,module,*args,timeout=12,required=True):
        link=self.out/'cli'/('px4-'+module)
        if not link.exists():link.symlink_to(self.binary)
        argv=[str(link),'--instance',str(self.instance),*map(str,args)]
        p=subprocess.run(argv,env=self.env,capture_output=True,text=True,timeout=timeout,cwd=self.rootfs)
        with (self.out/'logs/commands.log').open('a') as f:f.write(json.dumps({'command':argv,'exit_code':p.returncode,'output':p.stdout+p.stderr})+'\n')
        if required and p.returncode:raise RuntimeError(f'{module} {args}: {p.returncode}: {p.stdout+p.stderr}')
        return p.stdout+p.stderr

    def native_phase_end_bound(self):
        # Listener returns a native PX4 publication time before the later ROS
        # request. This is a proven conservative bound, without clock interpolation.
        output=self.command('listener','vehicle_angular_velocity','-n','1')
        match=re.search(r'\btimestamp:\s*(\d+)',output)
        if not match:raise RuntimeError('native phase boundary timestamp missing')
        return int(match.group(1))

    def topic(self,direction,name,typ):
        version=getattr(typ,'MESSAGE_VERSION',0)
        return f'/fmu/{direction}/{name}'+(f'_v{version}' if version else '')

    def init_ros(self):
        import rclpy
        from rclpy.qos import qos_profile_sensor_data
        import px4_msgs.msg as msgs
        self.rclpy=rclpy;self.msgs=msgs
        rclpy.init();self.node=rclpy.create_node('handover_lab_'+uuid.uuid4().hex[:8])
        for name,typename in [('vehicle_status','VehicleStatus'),('vehicle_odometry','VehicleOdometry'),('vehicle_attitude','VehicleAttitude'),('vehicle_local_position','VehicleLocalPosition'),('vehicle_land_detected','VehicleLandDetected'),('vehicle_command_ack','VehicleCommandAck'),('sensor_baro','SensorBaro'),('vehicle_air_data','VehicleAirData')]:
            typ=getattr(msgs,typename)
            self.node.create_subscription(typ,self.topic('out',name,typ),lambda msg,n=name:self.receive(n,msg),qos_profile_sensor_data)
        if self.variant=='raptor':
            for name,typename in [('raptor_status','RaptorStatus'),('raptor_input','RaptorInput')]:
                typ=getattr(msgs,typename)
                self.node.create_subscription(typ,self.topic('out',name,typ),lambda msg,n=name:self.receive(n,msg),qos_profile_sensor_data)
        self.cmdpub=self.node.create_publisher(msgs.VehicleCommand,self.topic('in','vehicle_command',msgs.VehicleCommand),10)
        self.offpub=self.node.create_publisher(msgs.OffboardControlMode,self.topic('in','offboard_control_mode',msgs.OffboardControlMode),10)
        self.trajpub=self.node.create_publisher(msgs.TrajectorySetpoint,self.topic('in','trajectory_setpoint',msgs.TrajectorySetpoint),10)

    def receive(self,name,msg):
        self.latest[name]=msg;self.received[name]=time.monotonic()
        if name=='vehicle_command_ack':
            self.acks.append(msg);self.event('command_ack',command=int(msg.command),result=int(msg.result),timestamp=int(msg.timestamp))

    def pump(self,seconds=0.1):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            self.rclpy.spin_once(self.node,timeout_sec=min(0.01 if self.stream else 0.05,max(0,end-time.monotonic())))
            if self.stream:self.stream()
            for name,p in self.procs:
                if p.poll() is not None and name not in self.expected_stopped:raise RuntimeError(f'{name} exited: {p.returncode}')
            now=time.monotonic()
            if now-self.last_resource>=1:
                self.last_resource=now
                metrics={'monotonic_ns':time.monotonic_ns(),'host_cpu_percent':psutil.cpu_percent(),
                         'host_memory_available_bytes':psutil.virtual_memory().available,
                         'disk_free_bytes':shutil.disk_usage(self.out).free,'processes':{}}
                for name,p in self.procs:
                    try:
                        process=psutil.Process(p.pid)
                        metrics['processes'][name]={'rss_bytes':process.memory_info().rss,'cpu_time_s':sum(process.cpu_times()[:2])}
                    except psutil.NoSuchProcess:pass
                self.resources.write(json.dumps(metrics)+'\n');self.resources.flush()
            if now-self.last_sample>0.1:
                self.last_sample=now
                local=self.latest.get('vehicle_local_position');status=self.latest.get('vehicle_status');att=self.latest.get('vehicle_attitude');odom=self.latest.get('vehicle_odometry')
                if local and status and att:
                    q=list(map(float,att.q));tilt=math.degrees(math.acos(max(-1,min(1,1-2*(q[1]**2+q[2]**2)))))
                    sample={'monotonic_ns':time.monotonic_ns(),'px4_timestamp':int(local.timestamp),'position':[float(local.x),float(local.y),float(local.z)],'velocity':[float(local.vx),float(local.vy),float(local.vz)],'q':q,'tilt_deg':tilt,'nav_state':int(status.nav_state),'arming_state':int(status.arming_state)}
                    self.samples.write(json.dumps(sample)+'\n');self.samples.flush()
                    if self.safe:
                        if now-self.received['vehicle_odometry']>2:raise RuntimeError('safety: DDS telemetry timeout')
                        if not all(math.isfinite(x) for x in sample['position']+sample['velocity']+q):raise RuntimeError('safety: nonfinite telemetry')
                        if math.hypot(local.x,local.y)>self.cfg['safety_radius_m'] or -local.z>self.cfg['safety_altitude_m'] or local.z>1 or tilt>self.cfg['safety_tilt_deg']:raise RuntimeError('safety: flight envelope exceeded')
                        if odom and max(abs(float(x)) for x in odom.angular_velocity)>self.cfg['safety_angular_rate_rad_s']:raise RuntimeError('safety: angular rate exceeded')
                        if self.alt_floor is not None and -local.z<self.alt_floor:raise RuntimeError('safety: altitude loss exceeded')

    def wait(self,predicate,timeout,description):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            self.pump()
            if predicate():self.event('ready',condition=description);return
        raise TimeoutError(description)

    def ros_command(self,command,**params):
        msg=self.msgs.VehicleCommand();msg.timestamp=int(time.time()*1e6);msg.command=command
        msg.target_system=self.instance+1;msg.target_component=1;msg.source_system=245;msg.source_component=191;msg.from_external=True
        for key,value in params.items():setattr(msg,key,float(value) if value is not None else float('nan'))
        start=len(self.acks);self.event('command_requested',command=command,params=params)
        self.cmdpub.publish(msg)
        self.wait(lambda:any(a.command==command for a in self.acks[start:]),5,'command acknowledgement')
        ack=next(a for a in self.acks[start:] if a.command==command)
        if ack.result!=0:raise RuntimeError(f'command {command} rejected: {ack.result}')

    def hover(self,duration,label,prefix='hover'):
        # P1 phases away from the P0 hover point use prefix 'p1_phase' so analyze.py does not judge them as hover windows.
        start=self.native_phase_end_bound()
        self.event(prefix+'_started',label=label,duration_s=duration,px4_start_us=start)
        deadline=time.monotonic()+3*duration+15
        while time.monotonic()<deadline:
            self.pump(0.2)
            end=self.native_phase_end_bound()
            if end-start>=duration*1e6:
                self.event(prefix+'_ended',label=label,px4_end_us=end)
                return
        raise TimeoutError('native simulation hover duration '+label)

    def native_bound_streaming(self):
        # Same native bound as native_phase_end_bound, but the reference stream keeps publishing while listener runs.
        link=self.out/'cli'/'px4-listener'
        if not link.exists():link.symlink_to(self.binary)
        argv=[str(link),'--instance',str(self.instance),'vehicle_angular_velocity','-n','1']
        started=time.monotonic()
        p=subprocess.Popen(argv,env=self.env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,cwd=self.rootfs)
        deadline=time.monotonic()+12
        while p.poll() is None:
            if time.monotonic()>deadline:p.kill();p.wait();raise RuntimeError('native boundary listener timeout')
            self.pump(0.005)
        output=p.stdout.read();p.stdout.close();self.listener_durations.append(time.monotonic()-started)
        with (self.out/'logs/commands.log').open('a') as f:f.write(json.dumps({'command':argv,'exit_code':p.returncode,'output':output})+'\n')
        match=re.search(r'\btimestamp:\s*(\d+)',output)
        if p.returncode or not match:raise RuntimeError('native phase boundary timestamp missing')
        return int(match.group(1))

    def wait_raptor_active(self):
        self.wait(lambda:self.latest.get('raptor_status') and self.latest['raptor_status'].active and self.latest.get('raptor_input') and self.latest['raptor_input'].active,5,'RAPTOR active diagnostic DDS')
        self.checks['raptor_diagnostic_dds']='PASS'
        self.command('listener','raptor_status','-n','1')
        self.command('listener','vehicle_control_mode','-n','1')

    def classic_target(self):
        # Start the P1 reference at the classic controller's current target (no step at OFFBOARD entry).
        text=self.command('listener','trajectory_setpoint','-n','1')
        position=re.search(r'position: \[([^\]]+)\]',text);yaw=re.search(r'\byaw: (\S+)',text)
        values=[float(x) for x in position.group(1).split(',')] if position else []
        if len(values)!=3 or not all(math.isfinite(x) for x in values) or not yaw or not math.isfinite(float(yaw.group(1))):
            raise RuntimeError('classic trajectory_setpoint target unavailable: '+text)
        return values,float(yaw.group(1)),'classic trajectory_setpoint (listener)'

    def raptor_target(self):
        # RAPTOR research state values 20..22 are its internal position target (activation capture here).
        values=self.state('raptor','read')['values']
        return [float(v) for v in values[20:23]],float(self.latest['vehicle_local_position'].heading),'raptor state values[20:23]; yaw from vehicle_local_position.heading'

    def profile_cfg(self):
        return getattr(self,'pcfg',None) or self.cfg['p1']

    def reposition(self,t):
        # Optional P2 move to start_offset_m along the axis (trapezoidal speed) before the hold. (s,v,a,duration)
        p=Experiment.profile_cfg(self);d=float(p.get('start_offset_m',0.))
        if not d:return 0.,0.,0.,0.
        r=p['reposition'];vm,am=float(r['speed_m_s']),float(r['accel_m_s2']);sign=1. if d>0 else -1.;d=abs(d)
        ta=min(vm/am,(d/am)**.5);vp=am*ta;tc=(d-am*ta*ta)/vp;total=2*ta+tc
        if t>=total:return sign*d,0.,0.,total
        if t<ta:return sign*.5*am*t*t,sign*am*t,sign*am,total
        if t<ta+tc:return sign*(.5*am*ta*ta+vp*(t-ta)),sign*vp,0.,total
        tau=total-t;return sign*(d-.5*am*tau*tau),sign*am*tau,-sign*am,total

    def profile_duration(self):
        p=Experiment.profile_cfg(self);decel=(self.cfg['p1_speed_m_s']-float(p['decel_to_m_s']))/float(p['decel_m_s2']) if p.get('decel_to_m_s') is not None else 0.
        return Experiment.reposition(self,0.)[3]+p['reference_hold_s']+p['accel_s']+p['cruise_s']+decel

    def planned_path_check(self,origin):
        # P4: origin + planned path to the event point + braking allowance inside the safety radius margin (before moving).
        p=Experiment.profile_cfg(self);c=p.get('planned_path_check')
        if not c:return None
        axis=[float(x) for x in p['motion_axis_ned']];s=Experiment.p1_profile(self,Experiment.profile_duration(self))[0]
        # P4-01c: the braking term is the speed-matched target's stop distance v^2/(2a) on top of the margin.
        a=c.get('braking_deceleration_m_s2');braking=self.cfg['p1_speed_m_s']**2/(2*float(a)) if a else 0.
        end=[origin[i]+axis[i]*s for i in range(3)];radius=max(math.hypot(origin[0],origin[1]),math.hypot(end[0],end[1]))+braking+float(c['braking_allowance_m'])
        limit=self.cfg['safety_radius_m']-float(c['radius_margin_m'])
        return {'origin_ned_m':origin,'event_point_ned_m':end,'path_m':s,'braking_distance_m':braking,'radius_with_allowance_m':radius,'limit_m':limit,'inside':radius<=limit}

    def p1_profile(self,t):
        # [Reposition,] hold, linear velocity ramp, cruise. Returns path length, speed, acceleration along the motion axis.
        # Class-qualified helpers keep this a pure function of cfg (unit-tested without an Experiment).
        p=Experiment.profile_cfg(self);v=self.cfg['p1_speed_m_s'];hold,acc=p['reference_hold_s'],p['accel_s']
        s0,v0,a0,tr=Experiment.reposition(self,t)
        if t<tr:return s0,v0,a0
        t-=tr
        if t<hold:return s0,0.,0.
        if t<hold+acc:
            tau=t-hold;return s0+.5*v*tau*tau/acc,v*tau/acc,v/acc
        vd=p.get('decel_to_m_s')
        if vd is None or t<hold+acc+p['cruise_s']:return s0+.5*v*acc+v*(t-hold-acc),v,0.
        # P4 M2: linear deceleration after the cruise down to decel_to_m_s (the event point), then that speed.
        a=float(p['decel_m_s2']);td=(v-float(vd))/a;r=t-hold-acc-p['cruise_s'];tau=min(r,td)
        return s0+.5*v*acc+v*p['cruise_s']+v*tau-.5*a*tau*tau+float(vd)*max(0.,r-td),v-a*tau,(-a if r<=td+1e-9 else 0.)

    def start_stream(self,origin,yaw,offboard,gaps=(),profile=None):
        prof=profile or self.p1_profile
        axis=[float(x) for x in self.profile_cfg()['motion_axis_ned']];period=self.profile_cfg()['setpoint_period_s']
        state={'last':0.,'count':0,'origin':origin,'yaw':yaw,'offboard':offboard,'gap':None,'last_t':None,'gaps_log':[]}
        self.stream_t0=None;self.stream_state=state
        def emit(t):
            s,v,a=prof(t);stamp=int(time.time()*1e6)
            if offboard:
                off=self.msgs.OffboardControlMode();off.timestamp=stamp;off.position=True;self.offpub.publish(off)
            traj=self.msgs.TrajectorySetpoint();traj.timestamp=stamp
            traj.position=[origin[i]+axis[i]*s for i in range(3)];traj.velocity=[axis[i]*v for i in range(3)]
            traj.acceleration=[axis[i]*a for i in range(3)];traj.yaw=yaw;traj.yawspeed=0.
            p11_before=time.monotonic_ns() if getattr(self,'p11_sends',None) else None
            self.trajpub.publish(traj)
            if getattr(self,'p11_sends',None):
                self.p11_sends.write(json.dumps({'send_id':state['count']+1,'profile_s':t,'stream_t0_monotonic_s':self.stream_t0,
                    'before_ns':p11_before,'after_ns':time.monotonic_ns(),'header_timestamp':stamp,
                    'previous_sidecar_ns':state.get('p11_sidecar_ns'),
                    'position':list(map(float,traj.position)),'velocity':list(map(float,traj.velocity)),'yaw':float(traj.yaw)},allow_nan=False)+'\n')
                self.p11_sends.flush()
                state['p11_sidecar_ns']=time.monotonic_ns()-p11_before
            state['count']+=1;state['last_position']=list(map(float,traj.position));state['last_velocity']=list(map(float,traj.velocity));state['last_t']=t
        def publish():
            now=time.monotonic();t=0. if self.stream_t0 is None else now-self.stream_t0
            # P5 gap injector: no setpoint inside a gap window (profile time keeps running); the first emission after the
            # gap is immediate and lies on the same time-parameterized line.
            k=next((i for i,(a,b) in enumerate(gaps) if a<=t<b),None) if self.stream_t0 is not None else None
            if k is not None:
                if state['gap']!=k:
                    state['gap']=k;item={'index':k,'planned_profile_s':list(gaps[k]),'first_skip_profile_s':t,'last_emit_profile_s':state['last_t'],'first_skip_monotonic_ns':time.monotonic_ns()}
                    state['gaps_log'].append(item);self.event('p5_gap_started',**item)
                return
            if state['gap'] is not None:
                item=state['gaps_log'][-1];item.update({'first_emit_profile_s':t,'first_emit_monotonic_ns':time.monotonic_ns()});state['gap']=None
                emit(t);state['last']=now;self.event('p5_gap_ended',**item);return
            if now-state['last']<period:return
            emit(t);state['last']=now
        self.stream=publish;self.stream_emit=emit
        self.event('p1_reference_started',origin_ned_m=origin,yaw_rad=yaw,offboard=offboard,axis_ned=axis,speed_m_s=self.cfg['p1_speed_m_s'],period_s=period)

    def stop_stream(self):
        state=self.stream_state;self.stream=None
        self.event('p1_reference_stopped',published=state['count'],last_position_ned_m=state.get('last_position'),
            last_velocity_ned_m_s=state.get('last_velocity'),since_last_publish_s=time.monotonic()-state['last'],
            **({'p11_last_sidecar_ns':state.get('p11_sidecar_ns')} if getattr(self,'p11_sends',None) else {}))

    def p1_flight(self,mode):
        kind=self.args.kind.replace('p2_','p1_');p=self.profile_cfg()
        classic_out=kind in ['p1_c_to_n','p1_baseline_classic']
        if classic_out:origin,yaw,source=self.classic_target()
        else:
            # Setup C->N at hover (S1-like, not the measured event); RAPTOR then holds its activation capture.
            self.event('handover_requested',end_bound_px4_us=self.native_phase_end_bound(),from_controller='C',to_controller='N',iteration=0,subject=False)
            self.mode(mode);self.wait_raptor_active();self.capture_states('neural_after_entry')
            self.hover(self.cfg['neural_s'],'neural')
            origin,yaw,source=self.raptor_target()
        self.event('p1_reference_origin',source=source,origin_ned_m=origin,yaw_rad=yaw)
        check=self.planned_path_check(origin)
        if check is not None:
            self.event('p4_planned_path_check',**check)
            if not check['inside']:raise RuntimeError(f"planned path would leave the safety radius margin: {check['radius_with_allowance_m']:.2f} m > {check['limit_m']:.2f} m")
        self.start_stream(origin,yaw,classic_out)
        if classic_out:
            self.pump(p['offboard_prestream_s'])
            self.mode(self.msgs.VehicleStatus.NAVIGATION_STATE_OFFBOARD)
        total=self.profile_duration()
        # P4 RAPTOR baselines: the stream ends `early` s (RAPTOR's setpoint timeout) before the event point, so RAPTOR
        # captures at the event point; its last setpoint is the profile state `ahead` s after the stop (calibrated so the
        # capture speed and acceleration match the C->N of the same condition).
        early=float(p.get('raptor_baseline_stop_early_s') or 0.) if kind=='p1_baseline_raptor' else 0.
        ahead=float(p.get('raptor_baseline_final_setpoint_ahead_s') or 0.) if early else 0.
        self.stream_t0=time.monotonic()
        self.event('p1_profile_started',px4_bound_us=self.native_bound_streaming(),duration_s=total,stop_early_s=early,final_setpoint_ahead_s=ahead)
        while time.monotonic()-self.stream_t0<total-early:self.pump(0.01)
        # Measured event: native bound while streaming, stop the stream, then request at once.
        bound=self.native_bound_streaming()
        if early:
            self.stream_emit(total-early+ahead);s,v,a=self.p1_profile(total-early+ahead)
            self.event('p4_final_setpoint',stop_early_s=early,ahead_s=ahead,profile_time_s=total-early+ahead,since_stream_start_s=time.monotonic()-self.stream_t0,
                       position_ned_m=self.stream_state['last_position'],velocity_ned_m_s=self.stream_state['last_velocity'],acceleration_along_axis_m_s2=a)
        self.stop_stream()
        subject={'p1_c_to_n':'C_to_N','p1_n_to_c':'N_to_C','p1_baseline_classic':'classic_brake','p1_baseline_raptor':'raptor_hold'}[kind]
        self.event('p1_trigger',subject=subject,condition=self.cfg['p1_condition'],speed_m_s=self.cfg['p1_speed_m_s'],end_bound_px4_us=bound,treatment=self.cfg.get('p2_treatment'))
        if kind=='p1_c_to_n':
            self.event('handover_requested',end_bound_px4_us=bound,from_controller='C',to_controller='N',iteration=0,subject=True)
            self.mode(mode);self.wait_raptor_active();self.capture_states('neural_after_entry')
        elif kind=='p1_n_to_c':
            self.event('handover_requested',end_bound_px4_us=bound,from_controller='N',to_controller='C',iteration=0,subject=True)
            self.mode(4);self.capture_states('classic_after_entry')
        elif kind=='p1_baseline_classic':self.mode(4)
        self.hover(p['post_handover_s'],'post_event',prefix='p1_phase')
        if kind=='p1_baseline_classic':
            # RAPTOR segment at rest after the measured window keeps the RAPTOR-build analysis requirements.
            self.event('handover_requested',end_bound_px4_us=self.native_phase_end_bound(),from_controller='C',to_controller='N',iteration=1,subject=False)
            self.mode(mode);self.wait_raptor_active();self.capture_states('neural_after_entry')
            self.hover(self.cfg['neural_s'],'tail_neural',prefix='p1_phase')
        if kind!='p1_n_to_c':
            self.event('handover_requested',end_bound_px4_us=self.native_phase_end_bound(),from_controller='N',to_controller='C',iteration=1,subject=False)
            self.mode(4);self.capture_states('classic_after_entry')
            self.hover(p['return_hold_s'],'return_classic',prefix='p1_phase')
        self.checks['p1_sequence']='PASS'

    def p5_gap_windows(self):
        # Gap k: profile times [cruise start + pre_gap_s + k*(D + recover), + D); cruise start after reposition, hold, ramp.
        p=self.pcfg;g=p['gaps'];t0=Experiment.reposition(self,0.)[3]+p['reference_hold_s']+p['accel_s']+p['pre_gap_s']
        if 'windows_s' in g:return [(t0+a,t0+b) for a,b in g['windows_s']]  # P6 C2 explicit windows
        return [(t0+k*(g['duration_s']+g['recover_s']),t0+k*(g['duration_s']+g['recover_s'])+g['duration_s']) for k in range(g['count'])]

    def p5_path_check(self,origin):
        # Start and end of the planned line + margin + interruption drift inside safety_radius_m - radius_margin_m.
        p=self.pcfg;c=self.cfg['p5']['planned_path_check'];axis=[float(x) for x in p['motion_axis_ned']];v=self.cfg['p1_speed_m_s']
        s0=float(p['start_offset_m']);s1=Experiment.p1_profile(self,Experiment.profile_duration(self))[0]
        start=[origin[i]+axis[i]*s0 for i in range(3)];end=[origin[i]+axis[i]*s1 for i in range(3)]
        last=self.p5_gap_windows()[-1][0];remaining=s1-Experiment.p1_profile(self,last)[0]
        drift=max(0.,v*float(c['stale_timeout_s'])+v*v/(2*float(c['worst_case_deceleration_m_s2']))-remaining)
        radius=max(math.hypot(start[0],start[1]),math.hypot(end[0],end[1]))+float(c['braking_allowance_m'])+drift
        limit=self.cfg['safety_radius_m']-float(c['radius_margin_m'])
        return {'origin_ned_m':origin,'start_ned_m':start,'end_ned_m':end,'path_m':s1-s0,'remaining_after_last_gap_start_m':remaining,
                'interruption_drift_m':drift,'radius_with_allowance_m':radius,'limit_m':limit,'inside':radius<=limit}

    def p5_gap_flight(self,mode):
        p=self.pcfg
        # Setup C->N at hover (not measured); RAPTOR then holds its activation capture, which is the line's centre.
        self.event('handover_requested',end_bound_px4_us=self.native_phase_end_bound(),from_controller='C',to_controller='N',iteration=0,subject=False)
        self.mode(mode);self.wait_raptor_active();self.capture_states('neural_after_entry')
        self.hover(self.cfg['neural_s'],'neural')
        origin,yaw,source=self.raptor_target()
        if self.cfg.get('p12',{}).get('common_world_reference'):
            # P12 development v2: a shared absolute task, not a per-run capture-origin task.
            origin=[float(x) for x in self.cfg['p12']['common_world_reference']['position_ned_m']]
            yaw=float(self.cfg['p12']['common_world_reference']['yaw_rad'])
            source='P12_FIXED_COMMON_WORLD_REFERENCE'
        self.event('p1_reference_origin',source=source,origin_ned_m=origin,yaw_rad=yaw)
        check=self.p5_path_check(origin);self.event('p5_planned_path_check',**check)
        if not check['inside']:raise RuntimeError(f"planned path would leave the safety radius margin: {check['radius_with_allowance_m']:.2f} m > {check['limit_m']:.2f} m")
        windows=self.p5_gap_windows();total=self.profile_duration()+p['end_hold_s']
        if 'p11' in self.cfg:
            # Remove complete events without changing the source trajectory or absolute times.
            mask=self.cfg['p11'].get('event_mask',list(range(len(windows))))
            windows=[w for i,w in enumerate(windows) if i in mask]
            shift=float(self.cfg['p11'].get('event_shift_s',0.))
            if not 0.<=shift<=.008:raise RuntimeError('P11 event phase shift outside declared [0,8ms]')
            windows=[(a+shift,b+shift) for a,b in windows]
        self.event('p5_gap_plan',windows_profile_s=windows,gaps=p['gaps'],profile_duration_s=total,cruise_s=p['cruise_s'],start_offset_m=p['start_offset_m'])
        p12_epoch=None
        if self.cfg.get('p12',{}).get('native_stream_anchor'):
            # Confirm an ACTUAL committed row. Its recorded CLOCK_MONOTONIC
            # defines the task epoch; neither sample nor native time is forged.
            deadline=time.monotonic()+2.;anchor=None
            while time.monotonic()<deadline:
                before=time.monotonic_ns();text=self.command('listener','research_p11','-n','1');after=time.monotonic_ns()
                fields={key:re.search(r'^\s*'+key+r':\s*(\d+)',text,re.M) for key in ['timestamp','timestamp_sample','run_wall_ns','local_position_sample']}
                if re.search(r'native_step:\s*True',text) and all(fields.values()):
                    values={key:int(value.group(1)) for key,value in fields.items()}
                    if 0<after-values['run_wall_ns']<30_000_000:
                        anchor={**values,'query_before_ns':before,'query_after_ns':after};break
                self.pump(.001)
            if anchor is None:raise RuntimeError('P12 native committed stream anchor not confirmed')
            p12_epoch=anchor['run_wall_ns']/1e9
            self.event('p12_confirmed_native_stream_anchor',**anchor,
                       scope='past actual commit row; async query age retained; no exact snapshot claim')
        if self.cfg.get('p12',{}).get('repair_sample_window'):
            if anchor is None:raise RuntimeError('sample repair window requires confirmed native epoch')
            # Same operation in every arm; future threshold from actual past sample
            # plus the fixed ORIGINAL first-event time, even if A is absent.
            first_event=self.p5_gap_windows()[0][0]
            gate_ms=int(math.ceil(anchor['timestamp_sample']/1000.+first_event*1000.))
            self.command('param','set','MC_RAPTOR_P12MS',str(gate_ms))
            shown=self.command('param','show','MC_RAPTOR_P12MS')
            if not re.search(r'MC_RAPTOR_P12MS\s*\[[^\]]*\]\s*:\s*'+str(gate_ms)+r'(?:\s|$)',shown):
                raise RuntimeError('P12 planned repair window readback failed')
            self.event('p12_planned_repair_window',not_before_sample_ms=gate_ms,
                       common_first_event_profile_s=first_event,anchor_sample_us=anchor['timestamp_sample'],
                       parameter_write_scope='identical all-arm protocol; no hidden/history/reset or target write')
        self.start_stream(origin,yaw,False,gaps=windows)
        self.stream_t0=p12_epoch if p12_epoch is not None else time.monotonic()
        self.event('p1_profile_started',px4_bound_us=self.native_bound_streaming(),duration_s=total)
        while time.monotonic()-self.stream_t0<total:self.pump(0.01)
        bound=self.native_bound_streaming();log=self.stream_state['gaps_log'];self.stop_stream()
        self.event('p5_stream_ended',end_bound_px4_us=bound,gaps=log,planned_gaps=len(windows))
        if len(log)!=len(windows) or any('first_emit_profile_s' not in g for g in log):raise RuntimeError('planned stream gaps not all executed')
        self.hover(p['post_stream_s'],'post_stream',prefix='p1_phase')
        self.event('handover_requested',end_bound_px4_us=self.native_phase_end_bound(),from_controller='N',to_controller='C',iteration=1,subject=False)
        self.mode(4);self.capture_states('classic_after_entry')
        self.hover(p['return_hold_s'],'return_classic',prefix='p1_phase')
        self.checks['p5_sequence']='PASS'

    # ---- P6: identification flights ----------------------------------------------------------------------------------
    def p6_family_start(self):
        return Experiment.reposition(self,0.)[3]+float(self.pcfg['reference_hold_s'])

    def p6_profile(self,t):
        # Reposition to the start offset, reference hold, then the family motion (p6_conditions.ident_motion).
        s0,v0,a0,tr=Experiment.reposition(self,t)
        if t<tr:return s0,v0,a0
        tau=t-tr-float(self.pcfg['reference_hold_s'])
        if tau<0:return s0,0.,0.
        s,v,a=getattr(self,'ident',p6_conditions).ident_motion(self.pcfg,tau,self.p6_switch_s);return s0+s,v,a

    def p6_total(self):
        return self.p6_family_start()+getattr(self,'ident',p6_conditions).ident_motion_duration(self.pcfg,self.p6_switch_s)+float(self.pcfg['end_hold_s'])

    def p6_chase_check(self,origin,axis):
        # chase: the target decelerates once the vehicle has caught up (along-axis distance to the target <= catch_up_m on
        # the latest DDS local position) or at max_chase_s after it appeared, whichever comes first.
        p=self.pcfg
        if p['family']!='chase' or self.p6_switch_s is not None or self.stream_t0 is None:return
        tau=time.monotonic()-self.stream_t0-self.p6_family_start()
        if tau<0:return
        local=self.latest['vehicle_local_position'];s_target=self.p6_profile(time.monotonic()-self.stream_t0)[0]
        s_vehicle=sum((float(x)-origin[i])*axis[i] for i,x in enumerate([local.x,local.y,local.z]))
        lag=s_target-s_vehicle
        if lag<=float(p['catch_up_m']) or tau>=float(p['max_chase_s']):
            self.p6_switch_s=min(tau,float(p['max_chase_s']))
            self.event('p6_chase_switch',family_time_s=self.p6_switch_s,reason='caught_up' if lag<=float(p['catch_up_m']) else 'max_chase_s',
                       along_axis_lag_m=lag,local_position_px4_us=int(local.timestamp))

    def p6_path_check(self,origin):
        p=self.pcfg;c=self.cfg['p6']['ident']['planned_path_check'];axis=[float(x) for x in p['motion_axis_ned']]
        s0=float(p['start_offset_m']);s1=s0+float(p['path_length_m'])
        start=[origin[i]+axis[i]*s0 for i in range(3)];end=[origin[i]+axis[i]*s1 for i in range(3)]
        radius=max(math.hypot(start[0],start[1]),math.hypot(end[0],end[1]))+float(c['braking_allowance_m'])
        limit=self.cfg['safety_radius_m']-float(c['radius_margin_m'])
        return {'origin_ned_m':origin,'start_ned_m':start,'end_ned_m':end,'path_m':s1-s0,'radius_with_allowance_m':radius,'limit_m':limit,'inside':radius<=limit}

    def p6_ident_flight(self,mode):
        p=self.pcfg
        # Setup C->N at hover (not measured); RAPTOR holds its activation capture, the centre of the planned path.
        self.event('handover_requested',end_bound_px4_us=self.native_phase_end_bound(),from_controller='C',to_controller='N',iteration=0,subject=False)
        self.mode(mode);self.wait_raptor_active();self.capture_states('neural_after_entry')
        self.hover(self.cfg['neural_s'],'neural')
        origin,yaw,source=self.raptor_target()
        self.event('p1_reference_origin',source=source,origin_ned_m=origin,yaw_rad=yaw)
        check=self.p6_path_check(origin);self.event('p6_planned_path_check',**check)
        if not check['inside']:raise RuntimeError(f"planned path would leave the safety radius margin: {check['radius_with_allowance_m']:.2f} m > {check['limit_m']:.2f} m")
        gap=getattr(self,'ident',p6_conditions).ident_gap(p);fs=self.p6_family_start();windows=[(fs+gap[0],fs+gap[1])] if gap else []
        axis=[float(x) for x in p['motion_axis_ned']]
        self.event('p6_ident_plan',family=p['family'],family_start_profile_s=fs,windows_profile_s=windows,planned_total_s=self.p6_total(),start_offset_m=p['start_offset_m'],path_length_m=p['path_length_m'])
        self.p6_switch_s=None
        self.alt_floor=-float(self.latest['vehicle_local_position'].z)-float(self.cfg['p6_altitude_loss_abort_m'])
        self.event('p6_altitude_abort_floor',altitude_m=self.alt_floor,loss_m=self.cfg['p6_altitude_loss_abort_m'],tilt_abort_deg=self.cfg['safety_tilt_deg'])
        self.start_stream(origin,yaw,False,gaps=windows,profile=self.p6_profile)
        self.stream_t0=time.monotonic()
        self.event('p1_profile_started',px4_bound_us=self.native_bound_streaming(),duration_s=self.p6_total())
        while time.monotonic()-self.stream_t0<self.p6_total():self.pump(0.01);self.p6_chase_check(origin,axis)
        bound=self.native_bound_streaming();log=self.stream_state['gaps_log'];self.stop_stream()
        self.event('p6_stream_ended',end_bound_px4_us=bound,gaps=log,planned_gaps=len(windows),chase_switch_family_s=self.p6_switch_s,profile_s=time.monotonic()-self.stream_t0)
        if len(log)!=len(windows) or any('first_emit_profile_s' not in g for g in log):raise RuntimeError('planned stream gaps not all executed')
        self.alt_floor=None
        self.hover(p['post_stream_s'],'post_stream',prefix='p1_phase')
        self.event('handover_requested',end_bound_px4_us=self.native_phase_end_bound(),from_controller='N',to_controller='C',iteration=1,subject=False)
        self.mode(4);self.capture_states('classic_after_entry')
        self.hover(p['return_hold_s'],'return_classic',prefix='p1_phase')
        self.checks['p6_ident_sequence']='PASS'

    def apply_treatment(self):
        # P2: controller-side parameters are set once before arming; RAPTOR applies them in its own thread.
        name=self.cfg['p2_treatment'];t=self.cfg['p2_treatment_parameters']
        rini,nco=int(t.get('rini',0)),int(t.get('nco',0))
        self.command('param','set','MC_RAPTOR_RINI',str(rini));self.command('param','set','MC_RAPTOR_NCO',str(nco))
        # P4-01c takeover target: set only by treatments that name it (others keep the defaults RTGT=0, RTDEC=2.0).
        target='rtgt' in t
        if target:self.command('param','set','MC_RAPTOR_RTGT',str(int(t['rtgt'])));self.command('param','set','MC_RAPTOR_RTDEC',repr(float(t['rtdec'])))
        # P7 rate-limited recovery: set only by treatments that name it (others keep the default RREC=0).
        recovery='rrec' in t
        if recovery:self.command('param','set','MC_RAPTOR_RREC',repr(float(t['rrec'])))
        if 'p12' in self.cfg:
            for param,value in {'MC_RAPTOR_P12':int(self.cfg['p12']['observe']),
                                'MC_RAPTOR_P12PH':int(self.cfg['p12']['phase']),
                                'MC_RAPTOR_P12R':int(self.cfg['p12']['repair'])}.items():
                self.command('param','set',param,str(value))
                shown_p12=self.command('param','show',param)
                match_p12=re.search(param+r'\s*\[[^\]]*\]\s*:\s*(-?\d+)',shown_p12)
                if not match_p12 or int(match_p12.group(1))!=value:
                    raise RuntimeError('P12 parameter readback failed: '+param)
            if self.cfg['p12'].get('repair_sample_window'):
                self.command('param','set','MC_RAPTOR_P12MS','0')
                shown=self.command('param','show','MC_RAPTOR_P12MS')
                if not re.search(r'MC_RAPTOR_P12MS\s*\[[^\]]*\]\s*:\s*0(?:\s|$)',shown):
                    raise RuntimeError('P12 repair window initial inhibit readback failed')
            self.event('p12_parameters_before_arming',parameters=self.cfg['p12'])
        if 'p12b' in self.cfg:
            value=int(self.cfg['p12b']['observe'])
            self.command('param','set','MC_RAPTOR_P12B',str(value))
            shown_b=self.command('param','show','MC_RAPTOR_P12B')
            if not re.search(r'MC_RAPTOR_P12B\s*\[[^\]]*\]\s*:\s*'+str(value)+r'(?:\s|$)',shown_b):
                raise RuntimeError('P12b observer parameter readback failed')
            self.event('p12b_parameters_before_arming',parameters=self.cfg['p12b'])
        shown={}
        for name_ in ['MC_RAPTOR_RINI','MC_RAPTOR_NCO','MC_RAPTOR_RSH']+(['MC_RAPTOR_RTGT','MC_RAPTOR_RTDEC'] if target else [])+(['MC_RAPTOR_RREC'] if recovery else []):
            text=self.command('param','show',name_);match=re.search(name_+r'\s*\[[^\]]*\]\s*:\s*(-?\d+(?:\.\d+)?)',text)
            if not match:raise RuntimeError('parameter readback failed: '+name_+': '+text)
            shown[name_]=float(match.group(1)) if name_ in ['MC_RAPTOR_RTDEC','MC_RAPTOR_RREC'] else int(match.group(1))
        want={'MC_RAPTOR_RINI':rini,'MC_RAPTOR_NCO':nco,'MC_RAPTOR_RSH':1}
        if target:want.update({'MC_RAPTOR_RTGT':int(t['rtgt']),'MC_RAPTOR_RTDEC':float(t['rtdec'])})
        if recovery:want['MC_RAPTOR_RREC']=float(t['rrec'])
        if set(shown)!=set(want) or any(abs(shown[k]-want[k])>1e-4 for k in want):raise RuntimeError(f'treatment parameters not applied: {shown}')
        staged=None
        if rini==5:
            values=[float(v) for v in self.cfg['p2']['nstar_memory']['values']]
            if len(values)!=20:raise RuntimeError('N* needs 20 staged values (GRU 16 + previous action 4)')
            staged=self.state('raptor','stage',*values)
        self.event('p2_treatment',treatment=name,parameters=shown,staged_values=self.cfg['p2']['nstar_memory']['values'] if staged else None)
        self.checks['p2_treatment']='PASS'

    # ---- P3: RAPTOR memory lifecycle -------------------------------------------------------------------------------
    def p3_motion(self,t):
        """D3 classic motion at time t [s] after the N->C request: (path s, speed v, accel a, yaw change, yaw rate) along
        one trapezoid; yaw turns in proportion to the path. Zero for conditions without motion. Pure function of cfg."""
        m=self.cfg['p3_condition_spec'].get('motion')
        if not m:return 0.,0.,0.,0.,0.
        if m.get('type')=='ramp_cruise':
            # P4 M3: after start_after_s a linear speed ramp over accel_s to speed_m_s, then cruise (no yaw change).
            vm,ta=float(m['speed_m_s']),float(m['accel_s']);tau=t-float(m['start_after_s'])
            if tau<=0:return 0.,0.,0.,0.,0.
            if tau<ta:return .5*vm*tau*tau/ta,vm*tau/ta,vm/ta,0.,0.
            return .5*vm*ta+vm*(tau-ta),vm,0.,0.,0.
        d,vm,am=float(m['distance_m']),float(m['speed_m_s']),float(m['accel_m_s2'])
        ta=min(vm/am,(d/am)**.5);vp=am*ta;tc=(d-am*ta*ta)/vp;total=2*ta+tc;tau=t-float(m['start_after_s'])
        if tau<=0:s,v,a=0.,0.,0.
        elif tau>=total:s,v,a=d,0.,0.
        elif tau<ta:s,v,a=.5*am*tau*tau,am*tau,am
        elif tau<ta+tc:s,v,a=.5*am*ta*ta+vp*(tau-ta),vp,0.
        else:r=total-tau;s,v,a=d-.5*am*r*r,am*r,-am
        k=math.radians(float(m['yaw_change_deg']))/d
        return s,v,a,k*s,k*v

    def p3_motion_end(self,origin):
        m=self.cfg['p3_condition_spec'].get('motion')
        if not m:return list(origin)
        # ramp_cruise: planned position at the second C->N (deactivation_s after the N->C request).
        d=Experiment.p3_motion(self,float(self.cfg['p3_condition_spec']['deactivation_s']))[0] if m.get('type')=='ramp_cruise' else float(m['distance_m'])
        return [origin[i]+float(m['axis_ned'][i])*d for i in range(3)]

    def start_p3_stream(self,origin,yaw):
        # One stationary OFFBOARD/RAPTOR-external trajectory_setpoint; during D3 it follows p3_motion from p3_motion_t0.
        period=self.cfg['p3']['sequence']['setpoint_period_s'];m=self.cfg['p3_condition_spec'].get('motion') or {}
        axis=[float(x) for x in m.get('axis_ned',[0.,0.,0.])]
        state={'last':0.,'count':0,'origin':origin,'yaw':yaw};self.stream_state=state;self.p3_motion_t0=None
        def publish():
            now=time.monotonic()
            if now-state['last']<period:return
            s,v,a,dyaw,rate=(0.,)*5 if self.p3_motion_t0 is None else self.p3_motion(now-self.p3_motion_t0)
            stamp=int(time.time()*1e6)
            off=self.msgs.OffboardControlMode();off.timestamp=stamp;off.position=True;self.offpub.publish(off)
            traj=self.msgs.TrajectorySetpoint();traj.timestamp=stamp
            traj.position=[origin[i]+axis[i]*s for i in range(3)];traj.velocity=[axis[i]*v for i in range(3)]
            traj.acceleration=[axis[i]*a for i in range(3)];traj.yaw=math.atan2(math.sin(yaw+dyaw),math.cos(yaw+dyaw));traj.yawspeed=rate
            self.trajpub.publish(traj)
            state['last']=now;state['count']+=1;state['last_position']=list(map(float,traj.position));state['last_velocity']=list(map(float,traj.velocity));state['last_yaw']=float(traj.yaw)
        self.stream=publish
        self.event('p3_reference_started',origin_ned_m=origin,yaw_rad=yaw,period_s=period)

    def p3_phase(self,duration,label):
        # Native-time phase that keeps the reference stream publishing (no blocking listener while streaming).
        bound=self.native_bound_streaming if self.stream else self.native_phase_end_bound
        start=bound();self.event('p3_phase_started',label=label,duration_s=duration,px4_start_us=start);t0=time.monotonic()
        while time.monotonic()<t0+3*duration+15:
            if time.monotonic()-t0<duration:self.pump(0.01);continue
            end=bound()
            if end-start>=duration*1e6:self.event('p3_phase_ended',label=label,px4_end_us=end);return
            self.pump(0.02)
        raise TimeoutError('native simulation phase duration '+label)

    def read_research_parameters(self):
        shown={}
        for name in ['MC_RAPTOR_RINI','MC_RAPTOR_NCO','MC_RAPTOR_RSH']:
            text=self.command('param','show',name);match=re.search(name+r'\s*\[[^\]]*\]\s*:\s*(-?\d+)',text)
            if not match:raise RuntimeError('parameter readback failed: '+name+': '+text)
            shown[name]=int(match.group(1))
        return shown

    def p3_parameters(self,rini,label):
        self.command('param','set','MC_RAPTOR_RINI',str(rini));self.command('param','set','MC_RAPTOR_NCO','0')
        shown=self.read_research_parameters()
        if shown!={'MC_RAPTOR_RINI':rini,'MC_RAPTOR_NCO':0,'MC_RAPTOR_RSH':1}:raise RuntimeError(f'P3 parameters not applied ({label}): {shown}')
        self.event('p3_parameters',label=label,treatment=self.cfg['p3_treatment'],parameters=shown)

    def raptor_capture_target(self):
        # RAPTOR's exact activation capture: position from the state read, yaw from its own capture message.
        values=self.state('raptor','read')['values'];position=[float(v) for v in values[20:23]]
        text=(self.out/'logs/px4.log').read_text(errors='replace')
        found=re.findall(r'trajectory_setpoint (?:turned stale|reset due to activation) at: (\S+) (\S+) (\S+), yaw: (\S+)',text)
        if not found:raise RuntimeError('RAPTOR capture message missing in px4.log')
        x,y,z,yaw=[float(v) for v in found[-1]]
        if max(abs(a-b) for a,b in zip(position,[x,y,z]))>1e-4:raise RuntimeError(f'RAPTOR capture message {found[-1]} differs from state read {position}')
        return position,yaw,'raptor state values[20:23]; yaw from RAPTOR capture message'

    def send_mode(self,mode):
        # Non-blocking NAV_SET request; the caller checks acknowledgement and nav_state.
        msg=self.msgs.VehicleCommand();msg.timestamp=int(time.time()*1e6);msg.command=100001;msg.param1=float(mode)
        msg.target_system=self.instance+1;msg.target_component=1;msg.source_system=245;msg.source_component=191;msg.from_external=True
        start=len(self.acks);self.event('command_requested',command=100001,params={'param1':mode})
        sent=time.monotonic();self.cmdpub.publish(msg);return start,sent

    def mode_progress(self,start,mode,state):
        if not state.get('acked'):
            ack=next((a for a in self.acks[start:] if a.command==100001),None)
            if ack is not None:
                if ack.result!=0:raise RuntimeError(f'command 100001 rejected: {ack.result}')
                state['acked']=True
        if not state.get('confirmed') and self.latest['vehicle_status'].nav_state==mode:
            state['confirmed']=True;self.event('mode_confirmed',mode=mode,px4_timestamp=int(self.latest['vehicle_status'].timestamp))
        return state.get('acked') and state.get('confirmed')

    def p3_c_to_n(self,mode,subject,iteration,bound=None):
        if bound is None:bound=self.native_bound_streaming()
        self.stop_stream()
        self.event('p3_trigger',subject=subject,end_bound_px4_us=bound,condition=self.cfg['p3_condition'],treatment=self.cfg['p3_treatment'])
        self.event('handover_requested',end_bound_px4_us=bound,from_controller='C',to_controller='N',iteration=iteration,subject=True)
        self.mode(mode);self.wait_raptor_active();self.capture_states('neural_after_entry')

    def p3_deactivation(self,mode,origin):
        seq=self.cfg['p3']['sequence'];spec=self.cfg['p3_condition_spec'];offboard=self.msgs.VehicleStatus.NAVIGATION_STATE_OFFBOARD
        if spec.get('motion'):
            end=self.p3_motion_end(origin);limit=self.cfg['safety_radius_m']-self.cfg['p3']['safety_check']['radius_margin_m']
            radius=max(math.hypot(origin[0],origin[1]),math.hypot(end[0],end[1]))+float(spec['motion'].get('braking_allowance_m',0.))
            self.event('p3_motion_check',origin_ned_m=origin,end_ned_m=end,max_planned_radius_m=radius,limit_m=limit,braking_allowance_m=spec['motion'].get('braking_allowance_m'))
            if radius>limit:raise RuntimeError(f'D3 motion would leave the safety radius margin: {radius:.2f} m > {limit:.2f} m')
        bound=self.native_bound_streaming()
        self.event('p3_trigger',subject='N_to_C',end_bound_px4_us=bound,condition=self.cfg['p3_condition'],treatment=self.cfg['p3_treatment'])
        self.event('handover_requested',end_bound_px4_us=bound,from_controller='N',to_controller='C',iteration=1,subject=True)
        start,t0=self.send_mode(offboard)
        if spec.get('motion'):self.p3_motion_t0=t0
        deadline=t0+float(spec['deactivation_s']);lead=max(seq['listener_lead_min_s'],1.5*max(self.listener_durations or [0.]));state={}
        # The acknowledgement gates the second request; the DDS nav_state echo (~0.2 s) is recorded when seen and
        # the actual ownership order is checked from the ULog.
        while not (self.mode_progress(start,offboard,state) or state.get('acked')) or time.monotonic()<deadline-lead:
            if time.monotonic()>t0+5 and not state.get('acked'):raise TimeoutError('N->C OFFBOARD not acknowledged')
            self.pump(0.002)
        bound=self.native_bound_streaming()
        while time.monotonic()<deadline:self.pump(0.002);self.mode_progress(start,offboard,state)
        if not state.get('confirmed'):
            self.mode_progress(start,offboard,state)
            if not state.get('confirmed'):self.event('p3_nav_state_echo_pending',mode=offboard)
        self.event('p3_deactivation_request',requested_s=float(spec['deactivation_s']),listener_lead_s=lead,
                   since_n_to_c_request_s=time.monotonic()-t0,stream_last_position_ned_m=self.stream_state.get('last_position'),stream_last_yaw_rad=self.stream_state.get('last_yaw'))
        self.p3_c_to_n(mode,'second_C_to_N',2,bound=bound)

    def p3_flight(self,mode):
        seq=self.cfg['p3']['sequence'];spec=self.cfg['p3_condition_spec'];baseline=self.args.kind=='p3_baseline_raptor'
        origin,yaw,source=self.classic_target()
        self.event('p3_reference_origin',stage='classic_hold',source=source,origin_ned_m=origin,yaw_rad=yaw)
        self.start_p3_stream(origin,yaw);self.pump(seq['offboard_prestream_s'])
        self.mode(self.msgs.VehicleStatus.NAVIGATION_STATE_OFFBOARD)
        self.p3_phase(seq['classic_hold_s'],'classic_offboard_hold')
        self.p3_c_to_n(mode,'first_C_to_N',0)
        self.p3_phase(seq['treatment_parameter_after_entry_s'],'neural_first_entry')
        self.p3_parameters(int(self.cfg['p3_treatment_parameters']['rini']),'treatment')
        origin,yaw,source=self.raptor_capture_target()
        self.event('p3_reference_origin',stage='raptor_hold',source=source,origin_ned_m=origin,yaw_rad=yaw)
        self.start_p3_stream(origin,yaw)
        self.p3_phase(seq['neural_s']-seq['treatment_parameter_after_entry_s'],'neural_hold')
        if baseline:
            self.p3_phase(float(spec['deactivation_s']),'neural_continued')
            bound=self.native_bound_streaming();self.stop_stream()
            self.event('p3_trigger',subject='baseline_recapture',end_bound_px4_us=bound,condition=self.cfg['p3_condition'],treatment=self.cfg['p3_treatment'])
        else:self.p3_deactivation(mode,origin)
        self.p3_phase(seq['post_handover_s'],'post_event')
        self.event('handover_requested',end_bound_px4_us=self.native_phase_end_bound(),from_controller='N',to_controller='C',iteration=3,subject=False)
        self.mode(4);self.capture_states('classic_after_entry')
        self.p3_phase(seq['return_hold_s'],'return_classic')
        self.checks['p3_sequence']='PASS'

    def crash_probe(self):
        # Infrastructure probe only: forced disarm in the air, free fall to the ground, then normal cleanup.
        self.safe=False
        self.event('crash_probe_disarm_requested',end_bound_px4_us=self.native_phase_end_bound())
        self.ros_command(400,param1=0,param2=21196)
        self.wait(lambda:-self.latest['vehicle_local_position'].z<0.3 and abs(self.latest['vehicle_local_position'].vz)<0.2,20,'crash probe on ground')
        self.pump(3)
        self.event('crash_probe_ground',px4_us=self.native_phase_end_bound(),position_ned_m=[float(self.latest['vehicle_local_position'].x),float(self.latest['vehicle_local_position'].y),float(self.latest['vehicle_local_position'].z)],
            arming_state=int(self.latest['vehicle_status'].arming_state))
        self.command('param','show');self.command('logger','status');self.command('mc_raptor','status')
        self.checks['crash_probe']='PASS'

    def wait_sensor_readiness(self):
        gate=Readiness();deadline=time.monotonic()+self.cfg['startup_timeout_s'];last_log=0
        with (self.out/'readiness.jsonl').open('w') as log:
            while time.monotonic()<deadline:
                self.pump(.1);now=time.monotonic();result=gate.update(self.latest,self.received,now)
                if now-last_log>=.5 or result['ready']:
                    last_log=now;log.write(json.dumps({'monotonic_ns':time.monotonic_ns(),**result})+'\n');log.flush()
                if result['ready']:
                    self.event('sensor_readiness',**result);self.checks['sensor_readiness']='PASS';return
        self.event('sensor_readiness_failed',**result)
        raise TimeoutError('fresh raw/selected barometer and valid local position for 2s')

    def capture_startup_diagnostics(self,intervene=False):
        for module,args in [('gz_bridge',['status']),('listener',['sensor_baro','-n','1']),('listener',['vehicle_air_data','-n','1']),('listener',['vehicle_local_position','-n','1']),('listener',['sensor_gyro','-n','1']),('listener',['sensor_accel','-n','1']),('listener',['sensor_mag','-n','1']),('sensors',['status'])]:
            try:self.command(module,*args,timeout=3,required=False)
            except Exception as error:self.event('diagnostic_unavailable',module=module,reason=str(error))
        try:
            result=subprocess.run(['gz','topic','-l'],env=self.env,capture_output=True,text=True,timeout=4)
            (self.out/'logs/gazebo-topics.txt').write_text(result.stdout+result.stderr)
            for sensor in ['imu_sensor/imu','air_pressure_sensor/air_pressure','magnetometer_sensor/magnetometer']:
                name=sensor.split('/')[0];topic=f'/world/default/model/x500_{self.instance}/link/base_link/sensor/'+sensor
                info=subprocess.run(['gz','topic','-i','-t',topic],env=self.env,capture_output=True,text=True,timeout=4)
                (self.out/'logs'/('gazebo-'+name+'-info.txt')).write_text(info.stdout+info.stderr)
        except Exception as error:self.event('diagnostic_unavailable',module='gazebo-topics',reason=str(error))
        if intervene:
            # Failed run stays FAIL: a late raw subscriber is an explicit diagnostic intervention.
            for sensor in ['imu_sensor/imu','air_pressure_sensor/air_pressure']:
                name='probe-'+sensor.split('/')[0]
                topic=f'/world/default/model/x500_{self.instance}/link/base_link/sensor/'+sensor
                self.event('sensor_probe_started',sensor=sensor,changes_subscription_graph=True)
                process=self.spawn(name,['gz','topic','-e','-t',topic])
                try:process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.expected_stopped.add(name);os.killpg(process.pid,signal.SIGINT)
                    try:process.wait(timeout=3)
                    except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
                self.expected_stopped.add(name)
                try:self.command('gz_bridge','status',timeout=3,required=False)
                except Exception as error:self.event('diagnostic_unavailable',module='post-probe-bridge',reason=str(error))
                self.event('sensor_probe_finished',sensor=sensor,exit_code=process.returncode)

    def state(self,target,operation,*values,expected=0):
        text=self.command('mc_raptor','state',target,operation,*values,required=False)
        data=next((json.loads(s) for s in text.splitlines() if s.startswith('{"request_id"')),None)
        if data is None or data['result']!=expected:
            raise RuntimeError(f'state {target}/{operation}: expected {expected}, got {text}')
        self.event('state_operation',target=target,operation=operation,response=data)
        return data

    def state_contract(self):
        for target in ['raptor','rate','velocity']:
            self.state(target,'hold')
            base=self.state(target,'read')['values']
            values=base[:]
            if target=='raptor':values[:20]=[0.05]*16+[0.03]*4
            else:values=[0.01,-0.01,0.015]
            self.state(target,'inject',*values)
            actual=self.state(target,'read')['values']
            if max(abs(a-b) for a,b in zip(values,actual))>1e-6:raise RuntimeError('injected state did not persist at controller boundary')
            self.state(target,'snapshot')
            reset=self.state(target,'reset')['values']
            if any(abs(v)>1e-7 for v in reset[:20 if target=='raptor' else 3]):raise RuntimeError('reset did not clear controller memory')
            restored=self.state(target,'restore')['values']
            if max(abs(a-b) for a,b in zip(values,restored))>1e-6:raise RuntimeError('restored state differs from snapshot')
            self.state(target,'inject',*values[:-1],expected=3)
            bad=values[:];bad[0]='nan';self.state(target,'inject',*bad,expected=4)
            bad=values[:];bad[0]=999;self.state(target,'inject',*bad,expected=5)
            self.state(target,'reset');self.state(target,'release')
        self.checks['state_contract']='PASS'

    def capture_states(self,label):
        self.event('state_capture_started',label=label)
        for target in ['raptor','rate','velocity']:self.state(target,'read')
        self.event('state_capture_finished',label=label)

    def mode(self,mode):
        # PX4 NAV_SET command carries navigation state directly; external ID is discovered.
        self.ros_command(100001,param1=mode)
        self.wait(lambda:self.latest['vehicle_status'].nav_state==mode,5,'nav_state='+str(mode))
        self.event('mode_confirmed',mode=mode,px4_timestamp=int(self.latest['vehicle_status'].timestamp))

    def execute(self):
        # Cooperative per-instance exclusion, plus actual PX4 instance/socket check.
        lock=(LAB/'.local/experiment-instance.lock').open('w');self.files.append(lock)
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        server_lock=Path(f'/tmp/px4_lock-{self.instance}')
        if server_lock.exists():
            with server_lock.open('r+') as f:
                try:fcntl.lockf(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError:raise RuntimeError('PX4 instance already active; refusing to attach')
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:s.bind(('127.0.0.1',self.cfg['agent_port']))
        if self.variant=='raptor':
            (self.rootfs/'raptor').mkdir()
            policy=self.source/'src/modules/mc_raptor/blob/policy.tar'
            shutil.copy2(policy,self.rootfs/'raptor/policy.tar');self.metadata['policy_sha256']=digest(policy)
        # Private etc tree permits logger configuration without changing the build or another run.
        shutil.copytree(self.runtime/'etc',self.rootfs/'etc')
        logging=self.rootfs/'etc/logging';logging.mkdir(exist_ok=True)
        names=['sensor_baro','vehicle_air_data','actuator_outputs','sensor_gyro','vehicle_imu','vehicle_imu_status','vehicle_local_position','vehicle_global_position','position_setpoint_triplet','takeoff_status','vehicle_attitude','vehicle_angular_velocity','vehicle_status','vehicle_control_mode','trajectory_setpoint','vehicle_attitude_setpoint','vehicle_rates_setpoint','vehicle_torque_setpoint','vehicle_thrust_setpoint','rate_ctrl_status','actuator_motors','vehicle_command','vehicle_command_ack']
        if self.variant=='raptor':names+=['research_output','research_angular_velocity','raptor_status','raptor_input','route_observability','research_state_request','research_state_response','research_timing','research_actuator','research_memory','research_target','research_recovery']
        if self.cfg.get('p11',{}).get('observe'):
            names+=['research_p11','vehicle_local_position_groundtruth','vehicle_attitude_groundtruth','vehicle_angular_velocity_groundtruth']
        if self.cfg.get('p12',{}).get('observe'):
            names+=['research_p12']
        if self.cfg.get('p12b',{}).get('observe'):names+=['research_p12b']
        (logging/'logger_topics.txt').write_text(''.join(n+' 0 0\n' for n in names)+(''.join(f'route_observability 0 {i}\n' for i in range(1,10)) if self.variant=='raptor' else ''))
        self.spawn('agent',[str(LAB/'scripts/MicroXRCEAgent'),'udp4','-p',str(self.cfg['agent_port']),'-v','4'])
        self.spawn('gazebo',['gz','sim','-r','-s','-v','3']+(['--seed',str(self.sim_seed)] if self.sim_seed is not None else [])+[str(self.source/'Tools/simulation/gz/worlds/default.sdf')])
        if self.args.capture_raw_sensors:
            self.spawn('gz-imu',['gz','topic','-e','-t',f'/world/default/model/x500_{self.instance}/link/base_link/sensor/imu_sensor/imu'])
            self.spawn('gz-pressure',['gz','topic','-e','-t',f'/world/default/model/x500_{self.instance}/link/base_link/sensor/air_pressure_sensor/air_pressure'])
        self.spawn('gz-stats',['gz','topic','-e','-t','/world/default/stats'])
        if Path('/usr/bin/tegrastats').exists():self.spawn('tegrastats',['/usr/bin/tegrastats','--interval','1000'])
        self.init_ros()
        px4_argv=[str(self.binary),'-d','-i',str(self.instance),'-w',str(self.rootfs),str(self.rootfs/'etc')]
        trace=os.environ.get('HANDOVER_PX4_TRACE')
        if trace:
            self.metadata['diagnostic_preload']={'path':trace,'sha256':digest(Path(trace))}
            px4_argv=['env','LD_PRELOAD='+trace]+px4_argv
        if os.environ.get('HANDOVER_PX4_GDB')=='1':px4_argv=['gdb','--batch','-ex','set pagination off','-ex','handle SIGCONT nostop noprint pass','-ex','run','-ex','thread apply all bt','--args']+px4_argv
        core_soft,core_hard=resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE,(core_hard,core_hard))
        self.metadata['core_capture']={'soft_limit':core_hard,'pattern':Path('/proc/sys/kernel/core_pattern').read_text().strip()}
        self.spawn('px4',px4_argv,cwd=self.rootfs)
        self.wait(lambda:all(n in self.latest for n in ['vehicle_status','vehicle_odometry','vehicle_local_position','vehicle_attitude']),self.cfg['startup_timeout_s'],'PX4 DDS telemetry')
        self.command('ver','all');self.command('gz_bridge','status');self.command('uxrce_dds_client','status')
        self.command('param','set','NAV_DLL_ACT','0')
        self.command('param','set','COM_DISARM_LAND','2')
        self.command('param','set','MIS_TAKEOFF_ALT',str(self.cfg['altitude_m']))
        if self.latest['vehicle_status'].system_id!=self.instance+1:
            raise RuntimeError('SITL identity mismatch')
        self.checks['telemetry']='PASS'
        self.wait_sensor_readiness()
        if self.startup_only:
            self.capture_startup_diagnostics()
            if self.variant=='raptor':
                text=(self.out/'logs/px4.log').read_text(errors='replace')
                if 'Checkpoint test passed' not in text:raise RuntimeError('startup policy self-test not confirmed')
                self.command('mc_raptor','status');self.checks['policy_selftest']='PASS'
            self.checks['startup_sequence']='PASS'
            return
        # Only address the localhost UDP socket of the PX4 process just created.
        from pymavlink import mavutil
        mav=mavutil.mavlink_connection(f'udpout:127.0.0.1:{18570+self.instance}',source_system=245,source_component=191)
        try:
            mav.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_GCS,mavutil.mavlink.MAV_AUTOPILOT_INVALID,0,0,0)
            heartbeat=mav.recv_match(type='HEARTBEAT',blocking=True,timeout=5)
            if heartbeat is None or heartbeat.get_srcSystem()!=self.instance+1 or heartbeat.autopilot!=mavutil.mavlink.MAV_AUTOPILOT_PX4:
                raise RuntimeError('owned SITL MAVLink heartbeat identity not confirmed')
            self.event('mavlink_identity',system_id=heartbeat.get_srcSystem(),autopilot=heartbeat.autopilot,udp_port=18570+self.instance)
            self.checks['mavlink']='PASS'
        finally:mav.close()
        old_stamp=int(self.latest['vehicle_odometry'].timestamp)
        agent=next(p for name,p in self.procs if name=='agent')
        self.expected_stopped.add('agent');agent.send_signal(signal.SIGINT);agent.wait(timeout=5)
        self.spawn('agent-reconnected',[str(LAB/'scripts/MicroXRCEAgent'),'udp4','-p',str(self.cfg['agent_port']),'-v','4'])
        self.wait(lambda:int(self.latest['vehicle_odometry'].timestamp)>old_stamp+2_000_000,25,'DDS Client reconnection with fresh telemetry')
        self.checks['dds_reconnection']='PASS'
        # Harmless ROS->PX4 command, and inbound setpoint checks while disarmed.
        self.ros_command(176,param1=1,param2=4,param3=3)
        for _ in range(10):
            off=self.msgs.OffboardControlMode();off.timestamp=int(time.time()*1e6);off.position=True;self.offpub.publish(off)
            traj=self.msgs.TrajectorySetpoint();traj.timestamp=off.timestamp;traj.position=[0.,0.,-self.cfg['altitude_m']];traj.velocity=[0.,0.,0.];traj.yaw=0.;traj.yawspeed=0.;self.trajpub.publish(traj);self.pump(0.1)
        self.mode(self.msgs.VehicleStatus.NAVIGATION_STATE_OFFBOARD)
        for _ in range(5):
            off.timestamp=int(time.time()*1e6);traj.timestamp=off.timestamp
            self.offpub.publish(off);self.trajpub.publish(traj);self.pump(0.05)
        off_evidence=self.command('listener','offboard_control_mode','-n','1')
        trajectory_evidence=self.command('listener','trajectory_setpoint','-n','1')
        expected_position=f'0.00000, 0.00000, {-float(self.cfg["altitude_m"]):.5f}'
        if 'position: True' not in off_evidence or expected_position not in trajectory_evidence:
            raise RuntimeError('inbound offboard/setpoint values not confirmed by uORB')
        self.mode(self.msgs.VehicleStatus.NAVIGATION_STATE_AUTO_LOITER)
        self.checks['bidirectional_dds']='PASS'
        if self.variant=='raptor':
            self.command('mc_raptor','status')
            end=time.monotonic()+10;mode=None
            while time.monotonic()<end:
                text=(self.out/'logs/px4.log').read_text(errors='replace')
                matches=re.findall(r'Raptor mode registration successful.*mode_id: (\d+)',text)
                if matches:mode=int(matches[-1]);break
                self.pump(0.1)
            if mode is None:raise RuntimeError('RAPTOR mode registration not confirmed')
            if 'Checkpoint test passed' not in text:raise RuntimeError('policy self-test not confirmed')
            self.metadata['raptor_mode_id']=mode;self.checks['policy_selftest']='PASS'
            self.command('param','set','MC_RAPTOR_RSH','0')
            self.state('raptor','read',expected=1)
            self.command('param','set','MC_RAPTOR_RSH','1')
            if self.cfg.get('p11',{}).get('observe'):
                self.command('param','set','MC_RAPTOR_P11','1')
        self.wait(lambda:self.latest['vehicle_local_position'].xy_valid and self.latest['vehicle_local_position'].z_valid,45,'valid local position')
        self.pump(4)
        if self.variant=='raptor':self.state_contract()
        if self.args.kind in P2_TREATMENT_KINDS or self.args.kind in P5_TREATMENT_KINDS or self.args.kind in P6_TREATMENT_KINDS:self.apply_treatment()
        if self.args.kind in P3_TREATMENT_KINDS:self.p3_parameters(0,'before_arming')
        self.ros_command(400,param1=1)
        self.safe=True
        self.ros_command(22,param4=None,param5=None,param6=None,param7=None)
        self.wait(lambda:-self.latest['vehicle_local_position'].z>self.cfg['altitude_m']-0.5,self.cfg['takeoff_timeout_s'],'takeoff altitude')
        self.mode(4) # AUTO_LOITER
        self.hover(self.cfg['hover_s'],'classic_before')
        if self.args.kind=='p2_crash_probe':
            self.crash_probe();return
        if self.args.kind.startswith(('p1_','p2_')):self.p1_flight(mode)
        elif self.args.kind.startswith('p3_'):self.p3_flight(mode)
        elif self.args.kind=='p5_gap':self.p5_gap_flight(mode)
        elif self.args.kind=='p6_ident':self.p6_ident_flight(mode)
        elif self.variant=='raptor':
            count=self.cfg['repetitions'] if self.args.kind=='repeated_handover' else 1
            for iteration in range(count):
                self.capture_states('classic_before_handover')
                if self.args.kind.startswith('state_'):
                    self.state('rate','snapshot');self.state('velocity','snapshot')
                if self.args.kind=='state_injection':
                    self.command('param','set','MC_RAPTOR_RINI','1')
                    self.state('raptor','hold')
                    values=self.state('raptor','read')['values'];values[:16]=[0.02]*16
                    self.state('raptor','inject',*values)
                self.event('handover_requested',end_bound_px4_us=self.native_phase_end_bound(),from_controller='C',to_controller='N',iteration=iteration)
                self.mode(mode)
                self.wait(lambda:self.latest.get('raptor_status') and self.latest['raptor_status'].active and self.latest.get('raptor_input') and self.latest['raptor_input'].active,5,'RAPTOR active diagnostic DDS')
                self.checks['raptor_diagnostic_dds']='PASS'
                self.command('listener','raptor_status','-n','1')
                self.command('listener','vehicle_control_mode','-n','1')
                self.capture_states('neural_after_entry')
                if self.args.kind.startswith('state_'):
                    self.state('raptor','restore',expected=2)
                    self.state('raptor','inject',*[0.0]*26,expected=2)
                if self.args.kind=='state_reset':
                    self.state('raptor','reset');self.state('rate','reset');self.state('velocity','reset')
                if self.args.kind=='state_hold':self.state('raptor','hold')
                if self.args.kind=='state_injection':self.state('raptor','release')
                if self.args.kind=='state_restore':
                    self.state('raptor','snapshot')
                self.hover(self.cfg['neural_s'],'neural')
                if self.args.kind=='state_hold':self.state('raptor','release')
                if self.args.kind=='state_restore':
                    self.state('rate','hold');self.state('velocity','hold')
                    self.state('rate','restore');self.state('velocity','restore')
                self.capture_states('neural_before_exit')
                self.event('handover_requested',end_bound_px4_us=self.native_phase_end_bound(),from_controller='N',to_controller='C',iteration=iteration)
                self.mode(4)
                if self.args.kind=='state_restore':
                    self.state('rate','release');self.state('velocity','release')
                self.capture_states('classic_after_entry')
                self.command('listener','raptor_status','-n','1');self.command('listener','vehicle_control_mode','-n','1')
                self.hover(self.cfg['hover_s'],'classic_after')
                if self.args.kind=='state_restore':
                    self.command('param','set','MC_RAPTOR_RINI','1')
                    self.state('raptor','hold');self.state('raptor','reset');self.state('raptor','restore')
                    self.event('handover_requested',end_bound_px4_us=self.native_phase_end_bound(),from_controller='C',to_controller='N',iteration=1)
                    self.mode(mode);self.state('raptor','release')
                    self.hover(self.cfg['neural_s'],'neural_restored')
                    self.event('handover_requested',end_bound_px4_us=self.native_phase_end_bound(),from_controller='N',to_controller='C',iteration=1)
                    self.mode(4);self.hover(self.cfg['hover_s'],'classic_after_restore')
        self.event('landing_requested',end_bound_px4_us=self.native_phase_end_bound())
        self.ros_command(21)
        self.wait(lambda:self.latest.get('vehicle_land_detected') and self.latest['vehicle_land_detected'].landed,self.cfg['landing_timeout_s'],'landing')
        self.safe=False
        self.wait(lambda:self.latest['vehicle_status'].arming_state!=2,15,'disarmed')
        self.command('param','show');self.command('logger','status')
        if self.variant=='raptor':self.command('mc_raptor','status')
        self.checks['flight_sequence']='PASS'

    def cleanup(self):
        self.safe=False
        if any(n=='px4' and p.poll() is None for n,p in self.procs):
            try:
                self.command('commander','land',timeout=3,required=False)
                self.command('shutdown',timeout=5,required=False)
            except Exception:self.event('shutdown_command_failed')
        for name,p in reversed(self.procs):
            if p.poll() is None:
                os.killpg(p.pid,signal.SIGINT)
                try:p.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    os.killpg(p.pid,signal.SIGTERM)
                    try:p.wait(timeout=5)
                    except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait(timeout=3)
            self.event('process_stopped',name=name,pid=p.pid,exit_code=p.returncode)
        if self.node:self.node.destroy_node()
        if self.rclpy and self.rclpy.ok():self.rclpy.shutdown()
        self.samples.close()
        self.resources.close()
        for f in self.files:f.close()
        logs=sorted(self.rootfs.glob('log/**/*.ulg'))
        if logs:
            if self.cfg.get('p11',{}).get('ulog_storage')=='hardlink_after_shutdown':
                # Both raw paths survive. Linking a NEW destination after every
                # owned process exits avoids a second physical copy, no unlink.
                os.link(logs[-1],self.out/'flight.ulg')
                self.metadata['ulog_storage']={'mode':'hardlink_after_shutdown','source':str(logs[-1]),
                    'inode':logs[-1].stat().st_ino,'links':logs[-1].stat().st_nlink}
            else:shutil.copy2(logs[-1],self.out/'flight.ulg')
            self.metadata['ulog_sha256']=digest(self.out/'flight.ulg')
        self.metadata['checks']=self.checks
        write(self.out/'metadata.json',self.metadata)
        self.events.close()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('kind',choices=TYPES);p.add_argument('--config',type=Path,default=ROOT/'config/experiment.json')
    p.add_argument('--capture-raw-sensors',action='store_true',help='Diagnostic only: adds sensor subscribers and may change startup behavior')
    p.add_argument('--startup-only',action='store_true',help='Preparation cold start; readiness only, never arm')
    p.add_argument('--output',type=Path);p.add_argument('--hover-s',type=float)
    p.add_argument('--sim-seed',type=int,help='P4: Gazebo random seed (gz sim --seed), recorded in config.json and metadata')
    p.add_argument('--initial-yaw-deg',type=float,help='P4: initial heading of the spawned x500 (PX4_GZ_MODEL_POSE yaw), recorded')
    p.add_argument('--condition',help='P1/P2 pre-handover motion condition (config p1.conditions / p2.conditions)')
    p.add_argument('--treatment',help='P2 treatment (config p2.treatments): N0 N1 N2g N2 N2s Nstar for p2_c_to_n, C0 C2 for p2_n_to_c, B for baselines; P3: N0 N3 N2s N2 for p3_sequence (conditions D1 D2 D3), B for p3_baseline_raptor (condition R); P5: T0 T1 T1a1 T1a3 for p5_gap (config p5.conditions); P6: also T1a0.75 T1a1.5 for p5_gap (generated conditions), T0 for p6_ident (config p6.ident.conditions; P8-A also the jump family)')
    args=p.parse_args();e=Experiment(args);status='FAIL';reason=None
    try:
        e.execute();status='PASS'
    except Exception as ex:
        reason=str(ex);e.event('failure',reason=reason);traceback.print_exc()
        if not e.safe:
            e.capture_startup_diagnostics(intervene=True)
        else:
            e.event('diagnostic_skipped',reason='flight failure proceeds directly to landing and cleanup')
    finally:
        e.cleanup()
        write(e.out/'validation.json',{'status':status,'execution_status':status,'reason':reason,'checks':e.checks})
    if (e.out/'flight.ulg').exists() and not e.startup_only:
        proc=subprocess.run([sys.executable,str(ROOT/'tools/analyze.py'),str(e.out)],capture_output=True,text=True)
        (e.out/'logs/analysis.log').write_text(proc.stdout+proc.stderr)
        if proc.returncode:status='FAIL'
        else:status=json.loads((e.out/'validation.json').read_text())['status']
    print(e.out,status,flush=True)
    exit_code=0 if status in ['PASS','PASS_WITH_WARNINGS'] else 1
    write(e.out/'execution.json',{'command':[sys.executable,*sys.argv],'exit_code':exit_code,'status':status})
    return exit_code

if __name__=='__main__':sys.exit(main())

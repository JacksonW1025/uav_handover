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
import psutil

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT/'uav_lab'
TYPES = ['classic_hover','raptor_hover','handover_c_to_n','handover_n_to_c',
         'handover_c_n_c','repeated_handover','state_reset','state_hold','state_restore','state_injection']

def write(path, value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

class Experiment:
    def __init__(self,args):
        self.args=args
        self.cfg=json.loads(args.config.read_text())
        if args.hover_s is not None:self.cfg['hover_s']=args.hover_s
        self.variant='classic' if args.kind=='classic_hover' else 'raptor'
        if os.environ.get('HANDOVER_VARIANT')!=self.variant:raise RuntimeError('use tools/experiment to select the correct overlay')
        self.out=(args.output or ROOT/'data'/(dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).strftime('%Y%m%dT%H%M%S')+'-'+args.kind+'-'+uuid.uuid4().hex[:6])).resolve()
        self.out.mkdir(parents=True,exist_ok=False)
        (self.out/'logs').mkdir();(self.out/'rootfs').mkdir();(self.out/'cli').mkdir()
        write(self.out/'config.json',self.cfg)
        self.events=(self.out/'events.jsonl').open('w')
        self.procs=[];self.files=[];self.latest={};self.received={};self.acks=[];self.expected_stopped=set()
        self.node=None;self.rclpy=None;self.safe=False;self.checks={};self.last_sample=0
        self.samples=(self.out/'telemetry.jsonl').open('w')
        self.resources=(self.out/'resources.jsonl').open('w');self.last_resource=0
        self.rootfs=self.out/'rootfs'
        self.source=LAB/'.local/checkouts'/('px4-'+self.variant)
        built=self.source/('build/px4_sitl_default' if self.variant=='classic' else 'build/px4_sitl_raptor')
        self.runtime=built if (built/'bin/px4').exists() else LAB/'.local/runtime/px4-classic'
        self.binary=self.runtime/'bin/px4'
        self.instance=self.cfg['instance']
        self.env=dict(os.environ,GZ_PARTITION='handover-'+uuid.uuid4().hex,HEADLESS='1',
                      PX4_GZ_STANDALONE='1',PX4_SYS_AUTOSTART='4001',PX4_SIM_MODEL='gz_x500',PX4_GZ_WORLD='default',
                      PX4_GZ_MODELS=str(self.source/'Tools/simulation/gz/models'),
                      PX4_GZ_WORLDS=str(self.source/'Tools/simulation/gz/worlds'),
                      GZ_SIM_SERVER_CONFIG_PATH=str(self.source/'Tools/simulation/gz/server.config'),
                      PX4_GZ_MODEL_POSE='0,0,0,0,0,0',PX4_UXRCE_DDS_NS='',
                      ROS_DOMAIN_ID=str(self.cfg['ros_domain_id']),PX4_UXRCE_DDS_PORT=str(self.cfg['agent_port']),
                      PX4_PARAM_NAV_DLL_ACT='0',PX4_PARAM_COM_RC_IN_MODE='4',
                      PX4_PARAM_MIS_TAKEOFF_ALT=str(self.cfg['altitude_m']),
                      PX4_PARAM_IMU_GYRO_RATEMAX='250',PX4_PARAM_SDLOG_MODE='1',
                      PX4_PARAM_MC_RAPTOR_ENABLE='1' if self.variant=='raptor' else '0',
                      PX4_PARAM_MC_RAPTOR_OFFB='0')
        self.env['GZ_SIM_RESOURCE_PATH']=self.env['PX4_GZ_MODELS']+':'+self.env['PX4_GZ_WORLDS']+':/opt/ros/jazzy/share'
        plugins=self.runtime/'src/modules/simulation/gz_plugins' if (self.runtime/'src').exists() else self.runtime/'plugins'
        plugin_paths=str(plugins)+(':'+str(plugins/'optical_flow') if (plugins/'optical_flow').is_dir() else '')
        self.env['GZ_SIM_SYSTEM_PLUGIN_PATH']=plugin_paths
        self.env['LD_LIBRARY_PATH']=plugin_paths+':'+self.env.get('LD_LIBRARY_PATH','')
        if self.variant=='classic':
            self.env.pop('PX4_PARAM_MC_RAPTOR_ENABLE',None)
            self.env.pop('PX4_PARAM_MC_RAPTOR_OFFB',None)
        # ROS middleware reads the domain at context initialization in this process.
        os.environ['ROS_DOMAIN_ID']=self.env['ROS_DOMAIN_ID']
        self.metadata={'experiment_type':args.kind,'variant':self.variant,'created_at':dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(),
                       'seed':self.cfg['seed'],'seed_scope':'recorded; Gazebo/PX4 do not expose a verified universal seed',
                       'initial_pose':'0,0,0,0,0,0','source_commit':subprocess.check_output(['git','-C',str(self.source),'rev-parse','HEAD'],text=True).strip(),
                       'source_diff_sha256':hashlib.sha256(subprocess.check_output(['git','-C',str(self.source),'diff','--binary'])).hexdigest(),
                       'binary':str(self.binary),'binary_sha256':digest(self.binary),
                       'environment':{k:v for k,v in self.env.items() if k.startswith(('PX4_','GZ_','ROS_DOMAIN'))},'processes':[]}
        self.event('created',thresholds=self.cfg)

    def event(self,event_name,**values):
        item={'event':event_name,'monotonic_ns':time.monotonic_ns(),'wall_time_ns':time.time_ns(),**values}
        self.events.write(json.dumps(item,allow_nan=False)+'\n');self.events.flush()
        print(event_name,values,flush=True)

    def spawn(self,name,argv,cwd=None):
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

    def topic(self,direction,name,typ):
        version=getattr(typ,'MESSAGE_VERSION',0)
        return f'/fmu/{direction}/{name}'+(f'_v{version}' if version else '')

    def init_ros(self):
        import rclpy
        from rclpy.qos import qos_profile_sensor_data
        import px4_msgs.msg as msgs
        self.rclpy=rclpy;self.msgs=msgs
        rclpy.init();self.node=rclpy.create_node('handover_lab_'+uuid.uuid4().hex[:8])
        for name,typename in [('vehicle_status','VehicleStatus'),('vehicle_odometry','VehicleOdometry'),('vehicle_attitude','VehicleAttitude'),('vehicle_local_position','VehicleLocalPosition'),('vehicle_land_detected','VehicleLandDetected'),('vehicle_command_ack','VehicleCommandAck')]:
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
            self.rclpy.spin_once(self.node,timeout_sec=min(0.05,max(0,end-time.monotonic())))
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

    def hover(self,duration,label):
        self.event('hover_started',label=label,duration_s=duration)
        start=int(self.latest['vehicle_local_position'].timestamp)
        # Cover the 0.1 s external event alignment uncertainty without reducing
        # the requested minimum duration in the ULog acceptance window.
        self.wait(lambda:int(self.latest['vehicle_local_position'].timestamp)-start>=(duration+0.2)*1e6,
                  3*duration+15,'simulation hover duration '+label)
        self.event('hover_ended',label=label)

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
        names=['vehicle_local_position','vehicle_global_position','position_setpoint_triplet','takeoff_status','vehicle_attitude','vehicle_angular_velocity','vehicle_status','vehicle_control_mode','trajectory_setpoint','vehicle_attitude_setpoint','vehicle_rates_setpoint','vehicle_torque_setpoint','vehicle_thrust_setpoint','rate_ctrl_status','actuator_motors','vehicle_command','vehicle_command_ack']
        if self.variant=='raptor':names+=['raptor_status','raptor_input','route_observability','research_state_request','research_state_response','research_timing','research_actuator']
        (logging/'logger_topics.txt').write_text(''.join(n+' 0 0\n' for n in names)+(''.join(f'route_observability 0 {i}\n' for i in range(1,10)) if self.variant=='raptor' else ''))
        self.spawn('agent',[str(LAB/'scripts/MicroXRCEAgent'),'udp4','-p',str(self.cfg['agent_port']),'-v','4'])
        self.spawn('gazebo',['gz','sim','-r','-s','-v','3',str(self.source/'Tools/simulation/gz/worlds/default.sdf')])
        self.spawn('gz-stats',['gz','topic','-e','-t','/world/default/stats'])
        if Path('/usr/bin/tegrastats').exists():self.spawn('tegrastats',['/usr/bin/tegrastats','--interval','1000'])
        self.init_ros()
        self.spawn('px4',[str(self.binary),'-d','-i',str(self.instance),'-w',str(self.rootfs),str(self.rootfs/'etc')])
        self.wait(lambda:all(n in self.latest for n in ['vehicle_status','vehicle_odometry','vehicle_local_position','vehicle_attitude']),self.cfg['startup_timeout_s'],'PX4 DDS telemetry')
        self.command('ver','all');self.command('gz_bridge','status');self.command('uxrce_dds_client','status')
        self.command('param','set','NAV_DLL_ACT','0')
        self.command('param','set','COM_DISARM_LAND','2')
        self.command('param','set','MIS_TAKEOFF_ALT',str(self.cfg['altitude_m']))
        if self.latest['vehicle_status'].system_id!=self.instance+1:
            raise RuntimeError('SITL identity mismatch')
        self.checks['telemetry']='PASS'
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
        self.wait(lambda:self.latest['vehicle_local_position'].xy_valid and self.latest['vehicle_local_position'].z_valid,45,'valid local position')
        self.pump(4)
        if self.variant=='raptor':self.state_contract()
        self.ros_command(400,param1=1)
        self.safe=True
        self.ros_command(22,param4=None,param5=None,param6=None,param7=None)
        self.wait(lambda:-self.latest['vehicle_local_position'].z>self.cfg['altitude_m']-0.5,self.cfg['takeoff_timeout_s'],'takeoff altitude')
        self.mode(4) # AUTO_LOITER
        self.hover(self.cfg['hover_s'],'classic_before')
        if self.variant=='raptor':
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
                self.event('handover_requested',from_controller='C',to_controller='N',iteration=iteration)
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
                self.event('handover_requested',from_controller='N',to_controller='C',iteration=iteration)
                self.mode(4)
                if self.args.kind=='state_restore':
                    self.state('rate','release');self.state('velocity','release')
                self.capture_states('classic_after_entry')
                self.command('listener','raptor_status','-n','1');self.command('listener','vehicle_control_mode','-n','1')
                self.hover(self.cfg['hover_s'],'classic_after')
                if self.args.kind=='state_restore':
                    self.command('param','set','MC_RAPTOR_RINI','1')
                    self.state('raptor','hold');self.state('raptor','reset');self.state('raptor','restore')
                    self.event('handover_requested',from_controller='C',to_controller='N',iteration=1)
                    self.mode(mode);self.state('raptor','release')
                    self.hover(self.cfg['neural_s'],'neural_restored')
                    self.event('handover_requested',from_controller='N',to_controller='C',iteration=1)
                    self.mode(4);self.hover(self.cfg['hover_s'],'classic_after_restore')
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
            shutil.copy2(logs[-1],self.out/'flight.ulg');self.metadata['ulog_sha256']=digest(self.out/'flight.ulg')
        self.metadata['checks']=self.checks
        write(self.out/'metadata.json',self.metadata)
        self.events.close()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('kind',choices=TYPES);p.add_argument('--config',type=Path,default=ROOT/'config/experiment.json')
    p.add_argument('--output',type=Path);p.add_argument('--hover-s',type=float)
    args=p.parse_args();e=Experiment(args);status='FAIL';reason=None
    try:
        e.execute();status='PASS'
    except Exception as ex:
        reason=str(ex);e.event('failure',reason=reason);traceback.print_exc()
    finally:
        e.cleanup()
        write(e.out/'validation.json',{'status':status,'execution_status':status,'reason':reason,'checks':e.checks})
    if (e.out/'flight.ulg').exists():
        proc=subprocess.run([sys.executable,str(ROOT/'tools/analyze.py'),str(e.out)],capture_output=True,text=True)
        (e.out/'logs/analysis.log').write_text(proc.stdout+proc.stderr)
        if proc.returncode:status='FAIL'
    print(e.out,status,flush=True)
    exit_code=0 if status=='PASS' else 1
    write(e.out/'execution.json',{'command':[sys.executable,*sys.argv],'exit_code':exit_code,'status':status})
    return exit_code

if __name__=='__main__':sys.exit(main())

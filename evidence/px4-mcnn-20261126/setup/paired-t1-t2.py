"""PX4/Gazebo x500 classic-only compatibility check. No MCNN mode request."""
import hashlib
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import threading
from pymavlink import mavutil
import uuid
import rclpy
from px4_msgs.msg import OffboardControlMode, TrajectorySetpoint
from pathlib import Path
import numpy as np
from pyulog import ULog

checkout, dest = map(lambda s: Path(s).resolve(), sys.argv[1:3])
coeff = 1.05
case = sys.argv[3]
assert case in {"t1_c","t1_n","t2_c","t2_n","t3_stale","t3_fresh","t4_hold","t4_release"}
bundle=Path(__file__).resolve().parent
assert 0.95 <= coeff <= 1.2
dest.mkdir()
runtime = checkout / "build/px4_sitl_default"
binary = runtime / "bin/px4"
root = dest / "rootfs"
root.mkdir()
shutil.copytree(runtime / "etc", root / "etc")
models = checkout / "Tools/simulation/gz"
world = models / "worlds/default.sdf"
plugins = runtime / "src/modules/simulation/gz_plugins"
instance = 7
seed = 20261126
env = {k:v for k,v in os.environ.items() if not k.startswith(("PX4_", "GZ_"))}
if "GZ_CONFIG_PATH" in os.environ:
    env["GZ_CONFIG_PATH"] = os.environ["GZ_CONFIG_PATH"]
env.update(
    GZ_IP="127.0.0.1", GZ_PARTITION=f"mcnn-bench-{uuid.uuid4().hex}", HEADLESS="1",
    PX4_GZ_STANDALONE="1", PX4_SYS_AUTOSTART="4001", PX4_SIM_MODEL="gz_x500",
    PX4_GZ_WORLD="default", PX4_GZ_MODELS=str(models/"models"), PX4_GZ_WORLDS=str(world.parent),
    GZ_SIM_RESOURCE_PATH=f"{models/'models'}:{world.parent}", PX4_GZ_NO_FOLLOW="1",
    GZ_SIM_SERVER_CONFIG_PATH=str(checkout/"src/modules/simulation/gz_bridge/server.config"),
    GZ_SIM_SYSTEM_PLUGIN_PATH=str(plugins), PX4_NET_INTERFACE="",
    PX4_UXRCE_DDS_PORT="18971", ROS_DOMAIN_ID="97",
    PX4_PARAM_MC_NN_MANL_CTRL="0", PX4_PARAM_MC_NN_THRST_COEF=str(coeff), PX4_PARAM_MIS_TAKEOFF_ALT="2",
    PX4_PARAM_COM_DISARM_LAND="2", PX4_PARAM_COM_RC_IN_MODE="4",
)
(dest/"motor").mkdir()
env.update(MCNN_NATIVE_TRACE=str(dest/"native.csv"),
           HANDOVER_GZ_MOTOR_TRACE=str(dest/"motor"),
           PX4_GZ_MODELS=str(bundle/"models"),
           GZ_SIM_RESOURCE_PATH=str(bundle/"models")+":"+env["GZ_SIM_RESOURCE_PATH"],
           GZ_SIM_SYSTEM_PLUGIN_PATH=str(bundle)+":"+env["GZ_SIM_SYSTEM_PLUGIN_PATH"])
os.environ["ROS_DOMAIN_ID"] = env["ROS_DOMAIN_ID"]
logging=root/"fs/etc/logging"
logging.mkdir(parents=True,exist_ok=True)
logging.joinpath("logger_topics.txt").write_text("\n".join(k+" 0 0" for k in [
    "vehicle_attitude","vehicle_local_position","vehicle_status","actuator_motors","esc_status","vehicle_command",
    "vehicle_command_ack","neural_control","trajectory_setpoint","vehicle_local_position_setpoint",
    "vehicle_land_detected","vehicle_control_mode","vehicle_angular_velocity"])+"\n")
for p in [binary, world, Path(env["GZ_SIM_SERVER_CONFIG_PATH"])]:
    assert p.is_file(), p
# Refuse a new launch if this instance or any of its listen ports are already in use.
for port in (14580+instance,14280+instance,13030+instance,18570+instance):
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("0.0.0.0", port))
proc = []
def launch(name, *args):
    with (dest/(name+".log")).open("w") as log:
        p = subprocess.Popen(args, cwd=root, env=env, stdin=subprocess.DEVNULL,
                             stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    proc.append((name,p))
    return p
def c(module, *args, timeout=8):
    link = dest/("px4-"+module)
    if not link.exists():
        link.symlink_to(binary)
    cmd = [str(link),"--instance",str(instance),module,*args]
    cmd.pop(3)
    p = subprocess.run(cmd, env=env, cwd=root, capture_output=True, text=True, timeout=timeout)
    output = p.stdout+p.stderr
    with (dest/"commands.jsonl").open("a") as log:
        log.write(json.dumps(dict(argv=cmd, code=p.returncode, output=output))+"\n")
    if p.returncode:
        raise RuntimeError(output)
    return output
def poll(fn, seconds, detail):
    deadline = time.monotonic()+seconds
    while time.monotonic() < deadline:
        if any(p.poll() is not None for _,p in proc):
            raise RuntimeError("SITL process unexpectedly exited during "+detail)
        v=fn()
        if v:
            return v
        time.sleep(.15)
    raise TimeoutError(detail)
def field(s,k):
    m=re.search(rf"^\s*{k}:\s*(-?[\d.]+)", s,re.M)
    return float(m[1]) if m else None
stats = dict(instance=instance,seed=seed,classification="official MCNN x500 paired SITL", coeff=coeff, case=case)
did_arm = False
error = None
gcs_stop = threading.Event()
def loopback_gcs():
    conn=mavutil.mavlink_connection(f"udpout:127.0.0.1:{18570+instance}",source_system=255)
    try:
        while not gcs_stop.is_set():
            conn.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_GCS,mavutil.mavlink.MAV_AUTOPILOT_INVALID,0,0,0)
            gcs_stop.wait(.5)
    finally:
        conn.close()
gcs = threading.Thread(target=loopback_gcs,daemon=True)
xrce=checkout.parent.parent/"runtime/xrce-agent/bin/MicroXRCEAgent"
rclpy.init()
node=rclpy.create_node("mcnn_case_runner")
spub=node.create_publisher(TrajectorySetpoint,"/uav_7/fmu/in/trajectory_setpoint",10)
opub=node.create_publisher(OffboardControlMode,"/uav_7/fmu/in/offboard_control_mode",10)
state={"sender":False, "start":None,"route":None, "pose":(0.,0.,-2.)}
pubstop=threading.Event()
def publisher():
    with (dest/"reference.jsonl").open("w") as log:
        while not pubstop.is_set():
            stamp=node.get_clock().now().nanoseconds//1000
            mode=OffboardControlMode()
            mode.timestamp=stamp
            mode.position=not state.get("velocity_only",False)
            mode.velocity=state.get("velocity_only",False)
            opub.publish(mode)
            if state["sender"]:
                start, route=state["start"],state["route"]
                dt=0. if start is None else time.monotonic()-start
                x,y,z=state["pose"]
                vx,ax=0.,0.
                if route=="brake":
                    # Continuous position/velocity/acceleration path, 3 m total.
                    t=min(3.,max(0.,dt))
                    u=t/3.
                    x+=3*(10*u**3-15*u**4+6*u**5)
                    vx=30*u**2-60*u**3+30*u**4
                    ax=(60*u-180*u**2+120*u**3)/3.
                elif route=="move":
                    t=min(4.,max(0.,dt))
                    u=t/4.
                    x+=2*(10*u**3-15*u**4+6*u**5)
                    vx=(2./4.)*(30*u**2-60*u**3+30*u**4)
                    ax=(2./16.)*(60*u-180*u**2+120*u**3)
                msg=TrajectorySetpoint()
                msg.timestamp=stamp
                msg.position=[float("nan")]*3 if state.get("velocity_only",False) else [x,y,z]
                msg.velocity=[vx,0.,0.]
                msg.acceleration=[ax,0.,0.]
                msg.jerk=[float("nan")]*3
                msg.yaw=float("nan")
                msg.yawspeed=float("nan")
                spub.publish(msg)
                log.write(json.dumps(dict(host_ns=time.monotonic_ns(), sender_timestamp_us=stamp,x=x,y=y,z=z,vx=vx,ax=ax))+"\n")
            pubstop.wait(.015)
pubthread=threading.Thread(target=publisher,daemon=True)
def event(name):
    t=int(field(c("listener","vehicle_status"),"timestamp"))
    stats.setdefault("events",{})[name]=dict(native_lower_bound_us=t,host_ns=time.monotonic_ns())
def nav(n):
    return field(c("listener","vehicle_status"),"nav_state")==n
def takeover(label):
    event(label)
    c("commander","mode","ext1")
    poll(lambda:nav(23),3,"MCNN mode active")
def offboard():
    state["sender"]=True
    time.sleep(1.1)
    c("commander","mode","offboard")
    poll(lambda:nav(14),4,"classical OFFBOARD mode")
relay_prefix=dest/"relay"
try:
    launch("agent",str(xrce),"udp4","-p","18971")
    launch("gazebo","gz","sim","-r","-s","-v","3","--seed",str(seed),str(world))
    poll(lambda:"/world/default/clock" in subprocess.check_output(["gz","topic","-l"],env=env,text=True,timeout=4),15,"Gazebo clock")
    launch("px4", str(binary),"-d","-i",str(instance),"-w",str(root),str(root/"etc"))
    def ready():
        t=(dest/"px4.log").read_text()
        return "Mode registration successful" in t or "mode registration successful" in t
    launch("relay",str(bundle/"sim-motor-relay"),"x500_"+str(instance),str(relay_prefix),
           "90000" if case=="t4_hold" else "0")
    gcs.start()
    pubthread.start()
    poll(ready, 35, "MCNN stock mode registration")
    stats["module_status"] = c("mc_nn_control","status")
    stats["vehicle_status_before"] = c("listener","vehicle_status")
    for p in ("MC_NN_MANL_CTRL","MC_NN_THRST_COEF","MC_NN_MIN_RPM","MC_NN_MAX_RPM","THR_MDL_FAC"):
        stats[p] = c("param","show",p)
    def zpos():
        s=c("listener","vehicle_local_position")
        return field(s,"z")
    ready_text=c("listener","vehicle_local_position")
    seconds=time.monotonic()+25
    while not ("xy_valid: true" in ready_text.lower() and "z_valid: true" in ready_text.lower()):
        if time.monotonic()>seconds:
            raise TimeoutError("Estimator readiness")
        time.sleep(.4); ready_text=c("listener","vehicle_local_position")
    poll(lambda: "pre_flight_checks_pass: true" in c("listener","vehicle_status").lower(),20,"stock preflight health")
    poll(lambda: relay_prefix.with_suffix(".ready").is_file(),10,"simulator motor trace relay")
    poll(lambda:spub.get_subscription_count()>0,12,"loopback trajectory subscriber")
    for _ in range(3):
        time.sleep(1.4)
        poll(lambda: "pre_flight_checks_pass: true" in c("listener","vehicle_status").lower(),12,"settled stock preflight health")
        c("commander","arm")
        try:
            poll(lambda:field(c("listener","vehicle_status"),"arming_state")==2,3,"classic arming")
            break
        except TimeoutError:
            pass
    else:
        raise RuntimeError("stock arming remained unavailable")
    did_arm=True
    c("commander","takeoff")
    poll(lambda:(zpos() or 0)<-1.65,15,"classic takeoff")
    time.sleep(3.0)
    b=c("listener","vehicle_local_position")
    status=c("listener","vehicle_status")
    if field(status,"system_id")!=instance+1 or abs(field(b,"z")+2)>0.35 or "mode id: 23" not in stats["module_status"]:
        raise RuntimeError("unexpected simulator identity, height or registration")
    pose=tuple(field(b,k) for k in ("x","y","z"))
    state["pose"]=pose
    offboard()
    if case.startswith("t3"):
        takeover("first_entry")
        time.sleep(2.0)
        state["velocity_only"]=True
        offboard()
        state.update(start=time.monotonic(),route="move")
        time.sleep(6.0)
        if case=="t3_stale":
            state["sender"]=False
            time.sleep(.10)
        else:
            settled=c("listener","vehicle_local_position")
            state.update(pose=tuple(field(settled,k) for k in ("x","y","z")),route=None,velocity_only=False)
            time.sleep(.10)
        takeover("study")
    elif case.startswith("t1") or case.startswith("t4"):
        state.update(start=time.monotonic(),route="brake")
        phase=1.55 if case.startswith("t1") else 1.2
        while time.monotonic()-state["start"]<phase:
            time.sleep(.005)
        if case.startswith("t4"):
            relay_prefix.with_suffix(".trigger").touch()
            poll(lambda:relay_prefix.with_suffix(".ack").is_file(),.2,"relay trigger")
        if case=="t1_c":
            event("study")
            c("commander","mode","offboard")
        else:
            takeover("study")
        if case=="t4_release":
            relay_prefix.with_suffix(".release").touch()
    else:
        before=c("listener","vehicle_local_position")
        state["pose"]=tuple(field(before,k) for k in ("x","y","z"))
        time.sleep(.10)
        if case=="t2_n":
            takeover("study")
        else:
            event("study")
            c("commander","mode","offboard")
    stats["switch_entry"] = b
    anchor=time.monotonic()
    while time.monotonic()-anchor<2.4:
        pos=c("listener","vehicle_local_position")
        z=field(pos,"z")
        vx=field(pos,"vx")
        if z is None or z>-1.15 or z<-3.0 or (vx is not None and abs(vx)>3.5):
            stats["experimental_stop"]=pos
            break
        time.sleep(.12)
    state["sender"]=False
    c("commander","land")
    poll(lambda:field(c("listener","vehicle_status"),"arming_state")==1,30,"auto-disarm after landing")
    did_arm=False
    stats["landed_status"] = c("listener","vehicle_land_detected")
except Exception as exc:
    error = str(exc)
    if did_arm:
        try:
            c("commander","land")
            poll(lambda:field(c("listener","vehicle_status"),"arming_state")==1,25,"cleanup landing")
        except Exception as land_exc:
            stats["cleanup_exception"] = str(land_exc)
finally:
    pubstop.set()
    if pubthread.is_alive(): pubthread.join(2)
    gcs_stop.set()
    if gcs.is_alive(): gcs.join(2)
    for name,p in reversed(proc):
        if p.poll() is None:
            os.killpg(p.pid,signal.SIGINT)
            try:
                p.wait(6)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid,signal.SIGTERM)
                p.wait(5)
        stats.setdefault("process_exit",{})[name]=p.returncode
    stats["error"]=error
    (dest/"baseline.json").write_text(json.dumps(stats,indent=2)+"\n")
logs=list(root.rglob("*.ulg"))
if not error:
    assert len(logs)==1,logs
    u=ULog(str(logs[0]))
    d=u.get_dataset("vehicle_local_position").data
    # Only settled part: skip first 1.5 s from reaching 1.65 m, follow for 2 s.
    t0=int(d["timestamp"][np.flatnonzero(d["z"]<-1.65)[0]])+1_500_000
    mask=(d["timestamp"]>=t0)&(d["timestamp"]<t0+2_000_000)
    assert mask.sum()>10
    esc=u.get_dataset("esc_status").data
    em=(esc["timestamp"]>=t0)&(esc["timestamp"]<t0+2_000_000)
    esc_command=[float(np.median(esc[f"esc[{i}].esc_rpm"][em])) for i in range(4)]
    st=u.get_dataset("vehicle_status").data
    stats.update(
        ulog=str(logs[0]), ulog_sha256=hashlib.file_digest(logs[0].open("rb"),"sha256").hexdigest(),
        binary_sha256=hashlib.file_digest(binary.open("rb"),"sha256").hexdigest(),
        ulog_dropouts=len(u.dropouts), hover_t0_us=t0, hover_samples=int(mask.sum()),
        median_height_m=float(-np.median(d["z"][mask])),
        median_horizontal_speed_m_s=float(np.median(np.hypot(d["vx"][mask],d["vy"][mask]))),
        median_bridge_echo_rad_s=esc_command,
        nav_states=sorted(int(s) for s in set(st["nav_state"])),
        final_arming_state=int(st["arming_state"][-1]),
        neural_native_times_us=sorted(set(int(t) for t in st["nav_state_timestamp"][st["nav_state"]==23])),
        ulog_params={k:v for k,v in u.initial_parameters.items() if k.startswith(("MC_NN_", "SIM_GZ_EC_","THR_MDL_"))}
    )
    (dest/"baseline.json").write_text(json.dumps(stats,indent=2)+"\n")
    print(json.dumps(stats,indent=2))
else:
    raise RuntimeError(error)

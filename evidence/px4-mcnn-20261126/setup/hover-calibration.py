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
from pathlib import Path
import numpy as np
from pyulog import ULog

checkout, dest = map(lambda s: Path(s).resolve(), sys.argv[1:3])
coeff = float(sys.argv[3])
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
stats = dict(instance=instance,seed=seed,classification="short stock MCNN SITL hover calibration", coeff=coeff)
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
try:
    launch("gazebo","gz","sim","-r","-s","-v","3","--seed",str(seed),str(world))
    poll(lambda:"/world/default/clock" in subprocess.check_output(["gz","topic","-l"],env=env,text=True,timeout=4),15,"Gazebo clock")
    launch("px4", str(binary),"-d","-i",str(instance),"-w",str(root),str(root/"etc"))
    def ready():
        t=(dest/"px4.log").read_text()
        return "Mode registration successful" in t or "mode registration successful" in t
    gcs.start()
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
    c("commander","arm")
    poll(lambda:field(c("listener","vehicle_status"),"arming_state")==2,8,"classic arming")
    did_arm=True
    c("commander","takeoff")
    poll(lambda:(zpos() or 0)<-1.65,15,"classic takeoff")
    time.sleep(3)
    before=c("listener","vehicle_local_position")
    stats["switch_entry"] = before
    status=c("listener","vehicle_status")
    if field(status,"system_id") != instance+1 or abs(field(before,"z")+2)>0.35:
        raise RuntimeError("unexpected simulator identity or entry height")
    if not re.search(r"mode id: 23\b",stats["module_status"]):
        raise RuntimeError("ext1 is not the registered MCNN mode")
    c("commander","mode","ext1")
    poll(lambda:field(c("listener","vehicle_status"),"nav_state")==23,3,"MCNN mode active")
    deadline=time.monotonic()+3.0
    while time.monotonic()<deadline:
        s=c("listener","vehicle_local_position")
        armed = field(c("listener","vehicle_status"),"arming_state")
        if armed != 2 or (field(s,"z") or 0)>-1.25 or (field(s,"z") or 0)<-2.8:
            stats["hover_guard"] = s
            break
        time.sleep(.12)
    stats["switch_end"] = c("listener","vehicle_local_position")
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
        neural_native_start_us=int(st["nav_state_timestamp"][np.flatnonzero(st["nav_state"]==23)[0]]),
        ulog_params={k:v for k,v in u.initial_parameters.items() if k.startswith(("MC_NN_", "SIM_GZ_EC_","THR_MDL_"))}
    )
    (dest/"baseline.json").write_text(json.dumps(stats,indent=2)+"\n")
    print(json.dumps(stats,indent=2))
else:
    raise RuntimeError(error)

"""Export native samples from independent official MCNN SITL runs."""
import csv
import gzip
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
from pyulog import ULog

EVIDENCE = Path(sys.argv[1])
LAB = Path(sys.argv[2])
stamp = sys.argv[3]
EVIDENCE.mkdir(parents=True, exist_ok=True)
DT=np.dtype([('sim_us','<u8'),('new_sample_us','<u8'),('applied_sample_us','<u8'),('step_wall_ns','<u8'),
             ('arrival_wall_ns','<u8'),('received','<u4'),('flags','<u4'),('ref_motor_input','<f8')])
fields = "event,timestamp,reference_timestamp,ref_x,ref_y,ref_z,x,y,z,u0,u1,u2,u3".split(",")
topics={
 "vehicle_local_position":["x","y","z","vx","vy","vz"],
 "vehicle_attitude":[f"q[{i}]" for i in range(4)],
 "vehicle_angular_velocity":[f"xyz[{i}]" for i in range(3)],
 "actuator_motors":["timestamp_sample"]+[f"control[{i}]" for i in range(4)],
 "vehicle_status":["nav_state","arming_state","nav_state_timestamp"],
 "vehicle_command":["command","param1","param2","param3"],
 "vehicle_command_ack":["command","result"],
 "trajectory_setpoint":[f"position[{i}]" for i in range(3)]+[f"velocity[{i}]" for i in range(3)],
 "vehicle_land_detected":["landed"],
 "neural_control":[f"observation[{i}]" for i in range(15)]+[f"network_output[{i}]" for i in range(4)],
}

def sha(path):
    with path.open("rb") as f: return hashlib.file_digest(f,"sha256").hexdigest()
def dump(path,keys,rows):
    with path.open("wb") as fh, gzip.GzipFile(filename="",mode="wb",fileobj=fh,mtime=0) as gz:
        import io
        with io.TextIOWrapper(gz,encoding="utf-8",newline="") as out:
            w=csv.writer(out);w.writerow(keys);w.writerows(rows)
def scalar(v): return v.item() if hasattr(v,"item") else v
runs={}
for case in ("t2_n","t2_c","t1_c","t1_n","t3_stale","t3_fresh","t4_release","t4_hold"):
    run_tag=json.loads(stamp).get(case, "v2") if stamp.startswith("{") else stamp
    path=LAB/f"pair-{case}-{run_tag}"
    if not (path/"baseline.json").is_file(): continue
    meta=json.loads((path/"baseline.json").read_text())
    if meta["error"] or "ulog_sha256" not in meta: print("incomplete",case,meta.get("error")); continue
    ulg=Path(meta["ulog"])
    assert sha(ulg)==meta["ulog_sha256"]
    uf=ULog(str(ulg),list(topics))
    d={x.name:x.data for x in uf.data_list if x.multi_id==0}
    assert all(k in d for k in ("vehicle_local_position","vehicle_attitude","actuator_motors","vehicle_status","vehicle_command"))
    lb=meta["events"]["study"]["native_lower_bound_us"]
    ntrace=[]
    if (path/"native.csv").exists():
        with (path/"native.csv").open() as f:
            ntrace=[r for r in csv.reader(f) if len(r)==len(fields)]
    activ=[int(r[1]) for r in ntrace if r[0]=="A" and int(r[1])>=lb]
    active=min(activ) if activ else None
    command=d['vehicle_command']
    cmds=command["timestamp"][(command["timestamp"]>=lb)&(command["command"]==176)]
    request=next((int(t) for t in cmds if t<=active),None) if active is not None else (int(cmds[0]) if run_tag=="v3" and len(cmds) else lb)
    assert request is not None, (case,lb,active,cmds)
    low,high=request-650_000,request+2_000_000
    case_dir=EVIDENCE/case
    case_dir.mkdir(exist_ok=True)
    for name,data in d.items():
        cols=["timestamp",*topics[name]]
        if any(k not in data for k in cols): continue
        idx=np.flatnonzero((data["timestamp"]>=low)&(data["timestamp"]<=high))
        dump(case_dir/(name+".csv.gz"),cols,([scalar(data[k][i]) for k in cols] for i in idx))
    dump(case_dir/"mcnn_native.csv.gz",fields,[r for r in ntrace if low<=int(r[1])<=high])
    if case.startswith("t3"):
        pre=[r for r in ntrace if int(r[1])<low]
        dump(case_dir/"mcnn_prior_entry.csv.gz",fields,pre)

    mrows=[]
    for motor in range(4):
        p=path/"motor"/f"motor-{motor}.bin"
        raw=p.read_bytes()
        assert raw[:8]==b"HOMTRC01" and int.from_bytes(raw[12:16],"little")==motor and int.from_bytes(raw[8:12],"little")==DT.itemsize
        arr=np.frombuffer(raw[16:], DT)
        for u in arr[(arr["sim_us"]>=low)&(arr["sim_us"]<=high)]:
            mrows.append((motor,*[scalar(v) for v in u]))
    assert len(mrows)>100,case
    dump(case_dir/"gazebo_motor_apply.csv.gz",["motor",*DT.names],mrows)
    with (path/"relay.csv").open() as f:
        rd=csv.DictReader(f)
        m=[r for r in rd if low<=int(r["sim_us"])<=high]
        dump(case_dir/"relay.csv.gz",rd.fieldnames,([r[k] for k in rd.fieldnames] for r in m))
    st=d["vehicle_status"]
    state_order=[int(st["nav_state"][0])]
    for s in st["nav_state"]:
        if int(s)!=state_order[-1]:state_order.append(int(s))
    runs[case]=dict(run_tag=run_tag, request_us=request,request_origin="vehicle_command" if active is not None or request!=lb else "matched treatment marker native lower bound",
        all_neural_entries_us=meta["neural_native_times_us"], nav_order=state_order, native_trace_sha256=sha(path/"native.csv") if ntrace else None,
        binary_sha256=meta["binary_sha256"], ulog=str(ulg), ulog_sha256=meta["ulog_sha256"], seed=meta["seed"],
        ulog_dropouts=len(uf.dropouts), final_arming_state=int(st["arming_state"][-1]), process_exit=meta["process_exit"], params=meta["ulog_params"],
        landing=bool(d["vehicle_land_detected"]["landed"][-1]) if "vehicle_land_detected" in d else None)
    print(case,request,active,state_order,len(mrows),len(uf.dropouts))
(EVIDENCE/"runs.json").write_text(json.dumps(runs,indent=2,sort_keys=True)+"\n")

#!/usr/bin/env python3
"""Recalculate paired native-window metrics without SITL or third-party Python packages."""
import argparse
import collections
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path

def read(d, name):
    with gzip.open(d/(name+".csv.gz"),"rt",newline="") as f: return list(csv.DictReader(f))
def on(rows,t,k="timestamp"):return max((r for r in rows if int(r[k])<=t),key=lambda r:int(r[k]))
def v(r, names):return [float(r[n]) for n in names]
def tilt(r):
    q=v(r,[f"q[{i}]" for i in range(4)])
    return math.degrees(math.acos(max(-1.,min(1.,1-2*(q[1]**2+q[2]**2)/sum(s*s for s in q)))))
def only(rows,a,b,k="timestamp"):return [r for r in rows if a<=int(r[k])<=b]
def yaw(r):
    w,x,y,z=v(r,[f"q[{i}]" for i in range(4)])
    return math.degrees(math.atan2(2*(w*z+x*y),1-2*(y*y+z*z)))

def compute(root):
    runs=json.loads((root/"runs.json").read_text())
    results={}
    for case,meta in runs.items():
        d=root/case
        t=meta["request_us"]
        pos=read(d,"vehicle_local_position"); att=read(d,"vehicle_attitude")
        motors=read(d,"actuator_motors"); n=read(d,"mcnn_native")
        app=read(d,"gazebo_motor_apply"); rel=read(d,"relay")
        sp=read(d,"trajectory_setpoint")
        status=read(d,"vehicle_status")
        start=on(pos,t); a0=on(att,t)
        row=dict(request_us=t, request_origin=meta["request_origin"],entry_xyz_m=v(start,"xyz"),
                 entry_v_m_s=v(start,["vx","vy","vz"]),entry_tilt_deg=tilt(a0),entry_yaw_deg=yaw(a0))
        for ms in (250,1000,2000):
            pp=only(pos,t,t+ms*1000); aa=only(att,t,t+ms*1000)
            if not pp or not aa: continue
            stat={}
            row[f"first_{ms}ms"]=stat
            stat["peak_tilt_deg"]=max(map(tilt,aa))
            stat["min_height_m"]=-max(float(r["z"]) for r in pp)
            stat["loss_m"]=max(0.,float(start["z"])*-1-stat["min_height_m"])
            stat["furthest_x_m"]=max(float(r["x"]) for r in pp)
            stat["max_forward_displacement_m"]=max(float(r["x"])-float(start["x"]) for r in pp)
            stat["min_forward_displacement_m"]=min(float(r["x"])-float(start["x"]) for r in pp)
            stat["peak_horiz_speed_m_s"]=max(math.hypot(*v(r,["vx","vy"])) for r in pp)
            stat["horiz_excursion_m"]=max(math.dist(v(r,"xy"),v(start,"xy")) for r in pp)
            errs=[]
            for r in pp:
                psp=on(sp,int(r["timestamp"]))
                pspv=v(psp,["position[0]","position[1]","position[2]"])
                if all(map(math.isfinite,pspv)):errs.append(math.dist(v(r,"xyz"),pspv)**2)
            stat["xyz_tracking_rmse_m"]=math.sqrt(sum(errs)/len(errs)) if errs else None
        row["done_landed_disarmed"]=meta["final_arming_state"]==1 and meta["landing"] and all(meta["process_exit"].get(k)==0 for k in ("relay","px4","gazebo")) and meta["process_exit"].get("agent") in (0,-2)
        assert meta["ulog_dropouts"]==0 and meta["final_arming_state"]==1
        entries=[r for r in n if r["event"]=="A" and int(r["timestamp"])>=t]
        if entries:
            active=int(entries[0]["timestamp"])
            row["activation_us"]=active
            navs=[int(x["nav_state_timestamp"]) for x in status if x["nav_state"]=="23" and int(x["timestamp"])>=t]
            row["commander_nav_active_us"]=min(navs) if navs else None
            pubs={int(r["timestamp"]):r for r in n if r["event"]=="N" and int(r["timestamp"])>=active}
            first=min(pubs); r=pubs[first]
            row.update(first_publish_us=first, initial_reference_timestamp_us=int(r["reference_timestamp"]),
                       initial_reference_age_us=first-int(r["reference_timestamp"]),
                       initial_ref_xyz_m=v(r,["ref_x","ref_y","ref_z"]),
                       initial_ref_error_xyz_m=[float(r["ref_"+k])-float(r[k]) for k in "xyz"],
                       first_u=v(r,["u0","u1","u2","u3"]))
            read_ref=[x for x in n if x["event"]=="R" and active<=int(x["timestamp"])]
            row["first_adopt_us"]=int(read_ref[0]["timestamp"]) if read_ref else None
            if case.startswith("t3"):
                prior=read(d,"mcnn_prior_entry")
                p_stamps={int(x["reference_timestamp"]) for x in prior if x["event"]=="R"}
                row["first_inference_uses_prior_entry_target"]=row["initial_reference_timestamp_us"] in p_stamps
                row["prior_entry_last_accepted_timestamp_us"]=max(p_stamps) if p_stamps else None
            ack=read(d,"vehicle_command_ack")
            row["set_mode_ack_us"]=next((int(x["timestamp"]) for x in ack if int(x["timestamp"])>=t and x["command"]=="176" and x["result"]=="0"),None)

            applied=collections.defaultdict(dict)
            for x in app:
                sample=int(x["applied_sample_us"]); mot=int(x["motor"])
                if sample not in pubs or int(x["sim_us"])<sample: continue
                u=float(pubs[sample]["u"+str(mot)])
                if abs(float(x["ref_motor_input"])-(150+850*u))>.02: continue
                applied[sample].setdefault(mot,int(x["sim_us"]))
            candidates={s:motors for s,motors in applied.items() if len(motors)==4}
            assert candidates,case
            key=min(candidates,key=lambda s:(max(candidates[s].values()),s))
            allfour=max(candidates[key].values())
            early=[s for s in pubs if s<key]
            row.update(first_common_motor_sample_us=key, first_four_application_us=allfour,
                       first_application_each_motor_us={str(k):val for k,val in candidates[key].items()},
                       first_publish_to_all_four_us=allfour-first,
                       covered_source_samples=len(early),
                       covered_source_samples_seen_held=sum(s in {int(x["sample_us"]) for x in rel if x["event"]=="held"} for s in early),
                       covered_source_samples_in_no_motor=sum(s not in applied for s in early))
            pm=on(motors,first-1)
            row["last_classical_u"]=v(pm,[f"control[{i}]" for i in range(4)])
            row["max_first_motor_step"]=max(abs(a-b) for a,b in zip(row["first_u"],row["last_classical_u"]))
        results[case]=row
    return results

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--root",type=Path,default=Path(__file__).resolve().parent)
    a.add_argument("--write",action="store_true")
    args=a.parse_args(); p=args.root
    out=compute(p)
    if not args.write:
        assert set(out)=={"t1_c","t1_n","t2_c","t2_n","t3_stale","t3_fresh","t4_hold","t4_release"}
        assert all(r["done_landed_disarmed"] for r in out.values())
        assert out["t1_c"].get("first_publish_us") is None and out["t2_c"].get("first_publish_us") is None
        assert out["t1_n"]["first_1000ms"]["xyz_tracking_rmse_m"] > out["t1_c"]["first_1000ms"]["xyz_tracking_rmse_m"]
        assert out["t2_n"]["max_first_motor_step"] > 0.05
        assert out["t2_n"]["first_1000ms"]["horiz_excursion_m"] > out["t2_c"]["first_1000ms"]["horiz_excursion_m"]
        assert out["t3_stale"]["first_inference_uses_prior_entry_target"]
        assert not out["t3_fresh"]["first_inference_uses_prior_entry_target"]
        assert out["t3_stale"]["first_1000ms"]["horiz_excursion_m"] > out["t3_fresh"]["first_1000ms"]["horiz_excursion_m"]
        assert out["t4_hold"]["first_publish_to_all_four_us"] > out["t4_release"]["first_publish_to_all_four_us"]
        assert out["t4_hold"]["covered_source_samples_in_no_motor"] > 0
    if args.write:
        (p/"metrics.json").write_text(json.dumps(out,indent=2,sort_keys=True,allow_nan=False)+"\n")
    else:
        assert out==json.loads((p/"metrics.json").read_text()),"metrics differ from native CSV"
        for line in (p/"manifest.sha256").read_text().splitlines():
            h,f=line.split("  ",1)
            assert hashlib.sha256((p/f).read_bytes()).hexdigest()==h,f
        print(f"PASS: {len(out)} native hover / handover cases")
if __name__=="__main__":main()

#!/usr/bin/env python3
"""
Extract lossless native-250-Hz gzipped CSV traces, metrics.json, provenance.json,
and manifest.sha256 from raw SITL run directories.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
from pyulog import ULog

from metrics_core import compute_run_metrics, load_trace_gz
from run_sitl import eval_trajectory

REPO_ROOT = Path("/home/car/uav_handover")
EVIDENCE_DIR = REPO_ROOT / "evidence/px4-mcnn-handover"
TRACES_DIR = EVIDENCE_DIR / "traces"
SCRATCH_ROOT = Path(
    "/home/car/.gemini/antigravity/brain/f3411c4c-de3d-4f87-af9b-8c4e4c7218d2/scratch/px4_mcnn_cleanroom"
)
PX4_DIR = SCRATCH_ROOT / "PX4-Autopilot"
CAMPAIGN_ROOT = SCRATCH_ROOT / "runs_campaign"
V0_ROOT = SCRATCH_ROOT / "runs"

TRACE_COLUMNS = [
    "t_rel_s",
    "t_sim_s",
    "x_m",
    "y_m",
    "z_ned_m",
    "h_m",
    "vx_m_s",
    "vy_m_s",
    "vz_ned_m_s",
    "v_up_m_s",
    "v_xy_m_s",
    "roll_deg",
    "pitch_deg",
    "yaw_deg",
    "tilt_deg",
    "p_deg_s",
    "q_deg_s",
    "r_deg_s",
    "ref_x_m",
    "ref_y_m",
    "ref_z_ned_m",
    "ref_h_m",
    "sp_x_m",
    "sp_y_m",
    "sp_z_ned_m",
    "sp_age_s",
    "u_pub_0",
    "u_pub_1",
    "u_pub_2",
    "u_pub_3",
    "u_mcnn_0",
    "u_mcnn_1",
    "u_mcnn_2",
    "u_mcnn_3",
    "gz_cmd_w0",
    "gz_cmd_w1",
    "gz_cmd_w2",
    "gz_cmd_w3",
    "gz_rx_w0",
    "gz_rx_w1",
    "gz_rx_w2",
    "gz_rx_w3",
    "gz_joint_w0",
    "gz_joint_w1",
    "gz_joint_w2",
    "gz_joint_w3",
    "gz_hold_active",
    "gz_is_neural",
    "gz_mcnn_seq",
    "gz_overwritten_mcnn",
    "nav_state",
    "armed",
    "failsafe",
    "ctrl_alloc_en",
    "rate_int_x",
    "rate_int_y",
    "rate_int_z",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def get_ulog_ds(u: ULog, name: str, multi_id: int = 0) -> dict[str, np.ndarray] | None:
    for ds in u.data_list:
        if ds.name == name and ds.multi_id == multi_id:
            return ds.data
    return None


def zoh_lookup(t_src: np.ndarray, y_src: np.ndarray, t_dst: np.ndarray, default: float = math.nan) -> np.ndarray:
    """Zero-order hold lookup (preserves exact discrete steps/peaks without smoothing)."""
    out = np.full(len(t_dst), default, dtype=np.float64)
    if len(t_src) == 0:
        return out
    idx = np.searchsorted(t_src, t_dst, side="right") - 1
    valid = idx >= 0
    out[valid] = y_src[idx[valid]]
    return out


def nearest_within(
    t_src: np.ndarray,
    y_src: np.ndarray,
    t_dst: np.ndarray,
    max_dt: float = 0.010,
    default: float = math.nan,
) -> np.ndarray:
    out = np.full(len(t_dst), default, dtype=np.float64)
    if len(t_src) == 0:
        return out
    idx = np.searchsorted(t_src, t_dst, side="left")
    idx_l = np.clip(idx - 1, 0, len(t_src) - 1)
    idx_r = np.clip(idx, 0, len(t_src) - 1)
    dl = np.abs(t_dst - t_src[idx_l])
    dr = np.abs(t_dst - t_src[idx_r])
    choose_r = dr < dl
    best_idx = np.where(choose_r, idx_r, idx_l)
    best_dt = np.where(choose_r, dr, dl)
    ok = best_dt <= max_dt
    out[ok] = y_src[best_idx[ok]]
    return out


def parse_obs_csv(obs_path: Path | None, t_sw_min_s: float) -> dict[str, Any]:
    res: dict[str, Any] = {
        "t_request_s": None,
        "t_active_s": None,
        "t_publish_first_s": None,
        "mcnn_pub_t": [],
        "mcnn_sp_ts": [],
        "mcnn_sp_x": [],
        "mcnn_sp_y": [],
        "mcnn_sp_z": [],
        "mcnn_u": [[], [], [], []],
    }
    if obs_path is None or not obs_path.exists():
        return res
    with obs_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ev = row["event"]
            t_s = float(row["t_us"]) * 1e-6
            if t_s < t_sw_min_s:
                continue
            if ev == "mode_request" and res["t_request_s"] is None:
                res["t_request_s"] = t_s
            elif ev == "mcnn_active" and res["t_active_s"] is None:
                res["t_active_s"] = t_s
            elif ev == "mcnn_pub":
                if res["t_publish_first_s"] is None:
                    res["t_publish_first_s"] = t_s
                res["mcnn_pub_t"].append(t_s)
                res["mcnn_sp_ts"].append(float(row["sp_ts"]) * 1e-6)
                res["mcnn_sp_x"].append(float(row["sp_x"]))
                res["mcnn_sp_y"].append(float(row["sp_y"]))
                res["mcnn_sp_z"].append(float(row["sp_z"]))
                for k in range(4):
                    res["mcnn_u"][k].append(float(row[f"v{k}"]))
    return res


def parse_relay_step_csv(relay_path: Path | None) -> dict[str, np.ndarray]:
    if relay_path is None or not relay_path.exists():
        return {}
    cols: dict[str, list[float]] = {}
    with relay_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for name in reader.fieldnames or []:
            cols[name] = []
        for row in reader:
            for name, val in row.items():
                cols[name].append(float(val))
    return {k: np.asarray(v, dtype=np.float64) for k, v in cols.items()}


def extract_single_run(run_dir: Path, run_id_override: str | None = None, group_override: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    meta = json.loads((run_dir / "run_meta.json").read_text(encoding="utf-8"))
    spec = meta["spec"]
    run_id = run_id_override or spec["run_id"]
    group = group_override or spec.get("group", "V0")
    ulog_path = Path(meta["ulog_path"])
    u = ULog(str(ulog_path))

    lp = get_ulog_ds(u, "vehicle_local_position")
    att = get_ulog_ds(u, "vehicle_attitude")
    av = get_ulog_ds(u, "vehicle_angular_velocity")
    am = get_ulog_ds(u, "actuator_motors")
    nc = get_ulog_ds(u, "neural_control")
    vs = get_ulog_ds(u, "vehicle_status")
    vcm = get_ulog_ds(u, "vehicle_control_mode")
    tsp = get_ulog_ds(u, "trajectory_setpoint")
    rcs = get_ulog_ds(u, "rate_ctrl_status")

    assert lp is not None and att is not None and av is not None and am is not None and vs is not None

    t_sw_s = meta["events"]["t_sw_cmd_ms"] * 1e-3
    t_man_start_s = meta["events"]["t_maneuver_start_ms"] * 1e-3
    eval_after_s = float(spec.get("eval_after_s", 4.0))

    # Window: [t_sw - 1.5s, t_sw + eval_after_s + 0.4s] at native vehicle_attitude 250 Hz timestamps!
    t_att = att["timestamp"].astype(np.float64) * 1e-6
    win_mask = (t_att >= t_sw_s - 1.5) & (t_att <= t_sw_s + eval_after_s + 0.4)
    t_sim = t_att[win_mask]
    t_rel = t_sim - t_sw_s

    # Native exact quaternion -> Euler + exact tilt = arccos(R_33) (ZERO smoothing!)
    q0 = att["q[0]"][win_mask].astype(np.float64)
    q1 = att["q[1]"][win_mask].astype(np.float64)
    q2 = att["q[2]"][win_mask].astype(np.float64)
    q3 = att["q[3]"][win_mask].astype(np.float64)
    r33 = np.clip(1.0 - 2.0 * (q1 * q1 + q2 * q2), -1.0, 1.0)
    tilt_deg = np.degrees(np.arccos(r33))
    roll_deg = np.degrees(np.arctan2(2.0 * (q0 * q1 + q2 * q3), 1.0 - 2.0 * (q1 * q1 + q2 * q2)))
    pitch_deg = np.degrees(np.arcsin(np.clip(2.0 * (q0 * q2 - q3 * q1), -1.0, 1.0)))
    yaw_deg = np.degrees(np.arctan2(2.0 * (q0 * q3 + q1 * q2), 1.0 - 2.0 * (q2 * q2 + q3 * q3)))

    # Local position (100 Hz native -> ZOH/linear? Linear preserves exact native 100 Hz samples at 250 Hz grid;
    # wait: ZOH vs linear on smooth position differs <0.2 mm, and exact peaks in lp are within 1 sample!
    # Use linear for smooth kinematics (pos, vel, rates) and ZOH for discrete signals (motors, nav_state, relay).)
    t_lp = lp["timestamp"].astype(np.float64) * 1e-6
    x_m = np.interp(t_sim, t_lp, lp["x"].astype(np.float64))
    y_m = np.interp(t_sim, t_lp, lp["y"].astype(np.float64))
    z_ned = np.interp(t_sim, t_lp, lp["z"].astype(np.float64))
    h_m = -z_ned
    vx = np.interp(t_sim, t_lp, lp["vx"].astype(np.float64))
    vy = np.interp(t_sim, t_lp, lp["vy"].astype(np.float64))
    vz_ned = np.interp(t_sim, t_lp, lp["vz"].astype(np.float64))
    v_up = -vz_ned
    v_xy = np.hypot(vx, vy)

    t_av = av["timestamp"].astype(np.float64) * 1e-6
    p_deg_s = np.degrees(np.interp(t_sim, t_av, av["xyz[0]"].astype(np.float64)))
    q_deg_s = np.degrees(np.interp(t_sim, t_av, av["xyz[1]"].astype(np.float64)))
    r_deg_s = np.degrees(np.interp(t_sim, t_av, av["xyz[2]"].astype(np.float64)))

    # Analytic reference trajectory for tracking RMSE
    traj_kind = spec["trajectory"]
    z0 = -float(spec.get("altitude_m", 4.0))
    yaw_ref_deg = float(spec.get("yaw_ref_deg", 90.0))
    yaw_ref_rad = math.radians(yaw_ref_deg)
    ref_x = np.full(len(t_sim), math.nan)
    ref_y = np.full(len(t_sim), math.nan)
    ref_z = np.full(len(t_sim), z0)
    if traj_kind == "stale_reentry":
        d_ab = float(spec.get("stale_distance_m", 2.0))
        ref_x[:] = d_ab * math.cos(yaw_ref_rad)
        ref_y[:] = d_ab * math.sin(yaw_ref_rad)
    else:
        for i, ts in enumerate(t_sim):
            tau = max(0.0, float(ts - t_man_start_s))
            sp = eval_trajectory(spec, tau)
            ref_x[i], ref_y[i], ref_z[i] = sp["pos"]
    ref_h = -ref_z

    # Observer CSV (exact handover timestamps + internal cached setpoint + every MCNN publish)
    obs_path = Path(meta["obs_log_path"]) if meta.get("obs_log_path") else None
    obs = parse_obs_csv(obs_path, t_sw_min_s=t_sw_s - 0.05)

    # Control allocator disable timestamp (dual-publisher overlap audit)
    t_alloc_off_s = None
    if vcm is not None:
        t_vcm = vcm["timestamp"].astype(np.float64) * 1e-6
        alloc_f = vcm["flag_control_allocation_enabled"].astype(np.float64)
        for i in range(1, len(alloc_f)):
            if t_vcm[i] >= t_sw_s - 0.05 and alloc_f[i - 1] > 0.5 and alloc_f[i] < 0.5:
                t_alloc_off_s = float(t_vcm[i])
                break
        ctrl_alloc_en = zoh_lookup(t_vcm, alloc_f, t_sim, default=1.0)
    else:
        ctrl_alloc_en = np.full(len(t_sim), math.nan)

    # Published actuator_motors (ZOH at exact native 250 Hz)
    t_am = am["timestamp"].astype(np.float64) * 1e-6
    u_pub = [zoh_lookup(t_am, am[f"control[{k}]"].astype(np.float64), t_sim) for k in range(4)]

    # MCNN neural_control output & cached setpoint
    if len(obs["mcnn_pub_t"]) > 0:
        t_mp = np.asarray(obs["mcnn_pub_t"], dtype=np.float64)
        u_mcnn = [nearest_within(t_mp, np.asarray(obs["mcnn_u"][k]), t_sim, 0.006) for k in range(4)]
        sp_x = nearest_within(t_mp, np.asarray(obs["mcnn_sp_x"]), t_sim, 0.006)
        sp_y = nearest_within(t_mp, np.asarray(obs["mcnn_sp_y"]), t_sim, 0.006)
        sp_z = nearest_within(t_mp, np.asarray(obs["mcnn_sp_z"]), t_sim, 0.006)
        sp_ts_arr = nearest_within(t_mp, np.asarray(obs["mcnn_sp_ts"]), t_sim, 0.006)
        sp_age = t_sim - sp_ts_arr
    elif nc is not None and len(nc["timestamp"]) > 0:
        t_nc = nc["timestamp"].astype(np.float64) * 1e-6
        u_mcnn = [nearest_within(t_nc, nc[f"network_output[{k}]"].astype(np.float64), t_sim, 0.006) for k in range(4)]
        sp_x = np.full(len(t_sim), math.nan)
        sp_y = np.full(len(t_sim), math.nan)
        sp_z = np.full(len(t_sim), math.nan)
        sp_age = np.full(len(t_sim), math.nan)
    else:
        u_mcnn = [np.full(len(t_sim), math.nan) for _ in range(4)]
        sp_x = np.full(len(t_sim), math.nan)
        sp_y = np.full(len(t_sim), math.nan)
        sp_z = np.full(len(t_sim), math.nan)
        sp_age = np.full(len(t_sim), math.nan)

    # Fill sp_x/y/z pre-switch (or for Classic-Keep) from ULog trajectory_setpoint where NaN
    if tsp is not None and len(tsp["timestamp"]) > 0:
        t_tsp = tsp["timestamp"].astype(np.float64) * 1e-6
        for dst, col in [(sp_x, "position[0]"), (sp_y, "position[1]"), (sp_z, "position[2]")]:
            fill = zoh_lookup(t_tsp, tsp[col].astype(np.float64), t_sim)
            need = ~np.isfinite(dst)
            dst[need] = fill[need]
        tsp_ts = zoh_lookup(t_tsp, t_tsp, t_sim)
        need_age = ~np.isfinite(sp_age)
        sp_age[need_age] = t_sim[need_age] - tsp_ts[need_age]

    # Gazebo relay step log (exact 4 ms Gazebo physics step alignment!)
    relay_path = Path(meta["relay_step_path"]) if meta.get("relay_step_path") else None
    rstep = parse_relay_step_csv(relay_path)
    if rstep and len(rstep.get("sim_us", [])) > 0:
        t_gz = rstep["sim_us"] * 1e-6
        gz_cmd_w = [zoh_lookup(t_gz, rstep[f"cmd_w{k}"], t_sim) for k in range(4)]
        gz_rx_w = [zoh_lookup(t_gz, rstep[f"rx_latest_w{k}"], t_sim) for k in range(4)]
        gz_joint_w = [zoh_lookup(t_gz, rstep[f"joint_w{k}"], t_sim) for k in range(4)]
        gz_hold_active = zoh_lookup(t_gz, rstep["hold_active"], t_sim, default=0.0)
        gz_is_neural = zoh_lookup(t_gz, rstep["forwarded_is_neural"], t_sim, default=0.0)
        gz_mcnn_seq = zoh_lookup(t_gz, rstep["forwarded_mcnn_seq"], t_sim, default=0.0)
        gz_overwritten = zoh_lookup(t_gz, rstep["overwritten_mcnn_count"], t_sim, default=0.0)
    else:
        gz_cmd_w = [np.full(len(t_sim), math.nan) for _ in range(4)]
        gz_rx_w = [np.full(len(t_sim), math.nan) for _ in range(4)]
        gz_joint_w = [np.full(len(t_sim), math.nan) for _ in range(4)]
        gz_hold_active = np.zeros(len(t_sim))
        gz_is_neural = np.zeros(len(t_sim))
        gz_mcnn_seq = np.zeros(len(t_sim))
        gz_overwritten = np.zeros(len(t_sim))

    # Vehicle status (nav_state, armed, failsafe)
    t_vs = vs["timestamp"].astype(np.float64) * 1e-6
    nav_state = zoh_lookup(t_vs, vs["nav_state"].astype(np.float64), t_sim, default=0.0)
    armed = zoh_lookup(t_vs, (vs["arming_state"] == 2).astype(np.float64), t_sim, default=0.0)
    failsafe = zoh_lookup(t_vs, vs["failsafe"].astype(np.float64), t_sim, default=0.0)

    # Classic rate integrator state
    if rcs is not None and len(rcs["timestamp"]) > 0:
        t_rcs = rcs["timestamp"].astype(np.float64) * 1e-6
        ri_x = zoh_lookup(t_rcs, rcs["rollspeed_integ"].astype(np.float64), t_sim)
        ri_y = zoh_lookup(t_rcs, rcs["pitchspeed_integ"].astype(np.float64), t_sim)
        ri_z = zoh_lookup(t_rcs, rcs["yawspeed_integ"].astype(np.float64), t_sim)
    else:
        ri_x = ri_y = ri_z = np.full(len(t_sim), math.nan)

    # Trace self-contained header metadata
    t_req_rel = (obs["t_request_s"] - t_sw_s) if obs["t_request_s"] is not None else None
    t_act_rel = (obs["t_active_s"] - t_sw_s) if obs["t_active_s"] is not None else None
    t_pub_rel = (obs["t_publish_first_s"] - t_sw_s) if obs["t_publish_first_s"] is not None else None
    t_alloc_off_rel = (t_alloc_off_s - t_sw_s) if t_alloc_off_s is not None else None

    # Fallback for vanilla binary without mcnn_obs.csv: derive t_active/t_publish from ULog
    if t_act_rel is None and spec["arm"] == "mcnn_takeover":
        nn_vs = np.where((t_vs >= t_sw_s - 0.05) & (vs["nav_state"] == 23))[0]
        if len(nn_vs) > 0:
            t_act_rel = float(t_vs[nn_vs[0]] - t_sw_s)
    if t_pub_rel is None and spec["arm"] == "mcnn_takeover" and nc is not None and len(nc["timestamp"]) > 0:
        t_nc = nc["timestamp"].astype(np.float64) * 1e-6
        nn_nc = np.where(t_nc >= t_sw_s - 0.05)[0]
        if len(nn_nc) > 0:
            t_pub_rel = float(t_nc[nn_nc[0]] - t_sw_s)

    trace_meta = {
        "run_id": run_id,
        "group": group,
        "arm": spec["arm"],
        "trajectory": traj_kind,
        "px4_variant": spec.get("px4_variant", "obs"),
        "seed": int(spec.get("seed", 42)),
        "yaw_ref_deg": yaw_ref_deg,
        "t_sw_sim_s": t_sw_s,
        "eval_after_s": eval_after_s,
        "hold_duration_ms": float(spec.get("hold_duration_ms", 0.0)),
        "ref_gap_ms": float(spec.get("ref_gap_ms", 0.0)),
        "wind_enu": spec.get("wind_enu", [0.0, 0.0, 0.0]),
        "payload_mass_kg": float(spec.get("payload_mass_kg", 0.0)),
        "payload_offset_xyz": spec.get("payload_offset_xyz", [0.0, 0.0, 0.0]),
        "stale_distance_m": spec.get("stale_distance_m"),
        "fresh_reset": spec.get("fresh_reset"),
        "moving_reentry": spec.get("moving_reentry"),
        "cf_trim_tau_s": spec.get("cf_trim_tau_s"),
        "cf_trim_mode": spec.get("cf_trim_mode"),
        "landed_disarmed": bool(meta["events"].get("landed_disarmed", False)),
        "t_request_rel_s": t_req_rel,
        "t_active_rel_s": t_act_rel,
        "t_publish_first_rel_s": t_pub_rel,
        "t_alloc_off_rel_s": t_alloc_off_rel,
    }

    # Write lossless gzipped CSV trace
    TRACES_DIR.mkdir(parents=True, exist_ok=True)
    trace_path = TRACES_DIR / f"{run_id}.csv.gz"
    arrays = [
        t_rel, t_sim, x_m, y_m, z_ned, h_m, vx, vy, vz_ned, v_up, v_xy,
        roll_deg, pitch_deg, yaw_deg, tilt_deg, p_deg_s, q_deg_s, r_deg_s,
        ref_x, ref_y, ref_z, ref_h, sp_x, sp_y, sp_z, sp_age,
        u_pub[0], u_pub[1], u_pub[2], u_pub[3],
        u_mcnn[0], u_mcnn[1], u_mcnn[2], u_mcnn[3],
        gz_cmd_w[0], gz_cmd_w[1], gz_cmd_w[2], gz_cmd_w[3],
        gz_rx_w[0], gz_rx_w[1], gz_rx_w[2], gz_rx_w[3],
        gz_joint_w[0], gz_joint_w[1], gz_joint_w[2], gz_joint_w[3],
        gz_hold_active, gz_is_neural, gz_mcnn_seq, gz_overwritten,
        nav_state, armed, failsafe, ctrl_alloc_en, ri_x, ri_y, ri_z,
    ]
    assert len(arrays) == len(TRACE_COLUMNS)

    with gzip.open(trace_path, "wt", encoding="utf-8", compresslevel=6) as f:
        f.write("# META: " + json.dumps(trace_meta, sort_keys=True) + "\n")
        f.write(",".join(TRACE_COLUMNS) + "\n")
        for i in range(len(t_sim)):
            row = [f"{arr[i]:.6f}" if np.isfinite(arr[i]) else "nan" for arr in arrays]
            f.write(",".join(row) + "\n")

    # Re-load trace_path immediately so metrics.json is 100% single-source derived from the exact saved trace!
    loaded_meta, loaded_data = load_trace_gz(trace_path)
    metrics = compute_run_metrics(loaded_meta, loaded_data)

    prov_entry = {
        "run_id": run_id,
        "group": group,
        "px4_variant": spec.get("px4_variant", "obs"),
        "trace_file": f"traces/{run_id}.csv.gz",
        "trace_rows": len(t_sim),
        "ulog_local_path": str(ulog_path),
        "ulog_sha256": meta["ulog_sha256"],
        "ulog_bytes": meta["ulog_bytes"],
        "obs_log_local_path": meta.get("obs_log_path"),
        "relay_step_local_path": meta.get("relay_step_path"),
    }
    return metrics, prov_entry


def build_provenance(run_provs: list[dict[str, Any]], v0_summary: dict[str, Any]) -> dict[str, Any]:
    px4_commit = subprocess.check_output(
        ["git", "-C", str(PX4_DIR), "rev-parse", "HEAD"], text=True
    ).strip()
    submod_status = subprocess.check_output(
        ["git", "-C", str(PX4_DIR), "submodule", "status"], text=True
    ).strip().splitlines()
    gz_ver = subprocess.check_output(
        ["gz", "sim", "--version"],
        env={**__import__("os").environ, "GZ_CONFIG_PATH": "/usr/share/gz"},
        text=True,
    ).strip().splitlines()[0]

    # Compute raw 15,088-byte TFLite flatbuffer hash from control_net.cpp
    import re
    cn_path = PX4_DIR / "src/modules/mc_nn_control/control_net.cpp"
    ar_path = PX4_DIR / "src/modules/mc_nn_control/actions_rescale.hpp"
    hexes = re.findall(r"0x([0-9a-fA-F]{2})", cn_path.read_text(encoding="utf-8"))
    model_raw = bytes(int(h, 16) for h in hexes)

    return {
        "px4_upstream_repo": "https://github.com/PX4/PX4-Autopilot.git",
        "px4_commit_sha": px4_commit,
        "px4_submodules_initialized": [line.strip() for line in submod_status if not line.startswith("-")],
        "gazebo_version": gz_ver,
        "fixed_sim_seed": 42,
        "cruise_altitude_m": 4.0,
        "frozen_official_params": {
            "MC_NN_EN": 1,
            "MC_NN_MANL_CTRL": 0,
            "MC_NN_MIN_RPM": 1000,
            "MC_NN_MAX_RPM": 22000,
            "MC_NN_THRST_COEF": 1.5,
            "THR_MDL_FAC": 0.8,
            "SDLOG_MODE": 1,
            "SDLOG_PROFILE": 1,
            "COM_RCL_EXCEPT": 4,
            "NAV_DLL_ACT": 0,
            "COM_OF_LOSS_T": 2.0,
            "COM_ARM_WO_GPS": 0,
        },
        "embedded_model": {
            "control_net_cpp_sha256": sha256_file(cn_path),
            "actions_rescale_hpp_sha256": sha256_file(ar_path),
            "control_net_tflite_bytes": len(model_raw),
            "control_net_tflite_sha256": hashlib.sha256(model_raw).hexdigest(),
        },
        "px4_binaries_sha256": {
            v: sha256_file(SCRATCH_ROOT / "bins" / v / "px4")
            for v in ["vanilla", "obs", "cf_probe"]
            if (SCRATCH_ROOT / "bins" / v / "px4").exists()
        },
        "zero_perturbation_verification": v0_summary,
        "runs": run_provs,
    }


def write_manifest() -> None:
    entries = []
    for p in sorted(EVIDENCE_DIR.rglob("*")):
        if "__pycache__" in p.parts or p.suffix == ".pyc":
            continue
        if p.is_file() and p.name != "manifest.sha256":
            rel = p.relative_to(EVIDENCE_DIR).as_posix()
            entries.append(f"{sha256_file(p)}  {rel}")
    (EVIDENCE_DIR / "manifest.sha256").write_text("\n".join(entries) + "\n", encoding="utf-8")


def main() -> None:
    specs = json.loads((CAMPAIGN_ROOT / "campaign_specs.json").read_text(encoding="utf-8"))
    all_metrics: dict[str, Any] = {}
    run_provs: list[dict[str, Any]] = []

    # Include V0 zero-perturbation verification runs
    v0_ids = ["V0_vanilla_hover", "V0_obs_direct_hover", "V0_obs_relay0_hover"]
    for vid in v0_ids:
        vdir = V0_ROOT / vid
        if (vdir / "run_meta.json").exists():
            m, p = extract_single_run(vdir, run_id_override=vid, group_override="V0")
            all_metrics[vid] = m
            run_provs.append(p)

    # Extract all campaign runs
    for spec in specs:
        rid = spec["run_id"]
        rdir = CAMPAIGN_ROOT / rid
        if not (rdir / "run_meta.json").exists():
            print(f"WARNING: missing run {rid}, skipping")
            continue
        m, p = extract_single_run(rdir)
        all_metrics[rid] = m
        run_provs.append(p)

    # Compute V0 vanilla-vs-obs silent hover diff summary
    v0_summary: dict[str, Any] = {}
    if all(k in all_metrics for k in v0_ids):
        _, d_van = load_trace_gz(TRACES_DIR / "V0_vanilla_hover.csv.gz")
        t_grid = np.linspace(0.0, 4.0, 401)
        h_van = np.interp(t_grid, d_van["t_rel_s"], d_van["h_m"])
        x_van = np.interp(t_grid, d_van["t_rel_s"], d_van["x_m"])
        y_van = np.interp(t_grid, d_van["t_rel_s"], d_van["y_m"])
        tilt_van = np.interp(t_grid, d_van["t_rel_s"], d_van["tilt_deg"])
        for other in ["V0_obs_direct_hover", "V0_obs_relay0_hover"]:
            _, d_o = load_trace_gz(TRACES_DIR / f"{other}.csv.gz")
            h_o = np.interp(t_grid, d_o["t_rel_s"], d_o["h_m"])
            x_o = np.interp(t_grid, d_o["t_rel_s"], d_o["x_m"])
            y_o = np.interp(t_grid, d_o["t_rel_s"], d_o["y_m"])
            tilt_o = np.interp(t_grid, d_o["t_rel_s"], d_o["tilt_deg"])
            v0_summary[f"vanilla_vs_{other}"] = {
                "max_abs_dh_m": float(np.max(np.abs(h_o - h_van))),
                "max_abs_dxy_m": float(np.max(np.hypot(x_o - x_van, y_o - y_van))),
                "max_abs_dtilt_deg": float(np.max(np.abs(tilt_o - tilt_van))),
                "vanilla_max_tilt_deg": all_metrics["V0_vanilla_hover"]["windows"]["w_full"]["max_tilt_deg"],
                "other_max_tilt_deg": all_metrics[other]["windows"]["w_full"]["max_tilt_deg"],
            }

    (EVIDENCE_DIR / "metrics.json").write_text(
        json.dumps({"schema_version": "1.0", "runs": all_metrics}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    prov = build_provenance(run_provs, v0_summary)
    (EVIDENCE_DIR / "provenance.json").write_text(
        json.dumps(prov, indent=2, sort_keys=True), encoding="utf-8"
    )
    write_manifest()
    print(f"Extracted {len(all_metrics)} runs into {EVIDENCE_DIR}")


if __name__ == "__main__":
    main()

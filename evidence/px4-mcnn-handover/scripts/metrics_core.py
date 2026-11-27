#!/usr/bin/env python3
"""
Pure offline single-source metrics engine for PX4 mc_nn_control handover experiments.
Computes every metric deterministically from traces/<run_id>.csv.gz alone (no ULog needed).
"""

from __future__ import annotations

import csv
import gzip
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

NAV_STATE_OFFBOARD = 14
NAV_STATE_AUTO_LAND = 18
NAV_STATE_NEURAL = 23


def load_trace_gz(path: Path) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    """Read a self-contained gzipped CSV trace with `# META: {...}` header line."""
    meta: dict[str, Any] = {}
    cols: dict[str, list[float]] = {}
    with gzip.open(path, "rt", encoding="utf-8") as f:
        first = f.readline()
        if first.startswith("# META:"):
            meta = json.loads(first[len("# META:") :].strip())
            header_line = f.readline()
        else:
            header_line = first
        fieldnames = [c.strip() for c in header_line.strip().split(",")]
        for name in fieldnames:
            cols[name] = []
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            for name, val in zip(fieldnames, row):
                try:
                    cols[name].append(float(val))
                except ValueError:
                    cols[name].append(math.nan)
    data = {k: np.asarray(v, dtype=np.float64) for k, v in cols.items()}
    return meta, data


def _finite_mask(arr: np.ndarray) -> np.ndarray:
    return np.isfinite(arr)


def wrap_deg_180(deg: np.ndarray | float) -> np.ndarray | float:
    return (deg + 180.0) % 360.0 - 180.0


def _window_metrics(
    t_rel: np.ndarray,
    data: dict[str, np.ndarray],
    h0: float,
    yaw0_deg: float,
    yaw_ref_rad: float,
    t_end: float,
    stop_t: float | None = None,
) -> dict[str, Any]:
    eff_end = min(t_end, stop_t) if stop_t is not None else t_end
    m = (t_rel >= -1e-9) & (t_rel <= eff_end + 1e-9)
    if not np.any(m):
        return {}
    t_w = t_rel[m]
    h_w = data["h_m"][m]
    dh_cm = (h_w - h0) * 100.0
    tilt_w = data["tilt_deg"][m]
    roll_w = data["roll_deg"][m]
    pitch_w = data["pitch_deg"][m]
    yaw_w = data["yaw_deg"][m]
    yaw_dev_w = np.abs(wrap_deg_180(yaw_w - yaw0_deg))
    vxy_w = data["v_xy_m_s"][m]
    vx_w = data["vx_m_s"][m]
    vy_w = data["vy_m_s"][m]
    v_fwd_w = vx_w * math.cos(yaw_ref_rad) + vy_w * math.sin(yaw_ref_rad)
    vup_w = data["v_up_m_s"][m]
    x_w = data["x_m"][m]
    y_w = data["y_m"][m]
    rx_w = data["ref_x_m"][m]
    ry_w = data["ref_y_m"][m]
    rh_w = data["ref_h_m"][m]

    idx_tilt = int(np.nanargmax(tilt_w))
    idx_hmin = int(np.nanargmin(h_w))
    idx_vup = int(np.nanargmin(vup_w))

    err_xy = np.hypot(x_w - rx_w, y_w - ry_w)
    err_3d = np.sqrt((x_w - rx_w) ** 2 + (y_w - ry_w) ** 2 + (h_w - rh_w) ** 2)

    valid_xy = _finite_mask(err_xy)
    valid_3d = _finite_mask(err_3d)

    max_alt_loss_cm = max(0.0, float(h0 - np.nanmin(h_w)) * 100.0)
    min_dh_cm = float(np.nanmin(dh_cm))
    max_dh_cm = float(np.nanmax(dh_cm))

    return {
        "max_tilt_deg": float(tilt_w[idx_tilt]),
        "t_max_tilt_s": float(t_w[idx_tilt]),
        "max_roll_deg": float(np.nanmax(roll_w)),
        "min_roll_deg": float(np.nanmin(roll_w)),
        "max_abs_roll_deg": float(np.nanmax(np.abs(roll_w))),
        "max_abs_pitch_deg": float(np.nanmax(np.abs(pitch_w))),
        "max_abs_yaw_dev_deg": float(np.nanmax(yaw_dev_w)),
        "min_v_xy_m_s": float(np.nanmin(vxy_w)),
        "max_v_xy_m_s": float(np.nanmax(vxy_w)),
        "min_vx_m_s": float(np.nanmin(vx_w)),
        "min_v_fwd_m_s": float(np.nanmin(v_fwd_w)),
        "min_v_up_m_s": float(vup_w[idx_vup]),
        "t_min_v_up_s": float(t_w[idx_vup]),
        "min_h_m": float(h_w[idx_hmin]),
        "t_min_h_s": float(t_w[idx_hmin]),
        "min_dh_cm": min_dh_cm,
        "max_dh_cm": max_dh_cm,
        "max_alt_loss_cm": max_alt_loss_cm,
        "xy_rmse_m": float(np.sqrt(np.mean(err_xy[valid_xy] ** 2))) if np.any(valid_xy) else math.nan,
        "pos3d_rmse_m": float(np.sqrt(np.mean(err_3d[valid_3d] ** 2))) if np.any(valid_3d) else math.nan,
        "max_xy_err_m": float(np.max(err_xy[valid_xy])) if np.any(valid_xy) else math.nan,
        "max_y_m": float(np.nanmax(y_w)),
        "min_y_m": float(np.nanmin(y_w)),
    }


def compute_run_metrics(meta: dict[str, Any], data: dict[str, np.ndarray]) -> dict[str, Any]:
    """Deterministically compute all standardized run metrics from trace arrays + trace metadata."""
    t_rel = data["t_rel_s"]
    eval_after_s = float(meta["eval_after_s"])
    arm = str(meta["arm"])

    # Exact entry index closest to t_rel == 0.0 (preferring sample <= 0 within 4 ms)
    idx0 = int(np.argmin(np.abs(t_rel)))
    h0 = float(data["h_m"][idx0])
    x0 = float(data["x_m"][idx0])
    y0 = float(data["y_m"][idx0])

    entry = {
        "t_rel_s": float(t_rel[idx0]),
        "x_m": x0,
        "y_m": y0,
        "h_m": h0,
        "vx_m_s": float(data["vx_m_s"][idx0]),
        "vy_m_s": float(data["vy_m_s"][idx0]),
        "v_xy_m_s": float(data["v_xy_m_s"][idx0]),
        "v_up_m_s": float(data["v_up_m_s"][idx0]),
        "roll_deg": float(data["roll_deg"][idx0]),
        "pitch_deg": float(data["pitch_deg"][idx0]),
        "yaw_deg": float(data["yaw_deg"][idx0]),
        "tilt_deg": float(data["tilt_deg"][idx0]),
        "p_deg_s": float(data["p_deg_s"][idx0]),
        "q_deg_s": float(data["q_deg_s"][idx0]),
        "r_deg_s": float(data["r_deg_s"][idx0]),
    }

    # Mode authority & crash / abort detection over evaluation window [0, eval_after_s]
    eval_mask = (t_rel >= 0.0) & (t_rel <= eval_after_s + 1e-9)
    t_ev = t_rel[eval_mask]
    h_ev = data["h_m"][eval_mask]
    nav_ev = data["nav_state"][eval_mask]
    arm_ev = data["armed"][eval_mask]
    fs_ev = data["failsafe"][eval_mask]

    outcome = "LANDED_CLEAN"
    event_t_rel_s: float | None = None
    event_nav_state: int | None = None
    event_detail: str = ""

    # Check ground impact crash first (altitude < 0.35 m during flight window)
    crash_idx = np.where(h_ev < 0.35)[0]
    if len(crash_idx) > 0:
        outcome = "GROUND_IMPACT_CRASH"
        ci = int(crash_idx[0])
        event_t_rel_s = float(t_ev[ci])
        event_nav_state = int(round(nav_ev[ci]))
        event_detail = f"Ground contact h={h_ev[ci]:.3f}m at t_rel={event_t_rel_s:.3f}s"
    else:
        # Check unexpected mode exit / failsafe during active control window [0.15 s, eval_after_s - 0.08 s]
        expected_nav = NAV_STATE_OFFBOARD if arm == "classic_keep" else NAV_STATE_NEURAL
        inner = (t_ev >= 0.15) & (t_ev <= eval_after_s - 0.08)
        if np.any(inner):
            bad_nav = np.where(inner & ((np.round(nav_ev) != expected_nav) | (fs_ev > 0.5) | (arm_ev < 0.5)))[0]
            if len(bad_nav) > 0:
                outcome = "MODE_EXIT_ABORT"
                bi = int(bad_nav[0])
                event_t_rel_s = float(t_ev[bi])
                event_nav_state = int(round(nav_ev[bi]))
                event_detail = (
                    f"Unexpected mode/failsafe nav_state={event_nav_state}, "
                    f"failsafe={int(round(fs_ev[bi]))}, armed={int(round(arm_ev[bi]))} at t_rel={event_t_rel_s:.3f}s"
                )

    if outcome == "LANDED_CLEAN" and not bool(meta.get("landed_disarmed", True)):
        outcome = "MODE_EXIT_ABORT"
        event_detail = "Did not complete clean landing/disarm"

    # First-step motor jump: max_i |u_N,0(i) - u_C,last(i)|
    first_motor_step = math.nan
    u_c_last = [math.nan] * 4
    u_n_first = [math.nan] * 4
    if arm == "mcnn_takeover":
        pre_idx = np.where((t_rel < 0.0) & (np.round(data["nav_state"]) == NAV_STATE_OFFBOARD))[0]
        post_idx = np.where(
            (t_rel >= -0.02)
            & np.isfinite(data["u_mcnn_0"])
            & np.isfinite(data["u_mcnn_1"])
            & np.isfinite(data["u_mcnn_2"])
            & np.isfinite(data["u_mcnn_3"])
        )[0]
        if len(pre_idx) > 0 and len(post_idx) > 0:
            ip = int(pre_idx[-1])
            iq = int(post_idx[0])
            u_c_last = [float(data[f"u_pub_{k}"][ip]) for k in range(4)]
            u_n_first = [float(data[f"u_mcnn_{k}"][iq]) for k in range(4)]
            first_motor_step = float(max(abs(u_n_first[k] - u_c_last[k]) for k in range(4)))
    else:
        # Classic keep or pre-entered: step across t_rel=0
        if idx0 > 0:
            u_c_last = [float(data[f"u_pub_{k}"][idx0 - 1]) for k in range(4)]
            u_n_first = [float(data[f"u_pub_{k}"][idx0]) for k in range(4)]
            first_motor_step = float(max(abs(u_n_first[k] - u_c_last[k]) for k in range(4)))

    # Multi-window metrics (evaluate up to crash time if crashed so ground-rest values don't pollute flight metrics,
    # while still capturing the crash peak itself at event_t_rel_s)
    yaw_ref_deg = float(meta.get("yaw_ref_deg", 90.0))
    yaw_ref_rad = math.radians(yaw_ref_deg)
    yaw0_deg = float(entry["yaw_deg"])
    stop_t = (event_t_rel_s + 0.02) if outcome == "GROUND_IMPACT_CRASH" and event_t_rel_s is not None else None
    windows = {
        "w_0_25s": _window_metrics(t_rel, data, h0, yaw0_deg, yaw_ref_rad, 0.25, stop_t),
        "w_1_00s": _window_metrics(t_rel, data, h0, yaw0_deg, yaw_ref_rad, 1.00, stop_t),
        "w_2_00s": _window_metrics(t_rel, data, h0, yaw0_deg, yaw_ref_rad, 2.00, stop_t),
        "w_full": _window_metrics(t_rel, data, h0, yaw0_deg, yaw_ref_rad, eval_after_s, stop_t),
    }

    # T3 reference continuity metrics (from cached setpoint columns in trace)
    t3_ref_age_s = math.nan
    t3_init_pos_err_m = math.nan
    t3_max_snapback_disp_m = math.nan
    post_sp = np.where((t_rel >= 0.0) & np.isfinite(data["sp_x_m"]) & np.isfinite(data["sp_age_s"]))[0]
    if len(post_sp) > 0:
        isp = int(post_sp[0])
        t3_ref_age_s = float(data["sp_age_s"][isp])
        t3_init_pos_err_m = float(
            math.sqrt(
                (data["sp_x_m"][isp] - data["x_m"][isp]) ** 2
                + (data["sp_y_m"][isp] - data["y_m"][isp]) ** 2
                + (data["sp_z_ned_m"][isp] - data["z_ned_m"][isp]) ** 2
            )
        )
    if meta.get("trajectory") == "stale_reentry":
        # Snapback toward point A (0, 0) along forward axis (cos(yaw_ref), sin(yaw_ref)):
        # Evaluated over the same pre-impact flight window as w_full so figures and JSON match exactly.
        snap_end = min(eval_after_s, stop_t) if stop_t is not None else eval_after_s
        snap_mask = (t_rel >= 0.0) & (t_rel <= snap_end)
        fx, fy = math.cos(yaw_ref_rad), math.sin(yaw_ref_rad)
        s0_fwd = x0 * fx + y0 * fy
        s_ev_fwd = data["x_m"][snap_mask] * fx + data["y_m"][snap_mask] * fy
        t3_max_snapback_disp_m = float(max(0.0, s0_fwd - float(np.nanmin(s_ev_fwd)))) if len(s_ev_fwd) else math.nan

    # T4 authority delivery & Gazebo application metrics (from trace + header timestamps)
    t_sw_sim_s = float(meta["t_sw_sim_s"])
    t_req_rel = meta.get("t_request_rel_s")
    t_act_rel = meta.get("t_active_rel_s")
    t_pub_rel = meta.get("t_publish_first_rel_s")
    t_alloc_off_rel = meta.get("t_alloc_off_rel_s")

    dual_pub_overlap_ms = (
        float((t_alloc_off_rel - t_pub_rel) * 1000.0)
        if (t_alloc_off_rel is not None and t_pub_rel is not None)
        else math.nan
    )

    # First Gazebo physics step adopting MCNN command (from gz_is_neural column in trace)
    t_apply_rel = None
    overwritten_at_apply = 0
    gz_nn = np.where((t_rel >= -0.02) & (data["gz_is_neural"] > 0.5) & (data["gz_hold_active"] < 0.5))[0]
    if arm == "mcnn_takeover" and len(gz_nn) > 0:
        ia = int(gz_nn[0])
        t_apply_rel = float(t_rel[ia])
        overwritten_at_apply = int(round(data["gz_overwritten_mcnn"][ia]))
    elif arm == "mcnn_takeover":
        ov_vals = data["gz_overwritten_mcnn"][eval_mask]
        if len(ov_vals) > 0 and np.any(np.isfinite(ov_vals)):
            overwritten_at_apply = int(round(np.nanmax(ov_vals)))

    delivery_latency_ms = (
        float((t_apply_rel - t_pub_rel) * 1000.0)
        if (t_apply_rel is not None and t_pub_rel is not None)
        else math.nan
    )

    # Pre-switch classic integrator magnitudes (for T2 memoryless attribution)
    pre_int_idx = np.where((t_rel >= -0.20) & (t_rel <= 0.0))[0]
    pre_rate_int_norm = (
        float(
            np.nanmean(
                np.sqrt(
                    data["rate_int_x"][pre_int_idx] ** 2
                    + data["rate_int_y"][pre_int_idx] ** 2
                    + data["rate_int_z"][pre_int_idx] ** 2
                )
            )
        )
        if len(pre_int_idx) > 0
        else math.nan
    )
    pre_thr_mean = (
        float(
            np.nanmean(
                0.25
                * (
                    data["u_pub_0"][pre_int_idx]
                    + data["u_pub_1"][pre_int_idx]
                    + data["u_pub_2"][pre_int_idx]
                    + data["u_pub_3"][pre_int_idx]
                )
            )
        )
        if len(pre_int_idx) > 0
        else math.nan
    )
    pre_diff_roll = (
        float(
            np.nanmean(
                0.5 * (data["u_pub_1"][pre_int_idx] + data["u_pub_2"][pre_int_idx])
                - 0.5 * (data["u_pub_0"][pre_int_idx] + data["u_pub_3"][pre_int_idx])
            )
        )
        if len(pre_int_idx) > 0
        else math.nan
    )

    return {
        "run_id": meta["run_id"],
        "group": meta["group"],
        "arm": arm,
        "trajectory": meta["trajectory"],
        "px4_variant": meta["px4_variant"],
        "seed": int(meta["seed"]),
        "yaw_ref_deg": yaw_ref_deg,
        "t_sw_sim_s": t_sw_sim_s,
        "eval_after_s": eval_after_s,
        "hold_duration_ms": float(meta.get("hold_duration_ms", 0.0)),
        "ref_gap_ms": float(meta.get("ref_gap_ms", 0.0)),
        "wind_enu": meta.get("wind_enu", [0.0, 0.0, 0.0]),
        "payload_mass_kg": float(meta.get("payload_mass_kg", 0.0)),
        "payload_offset_xyz": meta.get("payload_offset_xyz", [0.0, 0.0, 0.0]),
        "stale_distance_m": meta.get("stale_distance_m"),
        "fresh_reset": meta.get("fresh_reset"),
        "moving_reentry": meta.get("moving_reentry"),
        "cf_trim_tau_s": meta.get("cf_trim_tau_s"),
        "entry": entry,
        "first_motor_step": first_motor_step,
        "u_classic_last": u_c_last,
        "u_mcnn_first": u_n_first,
        "pre_switch_trim": {
            "rate_int_norm": pre_rate_int_norm,
            "motor_mean": pre_thr_mean,
            "motor_roll_diff": pre_diff_roll,
        },
        "windows": windows,
        "t3_reference": {
            "ref_age_at_sw_s": t3_ref_age_s,
            "initial_pos_err_m": t3_init_pos_err_m,
            "max_snapback_disp_m": t3_max_snapback_disp_m,
        },
        "t4_delivery": {
            "t_request_rel_s": t_req_rel,
            "t_active_rel_s": t_act_rel,
            "t_publish_first_rel_s": t_pub_rel,
            "t_alloc_off_rel_s": t_alloc_off_rel,
            "dual_pub_overlap_ms": dual_pub_overlap_ms,
            "t_apply_first_rel_s": t_apply_rel,
            "t_apply_motors_rel_s": [t_apply_rel] * 4 if t_apply_rel is not None else None,
            "delivery_latency_ms": delivery_latency_ms,
            "overwritten_mcnn_samples": overwritten_at_apply,
        },
        "outcome": {
            "status": outcome,
            "event_t_rel_s": event_t_rel_s,
            "event_nav_state": event_nav_state,
            "detail": event_detail,
            "landed_disarmed": bool(meta.get("landed_disarmed", False)),
        },
    }

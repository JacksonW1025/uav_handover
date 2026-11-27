#!/usr/bin/env python3
"""Master single-seed campaign runner for PX4 official mc_nn_control C -> N handover experiments.

All main mechanism runs (T1, T2, T3-A, T3-B, T4, ATTR) align pre-switch heading to NED yaw = +90 deg
(nose East = ENU 0 deg equilibrium of official mc_nn_control) to eliminate the +90 deg yaw-reference
confound. T3-C explicitly isolates the ignored-yaw-reference anomaly by contrasting NED yaw = 0 deg
(PX4 default North takeoff heading) against the aligned NED yaw = +90 deg baseline under identical kinematics.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
from pyulog import ULog

SCRATCH_ROOT = Path(
    "/home/car/.gemini/antigravity/brain/f3411c4c-de3d-4f87-af9b-8c4e4c7218d2/scratch/px4_mcnn_cleanroom"
)
CAMPAIGN_ROOT = SCRATCH_ROOT / "runs_campaign"
PYTHON_BIN = SCRATCH_ROOT / "venv/bin/python"
RUNNER_SCRIPT = Path(__file__).resolve().parent / "run_sitl.py"

SEED = 42
ALT_M = 4.0
T_MANEUVER_START_MS = 18000
YAW_ALIGNED_DEG = 90.0
# Calibrated 0-kg nominal hover collective mean from V0_obs_relay0_hover at yaw=+90 deg
CF_NOM_HOVER_U = 0.5675


def base_spec(run_id: str, group: str, **kwargs: Any) -> dict[str, Any]:
    s: dict[str, Any] = {
        "run_id": run_id,
        "group": group,
        "px4_variant": "obs",
        "use_relay_plugin": True,
        "hold_duration_ms": 0.0,
        "ref_gap_ms": 0.0,
        "wind_enu": [0.0, 0.0, 0.0],
        "wind_drag_quad": 0.0,
        "wind_drag_lin": 0.0,
        "payload_mass_kg": 0.0,
        "payload_offset_xyz": [0.0, 0.0, 0.0],
        "seed": SEED,
        "altitude_m": ALT_M,
        "t_maneuver_start_ms": T_MANEUVER_START_MS,
        "yaw_ref_deg": YAW_ALIGNED_DEG,
    }
    s.update(kwargs)
    return s


def build_campaign_specs() -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []

    # =========================================================================
    # T1: Physical & Environmental Margin Depletion (yaw = +90 deg aligned)
    # =========================================================================
    # 1) Dedicated gentle low-speed safety-envelope control (v = 0.9 m/s)
    benign = dict(
        trajectory="benign_cruise",
        speed_m_s=0.9,
        t_accel_s=2.0,
        tau_sw_s=3.5,
        eval_after_s=4.0,
    )
    specs.extend([
        base_spec("T1_benign_classic", "T1", arm="classic_keep", **benign),
        base_spec("T1_benign_mcnn", "T1", arm="mcnn_takeover", **benign),
    ])

    # 2) Tight banked turn 3-arm comparison (v=4.2 m/s, R=3.5 m, yaw=+90 deg)
    # Separates transient mid-turn handover shock from steady policy cornering envelope.
    turn_3arm = dict(
        trajectory="tight_turn_brake",
        speed_m_s=4.2,
        t_accel_s=2.0,
        t_turn_start_s=2.6,
        turn_radius_m=3.5,
        t_brake_s=4.3,
        t_decel_s=1.5,
        tau_sw_s=3.9,
        eval_after_s=4.0,
    )
    specs.extend([
        base_spec("T1_turn_w0_classic", "T1", arm="classic_keep", **turn_3arm),
        base_spec("T1_turn_w0_mcnn", "T1", arm="mcnn_takeover", **turn_3arm),
        base_spec("T1_turn_w0_preentered", "T1", arm="mcnn_preentered", **turn_3arm),
    ])

    # 3) Controlled environmental headwind sweep (constant wind_drag_quad=0.08 across 0 -> 5.5 -> 9.0 m/s)
    # Flying East (+X_ENU) against Westward headwind [-w, 0, 0] ENU.
    wind_cruise = dict(
        trajectory="straight_cruise",
        speed_m_s=2.2,
        t_accel_s=2.0,
        tau_sw_s=4.0,
        eval_after_s=4.0,
        wind_drag_quad=0.08,
    )
    specs.extend([
        base_spec("T1_wind_w0_classic", "T1W", arm="classic_keep", wind_enu=[0.0, 0.0, 0.0], **wind_cruise),
        base_spec("T1_wind_w0_mcnn", "T1W", arm="mcnn_takeover", wind_enu=[0.0, 0.0, 0.0], **wind_cruise),
        base_spec("T1_wind_w55_mcnn", "T1W", arm="mcnn_takeover", wind_enu=[-5.5, 0.0, 0.0], **wind_cruise),
        base_spec("T1_wind_w90_classic", "T1W", arm="classic_keep", wind_enu=[-9.0, 0.0, 0.0], **wind_cruise),
        base_spec("T1_wind_w90_mcnn", "T1W", arm="mcnn_takeover", wind_enu=[-9.0, 0.0, 0.0], **wind_cruise),
    ])

    # 4) High-speed straight braking (v=4.2 m/s, pure missing velocity feedforward crash even at yaw=+90 deg)
    sb_base = dict(
        trajectory="straight_brake",
        speed_m_s=4.2,
        t_accel_s=2.0,
        t_brake_s=4.4,
        t_decel_s=1.4,
        tau_sw_s=3.8,
        eval_after_s=4.0,
    )
    specs.extend([
        base_spec("T1_straight_brake_classic", "T1", arm="classic_keep", **sb_base),
        base_spec("T1_straight_brake_mcnn", "T1", arm="mcnn_takeover", **sb_base),
    ])

    # =========================================================================
    # T2: Memoryless Feedforward == Cleared Memory (yaw = +90 deg, pure hover)
    # Running T2 steady-disturbance sweeps at hover (v=0) eliminates BOTH yaw saturation
    # and T1 forward-braking pitch saturation, isolating pure collective & CoM/wind trim loss.
    # =========================================================================
    hov_base = dict(
        trajectory="hover",
        tau_sw_s=2.0,
        eval_after_s=4.0,
    )
    hov_wind = dict(
        trajectory="hover",
        tau_sw_s=2.0,
        eval_after_s=4.0,
        wind_drag_quad=0.08,
    )
    specs.extend([
        base_spec("T2_nom_classic", "T2", arm="classic_keep", **hov_wind),
        base_spec("T2_nom_mcnn", "T2", arm="mcnn_takeover", **hov_wind),
        base_spec("T2_wind55_mcnn", "T2", arm="mcnn_takeover", wind_enu=[-5.5, 0.0, 0.0], **hov_wind),
        base_spec("T2_wind85_classic", "T2", arm="classic_keep", wind_enu=[-8.5, 0.0, 0.0], **hov_wind),
        base_spec("T2_wind85_mcnn", "T2", arm="mcnn_takeover", wind_enu=[-8.5, 0.0, 0.0], **hov_wind),
        base_spec(
            "T2_com40_classic", "T2", arm="classic_keep",
            payload_mass_kg=0.40, payload_offset_xyz=[0.025, 0.020, 0.0], **hov_base
        ),
        base_spec(
            "T2_com40_mcnn", "T2", arm="mcnn_takeover",
            payload_mass_kg=0.40, payload_offset_xyz=[0.025, 0.020, 0.0], **hov_base
        ),
        base_spec(
            "T2_com65_mcnn", "T2", arm="mcnn_takeover",
            payload_mass_kg=0.65, payload_offset_xyz=[0.035, 0.028, 0.0], **hov_base
        ),
        base_spec(
            "T2_cf_probe_com40", "T2",
            px4_variant="cf_probe", cf_trim_tau_s=0.30, cf_trim_mode="bumpless_steady",
            cf_nom_hover_u=CF_NOM_HOVER_U,
            arm="mcnn_takeover",
            payload_mass_kg=0.40, payload_offset_xyz=[0.025, 0.020, 0.0], **hov_base
        ),
    ])

    # =========================================================================
    # T3: Setpoint Reference Continuity Anomaly (T3-A + T3-B + T3-C)
    # =========================================================================
    # T3-A: Cross-mode re-entry stale target retention (yaw = +90 deg aligned)
    specs.extend([
        base_spec(
            "T3A_stale_d0_fresh", "T3A", trajectory="stale_reentry", arm="mcnn_takeover",
            stale_distance_m=2.0, fresh_reset=True, moving_reentry=False,
            transit_speed_m_s=1.5, eval_after_s=4.0,
        ),
        base_spec(
            "T3A_stale_d10_static", "T3A", trajectory="stale_reentry", arm="mcnn_takeover",
            stale_distance_m=1.0, fresh_reset=False, moving_reentry=False,
            transit_speed_m_s=1.5, eval_after_s=4.0,
        ),
        base_spec(
            "T3A_stale_d20_static", "T3A", trajectory="stale_reentry", arm="mcnn_takeover",
            stale_distance_m=2.0, fresh_reset=False, moving_reentry=False,
            transit_speed_m_s=1.5, eval_after_s=4.0,
        ),
        base_spec(
            "T3A_stale_d35_static", "T3A", trajectory="stale_reentry", arm="mcnn_takeover",
            stale_distance_m=3.5, fresh_reset=False, moving_reentry=False,
            transit_speed_m_s=1.5, eval_after_s=4.0,
        ),
        base_spec(
            "T3A_stale_d20_moving_classic", "T3A", trajectory="stale_reentry", arm="classic_keep",
            stale_distance_m=2.0, fresh_reset=False, moving_reentry=True,
            transit_speed_m_s=2.2, eval_after_s=4.0,
        ),
        base_spec(
            "T3A_stale_d20_moving_mcnn", "T3A", trajectory="stale_reentry", arm="mcnn_takeover",
            stale_distance_m=2.0, fresh_reset=False, moving_reentry=True,
            transit_speed_m_s=2.2, eval_after_s=4.0,
        ),
    ])

    # T3-B: Mid-flight reference freeze/gap sweep at dynamic U-turn entry (yaw = +90 deg aligned)
    t3b_base = dict(
        trajectory="tight_turn_brake",
        speed_m_s=3.4,
        t_accel_s=1.8,
        t_turn_start_s=2.6,
        turn_radius_m=3.0,
        t_brake_s=4.5,
        t_decel_s=1.4,
        tau_sw_s=2.75,
        eval_after_s=4.0,
    )
    specs.extend([
        base_spec("T3B_gap_classic", "T3B", arm="classic_keep", ref_gap_ms=0.0, **t3b_base),
        base_spec("T3B_gap_0ms", "T3B", arm="mcnn_takeover", ref_gap_ms=0.0, **t3b_base),
        base_spec("T3B_gap_80ms", "T3B", arm="mcnn_takeover", ref_gap_ms=80.0, **t3b_base),
        base_spec("T3B_gap_160ms", "T3B", arm="mcnn_takeover", ref_gap_ms=160.0, **t3b_base),
        base_spec("T3B_gap_240ms", "T3B", arm="mcnn_takeover", ref_gap_ms=240.0, **t3b_base),
    ])

    # T3-C: Ignored Yaw Reference (NED yaw = 0 deg default North takeoff vs NED yaw = +90 deg ENU-aligned)
    # 1) Static hover at yaw=0 deg (directly contrasted with V0_obs_relay0_hover at yaw=+90 deg)
    # 2) Dynamic tight turn at yaw=0 deg (directly contrasted with T1_turn_w0_mcnn at yaw=+90 deg, identical v=4.2, R=3.5)
    specs.extend([
        base_spec(
            "T3C_yaw0_hover_classic", "T3C", arm="classic_keep", yaw_ref_deg=0.0,
            trajectory="hover", tau_sw_s=1.0, eval_after_s=4.0,
        ),
        base_spec(
            "T3C_yaw0_hover_mcnn", "T3C", arm="mcnn_takeover", yaw_ref_deg=0.0,
            trajectory="hover", tau_sw_s=1.0, eval_after_s=4.0,
        ),
        base_spec(
            "T3C_yaw0_turn_classic", "T3C", arm="classic_keep", yaw_ref_deg=0.0, **turn_3arm
        ),
        base_spec(
            "T3C_yaw0_turn_mcnn", "T3C", arm="mcnn_takeover", yaw_ref_deg=0.0, **turn_3arm
        ),
    ])

    # =========================================================================
    # T4: Control Authority Delivery Anomaly (yaw = +90 deg, tight-turn roll arrest hold sweep)
    # Full-scale body-roll arrest differential (-800 rad/s) on tight_turn_brake (v=4.2, R=3.5).
    # =========================================================================
    specs.extend([
        base_spec("T4_turn_classic", "T4", arm="classic_keep", hold_duration_ms=0.0, **turn_3arm),
        base_spec("T4_turn_hold0", "T4", arm="mcnn_takeover", hold_duration_ms=0.0, **turn_3arm),
        base_spec("T4_turn_hold40", "T4", arm="mcnn_takeover", hold_duration_ms=40.0, **turn_3arm),
        base_spec("T4_turn_hold80", "T4", arm="mcnn_takeover", hold_duration_ms=80.0, **turn_3arm),
        base_spec("T4_turn_hold120", "T4", arm="mcnn_takeover", hold_duration_ms=120.0, **turn_3arm),
        base_spec("T4_turn_hold160", "T4", arm="mcnn_takeover", hold_duration_ms=160.0, **turn_3arm),
    ])

    # =========================================================================
    # ATTR: Compound Failure & 4-Step Counterfactual Attribution Ladder (yaw = +90 deg)
    # Roll-bank exit (v=2.8, a_lat=9.5, T1) + 0.40 kg CoM payload (T2) + 240 ms freeze (T3) + 120 ms hold (T4).
    # All 5 runs share the EXACT same physical vehicle (+0.40 kg CoM) and identical yaw=+90 deg pre-switch prefix.
    # Step 3 uses the explicitly labeled counterfactual steady collective trim probe (cf_probe, mode=steady).
    # Steps 4 & 2 also serve as T2-Disturbance-Turn (banked turn + CoM payload under native MCNN vs Classic).
    # =========================================================================
    attr_kin = dict(
        trajectory="roll_bank_exit",
        speed_m_s=2.8,
        t_accel_s=1.8,
        t_bank_start_s=2.4,
        t_bank_peak_s=2.95,
        a_lat_peak_m_s2=9.5,
        t_rev_s=0.80,
        t_decel_s=1.6,
        tau_sw_s=2.88,
        eval_after_s=3.5,
    )
    attr_payload = dict(
        payload_mass_kg=0.40,
        payload_offset_xyz=[0.022, 0.018, 0.0],
    )
    specs.extend([
        base_spec(
            "ATTR_step0_compound", "ATTR", arm="mcnn_takeover",
            ref_gap_ms=240.0, hold_duration_ms=120.0, **attr_kin, **attr_payload
        ),
        base_spec(
            "ATTR_step1_strip_t4", "ATTR", arm="mcnn_takeover",
            ref_gap_ms=240.0, hold_duration_ms=0.0, **attr_kin, **attr_payload
        ),
        base_spec(
            "ATTR_step2_strip_t4_t3", "ATTR", arm="mcnn_takeover",
            ref_gap_ms=0.0, hold_duration_ms=0.0, **attr_kin, **attr_payload
        ),
        base_spec(
            "ATTR_step3_strip_t4_t3_t2", "ATTR", arm="mcnn_takeover",
            px4_variant="cf_probe", cf_trim_tau_s=-1.0, cf_trim_mode="steady",
            cf_nom_hover_u=CF_NOM_HOVER_U,
            ref_gap_ms=0.0, hold_duration_ms=0.0, **attr_kin, **attr_payload
        ),
        base_spec(
            "ATTR_step4_classic", "ATTR", arm="classic_keep",
            ref_gap_ms=0.0, hold_duration_ms=0.0, **attr_kin, **attr_payload
        ),
    ])

    return specs


def quick_summary(out_dir: Path, spec: dict[str, Any]) -> str:
    meta = json.loads((out_dir / "run_meta.json").read_text(encoding="utf-8"))
    if not meta.get("ulog_path"):
        return "NO ULOG"
    u = ULog(meta["ulog_path"])
    lp = [ds.data for ds in u.data_list if ds.name == "vehicle_local_position" and ds.multi_id == 0][0]
    att = [ds.data for ds in u.data_list if ds.name == "vehicle_attitude" and ds.multi_id == 0][0]
    t_sw = meta["events"]["t_sw_cmd_ms"] / 1000.0
    eval_s = float(spec.get("eval_after_s", 4.0))
    tlp, tatt = lp["timestamp"] / 1e6, att["timestamp"] / 1e6
    m = (tlp >= t_sw) & (tlp <= t_sw + eval_s)
    ma = (tatt >= t_sw) & (tatt <= t_sw + eval_s)
    h = -lp["z"][m]
    dh_loss = max(0.0, float(h[0] - h.min())) * 100.0 if len(h) else float("nan")
    q0, q1, q2, q3 = att["q[0]"][ma], att["q[1]"][ma], att["q[2]"][ma], att["q[3]"][ma]
    tilt = np.degrees(np.arccos(np.clip(1.0 - 2.0 * (q1 * q1 + q2 * q2), -1.0, 1.0)))
    yaw = np.degrees(np.arctan2(2.0 * (q0 * q3 + q1 * q2), 1.0 - 2.0 * (q2 * q2 + q3 * q3)))
    tilt0 = float(tilt[0]) if len(tilt) else float("nan")
    yaw0 = float(yaw[0]) if len(yaw) else float("nan")
    v0 = float(np.hypot(np.interp(t_sw, tlp, lp["vx"]), np.interp(t_sw, tlp, lp["vy"])))
    min_vz = float((-lp["vz"][m]).min()) if len(h) else float("nan")
    return (
        f"entry(v={v0:.2f}m/s, yaw={yaw0:.1f}deg, tilt={tilt0:.1f}deg, h={h[0]:.2f}m) -> "
        f"max_tilt={tilt.max():.1f}deg, alt_loss={dh_loss:.1f}cm, "
        f"min_vz={min_vz:.2f}m/s, early={meta['events'].get('early_stop_reason')}, "
        f"landed={meta['events'].get('landed_disarmed')}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--groups", nargs="*", default=None, help="Filter by group names (e.g. T1 T2)")
    parser.add_argument("--runs", nargs="*", default=None, help="Filter by specific run_ids")
    parser.add_argument("--skip-existing", action="store_true", help="Skip runs that already have run_meta.json")
    args = parser.parse_args()

    all_specs = build_campaign_specs()
    CAMPAIGN_ROOT.mkdir(parents=True, exist_ok=True)
    (CAMPAIGN_ROOT / "campaign_specs.json").write_text(json.dumps(all_specs, indent=2), encoding="utf-8")

    selected = all_specs
    if args.groups:
        gset = set(args.groups)
        selected = [s for s in selected if s["group"] in gset]
    if args.runs:
        rset = set(args.runs)
        selected = [s for s in selected if s["run_id"] in rset]

    print(f"Running {len(selected)}/{len(all_specs)} campaign runs into {CAMPAIGN_ROOT}", flush=True)
    t_all = time.monotonic()
    failures = []
    for idx, spec in enumerate(selected, 1):
        rid = spec["run_id"]
        out = CAMPAIGN_ROOT / rid
        if args.skip_existing and (out / "run_meta.json").exists():
            print(f"[{idx}/{len(selected)}] SKIP {rid}: {quick_summary(out, spec)}", flush=True)
            continue
        out.mkdir(parents=True, exist_ok=True)
        # Clean stale artifacts if overwriting an existing run dir
        for stale in list(out.rglob("*.ulg")) + [out / "mcnn_obs.csv", out / "relay_step.csv", out / "relay_rx.csv", out / "run_meta.json"]:
            if stale.exists():
                stale.unlink()
        sp = out / "spec.json"
        sp.write_text(json.dumps(spec, indent=2), encoding="utf-8")
        t0 = time.monotonic()
        r = subprocess.run(
            [str(PYTHON_BIN), str(RUNNER_SCRIPT), "--spec", str(sp), "--out", str(out)],
            capture_output=True,
            text=True,
        )
        dt = time.monotonic() - t0
        if r.returncode != 0:
            print(f"[{idx}/{len(selected)}] FAIL {rid} ({dt:.1f}s): {r.stderr[-400:]}", flush=True)
            failures.append(rid)
        else:
            print(f"[{idx}/{len(selected)}] OK   {rid} ({dt:.1f}s): {quick_summary(out, spec)}", flush=True)

    print(f"Done in {time.monotonic() - t_all:.1f}s. Failures: {failures}", flush=True)
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()

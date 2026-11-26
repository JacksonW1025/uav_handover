#!/usr/bin/env python3
"""Master single-seed campaign runner for PX4 official mc_nn_control C -> N handover experiments."""

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


def base_spec(run_id: str, group: str, **kwargs: Any) -> dict[str, Any]:
    s = {
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
    }
    s.update(kwargs)
    return s


def build_campaign_specs() -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []

    # --- T1: Physical & Environmental Margin Depletion ---
    # 1) Tight banked turn 3-arm comparison (separates transient handover shock vs policy envelope)
    turn_3arm = dict(
        trajectory="tight_turn_brake",
        speed_m_s=3.6,
        t_accel_s=2.0,
        t_turn_start_s=2.6,
        turn_radius_m=3.5,
        t_brake_s=4.4,
        t_decel_s=1.5,
        tau_sw_s=4.0,
        eval_after_s=4.0,
    )
    specs.extend([
        base_spec("T1_turn_w0_classic", "T1", arm="classic_keep", **turn_3arm),
        base_spec("T1_turn_w0_mcnn", "T1", arm="mcnn_takeover", **turn_3arm),
        base_spec("T1_turn_w0_preentered", "T1", arm="mcnn_preentered", **turn_3arm),
    ])

    # 2) Environmental crosswind-margin sweep on moderate banked turn braking (pure outward/lateral crosswind
    # perpendicular to initial North leg: strictly loads roll/lateral margin without assisting forward braking)
    turn_wind = dict(
        trajectory="tight_turn_brake",
        speed_m_s=2.9,
        t_accel_s=2.0,
        t_turn_start_s=2.6,
        turn_radius_m=3.8,
        t_brake_s=4.4,
        t_decel_s=1.5,
        tau_sw_s=3.9,
        eval_after_s=4.0,
    )
    # Opposing wind along (-0.84, -0.54, 0) ENU at 0 -> 7.0 -> 8.0 m/s strictly degrades margin
    specs.extend([
        base_spec("T1_wind_w0_classic", "T1W", arm="classic_keep", **turn_wind),
        base_spec("T1_wind_w0_mcnn", "T1W", arm="mcnn_takeover", **turn_wind),
        base_spec(
            "T1_wind_w70_mcnn", "T1W", arm="mcnn_takeover",
            wind_enu=[-5.88, -3.78, 0.0], wind_drag_quad=0.08, **turn_wind
        ),
        base_spec(
            "T1_wind_w80_classic", "T1W", arm="classic_keep",
            wind_enu=[-6.72, -4.32, 0.0], wind_drag_quad=0.08, **turn_wind
        ),
        base_spec(
            "T1_wind_w80_mcnn", "T1W", arm="mcnn_takeover",
            wind_enu=[-6.72, -4.32, 0.0], wind_drag_quad=0.08, **turn_wind
        ),
    ])

    # 3) High-speed straight braking (exposes missing velocity feedforward: hard brake then lag/flip)
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

    # --- T2: Memoryless Feedforward == Cleared Memory ---
    # Benign nominal straight cruise (v=1.8 m/s) serves as both T1-Benign & T2 wind=0 baseline.
    nom_base = dict(
        trajectory="straight_cruise",
        speed_m_s=1.8,
        t_accel_s=2.0,
        tau_sw_s=4.0,
        eval_after_s=4.0,
    )
    specs.extend([
        base_spec("T2_nom_classic", "T2", arm="classic_keep", **nom_base),
        base_spec("T2_nom_mcnn", "T2", arm="mcnn_takeover", **nom_base),
        base_spec(
            "T2_wind50_mcnn", "T2", arm="mcnn_takeover",
            wind_enu=[0.0, -5.0, 0.0], wind_drag_quad=0.08, **nom_base
        ),
        base_spec(
            "T2_wind80_classic", "T2", arm="classic_keep",
            wind_enu=[0.0, -8.0, 0.0], wind_drag_quad=0.08, **nom_base
        ),
        base_spec(
            "T2_wind80_mcnn", "T2", arm="mcnn_takeover",
            wind_enu=[0.0, -8.0, 0.0], wind_drag_quad=0.08, **nom_base
        ),
        base_spec(
            "T2_com35_classic", "T2", arm="classic_keep",
            payload_mass_kg=0.35, payload_offset_xyz=[0.025, 0.020, 0.0], **nom_base
        ),
        base_spec(
            "T2_com35_mcnn", "T2", arm="mcnn_takeover",
            payload_mass_kg=0.35, payload_offset_xyz=[0.025, 0.020, 0.0], **nom_base
        ),
        base_spec(
            "T2_com50_mcnn", "T2", arm="mcnn_takeover",
            payload_mass_kg=0.50, payload_offset_xyz=[0.035, 0.028, 0.0], **nom_base
        ),
        base_spec(
            "T2_cf_probe_com35", "T2",
            px4_variant="cf_probe", cf_trim_tau_s=0.30, cf_trim_mode="bumpless_steady",
            arm="mcnn_takeover",
            payload_mass_kg=0.35, payload_offset_xyz=[0.025, 0.020, 0.0], **nom_base
        ),
    ])

    # --- T3: Setpoint Reference Continuity Anomaly ---
    # T3-A: Cross-mode re-entry stale target retention
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

    # T3-B: Mid-flight reference gap/freeze sweep at dynamic U-turn entry (v=3.4 m/s, R=3.0 m)
    # During [t_sw, t_sw + ref_gap_ms], reference curves sharply into the turn while MCNN brakes
    # toward the frozen entry point; upon resume, MCNN whips into a monotonic brake-then-chase recovery.
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

    # --- T4: Control Authority Delivery Anomaly (Roll-Bank Exit Hold Sweep) ---
    roll_base = dict(
        trajectory="roll_bank_exit",
        speed_m_s=2.8,
        t_accel_s=1.8,
        t_bank_start_s=2.5,
        t_bank_peak_s=3.10,
        a_lat_peak_m_s2=8.5,
        t_rev_s=0.85,
        t_decel_s=1.8,
        tau_sw_s=3.05,
        eval_after_s=3.5,
    )
    specs.extend([
        base_spec("T4_roll_classic", "T4", arm="classic_keep", hold_duration_ms=0.0, **roll_base),
        base_spec("T4_roll_hold0", "T4", arm="mcnn_takeover", hold_duration_ms=0.0, **roll_base),
        base_spec("T4_roll_hold24", "T4", arm="mcnn_takeover", hold_duration_ms=24.0, **roll_base),
        base_spec("T4_roll_hold40", "T4", arm="mcnn_takeover", hold_duration_ms=40.0, **roll_base),
        base_spec("T4_roll_hold60", "T4", arm="mcnn_takeover", hold_duration_ms=60.0, **roll_base),
        base_spec("T4_roll_hold80", "T4", arm="mcnn_takeover", hold_duration_ms=80.0, **roll_base),
    ])

    # --- ATTR: Compound Failure & 4-Step Counterfactual Attribution Ladder ---
    # Banked roll_bank_exit + 0.42 kg CoM payload offset + 240 ms reference freeze + 60 ms stale motor hold.
    # All 5 runs share the EXACT same physical vehicle (+0.42 kg CoM offset) and identical pre-switch prefix.
    # Step 3 uses the explicitly labeled counterfactual steady shadow-trim probe (cf_probe, mode=steady),
    # which estimates u_C_hover - u_N(pos_err=0) online during pre-maneuver hover to isolate T2's missing
    # steady mass/CoM trim memory while leaving the dynamic roll maneuver intact.
    # Steps 4 & 2 also serve as T2-Disturbance-Turn (native MCNN vs Classic-Keep under banked disturbance).
    attr_kin = dict(
        trajectory="roll_bank_exit",
        speed_m_s=2.6,
        t_accel_s=1.8,
        t_bank_start_s=2.5,
        t_bank_peak_s=3.10,
        a_lat_peak_m_s2=7.2,
        t_rev_s=0.85,
        t_decel_s=1.8,
        tau_sw_s=3.05,
        eval_after_s=3.5,
    )
    attr_payload = dict(
        payload_mass_kg=0.42,
        payload_offset_xyz=[0.022, 0.018, 0.0],
    )
    specs.extend([
        base_spec(
            "ATTR_step0_compound", "ATTR", arm="mcnn_takeover",
            ref_gap_ms=240.0, hold_duration_ms=60.0, **attr_kin, **attr_payload
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
    q1, q2 = att["q[1]"][ma], att["q[2]"][ma]
    tilt = np.degrees(np.arccos(np.clip(1.0 - 2.0 * (q1 * q1 + q2 * q2), -1.0, 1.0)))
    tilt0 = float(tilt[0]) if len(tilt) else float("nan")
    v0 = float(np.hypot(np.interp(t_sw, tlp, lp["vx"]), np.interp(t_sw, tlp, lp["vy"])))
    min_vz = float((-lp["vz"][m]).min()) if len(h) else float("nan")
    return (
        f"entry(v={v0:.2f}m/s, tilt={tilt0:.1f}deg, h={h[0]:.2f}m) -> "
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

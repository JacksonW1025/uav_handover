#!/usr/bin/env python3
"""Offline verification for Crazyflie 2.1 T1-T4 handover evidence (69 runs)."""

import csv
import gzip
import hashlib
import json
import math
from pathlib import Path

BASE = Path(__file__).resolve().parent


def read_json(path: Path):
    return json.loads(path.read_text())


def read_trace(name: str):
    path = BASE / "traces" / name
    with gzip.open(path, "rt", newline="") as stream:
        return list(csv.DictReader(stream))


def near(actual: float, expected: float, tol: float):
    assert math.isclose(actual, expected, rel_tol=0.0, abs_tol=tol), (actual, expected, tol)


def find_run(rows, case_id: str, arm_substr: str):
    matches = [r for r in rows if r["case_id"] == case_id and arm_substr in r["arm_name"]]
    assert len(matches) == 1, (case_id, arm_substr, len(matches))
    return matches[0]


def verify_manifest():
    manifest = read_json(BASE / "manifest.json")
    assert manifest["total_runs"] == 69
    assert manifest["figure_count"] == 5
    assert manifest["trace_count"] == 64
    for rel, meta in manifest["files"].items():
        path = BASE / rel
        assert path.exists(), f"Missing archived file: {path}"
        raw = path.read_bytes()
        assert len(raw) == meta["bytes"], (rel, len(raw), meta["bytes"])
        assert hashlib.sha256(raw).hexdigest() == meta["sha256"], f"SHA-256 mismatch: {rel}"
    return manifest


def verify_summary_and_traces():
    rows = read_json(BASE / "summary.json")
    assert len(rows) == 69

    # T1: Tight turn + tailwind sweep
    t1_c0 = find_run(rows, "t1_turn_wx0.0", "Classic-Keep")
    t1_n0 = find_run(rows, "t1_turn_wx0.0", "NN-Ideal-Takeover")
    t1_n14 = find_run(rows, "t1_turn_wx1.4", "NN-Ideal-Takeover")
    t1_n18 = find_run(rows, "t1_turn_wx1.8", "NN-Ideal-Takeover")
    near(t1_c0["peak_tilt_deg"], 18.397, 0.01)
    near(t1_n0["peak_tilt_deg"], 46.384, 0.01)
    near(t1_n0["max_alt_loss_cm"], 40.394, 0.05)
    near(t1_n14["peak_tilt_deg"], 47.734, 0.01)
    near(t1_n14["max_alt_loss_cm"], 51.231, 0.05)
    near(t1_n18["peak_tilt_deg"], 48.413, 0.01)
    near(t1_n18["max_alt_loss_cm"], 55.564, 0.05)

    # T2: Cold reset (l2f_reset) and rlt.orig=-0.8 poisoning
    t2_warm = find_run(rows, "t2_straight_com5.3", "NN-Warm-Shadow")
    t2_cold = find_run(rows, "t2_straight_com5.3", "NN-Cold-Reset")
    t2_pois = find_run(rows, "t2_straight_com5.3", "NN-Orig-Poison")
    near(t2_warm["max_alt_loss_cm"], 15.859, 0.05)
    near(t2_cold["max_alt_loss_cm"], 54.289, 0.05)
    near(t2_pois["max_alt_loss_cm"], 67.600, 0.05)
    assert t2_warm["first_motor_jump"] < t2_cold["first_motor_jump"] < t2_pois["first_motor_jump"]

    t2_turn_warm = find_run(rows, "t2_turn_com4.8", "NN-Warm-Shadow")
    t2_turn_pois = find_run(rows, "t2_turn_com4.8", "NN-Orig-Poison")
    assert not t2_turn_warm["crashed"]
    assert t2_turn_pois["crashed"]
    near(t2_turn_pois["max_speed_xy"], 2.5763, 0.01)

    # T3: Reference gap (straight + 168 ms aligned U-turn)
    t3_s0 = find_run(rows, "t3_straight", "NN-Gap-0ms")
    t3_s180 = find_run(rows, "t3_straight", "NN-Gap-180ms")
    t3_s260 = find_run(rows, "t3_straight", "NN-Gap-260ms")
    assert t3_s0["peak_tilt_deg"] < t3_s180["peak_tilt_deg"] < t3_s260["peak_tilt_deg"]
    near(t3_s180["peak_tilt_deg"], 30.423, 0.01)
    near(t3_s260["max_alt_loss_cm"], 28.246, 0.05)

    t3_t0 = find_run(rows, "t3_turn", "NN-Gap-0ms")
    t3_t168 = find_run(rows, "t3_turn", "NN-Gap-168ms")
    t3_t220 = find_run(rows, "t3_turn", "NN-Gap-220ms")
    near(t3_t0["peak_tilt_deg"], 32.184, 0.01)
    near(t3_t168["peak_tilt_deg"], 40.838, 0.01)
    near(t3_t168["max_alt_loss_cm"], 42.376, 0.05)
    near(t3_t220["peak_tilt_deg"], 43.151, 0.01)
    near(t3_t220["max_alt_loss_cm"], 55.611, 0.05)

    # T4: Warmup vacuum (T4-A) + turn-exit stale hold (T4-B)
    t4_w500 = find_run(rows, "t4_warmup", "NN-Warmup-500ms")
    near(t4_w500["min_vz"], -2.6172, 0.01)
    near(t4_w500["max_alt_loss_cm"], 173.199, 0.05)

    holds = [find_run(rows, "t4_turn_exit", f"NN-StaleHold-{ms}ms") for ms in (0, 16, 24, 40, 60)]
    tilts = [r["peak_tilt_deg"] for r in holds]
    assert tilts == sorted(tilts), tilts
    near(tilts[0], 28.725, 0.01)
    near(tilts[2], 39.112, 0.01)
    near(tilts[-1], 50.834, 0.01)

    # 4-step counterfactual attribution staircase
    steps = [
        (find_run(rows, "cf_attribution", f"{idx}."), f"cf_attr_step{idx}.csv.gz")
        for idx in range(5)
    ]
    assert [s[0]["crashed"] for s in steps] == [True, True, True, False, False]
    near(steps[0][0]["peak_tilt_deg"], 85.158, 0.02)
    near(steps[3][0]["peak_tilt_deg"], 25.391, 0.02)
    near(steps[4][0]["peak_tilt_deg"], 25.501, 0.02)

    # Cross-check sampled trace CSVs against summary.json (traces logged at 500 Hz / 2 ms,
    # whereas summary.json records the exact 1000 Hz / 1 ms peak, including final crash tick)
    sample_checks = [
        ("t1_turn_wx0.0_neural.csv.gz", t1_n0, 0.25),
        ("t1_turn_wx1.4_neural.csv.gz", t1_n14, 0.25),
        ("t2_straight_com5.3_poison.csv.gz", t2_pois, 0.25),
        ("cf_attr_step0.csv.gz", steps[0][0], 1.0),
        ("cf_attr_step3.csv.gz", steps[3][0], 0.25),
    ]
    for trace_name, row, tol in sample_checks:
        trace = read_trace(trace_name)
        post = [x for x in trace if float(x["t_s"]) >= row["t_sw"] - 1e-6]
        assert post, trace_name
        trace_peak_tilt = max(float(x["tilt_deg"]) for x in post)
        assert trace_peak_tilt <= row["peak_tilt_deg"] + 1e-3, (trace_name, trace_peak_tilt, row["peak_tilt_deg"])
        near(trace_peak_tilt, row["peak_tilt_deg"], tol)


def main():
    verify_manifest()
    verify_summary_and_traces()
    print("Crazyflie 2.1 · 69 runs, 5 figures, 64 gzipped traces, T1-T4 and 5-step attribution verified")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Completely offline verification gate for PX4 mc_nn_control handover evidence.
Checks:
  Gate 1: Pre-switch twin-prefix consistency (|dpos_xy|<0.05m, |dh|<0.03m, |dv_xy|<0.05m/s, |dtilt|<0.5deg)
  Gate 2: Mode authority & flight outcome integrity (nav_state / failsafe / crash alignment)
  Gate 3: Single-source offline recomputation from traces/*.csv.gz matches metrics.json (<1e-6)
          AND all files match manifest.sha256.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

from metrics_core import compute_run_metrics, load_trace_gz

EVIDENCE_DIR = Path(__file__).resolve().parent.parent
TRACES_DIR = EVIDENCE_DIR / "traces"

# Twin comparison groups: (group_name, reference_run_id, [twin_run_ids])
TWIN_GROUPS = [
    ("T1_turn_w0", "T1_turn_w0_classic", ["T1_turn_w0_mcnn"]),
    ("T1_wind_w0", "T1_wind_w0_classic", ["T1_wind_w0_mcnn"]),
    ("T1_wind_w80", "T1_wind_w80_classic", ["T1_wind_w80_mcnn"]),
    ("T1_straight_brake", "T1_straight_brake_classic", ["T1_straight_brake_mcnn"]),
    ("T2_nom", "T2_nom_classic", ["T2_nom_mcnn"]),
    ("T2_wind80", "T2_wind80_classic", ["T2_wind80_mcnn"]),
    ("T2_com35", "T2_com35_classic", ["T2_com35_mcnn", "T2_cf_probe_com35"]),
    ("T3A_d20_moving", "T3A_stale_d20_moving_classic", ["T3A_stale_d20_moving_mcnn"]),
    (
        "T3B_gap_sweep",
        "T3B_gap_classic",
        ["T3B_gap_0ms", "T3B_gap_80ms", "T3B_gap_160ms", "T3B_gap_240ms"],
    ),
    (
        "T4_roll_hold_sweep",
        "T4_roll_classic",
        ["T4_roll_hold0", "T4_roll_hold24", "T4_roll_hold40", "T4_roll_hold60", "T4_roll_hold80"],
    ),
    (
        "ATTR_ladder",
        "ATTR_step4_classic",
        [
            "ATTR_step0_compound",
            "ATTR_step1_strip_t4",
            "ATTR_step2_strip_t4_t3",
            "ATTR_step3_strip_t4_t3_t2",
        ],
    ),
]

THRESH_XY_M = 0.05
THRESH_H_M = 0.03
THRESH_VXY_M_S = 0.05
THRESH_TILT_DEG = 0.50


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def compare_nested(a: Any, b: Any, path: str, errs: list[str], tol: float = 1e-6) -> None:
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a.keys()) != set(b.keys()):
            errs.append(f"Key mismatch at {path}: {set(a.keys()) ^ set(b.keys())}")
            return
        for k in a:
            compare_nested(a[k], b[k], f"{path}.{k}", errs, tol)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            errs.append(f"Length mismatch at {path}: {len(a)} vs {len(b)}")
            return
        for i, (x, y) in enumerate(zip(a, b)):
            compare_nested(x, y, f"{path}[{i}]", errs, tol)
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        if math.isnan(a) and math.isnan(b):
            return
        if math.isnan(a) != math.isnan(b) or abs(float(a) - float(b)) > tol:
            errs.append(f"Numeric mismatch at {path}: stored={a} vs recomputed={b}")
    else:
        if a != b:
            errs.append(f"Value mismatch at {path}: stored={a} vs recomputed={b}")


def main() -> None:
    metrics_doc = json.loads((EVIDENCE_DIR / "metrics.json").read_text(encoding="utf-8"))
    runs: dict[str, Any] = metrics_doc["runs"]

    all_ok = True

    # === GATE 3A: Offline single-source recomputation from traces/*.csv.gz ===
    print("=== Gate 3A: Single-source offline recomputation (traces/*.csv.gz -> metrics.json) ===")
    recomp_errs: list[str] = []
    for rid, stored in sorted(runs.items()):
        tpath = TRACES_DIR / f"{rid}.csv.gz"
        if not tpath.exists():
            recomp_errs.append(f"Missing trace file: {tpath}")
            continue
        meta, data = load_trace_gz(tpath)
        recomp = compute_run_metrics(meta, data)
        # JSON round-trip normalizes NaN handling identically
        recomp_rt = json.loads(json.dumps(recomp))
        compare_nested(stored, recomp_rt, rid, recomp_errs, tol=1e-6)
    if recomp_errs:
        all_ok = False
        print(f"FAIL: {len(recomp_errs)} recomputation mismatches:")
        for e in recomp_errs[:20]:
            print("  ", e)
    else:
        print(f"PASS: All {len(runs)} runs recomputed offline with max numerical error < 1e-6.")

    # === GATE 1: Pre-switch twin-prefix consistency ===
    print("\n=== Gate 1: Pre-switch twin-prefix consistency ===")
    prefix_errs: list[str] = []
    for gname, ref_id, twins in TWIN_GROUPS:
        if ref_id not in runs:
            prefix_errs.append(f"Missing reference run {ref_id} for group {gname}")
            continue
        ref = runs[ref_id]["entry"]
        for tid in twins:
            if tid not in runs:
                prefix_errs.append(f"Missing twin run {tid} for group {gname}")
                continue
            cur = runs[tid]["entry"]
            dxy = math.hypot(cur["x_m"] - ref["x_m"], cur["y_m"] - ref["y_m"])
            dh = abs(cur["h_m"] - ref["h_m"])
            dv = abs(cur["v_xy_m_s"] - ref["v_xy_m_s"])
            dtilt = abs(cur["tilt_deg"] - ref["tilt_deg"])
            ok = (
                dxy < THRESH_XY_M
                and dh < THRESH_H_M
                and dv < THRESH_VXY_M_S
                and dtilt < THRESH_TILT_DEG
            )
            status = "PASS" if ok else "FAIL"
            print(
                f"  [{status}] {gname}: {tid} vs {ref_id} | "
                f"dxy={dxy:.4f}m (<{THRESH_XY_M}), dh={dh:.4f}m (<{THRESH_H_M}), "
                f"dv={dv:.4f}m/s (<{THRESH_VXY_M_S}), dtilt={dtilt:.3f}deg (<{THRESH_TILT_DEG})"
            )
            if not ok:
                prefix_errs.append(
                    f"{gname} {tid}: dxy={dxy:.4f}, dh={dh:.4f}, dv={dv:.4f}, dtilt={dtilt:.3f}"
                )
    if prefix_errs:
        all_ok = False

    # === GATE 2: Mode authority & outcome integrity ===
    print("\n=== Gate 2: Mode authority & outcome integrity ===")
    mode_errs: list[str] = []
    for rid, r in sorted(runs.items()):
        out = r["outcome"]
        if r["arm"] == "classic_keep" and out["status"] != "LANDED_CLEAN":
            mode_errs.append(f"Classic Oracle {rid} did not finish cleanly: {out}")
        if out["status"] != "LANDED_CLEAN":
            if out["event_t_rel_s"] is None:
                mode_errs.append(f"Non-clean run {rid} missing exact event_t_rel_s: {out}")
            print(
                f"  [EVENT] {rid}: {out['status']} @ t_rel={out['event_t_rel_s']}s "
                f"(nav={out['event_nav_state']}): {out['detail']}"
            )
    if mode_errs:
        all_ok = False
        print("FAIL: Mode/Oracle integrity errors:")
        for e in mode_errs:
            print("  ", e)
    else:
        print("PASS: All Classic Oracles finished LANDED_CLEAN and all anomaly/crash events are explicitly timestamped.")

    # === GATE 3B: SHA-256 manifest integrity ===
    print("\n=== Gate 3B: SHA-256 manifest verification ===")
    manifest_path = EVIDENCE_DIR / "manifest.sha256"
    sha_errs: list[str] = []
    if not manifest_path.exists():
        sha_errs.append("Missing manifest.sha256")
    else:
        lines = [ln.strip() for ln in manifest_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        checked = 0
        for ln in lines:
            expected_sha, rel = ln.split(None, 1)
            fp = EVIDENCE_DIR / rel
            if not fp.exists():
                sha_errs.append(f"Manifest file missing: {rel}")
                continue
            actual_sha = sha256_file(fp)
            if actual_sha != expected_sha:
                sha_errs.append(f"SHA-256 mismatch for {rel}: {actual_sha} != {expected_sha}")
            checked += 1
        # Check no unlisted files exist in evidence dir
        listed = {ln.split(None, 1)[1] for ln in lines}
        for p in sorted(EVIDENCE_DIR.rglob("*")):
            if "__pycache__" in p.parts or p.suffix == ".pyc":
                continue
            if p.is_file() and p.name != "manifest.sha256":
                rel = p.relative_to(EVIDENCE_DIR).as_posix()
                if rel not in listed:
                    sha_errs.append(f"Unlisted file not in manifest.sha256: {rel}")
        if not sha_errs:
            print(f"PASS: All {checked} files match manifest.sha256.")
    if sha_errs:
        all_ok = False
        print(f"FAIL: {len(sha_errs)} manifest errors:")
        for e in sha_errs[:20]:
            print("  ", e)

    print("\n" + ("ALL VERIFICATION GATES PASSED" if all_ok else "VERIFICATION FAILED"))
    if not all_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()

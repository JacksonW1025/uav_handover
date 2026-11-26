#!/usr/bin/env python3
import csv
import gzip
import json
import os
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

BASE_DIR = Path(__file__).resolve().parents[1]
RES_DIR = str(BASE_DIR)
TR_DIR = str(BASE_DIR / "traces")
ART_DIR = str(BASE_DIR / "figures")
os.makedirs(ART_DIR, exist_ok=True)

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
    "axes.edgecolor": "#334155",
    "axes.linewidth": 0.9,
    "axes.grid": True,
    "grid.color": "#e2e8f0",
    "grid.linestyle": "--",
    "grid.linewidth": 0.6,
    "axes.titlesize": 11,
    "axes.titleweight": "bold",
    "axes.labelsize": 9.5,
    "xtick.labelsize": 8.5,
    "ytick.labelsize": 8.5,
    "legend.fontsize": 8.2,
    "figure.facecolor": "white",
    "axes.facecolor": "#fcfdff",
})

C_CLASSIC = "#0f766e"   # Deep teal
C_IDEAL   = "#2563eb"   # Royal blue
C_WARN    = "#d97706"   # Amber
C_FAULT   = "#dc2626"   # Crimson
C_SEVERE  = "#7f1d1d"   # Dark maroon
C_REF     = "#64748b"   # Slate gray

def load_trace(name):
    path = os.path.join(TR_DIR, name)
    gz_path = path + ".gz"
    cols = {}
    if os.path.exists(path):
        opener = open(path, "r")
    elif os.path.exists(gz_path):
        opener = gzip.open(gz_path, "rt")
    else:
        raise FileNotFoundError(f"Trace not found: {path} or {gz_path}")
    with opener as f:
        reader = csv.DictReader(f)
        for row in reader:
            for k, v in row.items():
                cols.setdefault(k, []).append(float(v))
    return {k: np.array(v) for k, v in cols.items()}

with open(os.path.join(RES_DIR, "summary.json"), "r") as f:
    SUMMARY = json.load(f)

def find_run(case_id, arm_substr):
    for r in SUMMARY:
        if r["case_id"] == case_id and arm_substr in r["arm_name"]:
            return r
    raise KeyError(f"Not found: {case_id} / {arm_substr}")

# -------------------------------------------------------------------------
# 1. Overview Synthesis + 4-Step Counterfactual Attribution
# -------------------------------------------------------------------------
def plot_overview():
    fig = plt.figure(figsize=(14.5, 8.2), dpi=220)
    gs = GridSpec(2, 3, figure=fig, height_ratios=[1.08, 1.0], hspace=0.38, wspace=0.26)

    # Flagship comparisons for T1, T2, T3, T4
    cats = ["T1: Margin\n(J-Turn)", "T2: History\n(CoM+Wind)", "T3: Setpoint\n(168ms Gap)", "T4: Delivery\n(40ms Hold)"]
    r_t1_ck = find_run("t1_turn_wx1.4", "Classic-Keep")
    r_t1_id = find_run("t1_benign_margin", "NN-Ideal")
    r_t1_fl = find_run("t1_turn_wx1.4", "NN-Ideal-Takeover")

    r_t2_ck = find_run("t2_straight_com5.3", "Classic-Keep")
    r_t2_wm = find_run("t2_straight_com5.3", "NN-Warm-Shadow")
    r_t2_fl = find_run("t2_straight_com5.3", "NN-Orig-Poison")

    r_t3_ck = find_run("t3_turn", "Classic-Keep")
    r_t3_wm = find_run("t3_turn", "NN-Gap-0ms")
    r_t3_fl = find_run("t3_turn", "NN-Gap-168ms")

    r_t4_ck = find_run("t4_turn_exit", "Classic-Keep")
    r_t4_wm = find_run("t4_turn_exit", "NN-StaleHold-0ms")
    r_t4_fl = find_run("t4_turn_exit", "NN-StaleHold-40ms")

    tilts = [
        (r_t1_ck["peak_tilt_deg"], r_t1_id["peak_tilt_deg"], r_t1_fl["peak_tilt_deg"]),
        (r_t2_ck["peak_tilt_deg"], r_t2_wm["peak_tilt_deg"], r_t2_fl["peak_tilt_deg"]),
        (r_t3_ck["peak_tilt_deg"], r_t3_wm["peak_tilt_deg"], r_t3_fl["peak_tilt_deg"]),
        (28.7,                     r_t4_wm["peak_tilt_deg"], r_t4_fl["peak_tilt_deg"]),
    ]
    vz_abs = [
        (abs(r_t1_ck["min_vz"]), abs(r_t1_id["min_vz"]), abs(r_t1_fl["min_vz"])),
        (abs(r_t2_ck["min_vz"]), abs(r_t2_wm["min_vz"]), abs(r_t2_fl["min_vz"])),
        (abs(r_t3_ck["min_vz"]), abs(r_t3_wm["min_vz"]), abs(r_t3_fl["min_vz"])),
        (abs(r_t4_ck["min_vz"]), abs(r_t4_wm["min_vz"]), abs(r_t4_fl["min_vz"])),
    ]
    dz_cm = [
        (r_t1_ck["max_alt_loss_cm"], r_t1_id["max_alt_loss_cm"], r_t1_fl["max_alt_loss_cm"]),
        (r_t2_ck["max_alt_loss_cm"], r_t2_wm["max_alt_loss_cm"], r_t2_fl["max_alt_loss_cm"]),
        (r_t3_ck["max_alt_loss_cm"], r_t3_wm["max_alt_loss_cm"], r_t3_fl["max_alt_loss_cm"]),
        (r_t4_ck["max_alt_loss_cm"], r_t4_wm["max_alt_loss_cm"], r_t4_fl["max_alt_loss_cm"]),
    ]

    x = np.arange(4)
    w = 0.25
    panels = [
        (gs[0, 0], tilts, "Peak Tilt Angle (deg)", "A. Tri-Metric Evidence: Peak Tilt", 47.0, "Static TWR Ceiling (47.0 deg)"),
        (gs[0, 1], vz_abs, "Peak Descent Rate |vz_min| (m/s)", "B. Tri-Metric Evidence: Vertical Plunge Speed", None, None),
        (gs[0, 2], dz_cm, "Max Altitude Loss (cm)", "C. Tri-Metric Evidence: Altitude Drop", None, None),
    ]
    for spec, arr, ylabel, title, hline, hlabel in panels:
        ax = fig.add_subplot(spec)
        v0 = [a[0] for a in arr]
        v1 = [a[1] for a in arr]
        v2 = [a[2] for a in arr]
        b0 = ax.bar(x - w, v0, w, color=C_CLASSIC, label="Classic-Keep Oracle")
        b1 = ax.bar(x,     v1, w, color=C_IDEAL,   label="Controlled / Ideal NN Baseline")
        b2 = ax.bar(x + w, v2, w, color=C_FAULT,   label="T1-T4 Triggered NN Handover")
        if hline is not None:
            ax.axhline(hline, color=C_SEVERE, ls=":", lw=1.2, label=hlabel)
        for bars in (b0, b1, b2):
            for bar in bars:
                h = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2, h + max(v2)*0.02, f"{h:.1f}",
                        ha="center", va="bottom", fontsize=7.3, fontweight="bold", color="#1e293b")
        ax.set_xticks(x)
        ax.set_xticklabels(cats, fontsize=8.0)
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.set_ylim(0, max(v2) * (1.38 if spec == gs[0, 0] else 1.24))
        if spec == gs[0, 0]:
            ax.legend(loc="upper right", framealpha=0.92, fontsize=7.3)

    # Bottom row: 4-step Counterfactual Attribution traces + staircase
    ax_tr = fig.add_subplot(gs[1, 0:2])
    attr_files = [
        ("cf_attr_step0.csv", "Step 0: Raw Takeover (T1+T2+T3+T4) [Flip >85° @ 3.78s]", C_SEVERE, "-"),
        ("cf_attr_step1.csv", "Step 1: Strip T4 (-Warmup Vacuum) [CRASH @ 4.55s]", C_FAULT, "--"),
        ("cf_attr_step2.csv", "Step 2: Strip T4+T3 (-168ms Ref Gap) [CRASH @ 4.72s]", C_WARN, "-."),
        ("cf_attr_step3.csv", "Step 3: Strip T4+T3+T2 (Pure T1 Residual) [SURVIVES]", C_IDEAL, "-"),
        ("cf_attr_step4.csv", "Step 4: Classic-Keep Oracle [SURVIVES]", C_CLASSIC, "-"),
    ]
    for fn, lbl, col, ls in attr_files:
        tr = load_trace(fn)
        mask = (tr["t_s"] >= 3.2) & (tr["t_s"] <= 5.6)
        ax_tr.plot(tr["t_s"][mask], tr["z"][mask], color=col, ls=ls, lw=2.1, label=lbl)
        if "step0" in fn:
            ax_tr.scatter([tr["t_s"][mask][-1]], [tr["z"][mask][-1]], color=C_SEVERE, marker="X", s=90, zorder=8)
            ax_tr.annotate("Flip >85°\n(3.78s)", (tr["t_s"][mask][-1], tr["z"][mask][-1]),
                           textcoords="offset points", xytext=(8, -22), fontsize=7.6, fontweight="bold", color=C_SEVERE)
    ax_tr.axvline(3.55, color="#0f172a", ls=":", lw=1.3, label="Handover Trigger t_sw = 3.55s")
    ax_tr.set_title("D. 4-Step Counterfactual Factor Diagnoser: Altitude Recovery Trajectory z(t)")
    ax_tr.set_xlabel("Mission Time t (s)")
    ax_tr.set_ylabel("World Altitude z (m)")
    ax_tr.set_ylim(0.0, 2.45)
    ax_tr.legend(loc="lower left", ncol=2, framealpha=0.93, fontsize=7.8)

    ax_st = fig.add_subplot(gs[1, 2])
    steps_lbl = ["0. Raw\n(All 4)", "1. -T4\n(0ms Deliv)", "2. -T4,-T3\n(Cont Ref)", "3. Pure T1\n(Warm GRU)", "4. Classic\nOracle"]
    attr_runs = [r for r in SUMMARY if r["case_id"] == "cf_attribution"]
    t_vals = [r["peak_tilt_deg"] for r in attr_runs]
    v_vals = [r["max_speed_xy"] for r in attr_runs]
    s_idx = np.arange(5)
    ax_st2 = ax_st.twinx()
    ax_st2.grid(False)
    l1 = ax_st.plot(s_idx, t_vals, "o-", color=C_FAULT, lw=2.2, ms=6.5, label="Peak Tilt (deg)")
    l2 = ax_st2.plot(s_idx, v_vals, "s--", color=C_IDEAL, lw=2.0, ms=6.0, label="Peak Horiz Speed (m/s)")
    for i, (tv, vv) in enumerate(zip(t_vals, v_vals)):
        ax_st.annotate(f"{tv:.1f}°", (i, tv), textcoords="offset points", xytext=(0, 7), ha="center", fontsize=7.8, color=C_FAULT, fontweight="bold")
    ax_st.set_xticks(s_idx)
    ax_st.set_xticklabels(steps_lbl, fontsize=7.8)
    ax_st.set_ylabel("Peak Tilt (deg)", color=C_FAULT)
    ax_st2.set_ylabel("Peak Speed v_xy (m/s)", color=C_IDEAL)
    ax_st.set_ylim(15, 98)
    ax_st2.set_ylim(1.2, 3.0)
    ax_st.set_title("E. Counterfactual Attribution Staircase")
    lines = l1 + l2
    ax_st.legend(lines, [l.get_label() for l in lines], loc="upper right", fontsize=7.8)

    fig.suptitle("Crazyflie 2.1 Closed-Loop Handover Evidence (RLtools Foundation Policy + Bitcraze Firmware)", fontsize=13, fontweight="bold", y=0.98)
    fig.savefig(os.path.join(ART_DIR, "cf_overview_px4_alignment.png"), bbox_inches="tight")
    plt.close(fig)

# -------------------------------------------------------------------------
# 2. T1 Figure: Physical & Environmental Margin Depletion
# -------------------------------------------------------------------------
def plot_t1():
    fig = plt.figure(figsize=(14.0, 8.2), dpi=220)
    gs = GridSpec(2, 2, figure=fig, hspace=0.34, wspace=0.24)

    ck0 = load_trace("t1_turn_wx0.0_classic.csv")
    nn0 = load_trace("t1_turn_wx0.0_neural.csv")
    ck14 = load_trace("t1_turn_wx1.4_classic.csv")
    nn14 = load_trace("t1_turn_wx1.4_neural.csv")
    nnb = load_trace("t1_benign_neural.csv")

    # Panel A: 2D XY Trajectory
    ax = fig.add_subplot(gs[0, 0])
    m = (nn0["t_s"] >= 2.0) & (nn0["t_s"] <= 6.2)
    ax.plot(nn0["tx"][m], nn0["ty"][m], color=C_REF, ls=":", lw=1.8, label="Reference J-Turn + Brake")
    ax.plot(ck0["x"][m], ck0["y"][m], color=C_CLASSIC, lw=2.1, label="Classic-Keep (wx=0, max 18.4°)")
    ax.plot(nn0["x"][m], nn0["y"][m], color=C_IDEAL, lw=2.1, label="NN-Ideal (wx=0, 46.4°, -40.4cm)")
    ax.plot(nn14["x"][m], nn14["y"][m], color=C_FAULT, lw=2.1, ls="--", label="NN-Ideal (wx=1.4m/s, 47.7°, -51.2cm)")
    sw_i = np.argmin(np.abs(nn0["t_s"] - 3.85))
    pk_i = np.argmax(nn0["tilt_deg"])
    ax.scatter([nn0["x"][sw_i]], [nn0["y"][sw_i]], color="#0f172a", s=55, zorder=6, label="Handover t_sw = 3.85s")
    ax.scatter([nn0["x"][pk_i]], [nn0["y"][pk_i]], color=C_FAULT, marker="*", s=110, zorder=7, label="Braking Peak Tilt (4.07s)")
    ax.set_title("A. Ground-Track Overshoot in Tight J-Turn + Braking")
    ax.set_xlabel("World X (m)")
    ax.set_ylabel("World Y (m)")
    ax.legend(loc="upper left", fontsize=7.6, framealpha=0.92)

    # Panel B: Tilt Angle
    ax = fig.add_subplot(gs[0, 1])
    w = (nn0["t_s"] >= 3.2) & (nn0["t_s"] <= 5.8)
    ax.plot(ck0["t_s"][w], ck0["tilt_deg"][w], color=C_CLASSIC, lw=2.0, label="Classic-Keep (wx=0): 18.4°")
    ax.plot(nnb["t_s"][w], nnb["tilt_deg"][w], color="#0284c7", ls="-.", lw=1.7, label="NN Benign Margin (V=1.1,R=0.85): 27.0°")
    ax.plot(nn0["t_s"][w], nn0["tilt_deg"][w], color=C_IDEAL, lw=2.1, label="NN-Ideal (wx=0): 46.4°")
    ax.plot(nn14["t_s"][w], nn14["tilt_deg"][w], color=C_FAULT, lw=2.1, ls="--", label="NN-Ideal + Tailwind (wx=1.4): 47.7°")
    ax.axhline(47.0, color=C_SEVERE, ls=":", lw=1.3, label="Crazyflie Static TWR Ceiling (47.0°)")
    ax.axvline(3.85, color="#0f172a", ls=":", lw=1.2)
    ax.set_title("B. Attitude Excursion vs. Airframe TWR Tilt Ceiling")
    ax.set_xlabel("Mission Time t (s)")
    ax.set_ylabel("Total Tilt Angle (deg)")
    ax.set_ylim(0, 56)
    ax.legend(loc="upper right", fontsize=7.6, framealpha=0.92)

    # Panel C: Horizontal Speed & Vertical Plunge Rate
    ax = fig.add_subplot(gs[1, 0])
    ax.plot(nn0["t_s"][w], nn0["target_speed_xy"][w], color=C_REF, ls=":", lw=1.5, label="Target Speed v_ref")
    ax.plot(ck0["t_s"][w], ck0["speed_xy"][w], color=C_CLASSIC, lw=2.0, label="Classic v_xy (max 1.37 m/s)")
    ax.plot(nn0["t_s"][w], nn0["speed_xy"][w], color=C_IDEAL, lw=2.1, label="NN v_xy wx=0 (surge 1.88 m/s)")
    ax.plot(nn0["t_s"][w], nn0["vz"][w], color=C_IDEAL, ls="--", lw=1.6, label="NN vz wx=0 (min -0.93 m/s)")
    ax.plot(nn14["t_s"][w], nn14["vz"][w], color=C_FAULT, ls="--", lw=1.8, label="NN vz wx=1.4 (min -1.08 m/s)")
    ax.axhline(0.0, color="#94a3b8", lw=0.8)
    ax.axvline(3.85, color="#0f172a", ls=":", lw=1.2)
    ax.set_title("C. Speed Overshoot & Rotor-Saturated Vertical Plunge Rate")
    ax.set_xlabel("Mission Time t (s)")
    ax.set_ylabel("Velocity (m/s)")
    ax.legend(loc="lower right", fontsize=7.6, framealpha=0.92)

    # Panel D: Altitude Drop + Tailwind Sweep
    ax = fig.add_subplot(gs[1, 1])
    ax.plot(ck0["t_s"][w], (ck0["z"][w] - 2.0)*100, color=C_CLASSIC, lw=2.0, label="Classic-Keep (wx=0): -1.2 cm")
    ax.plot(ck14["t_s"][w], (ck14["z"][w] - 2.0)*100, color=C_CLASSIC, ls="--", lw=1.6, label="Classic-Keep (wx=1.4): -2.8 cm")
    ax.plot(nnb["t_s"][w], (nnb["z"][w] - 2.0)*100, color="#0284c7", ls="-.", lw=1.7, label="NN Benign Margin: -15.7 cm")
    ax.plot(nn0["t_s"][w], (nn0["z"][w] - 2.0)*100, color=C_IDEAL, lw=2.1, label="NN-Ideal (wx=0): -40.4 cm")
    ax.plot(nn14["t_s"][w], (nn14["z"][w] - 2.0)*100, color=C_FAULT, lw=2.2, label="NN-Ideal (wx=1.4): -51.2 cm")
    ax.axvline(3.85, color="#0f172a", ls=":", lw=1.2)
    ax.set_title("D. Altitude Deviation z(t) - z_ref Under Ideal History/Ref/Delivery")
    ax.set_xlabel("Mission Time t (s)")
    ax.set_ylabel("Altitude Change (cm)")
    ax.set_ylim(-60, 10)
    ax.legend(loc="lower right", fontsize=7.6, framealpha=0.92)

    fig.suptitle("T1 Evidence — Physical & Environmental Margin Depletion (Tight J-Turn + Braking, T2/T3/T4 Stripped)", fontsize=12.5, fontweight="bold", y=0.98)
    fig.savefig(os.path.join(ART_DIR, "cf_t1_margin_depletion.png"), bbox_inches="tight")
    plt.close(fig)

# -------------------------------------------------------------------------
# 3. T2 Figure: Controller History State Continuity Error
# -------------------------------------------------------------------------
def plot_t2():
    fig = plt.figure(figsize=(14.0, 8.2), dpi=220)
    gs = GridSpec(2, 2, figure=fig, hspace=0.35, wspace=0.25)

    s_ck = load_trace("t2_straight_com5.3_classic.csv")
    s_wm = load_trace("t2_straight_com5.3_warm.csv")
    s_cd = load_trace("t2_straight_com5.3_cold.csv")
    s_ps = load_trace("t2_straight_com5.3_poison.csv")

    t_ck = load_trace("t2_turn_com4.8_classic.csv")
    t_wm = load_trace("t2_turn_com4.8_warm.csv")
    t_ps = load_trace("t2_turn_com4.8_poison.csv")

    # Panel A: Straight Cruise Tilt & Motor Jump
    ax = fig.add_subplot(gs[0, 0])
    w = (s_wm["t_s"] >= 3.75) & (s_wm["t_s"] <= 5.6)
    ax.plot(s_ck["t_s"][w], s_ck["tilt_deg"][w], color=C_CLASSIC, lw=2.0, label="Classic-Keep (5.7°, du=0.002)")
    ax.plot(s_wm["t_s"][w], s_wm["tilt_deg"][w], color=C_IDEAL, lw=2.1, label="NN Warm-Shadow (10.7°, du=0.114)")
    ax.plot(s_cd["t_s"][w], s_cd["tilt_deg"][w], color=C_WARN, lw=2.1, label="Upstream l2f_reset() Cold (16.9°, du=0.474)")
    ax.plot(s_ps["t_s"][w], s_ps["tilt_deg"][w], color=C_FAULT, lw=2.1, ls="--", label="Upstream rlt.orig=-0.8 Poison (17.7°, du=0.737)")
    ax.axvline(4.00, color="#0f172a", ls=":", lw=1.2, label="Handover t_sw = 4.00s")
    ax.set_title("A. [T2-Straight] Tilt Spike After GRU Wipe")
    ax.set_xlabel("Mission Time t (s)")
    ax.set_ylabel("Total Tilt Angle (deg)")
    ax.legend(loc="upper right", fontsize=7.5, framealpha=0.92)

    # Panel B: Straight Cruise Plunge Velocity & Altitude Drop
    ax = fig.add_subplot(gs[0, 1])
    ax.plot(s_ck["t_s"][w], (s_ck["z"][w] - 2.2)*100, color=C_CLASSIC, lw=2.0, label="Classic-Keep (-0.3 cm, vz=-0.04 m/s)")
    ax.plot(s_wm["t_s"][w], (s_wm["z"][w] - 2.2)*100, color=C_IDEAL, lw=2.1, label="NN Warm-Shadow (-15.9 cm, vz=-0.34 m/s)")
    ax.plot(s_cd["t_s"][w], (s_cd["z"][w] - 2.2)*100, color=C_WARN, lw=2.1, label="Upstream l2f_reset() (-54.3 cm, vz=-0.75 m/s)")
    ax.plot(s_ps["t_s"][w], (s_ps["z"][w] - 2.2)*100, color=C_FAULT, lw=2.2, ls="--", label="Upstream rlt.orig=-0.8 (-67.6 cm, vz=-0.85 m/s)")
    ax.axvline(4.00, color="#0f172a", ls=":", lw=1.2)
    ax.set_title("B. [T2-Straight] Altitude Plunge (com=5.3mm)")
    ax.set_xlabel("Mission Time t (s)")
    ax.set_ylabel("Altitude Change (cm)")
    ax.legend(loc="lower right", fontsize=7.5, framealpha=0.92)

    # Panel C: Banked Right Turn (t2-turn) Speed & Altitude Crash vs Warm Survival
    ax = fig.add_subplot(gs[1, 0])
    wt = (t_wm["t_s"] >= 3.2) & (t_wm["t_s"] <= 5.6)
    wt_p = (t_ps["t_s"] >= 3.2) & (t_ps["t_s"] <= 5.6)
    ax.plot(t_ck["t_s"][wt], t_ck["speed_xy"][wt], color=C_CLASSIC, lw=2.0, label="Classic v_xy (max 1.57 m/s, 26.6°)")
    ax.plot(t_wm["t_s"][wt], t_wm["speed_xy"][wt], color=C_IDEAL, lw=2.1, label="NN Warm-Shadow v_xy (max 1.84 m/s, Survives)")
    ax.plot(t_ps["t_s"][wt_p], t_ps["speed_xy"][wt_p], color=C_FAULT, lw=2.2, label="NN rlt.orig=-0.8 Poison v_xy (2.58 m/s, 33.1° CRASH)")
    ax.plot(t_wm["t_s"][wt], np.abs(t_wm["vz"][wt]), color=C_IDEAL, ls=":", lw=1.5, label="NN Warm |vz| (max 0.58 m/s)")
    ax.plot(t_ps["t_s"][wt_p], np.abs(t_ps["vz"][wt_p]), color=C_FAULT, ls=":", lw=1.7, label="NN Poison |vz| (max 2.63 m/s)")
    ax.axvline(3.55, color="#0f172a", ls=":", lw=1.2)
    ax.set_title("C. [T2-Turn] Right-Turn Speed & Plunge Runaway")
    ax.set_xlabel("Mission Time t (s)")
    ax.set_ylabel("Speed / |vz| (m/s)")
    ax.legend(loc="upper left", fontsize=7.4, framealpha=0.92)

    # Panel D: CoM Disturbance Severity Sweep
    ax = fig.add_subplot(gs[1, 1])
    coms = [0.0, 3.8, 4.8, 5.3]
    dz_ck = [find_run(f"t2_straight_com{c:.1f}", "Classic-Keep")["max_alt_loss_cm"] for c in coms]
    dz_wm = [find_run(f"t2_straight_com{c:.1f}", "NN-Warm-Shadow")["max_alt_loss_cm"] for c in coms]
    dz_cd = [find_run(f"t2_straight_com{c:.1f}", "NN-Cold-Reset")["max_alt_loss_cm"] for c in coms]
    dz_ps = [find_run(f"t2_straight_com{c:.1f}", "NN-Orig-Poison")["max_alt_loss_cm"] for c in coms]
    ax.plot(coms, dz_ck, "o-", color=C_CLASSIC, lw=2.0, label="Classic-Keep")
    ax.plot(coms, dz_wm, "s-", color=C_IDEAL, lw=2.1, label="NN Warm-Shadow (Teacher-Forced)")
    ax.plot(coms, dz_cd, "^-", color=C_WARN, lw=2.1, label="Upstream l2f_reset() (rl_tools_controller.c:439)")
    ax.plot(coms, dz_ps, "D--", color=C_FAULT, lw=2.2, label="Upstream rlt.orig=-0.8 (rl_tools_controller.c:668)")
    ax.set_title("D. Battery CoM Sweep vs. Max Altitude Drop")
    ax.set_xlabel("Battery CoM Shift Magnitude (mm)")
    ax.set_ylabel("Max Post-Handover Altitude Drop (cm)")
    ax.legend(loc="upper left", fontsize=7.5, framealpha=0.92)

    fig.suptitle("T2 Evidence — Recurrent GRU History Continuity Error (l2f_reset() Wipe & rlt.orig=-0.8 Poisoning)", fontsize=12.5, fontweight="bold", y=0.98)
    fig.savefig(os.path.join(ART_DIR, "cf_t2_history_mismatch.png"), bbox_inches="tight")
    plt.close(fig)

# -------------------------------------------------------------------------
# 4. T3 Figure: Setpoint Reference Continuity Anomaly
# -------------------------------------------------------------------------
def plot_t3():
    fig = plt.figure(figsize=(14.0, 8.2), dpi=220)
    gs = GridSpec(2, 2, figure=fig, hspace=0.35, wspace=0.24)

    s0   = load_trace("t3_straight_gap0ms.csv")
    s80  = load_trace("t3_straight_gap80ms.csv")
    s180 = load_trace("t3_straight_gap180ms.csv")
    s260 = load_trace("t3_straight_gap260ms.csv")

    u_ck  = load_trace("t3_turn_classic.csv")
    u_0   = load_trace("t3_turn_gap0ms.csv")
    u_168 = load_trace("t3_turn_gap168ms.csv")
    u_220 = load_trace("t3_turn_gap220ms.csv")
    u_ff  = load_trace("t3_turn_zerovelff.csv")

    # Panel A: Straight Cruise Brake-then-Chase Speed & Tilt
    ax = fig.add_subplot(gs[0, 0])
    w = (s0["t_s"] >= 3.55) & (s0["t_s"] <= 5.20)
    ax.plot(s0["t_s"][w], s0["speed_xy"][w], color=C_IDEAL, lw=2.0, label="Gap 0ms (1.15..1.20 m/s, 4.8°)")
    ax.plot(s80["t_s"][w], s80["speed_xy"][w], color="#0284c7", lw=1.9, label="Gap 80ms (0.86..1.32 m/s, 16.2°)")
    ax.plot(s180["t_s"][w], s180["speed_xy"][w], color=C_WARN, lw=2.1, label="Gap 180ms (0.44..1.56 m/s, 30.4°)")
    ax.plot(s260["t_s"][w], s260["speed_xy"][w], color=C_FAULT, lw=2.1, label="Gap 260ms (0.08..1.85 m/s, 31.0°)")
    ax.axvline(3.80, color="#0f172a", ls=":", lw=1.2, label="Handover t_sw = 3.80s")
    ax.set_title("A. [T3-Straight] Zero-Velocity Origin Hold -> Brake-then-Chase Speed")
    ax.set_xlabel("Mission Time t (s)")
    ax.set_ylabel("Horizontal Speed v_xy (m/s)")
    ax.legend(loc="lower right", fontsize=7.5, framealpha=0.92)

    # Panel B: Constant-Altitude Tight U-Turn XY Swing-Out
    ax = fig.add_subplot(gs[0, 1])
    mu = (u_0["t_s"] >= 2.8) & (u_0["t_s"] <= 6.2)
    ax.plot(u_ck["tx"][mu], u_ck["ty"][mu], color=C_REF, ls=":", lw=1.8, label="Reference U-Turn (R=0.58m, V=1.62m/s)")
    ax.plot(u_ck["x"][mu], u_ck["y"][mu], color=C_CLASSIC, lw=2.0, label="Classic-Keep (err=0.09m, dZ=0.0cm)")
    ax.plot(u_0["x"][mu], u_0["y"][mu], color=C_IDEAL, lw=2.0, label="NN Gap 0ms (32.2°, dZ=25.1cm)")
    ax.plot(u_168["x"][mu], u_168["y"][mu], color=C_FAULT, lw=2.2, label="NN Gap 168ms (40.8°, vmax=2.19, dZ=42.4cm)")
    ax.plot(u_ff["x"][mu], u_ff["y"][mu], color=C_WARN, ls="--", lw=1.8, label="Historical target_vel=0 Bug (err=0.89m)")
    sw_i = np.argmin(np.abs(u_0["t_s"] - 3.92))
    ax.scatter([u_0["x"][sw_i]], [u_0["y"][sw_i]], color="#0f172a", s=55, zorder=6, label="Handover t_sw = 3.92s")
    ax.set_title("B. [T3-Turn] U-Turn Entry Deceleration & Wide-Arc Swing-Out")
    ax.set_xlabel("World X (m)")
    ax.set_ylabel("World Y (m)")
    ax.legend(loc="lower left", fontsize=7.3, framealpha=0.92)

    # Panel C: Tight U-Turn Tilt & Altitude Drop
    ax = fig.add_subplot(gs[1, 0])
    wu = (u_0["t_s"] >= 3.6) & (u_0["t_s"] <= 5.6)
    ax.plot(u_0["t_s"][wu], u_0["tilt_deg"][wu], color=C_IDEAL, lw=2.0, label="NN Gap 0ms Tilt (peak 32.2°)")
    ax.plot(u_168["t_s"][wu], u_168["tilt_deg"][wu], color=C_WARN, lw=2.1, label="NN Gap 168ms Tilt (peak 40.8°)")
    ax.plot(u_220["t_s"][wu], u_220["tilt_deg"][wu], color=C_FAULT, lw=2.2, label="NN Gap 220ms Tilt (peak 43.2°)")
    ax2 = ax.twinx()
    ax2.grid(False)
    ax2.plot(u_0["t_s"][wu], (u_0["z"][wu] - 2.0)*100, color=C_IDEAL, ls=":", lw=1.6, label="Gap 0ms Alt (-25.1cm)")
    ax2.plot(u_168["t_s"][wu], (u_168["z"][wu] - 2.0)*100, color=C_WARN, ls=":", lw=1.7, label="Gap 168ms Alt (-42.4cm)")
    ax2.plot(u_220["t_s"][wu], (u_220["z"][wu] - 2.0)*100, color=C_FAULT, ls=":", lw=1.9, label="Gap 220ms Alt (-55.6cm)")
    ax.axvline(3.92, color="#0f172a", ls=":", lw=1.2)
    ax.set_title("C. [T3-Turn] Catch-Up Bank Spike & Constant-Z Altitude Drop")
    ax.set_xlabel("Mission Time t (s)")
    ax.set_ylabel("Total Tilt Angle (deg)")
    ax2.set_ylabel("Altitude Change z - z_ref (cm)")
    ax.set_ylim(0, 52)
    ax2.set_ylim(-65, 10)
    lns = ax.get_lines()[:3] + ax2.get_lines()
    ax.legend(lns, [l.get_label() for l in lns], loc="upper right", fontsize=7.2, ncol=2, framealpha=0.92)

    # Panel D: Gap Duration Sweep
    ax = fig.add_subplot(gs[1, 1])
    gaps_s = [0, 80, 180, 260]
    gaps_u = [0, 80, 168, 220]
    t_s_arr = [find_run("t3_straight", f"NN-Gap-{g}ms")["peak_tilt_deg"] for g in gaps_s]
    dz_s_arr = [find_run("t3_straight", f"NN-Gap-{g}ms")["max_alt_loss_cm"] for g in gaps_s]
    t_u_arr = [find_run("t3_turn", f"NN-Gap-{g}ms")["peak_tilt_deg"] for g in gaps_u]
    dz_u_arr = [find_run("t3_turn", f"NN-Gap-{g}ms")["max_alt_loss_cm"] for g in gaps_u]
    ax.plot(gaps_s, t_s_arr, "o--", color="#0284c7", lw=2.0, label="Straight Cruise: Peak Tilt (deg)")
    ax.plot(gaps_s, dz_s_arr, "s-", color=C_IDEAL, lw=2.0, label="Straight Cruise: Altitude Loss (cm)")
    ax.plot(gaps_u, t_u_arr, "^--", color=C_WARN, lw=2.1, label="Tight U-Turn: Peak Tilt (deg)")
    ax.plot(gaps_u, dz_u_arr, "D-", color=C_FAULT, lw=2.2, label="Tight U-Turn: Altitude Loss (cm)")
    ax.set_title("D. Monotonic Setpoint Gap Sweep (Tilt & Altitude Loss)")
    ax.set_xlabel("Reference Continuity Gap Duration (ms)")
    ax.set_ylabel("Magnitude (deg / cm)")
    ax.legend(loc="upper left", fontsize=7.5, framealpha=0.92)

    fig.suptitle("T3 Evidence — Setpoint Reference Continuity Anomaly (Zero-Velocity Origin Hold & Feedforward Drop)", fontsize=12.5, fontweight="bold", y=0.98)
    fig.savefig(os.path.join(ART_DIR, "cf_t3_setpoint_gap.png"), bbox_inches="tight")
    plt.close(fig)

# -------------------------------------------------------------------------
# 5. T4 Figure: Authority Delivery Anomaly
# -------------------------------------------------------------------------
def plot_t4():
    fig = plt.figure(figsize=(14.0, 8.2), dpi=220)
    gs = GridSpec(2, 2, figure=fig, hspace=0.35, wspace=0.25)

    w_ck  = load_trace("t4_warmup_classic.csv")
    w_0   = load_trace("t4_warmup_0ms.csv")
    w_220 = load_trace("t4_warmup_220ms.csv")
    w_350 = load_trace("t4_warmup_350ms.csv")
    w_500 = load_trace("t4_warmup_500ms.csv")

    h_0  = load_trace("t4_turn_exit_hold0ms.csv")
    h_16 = load_trace("t4_turn_exit_hold16ms.csv")
    h_24 = load_trace("t4_turn_exit_hold24ms.csv")
    h_40 = load_trace("t4_turn_exit_hold40ms.csv")
    h_60 = load_trace("t4_turn_exit_hold60ms.csv")

    # Panel A: T4-A Upstream motor_warmup=1 Mid-Air Authority Vacuum
    ax = fig.add_subplot(gs[0, 0])
    mw = (w_0["t_s"] >= 3.4) & (w_0["t_s"] <= 5.6)
    ax.plot(w_ck["t_s"][mw], (w_ck["z"][mw] - 2.0)*100, color=C_CLASSIC, lw=2.0, label="Classic-Keep (-1.2 cm, vz=-0.04 m/s)")
    ax.plot(w_0["t_s"][mw], (w_0["z"][mw] - 2.0)*100, color=C_IDEAL, lw=2.0, label="Warmup 0ms Fixed (-12.0 cm, vz=-0.21 m/s)")
    ax.plot(w_220["t_s"][mw], (w_220["z"][mw] - 2.0)*100, color="#0284c7", lw=2.0, label="Warmup 220ms (-30.9 cm, vz=-0.93 m/s)")
    ax.plot(w_350["t_s"][mw], (w_350["z"][mw] - 2.0)*100, color=C_WARN, lw=2.1, label="Warmup 350ms (-85.0 cm, vz=-1.68 m/s)")
    ax.plot(w_500["t_s"][mw], (w_500["z"][mw] - 2.0)*100, color=C_FAULT, lw=2.2, label="Warmup 500ms Upstream Default (-173.2 cm, vz=-2.62)")
    ax.axvspan(3.70, 4.20, color="#fee2e2", alpha=0.55, label="500ms 25%-Throttle Authority Vacuum")
    ax.set_title("A. [T4-A] Upstream Default rlt.motor_warmup=1 Mid-Air Plunge")
    ax.set_xlabel("Mission Time t (s)")
    ax.set_ylabel("Altitude Change z - z_ref (cm)")
    ax.legend(loc="lower left", fontsize=7.3, framealpha=0.92)

    # Panel B: T4-B Turn-Exit Stale Classic Differential Motor Hold -> Tilt Surge
    ax = fig.add_subplot(gs[0, 1])
    mh = (h_0["t_s"] >= 3.45) & (h_0["t_s"] <= 4.35)
    ax.plot(h_0["t_s"][mh], h_0["tilt_deg"][mh], color=C_IDEAL, lw=2.1, label="Hold 0ms Instant (28.7°, dZ=8.4cm)")
    ax.plot(h_16["t_s"][mh], h_16["tilt_deg"][mh], color="#0284c7", lw=1.9, label="Hold 16ms (35.8°, dZ=10.5cm)")
    ax.plot(h_24["t_s"][mh], h_24["tilt_deg"][mh], color=C_WARN, lw=2.1, label="Hold 24ms [PX4 Match] (39.1°, dZ=11.7cm)")
    ax.plot(h_40["t_s"][mh], h_40["tilt_deg"][mh], color=C_FAULT, lw=2.1, label="Hold 40ms (44.7°, dZ=15.2cm)")
    ax.plot(h_60["t_s"][mh], h_60["tilt_deg"][mh], color=C_SEVERE, lw=2.2, ls="--", label="Hold 60ms (50.8°, vmax=1.86, dZ=21.8cm)")
    ax.axhline(47.0, color=C_SEVERE, ls=":", lw=1.2)
    ax.axvline(3.56, color="#0f172a", ls=":", lw=1.2, label="Turn-Exit Handover t_sw = 3.56s")
    ax.set_title("B. [T4-B] Turn-Exit Stale Differential Motor Hold -> Attitude Roll-Over")
    ax.set_xlabel("Mission Time t (s)")
    ax.set_ylabel("Total Tilt Angle (deg)")
    ax.set_ylim(0, 56)
    ax.legend(loc="upper right", fontsize=7.3, framealpha=0.92)

    # Panel C: T4-B Published vs Applied Motor Commands (t_publish -> t_apply)
    ax = fig.add_subplot(gs[1, 0])
    zoom = (h_40["t_s"] >= 3.50) & (h_40["t_s"] <= 3.70)
    ax.plot(h_40["t_s"][zoom], h_40["pub_m1"][zoom], color=C_IDEAL, ls="--", lw=1.8, label="Published NN M1 (Counter-Roll Command)")
    ax.plot(h_40["t_s"][zoom], h_40["m1"][zoom], color=C_FAULT, lw=2.2, label="Applied Actuator M1 (Latched Classic 40ms)")
    ax.plot(h_40["t_s"][zoom], h_40["pub_m3"][zoom], color="#0284c7", ls="--", lw=1.8, label="Published NN M3")
    ax.plot(h_40["t_s"][zoom], h_40["m3"][zoom], color=C_WARN, lw=2.2, label="Applied Actuator M3 (Latched Classic 40ms)")
    ax.axvspan(3.56, 3.60, color="#fef3c7", alpha=0.75, label="[t_publish, t_apply] 40ms Stale Latch")
    ax.set_title("C. [T4-B] Published Neural vs. Applied Actuator Motor Ratio (M1 vs M3)")
    ax.set_xlabel("Mission Time t (s)")
    ax.set_ylabel("Normalized Motor Command [0, 1]")
    ax.set_ylim(0.0, 1.08)
    ax.legend(loc="lower right", fontsize=7.3, framealpha=0.92)

    # Panel D: T4-B Turn-Exit Monotonic Delay Sweep (Tilt, Speed, Altitude Loss)
    ax = fig.add_subplot(gs[1, 1])
    holds = [0, 16, 24, 40, 60]
    htilt = [find_run("t4_turn_exit", f"NN-StaleHold-{h}ms")["peak_tilt_deg"] for h in holds]
    hdz   = [find_run("t4_turn_exit", f"NN-StaleHold-{h}ms")["max_alt_loss_cm"] for h in holds]
    hvmax = [find_run("t4_turn_exit", f"NN-StaleHold-{h}ms")["max_speed_xy"] for h in holds]
    ax2 = ax.twinx()
    ax2.grid(False)
    l1 = ax.plot(holds, htilt, "o-", color=C_FAULT, lw=2.2, label="Peak Tilt (deg)")
    l2 = ax.plot(holds, hdz, "s-", color=C_WARN, lw=2.1, label="Max Altitude Loss (cm)")
    l3 = ax2.plot(holds, hvmax, "^--", color=C_IDEAL, lw=2.0, label="Peak Horiz Speed (m/s)")
    ax.set_title("D. [T4-B] Turn-Exit Delivery Delay Sweep (0 -> 60 ms)")
    ax.set_xlabel("Downstream Stale Motor Hold Duration (ms)")
    ax.set_ylabel("Peak Tilt (deg) / Altitude Loss (cm)")
    ax2.set_ylabel("Peak Horizontal Speed (m/s)", color=C_IDEAL)
    ax.set_ylim(0, 56)
    ax2.set_ylim(1.35, 1.95)
    lns = l1 + l2 + l3
    ax.legend(lns, [l.get_label() for l in lns], loc="upper left", fontsize=7.6, framealpha=0.92)

    fig.suptitle("T4 Evidence — Control Authority Delivery Anomaly (Upstream 500ms Warmup Vacuum & Turn-Exit Stale Motor Hold)", fontsize=12.5, fontweight="bold", y=0.98)
    fig.savefig(os.path.join(ART_DIR, "cf_t4_authority_delivery.png"), bbox_inches="tight")
    plt.close(fig)

if __name__ == "__main__":
    plot_overview()
    plot_t1()
    plot_t2()
    plot_t3()
    plot_t4()
    print("Generated all 5 publication figures in:", ART_DIR)

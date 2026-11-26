#!/usr/bin/env python3
"""
Generate all 5 publication-grade figures (300 DPI PNG + vector PDF) directly from
the single source of truth: traces/*.csv.gz and metrics.json (zero smoothing, zero hard-coded numbers).
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from metrics_core import load_trace_gz

EVIDENCE_DIR = Path(__file__).resolve().parent.parent
TRACES_DIR = EVIDENCE_DIR / "traces"
FIG_DIR = EVIDENCE_DIR / "figures"

# Clean academic palette (colorblind-safe Okabe-Ito inspired)
C_BLUE = "#0072B2"
C_TEAL = "#009E73"
C_ORANGE = "#E69F00"
C_VERM = "#D55E00"
C_RED = "#C02942"
C_PURPLE = "#7A378B"
C_NAVY = "#1F3A5F"
C_GRAY = "#5A5A5A"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9.5,
    "axes.titlesize": 10.5,
    "axes.titleweight": "bold",
    "axes.labelsize": 9.5,
    "legend.fontsize": 8.2,
    "xtick.labelsize": 8.8,
    "ytick.labelsize": 8.8,
    "axes.grid": True,
    "grid.alpha": 0.28,
    "grid.linestyle": "--",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "savefig.dpi": 300,
    "figure.dpi": 150,
})


def load_all() -> tuple[dict[str, Any], dict[str, dict[str, np.ndarray]]]:
    metrics = json.loads((EVIDENCE_DIR / "metrics.json").read_text(encoding="utf-8"))["runs"]
    traces: dict[str, dict[str, np.ndarray]] = {}
    for rid in metrics:
        _, d = load_trace_gz(TRACES_DIR / f"{rid}.csv.gz")
        traces[rid] = d
    return metrics, traces


def clip_trace_to_event(d: dict[str, np.ndarray], m: dict[str, Any], t_min: float, t_max: float) -> np.ndarray:
    t = d["t_rel_s"]
    out = m["outcome"]
    eff_max = t_max
    if out["status"] == "GROUND_IMPACT_CRASH" and out["event_t_rel_s"] is not None:
        eff_max = min(eff_max, float(out["event_t_rel_s"]) + 0.02)
    return (t >= t_min) & (t <= eff_max)


def mark_event(ax: plt.Axes, d: dict[str, np.ndarray], m: dict[str, Any], y_arr: np.ndarray, color: str, dx: float = 0.06, dy: float = 0.0) -> None:
    out = m["outcome"]
    if out["status"] == "LANDED_CLEAN" or out["event_t_rel_s"] is None:
        return
    te = float(out["event_t_rel_s"])
    idx = int(np.argmin(np.abs(d["t_rel_s"] - te)))
    ye = float(y_arr[idx])
    lbl = "Crash" if out["status"] == "GROUND_IMPACT_CRASH" else "Abort"
    ax.scatter([te], [ye], marker="X", s=68, color=color, edgecolor="black", linewidth=0.7, zorder=8)
    ax.annotate(
        f"{lbl} @ {te:.2f}s",
        xy=(te, ye),
        xytext=(te + dx, ye + dy),
        fontsize=7.8,
        fontweight="bold",
        color=color,
        bbox=dict(boxstyle="round,pad=0.18", facecolor="white", edgecolor=color, alpha=0.88, lw=0.7),
        arrowprops=dict(arrowstyle="->", color=color, lw=0.8),
        zorder=9,
    )


def save_fig(fig: plt.Figure, stem: str) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_DIR / f"{stem}.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIG_DIR / f"{stem}.pdf", bbox_inches="tight")
    plt.close(fig)


# =====================================================================
# Figure 1: T1 Physical & Environmental Margin Depletion
# =====================================================================
def plot_t1(metrics: dict[str, Any], traces: dict[str, dict[str, np.ndarray]]) -> None:
    fig, axs = plt.subplots(2, 2, figsize=(12.6, 8.6), constrained_layout=True)

    # (a) XY Ground Trajectory Overshoot (Tight-Turn 3-Arm)
    ax = axs[0, 0]
    ref_d = traces["T1_turn_w0_classic"]
    m_ref = (ref_d["t_rel_s"] >= -1.4) & (ref_d["t_rel_s"] <= 3.8)
    ax.plot(ref_d["ref_y_m"][m_ref], ref_d["ref_x_m"][m_ref], ":", color=C_GRAY, lw=1.4, label="Reference path")
    for rid, lbl, col, ls in [
        ("T1_turn_w0_classic", "Classic-Keep (Oracle)", C_BLUE, "-"),
        ("T1_turn_w0_preentered", "MCNN-PreEntered", C_TEAL, "--"),
        ("T1_turn_w0_mcnn", "MCNN-Takeover (mid-turn)", C_RED, "-"),
    ]:
        d, m = traces[rid], metrics[rid]
        msk = clip_trace_to_event(d, m, -1.4, 3.8)
        ax.plot(d["y_m"][msk], d["x_m"][msk], color=col, ls=ls, lw=1.9, label=lbl)
        if m["outcome"]["status"] == "GROUND_IMPACT_CRASH" and m["outcome"]["event_t_rel_s"] is not None:
            te = float(m["outcome"]["event_t_rel_s"])
            idx = int(np.argmin(np.abs(d["t_rel_s"] - te)))
            ax.scatter([d["y_m"][idx]], [d["x_m"][idx]], marker="X", s=72, color=col, edgecolor="black", lw=0.7, zorder=8)
            ax.annotate(
                f"Crash @ {te:.2f}s",
                xy=(d["y_m"][idx], d["x_m"][idx]),
                xytext=(d["y_m"][idx] - 3.3, d["x_m"][idx] + 0.65),
                fontsize=7.8, fontweight="bold", color=col,
                bbox=dict(boxstyle="round,pad=0.18", facecolor="white", edgecolor=col, alpha=0.92),
                arrowprops=dict(arrowstyle="->", color=col, lw=0.9),
            )
    e0 = metrics["T1_turn_w0_classic"]["entry"]
    ax.scatter([e0["y_m"]], [e0["x_m"]], marker="*", s=110, color="gold", edgecolor="black", lw=0.7, zorder=9, label=r"Handover $t_{\mathrm{sw}}$")
    ax.set_title("(a) Tight-Turn 3-Arm Ground Track (NED East vs. North)")
    ax.set_xlabel("East Position y (m)")
    ax.set_ylabel("North Position x (m)")
    ax.set_aspect("equal", adjustable="datalim")
    ax.legend(loc="lower left", framealpha=0.92)

    # (b) Tilt Angle: Tight-Turn 3-Arm & Aligned-Tailwind Margin Sweep
    ax = axs[0, 1]
    ax.axvline(0.0, color="black", ls=":", lw=1.0)
    series_b = [
        ("T1_turn_w0_classic", "Turn 3.6m/s Classic", C_BLUE, "-", 1.6),
        ("T1_turn_w0_preentered", "Turn 3.6m/s PreEntered", C_TEAL, "--", 1.7),
        ("T1_turn_w0_mcnn", "Turn 3.6m/s MCNN-Takeover", C_RED, "-", 1.9),
        ("T1_wind_w0_mcnn", "WindSweep 0 m/s (MCNN)", C_ORANGE, "-", 1.6),
        ("T1_wind_w70_mcnn", "WindSweep 7.0 m/s (MCNN)", C_VERM, "-", 1.6),
        ("T1_wind_w80_mcnn", "WindSweep 8.0 m/s (MCNN)", C_PURPLE, "-", 1.8),
        ("T1_wind_w80_classic", "WindSweep 8.0 m/s (Classic)", C_NAVY, ":", 1.5),
    ]
    for rid, lbl, col, ls, lw in series_b:
        if rid not in traces:
            continue
        d, m = traces[rid], metrics[rid]
        msk = clip_trace_to_event(d, m, -0.35, 3.5)
        pk = m["windows"]["w_full"]["max_tilt_deg"]
        ax.plot(d["t_rel_s"][msk], d["tilt_deg"][msk], color=col, ls=ls, lw=lw, label=f"{lbl} ({pk:.1f}°)")
        if m["outcome"]["status"] == "GROUND_IMPACT_CRASH":
            mark_event(ax, d, m, d["tilt_deg"], col, dx=-1.18, dy=-4.0)
    ax.set_title(r"(b) Unsmoothed Total Tilt $\arccos(R_{33})$: 3-Arm & Wind Sweep")
    ax.set_xlabel(r"Time Relative to Handover $t - t_{\mathrm{sw}}$ (s)")
    ax.set_ylabel("Total Tilt Angle (deg)")
    ax.set_xlim(-0.35, 3.55)
    ax.legend(loc="upper right", fontsize=7.5, framealpha=0.92)

    # (c) Straight-Brake Speed & Plunge Rate (Missing Velocity Feedforward)
    ax = axs[1, 0]
    ax.axvline(0.0, color="black", ls=":", lw=1.0)
    for rid, lbl, col in [
        ("T1_straight_brake_classic", "Classic-Keep", C_BLUE),
        ("T1_straight_brake_mcnn", "MCNN-Takeover", C_RED),
    ]:
        d, m = traces[rid], metrics[rid]
        msk = clip_trace_to_event(d, m, -0.35, 3.5)
        ax.plot(d["t_rel_s"][msk], d["v_xy_m_s"][msk], color=col, lw=1.9, label=f"{lbl} horiz. speed $v_{{xy}}$")
        ax.plot(d["t_rel_s"][msk], d["v_up_m_s"][msk], color=col, ls="--", lw=1.5, alpha=0.85, label=f"{lbl} vert. vel. $v_z$ (+up)")
        if m["outcome"]["status"] == "GROUND_IMPACT_CRASH":
            mark_event(ax, d, m, d["v_up_m_s"], col, dx=0.14, dy=1.2)
    ax.axhline(0.0, color=C_GRAY, ls="-", lw=0.7, alpha=0.6)
    ax.set_title("(c) High-Speed Straight Brake: Missing Velocity Feedforward")
    ax.set_xlabel(r"Time Relative to Handover $t - t_{\mathrm{sw}}$ (s)")
    ax.set_ylabel("Velocity (m/s)")
    ax.set_xlim(-0.35, 3.55)
    ax.legend(loc="lower left", fontsize=7.8, framealpha=0.92)

    # (d) Relative Altitude Change Δh(t) = (h(t) - h(t_sw)) * 100 (cm)
    ax = axs[1, 1]
    ax.axvline(0.0, color="black", ls=":", lw=1.0)
    ax.axhline(0.0, color=C_GRAY, ls="-", lw=0.7, alpha=0.6)
    for rid, lbl, col, ls in [
        ("T1_turn_w0_classic", "Turn Classic-Keep", C_BLUE, "-"),
        ("T1_turn_w0_preentered", "Turn MCNN-PreEntered", C_TEAL, "--"),
        ("T1_turn_w0_mcnn", "Turn MCNN-Takeover", C_RED, "-"),
        ("T1_wind_w0_mcnn", "Wind 0 m/s (MCNN)", C_ORANGE, "-"),
        ("T1_wind_w70_mcnn", "Wind 7.0 m/s (MCNN)", C_VERM, "-"),
        ("T1_wind_w80_mcnn", "Wind 8.0 m/s (MCNN)", C_PURPLE, "-"),
        ("T1_wind_w80_classic", "Wind 8.0 m/s (Classic)", C_NAVY, ":"),
    ]:
        if rid not in traces:
            continue
        d, m = traces[rid], metrics[rid]
        h0 = m["entry"]["h_m"]
        dh = (d["h_m"] - h0) * 100.0
        msk = clip_trace_to_event(d, m, -0.35, 3.5)
        loss = m["windows"]["w_full"]["max_alt_loss_cm"]
        ax.plot(d["t_rel_s"][msk], dh[msk], color=col, ls=ls, lw=1.7, label=f"{lbl} (loss {loss:.1f} cm)")
        if m["outcome"]["status"] == "GROUND_IMPACT_CRASH":
            mark_event(ax, d, m, dh, col, dx=0.15, dy=35.0 if rid == "T1_turn_w0_mcnn" else 75.0)
    ax.set_title(r"(d) Relative Altitude Change $\Delta h(t) = h(t) - h(t_{\mathrm{sw}})$ (neg. = drop)")
    ax.set_xlabel(r"Time Relative to Handover $t - t_{\mathrm{sw}}$ (s)")
    ax.set_ylabel(r"$\Delta h$ (cm)")
    ax.set_xlim(-0.35, 3.55)
    ax.legend(loc="lower left", fontsize=7.4, framealpha=0.92)

    fig.suptitle("T1: Physical & Environmental Margin Depletion in PX4 mc_nn_control Handover (Seed 42)", fontsize=12, fontweight="bold")
    save_fig(fig, "mcnn_t1_margin_depletion")


# =====================================================================
# Figure 2: T2 Memoryless Feedforward == Cleared Memory
# =====================================================================
def plot_t2(metrics: dict[str, Any], traces: dict[str, dict[str, np.ndarray]]) -> None:
    fig, axs = plt.subplots(2, 2, figsize=(12.6, 8.6), constrained_layout=True)

    # (a) First-step 4-motor normalized jump across t_sw (T2_com35_mcnn vs T2_cf_probe_com35)
    ax = axs[0, 0]
    m_raw = metrics["T2_com35_mcnn"]
    m_cf = metrics["T2_cf_probe_com35"]
    motors = np.arange(4)
    w = 0.25
    ax.bar(motors - w, m_raw["u_classic_last"], width=w, color=C_BLUE, label="Classic Last Trim $u_{C,\\mathrm{last}}$")
    ax.bar(motors, m_raw["u_mcnn_first"], width=w, color=C_RED, label=f"Native MCNN $u_{{N,0}}$ ($\\Delta u_0={m_raw['first_motor_step']:.3f}$)")
    ax.bar(motors + w, m_cf["u_mcnn_first"], width=w, color=C_TEAL, label=f"CF-Probe $u_{{\\mathrm{{CF}},0}}$ ($\\Delta u_0={m_cf['first_motor_step']:.3f}$)")
    for i in range(4):
        ax.text(i - w, m_raw["u_classic_last"][i] + 0.02, f"{m_raw['u_classic_last'][i]:.2f}", ha="center", va="bottom", fontsize=7.5, color=C_BLUE)
        ax.text(i, m_raw["u_mcnn_first"][i] + 0.02, f"{m_raw['u_mcnn_first'][i]:.2f}", ha="center", va="bottom", fontsize=7.5, color=C_RED)
        ax.text(i + w, m_cf["u_mcnn_first"][i] + 0.02, f"{m_cf['u_mcnn_first'][i]:.2f}", ha="center", va="bottom", fontsize=7.5, color=C_TEAL)
    ax.set_xticks(motors)
    ax.set_xticklabels(["Motor 0", "Motor 1", "Motor 2", "Motor 3"])
    ax.set_ylim(0.0, 1.15)
    ax.set_ylabel("Normalized Motor Command [0, 1]")
    ax.set_title("(a) First-Step Motor Trim Discontinuity (+0.35 kg CoM Offset)")
    ax.legend(loc="upper right", fontsize=7.8, framealpha=0.92)

    # (b) Tilt Angle Spike under Steady Wind & CoM Trim Loss
    ax = axs[0, 1]
    ax.axvline(0.0, color="black", ls=":", lw=1.0)
    for rid, lbl, col, ls in [
        ("T2_nom_classic", "Wind 0 m/s Classic", C_GRAY, ":"),
        ("T2_nom_mcnn", "Wind 0 m/s MCNN", C_ORANGE, "-"),
        ("T2_wind50_mcnn", "Headwind 5.0 m/s MCNN", C_VERM, "-"),
        ("T2_wind80_classic", "Headwind 8.0 m/s Classic", C_BLUE, "--"),
        ("T2_wind80_mcnn", "Headwind 8.0 m/s MCNN", C_RED, "-"),
    ]:
        d, m = traces[rid], metrics[rid]
        msk = clip_trace_to_event(d, m, -0.35, 3.2)
        pk = m["windows"]["w_full"]["max_tilt_deg"]
        ax.plot(d["t_rel_s"][msk], d["tilt_deg"][msk], color=col, ls=ls, lw=1.8, label=f"{lbl} (max {pk:.1f}°)")
    ax.set_title("(b) Tilt Spike as Pre-Switch Wind Trim Increases")
    ax.set_xlabel(r"Time Relative to Handover $t - t_{\mathrm{sw}}$ (s)")
    ax.set_ylabel("Total Tilt Angle (deg)")
    ax.set_xlim(-0.35, 3.25)
    ax.legend(loc="upper right", fontsize=7.8, framealpha=0.92)

    # (c) Relative Altitude Drop Δh(t) under Payload/CoM Offset & CF-Probe
    ax = axs[1, 0]
    ax.axvline(0.0, color="black", ls=":", lw=1.0)
    ax.axhline(0.0, color=C_GRAY, ls="-", lw=0.7, alpha=0.6)
    for rid, lbl, col, ls in [
        ("T2_com35_classic", "+0.35 kg CoM Classic-Keep", C_BLUE, "-"),
        ("T2_nom_mcnn", "0 kg Nominal MCNN", C_ORANGE, "-"),
        ("T2_cf_probe_com35", "+0.35 kg CF-Probe [Trim-Aligned]", C_TEAL, "--"),
        ("T2_com35_mcnn", "+0.35 kg CoM Native MCNN", C_VERM, "-"),
        ("T2_com50_mcnn", "+0.50 kg CoM Native MCNN", C_RED, "-"),
    ]:
        d, m = traces[rid], metrics[rid]
        h0 = m["entry"]["h_m"]
        dh = (d["h_m"] - h0) * 100.0
        msk = clip_trace_to_event(d, m, -0.35, 4.0)
        loss = m["windows"]["w_full"]["max_alt_loss_cm"]
        ax.plot(d["t_rel_s"][msk], dh[msk], color=col, ls=ls, lw=1.9, label=f"{lbl} (loss {loss:.1f} cm)")
        if m["outcome"]["status"] == "GROUND_IMPACT_CRASH":
            mark_event(ax, d, m, dh, col, dx=0.1, dy=20.0)
    ax.set_title(r"(c) Altitude Loss $\Delta h(t)$: Mass/CoM Trim Loss vs. CF-Probe")
    ax.set_xlabel(r"Time Relative to Handover $t - t_{\mathrm{sw}}$ (s)")
    ax.set_ylabel(r"$\Delta h$ (cm)")
    ax.set_xlim(-0.35, 4.05)
    ax.legend(loc="lower left", fontsize=7.8, framealpha=0.92)

    # (d) Monotonic Disturbance Sweep Summary (Wind & Payload/CoM)
    ax = axs[1, 1]
    w_x = [0.0, 5.0, 8.0]
    w_rids = ["T2_nom_mcnn", "T2_wind50_mcnn", "T2_wind80_mcnn"]
    w_tilt = [metrics[r]["windows"]["w_full"]["max_tilt_deg"] for r in w_rids]
    w_du = [metrics[r]["first_motor_step"] for r in w_rids]

    m_x = [0.0, 0.35, 0.50]
    m_rids = ["T2_nom_mcnn", "T2_com35_mcnn", "T2_com50_mcnn"]
    m_loss = [metrics[r]["windows"]["w_full"]["max_alt_loss_cm"] for r in m_rids]
    m_vz = [abs(metrics[r]["windows"]["w_full"]["min_v_up_m_s"]) for r in m_rids]

    # Plot normalized severity index / dual panel via twin axis: bottom axis = CoM mass (kg), top axis = Headwind (m/s)
    l1 = ax.plot(m_x, m_loss, "o-", color=C_RED, lw=2.0, markersize=6, label="CoM Sweep: Max Alt. Loss (cm) [bottom x]")
    cf_loss = metrics["T2_cf_probe_com35"]["windows"]["w_full"]["max_alt_loss_cm"]
    l_cf = ax.scatter([0.35], [cf_loss], marker="*", s=130, color=C_TEAL, edgecolor="black", lw=0.7, zorder=8,
                      label=f"CF-Probe (+0.35 kg): {cf_loss:.1f} cm")
    for xv, yv in zip(m_x, m_loss):
        off = (0, 8) if xv != 0.35 else (6, -15)
        ax.annotate(f"{yv:.1f} cm", (xv, yv), xytext=off, textcoords="offset points", ha="center", fontsize=8, color=C_RED, fontweight="bold")
    ax.annotate(f"{cf_loss:.1f} cm (-{(1 - cf_loss/m_loss[1])*100:.0f}%)", (0.35, cf_loss),
                xytext=(-22, 12), textcoords="offset points", ha="center", fontsize=7.8, color=C_TEAL, fontweight="bold")
    ax.set_xlabel("Added Payload Mass with CoM Offset (kg)", color=C_RED)
    ax.set_ylabel("Max Altitude Loss (cm)", color=C_RED)
    ax.set_xlim(-0.05, 0.58)
    ax.set_ylim(-5, max(m_loss) * 1.24)

    ax_top = ax.twiny()
    ax_r = ax.twinx()
    ax_top.spines["top"].set_visible(True)
    ax_r.spines["right"].set_visible(True)
    l2 = ax_r.plot(
        [x / 8.0 * 0.50 for x in w_x], w_tilt, "s--", color=C_NAVY, lw=1.9, markersize=6,
        label="Wind Sweep: Peak Tilt (deg) [top x]"
    )
    ax_top.set_xlim(-0.05 / 0.50 * 8.0, 0.58 / 0.50 * 8.0)
    ax_top.set_xticks(w_x)
    ax_top.set_xticklabels([f"{v:.1f}" for v in w_x])
    ax_top.set_xlabel("Steady Headwind Speed (m/s)", color=C_NAVY)
    ax_r.set_ylabel("Peak Tilt Angle (deg)", color=C_NAVY)
    ax_r.set_ylim(-2, max(w_tilt) * 1.35)
    for xv, yv in zip([x / 8.0 * 0.50 for x in w_x], w_tilt):
        off = (0, -15) if xv > 0.4 else (0, 8)
        ax_r.annotate(f"{yv:.1f}°", (xv, yv), xytext=off, textcoords="offset points", ha="center", fontsize=8, color=C_NAVY, fontweight="bold")
    ax_r.grid(False)
    ax_top.grid(False)

    handles = l1 + [l_cf] + l2
    labels = [h.get_label() for h in handles]
    ax.legend(handles, labels, loc="upper left", fontsize=7.6, framealpha=0.92)
    ax.set_title("(d) Monotonic Degradation vs. Steady Disturbance Load")

    fig.suptitle("T2: Memoryless Feedforward (Cleared Memory) Trim Loss & Counterfactual Attribution", fontsize=12, fontweight="bold")
    save_fig(fig, "mcnn_t2_memoryless_trim")


# =====================================================================
# Figure 3: T3 Reference Continuity Anomaly (T3-A Stale + T3-B Gap)
# =====================================================================
def plot_t3(metrics: dict[str, Any], traces: dict[str, dict[str, np.ndarray]]) -> None:
    fig, axs = plt.subplots(2, 2, figsize=(12.6, 8.6), constrained_layout=True)

    # (a) T3-A Stale Re-entry Displacement Snapback x(t) - x(t_sw)
    ax = axs[0, 0]
    ax.axvline(0.0, color="black", ls=":", lw=1.0)
    ax.axhline(0.0, color=C_GRAY, ls="-", lw=0.7, alpha=0.6)
    t3a_list = [
        ("T3A_stale_d0_fresh", "Fresh Reset ($d_{AB}=0$ m)", C_TEAL, "--"),
        ("T3A_stale_d10_static", "Stale Static ($d_{AB}=1.0$ m)", C_ORANGE, "-"),
        ("T3A_stale_d20_static", "Stale Static ($d_{AB}=2.0$ m)", C_VERM, "-"),
        ("T3A_stale_d35_static", "Stale Static ($d_{AB}=3.5$ m)", C_RED, "-"),
        ("T3A_stale_d20_moving_classic", "Moving 2.2 m/s Classic", C_BLUE, ":"),
        ("T3A_stale_d20_moving_mcnn", "Stale Moving ($d_{AB}=2.0$ m)", C_PURPLE, "-"),
    ]
    for rid, lbl, col, ls in t3a_list:
        d, m = traces[rid], metrics[rid]
        x0 = m["entry"]["x_m"]
        dx = d["x_m"] - x0
        msk = clip_trace_to_event(d, m, -0.35, 3.8)
        sb = m["t3_reference"]["max_snapback_disp_m"]
        ax.plot(d["t_rel_s"][msk], dx[msk], color=col, ls=ls, lw=1.8, label=f"{lbl} (snap {sb:.2f} m)")
        if m["outcome"]["status"] == "GROUND_IMPACT_CRASH":
            dy_v = 1.05 if rid == "T3A_stale_d20_moving_mcnn" else 0.45
            mark_event(ax, d, m, dx, col, dx=0.14, dy=dy_v)
    ax.set_title(r"(a) T3-A Stale Re-Entry: Snapback Displacement $x(t)-x(t_{\mathrm{sw}})$")
    ax.set_xlabel(r"Time Relative to Re-Entry $t - t_{\mathrm{sw}}$ (s)")
    ax.set_ylabel("North Displacement from Point B (m)")
    ax.set_xlim(-0.35, 3.85)
    ax.legend(loc="lower left", fontsize=7.5, framealpha=0.92)

    # (b) T3-A Stale Re-entry Tilt Angle Surge
    ax = axs[0, 1]
    ax.axvline(0.0, color="black", ls=":", lw=1.0)
    for rid, lbl, col, ls in t3a_list:
        d, m = traces[rid], metrics[rid]
        msk = clip_trace_to_event(d, m, -0.35, 3.5)
        pk = m["windows"]["w_full"]["max_tilt_deg"]
        age = m["t3_reference"]["ref_age_at_sw_s"]
        age_str = f", age {age:.1f}s" if np.isfinite(age) else ""
        ax.plot(d["t_rel_s"][msk], d["tilt_deg"][msk], color=col, ls=ls, lw=1.8, label=f"{lbl} ({pk:.1f}°{age_str})")
        if m["outcome"]["status"] == "GROUND_IMPACT_CRASH":
            if rid == "T3A_stale_d20_moving_mcnn":
                mark_event(ax, d, m, d["tilt_deg"], col, dx=-0.88, dy=-12.0)
            else:
                mark_event(ax, d, m, d["tilt_deg"], col, dx=0.20, dy=-22.0)
    ax.set_title("(b) T3-A Stale Re-Entry: Unsmoothed Peak Tilt & Target Age")
    ax.set_xlabel(r"Time Relative to Re-Entry $t - t_{\mathrm{sw}}$ (s)")
    ax.set_ylabel("Total Tilt Angle (deg)")
    ax.set_xlim(-0.35, 3.55)
    ax.set_ylim(-5, 178)
    ax.legend(loc="upper right", fontsize=7.2, framealpha=0.92)

    # (c) T3-B Mid-Flight Reference Freeze/Gap: Brake-then-Chase Speed & Tilt
    ax = axs[1, 0]
    ax.axvline(0.0, color="black", ls=":", lw=1.0)
    ax.axvspan(0.0, 0.24, color=C_ORANGE, alpha=0.14, label="Max gap window (240 ms)")
    t3b_list = [
        ("T3B_gap_classic", "Classic-Keep", C_BLUE, "--"),
        ("T3B_gap_0ms", "Gap 0 ms", C_TEAL, "-"),
        ("T3B_gap_80ms", "Gap 80 ms", C_ORANGE, "-"),
        ("T3B_gap_160ms", "Gap 160 ms", C_VERM, "-"),
        ("T3B_gap_240ms", "Gap 240 ms", C_RED, "-"),
    ]
    for rid, lbl, col, ls in t3b_list:
        d, m = traces[rid], metrics[rid]
        msk = clip_trace_to_event(d, m, -0.30, 3.2)
        pk = m["windows"]["w_full"]["max_tilt_deg"]
        ax.plot(d["t_rel_s"][msk], d["tilt_deg"][msk], color=col, ls=ls, lw=1.8, label=f"{lbl} (max {pk:.1f}°)")
        if m["outcome"]["status"] == "GROUND_IMPACT_CRASH":
            mark_event(ax, d, m, d["tilt_deg"], col, dx=0.1, dy=-15.0)
    ax.set_title("(c) T3-B Mid-Flight Reference Freeze: Brake-Then-Chase Tilt")
    ax.set_xlabel(r"Time Relative to Handover $t - t_{\mathrm{sw}}$ (s)")
    ax.set_ylabel("Total Tilt Angle (deg)")
    ax.set_xlim(-0.30, 3.25)
    ax.legend(loc="upper right", fontsize=7.6, framealpha=0.92)

    # (d) T3-A & T3-B Parameter Sweep Monotonic Curves
    ax = axs[1, 1]
    d_vals = [0.0, 1.0, 2.0, 3.5]
    d_rids = ["T3A_stale_d0_fresh", "T3A_stale_d10_static", "T3A_stale_d20_static", "T3A_stale_d35_static"]
    d_tilt = [metrics[r]["windows"]["w_full"]["max_tilt_deg"] for r in d_rids]
    d_snap = [metrics[r]["t3_reference"]["max_snapback_disp_m"] for r in d_rids]

    g_vals = [0.0, 80.0, 160.0, 240.0]
    g_rids = ["T3B_gap_0ms", "T3B_gap_80ms", "T3B_gap_160ms", "T3B_gap_240ms"]
    g_tilt = [metrics[r]["windows"]["w_full"]["max_tilt_deg"] for r in g_rids]
    g_rmse = [metrics[r]["windows"]["w_full"]["xy_rmse_m"] for r in g_rids]

    l1 = ax.plot(d_vals, d_tilt, "o-", color=C_RED, lw=2.0, ms=6, label="T3-A Stale: Peak Tilt (deg) [bottom x]")
    for x, y in zip(d_vals, d_tilt):
        ax.annotate(f"{y:.1f}°", (x, y), xytext=(0, 7), textcoords="offset points", ha="center", fontsize=8, color=C_RED, fontweight="bold")
    ax.set_xlabel(r"T3-A Stale Target Distance $d_{AB}$ (m)", color=C_RED)
    ax.set_ylabel("Peak Tilt Angle (deg)")
    ax.set_xlim(-0.25, 3.85)
    ymax = max(max(d_tilt), max(g_tilt)) * 1.25
    ax.set_ylim(0, ymax)

    ax_top = ax.twiny()
    ax_top.spines["top"].set_visible(True)
    l2 = ax.plot([v / 240.0 * 3.5 for v in g_vals], g_tilt, "s--", color=C_BLUE, lw=1.9, ms=6, label="T3-B Freeze: Peak Tilt (deg) [top x]")
    for idx_g, (x, y) in enumerate(zip([v / 240.0 * 3.5 for v in g_vals], g_tilt)):
        off = (-22, 8) if idx_g == 2 else (0, -14)
        ax.annotate(f"{y:.1f}°", (x, y), xytext=off, textcoords="offset points", ha="center", fontsize=8, color=C_BLUE, fontweight="bold")
    ax_top.set_xlim(-0.25 / 3.5 * 240.0, 3.85 / 3.5 * 240.0)
    ax_top.set_xticks(g_vals)
    ax_top.set_xticklabels([f"{int(v)}" for v in g_vals])
    ax_top.set_xlabel(r"T3-B Reference Freeze Duration $\Delta t_{\mathrm{ref}}$ (ms)", color=C_BLUE)
    ax_top.grid(False)

    ax.legend(handles=l1 + l2, loc="upper left", fontsize=7.8, framealpha=0.92)
    ax.set_title("(d) Monotonic Peak Tilt Escalation across T3-A & T3-B")

    fig.suptitle("T3: Setpoint Reference Continuity Anomalies (Stale Re-Entry & Mid-Flight Freeze)", fontsize=12, fontweight="bold")
    save_fig(fig, "mcnn_t3_reference_continuity")


# =====================================================================
# Figure 4: T4 Control Authority Delivery Anomaly
# =====================================================================
def plot_t4(metrics: dict[str, Any], traces: dict[str, dict[str, np.ndarray]]) -> None:
    fig, axs = plt.subplots(2, 2, figsize=(12.6, 8.6), constrained_layout=True)

    # (a) Published vs Gazebo-Applied Roll Differential Motor Command (T4_roll_hold80 micro-window)
    ax = axs[0, 0]
    rid_demo = "T4_roll_hold80"
    d80, m80 = traces[rid_demo], metrics[rid_demo]
    msk = (d80["t_rel_s"] >= -0.04) & (d80["t_rel_s"] <= 0.22)
    t = d80["t_rel_s"][msk] * 1000.0  # ms
    # Roll differential in rad/s: (left motors 1+2) - (right motors 0+3)
    rx_diff = 0.5 * (d80["gz_rx_w1"][msk] + d80["gz_rx_w2"][msk]) - 0.5 * (d80["gz_rx_w0"][msk] + d80["gz_rx_w3"][msk])
    cmd_diff = 0.5 * (d80["gz_cmd_w1"][msk] + d80["gz_cmd_w2"][msk]) - 0.5 * (d80["gz_cmd_w0"][msk] + d80["gz_cmd_w3"][msk])
    # Actual physical rotor speed magnitude diff (|joint_w| * 10 due to rotorVelocitySlowdownSim=10 and CW/CCW spin signs)
    jnt_diff = 10.0 * (
        0.5 * (np.abs(d80["gz_joint_w1"][msk]) + np.abs(d80["gz_joint_w2"][msk]))
        - 0.5 * (np.abs(d80["gz_joint_w0"][msk]) + np.abs(d80["gz_joint_w3"][msk]))
    )
    t_pub_ms = m80["t4_delivery"]["t_publish_first_rel_s"] * 1000.0
    t_app_ms = m80["t4_delivery"]["t_apply_first_rel_s"] * 1000.0
    ov80 = m80["t4_delivery"]["overwritten_mcnn_samples"]
    ax.axvspan(t_pub_ms, t_app_ms, color=C_RED, alpha=0.14, label=f"Hold window ({t_app_ms - t_pub_ms:.0f} ms, {ov80} MCNN samples dropped)")
    ax.step(t, rx_diff, where="post", color=C_ORANGE, ls="--", lw=1.9, label="PX4 Published Roll Diff. (rad/s)")
    ax.step(t, cmd_diff, where="post", color=C_RED, lw=2.1, label="Gazebo Applied Motor Cmd Diff. (rad/s)")
    ax.plot(t, jnt_diff, color=C_NAVY, ls=":", lw=1.8, label="Gazebo Physical Rotor Speed Diff. (rad/s)")
    ax.axvline(t_pub_ms, color=C_ORANGE, ls="--", lw=1.0)
    ax.axvline(t_app_ms, color=C_RED, ls="-", lw=1.1)
    ax.set_title("(a) Published vs. Applied Differential Command (Hold = 80 ms)")
    ax.set_xlabel(r"Time Relative to Handover $t - t_{\mathrm{sw}}$ (ms)")
    ax.set_ylabel("Roll Differential Rotor Speed (rad/s)")
    ax.set_xlim(-40, 220)
    ax.set_ylim(-235, 115)
    ax.legend(loc="lower left", fontsize=7.4, framealpha=0.92)

    # (b) Over-Roll & Total Tilt Family across Hold Sweep
    ax = axs[0, 1]
    ax.axvline(0.0, color="black", ls=":", lw=1.0)
    t4_list = [
        ("T4_roll_classic", "Classic-Keep", C_BLUE, "--"),
        ("T4_roll_hold0", "Hold 0 ms (Native)", C_TEAL, "-"),
        ("T4_roll_hold24", "Hold 24 ms", C_ORANGE, "-"),
        ("T4_roll_hold40", "Hold 40 ms", "#D97B00", "-"),
        ("T4_roll_hold60", "Hold 60 ms", C_VERM, "-"),
        ("T4_roll_hold80", "Hold 80 ms", C_RED, "-"),
    ]
    for rid, lbl, col, ls in t4_list:
        d, m = traces[rid], metrics[rid]
        msk = clip_trace_to_event(d, m, -0.30, 1.8)
        pk = m["windows"]["w_full"]["max_tilt_deg"]
        ax.plot(d["t_rel_s"][msk], d["tilt_deg"][msk], color=col, ls=ls, lw=1.8, label=f"{lbl} (max {pk:.1f}°)")
        if m["outcome"]["status"] == "GROUND_IMPACT_CRASH":
            mark_event(ax, d, m, d["tilt_deg"], col, dx=-0.56, dy=-12.0)
    ax.set_title("(b) Roll-Bank Exit Tilt Family vs. Stale-Command Hold Duration")
    ax.set_xlabel(r"Time Relative to Handover $t - t_{\mathrm{sw}}$ (s)")
    ax.set_ylabel("Total Tilt Angle (deg)")
    ax.set_xlim(-0.30, 1.88)
    ax.legend(loc="upper left", fontsize=7.6, framealpha=0.92)

    # (c) Monotonic Degradation vs Δt_hold
    ax = axs[1, 0]
    holds = [0, 24, 40, 60, 80]
    rids = [f"T4_roll_hold{h}" for h in holds]
    tilts = [metrics[r]["windows"]["w_full"]["max_tilt_deg"] for r in rids]
    rolls = [metrics[r]["windows"]["w_full"]["max_roll_deg"] for r in rids]
    losses = [metrics[r]["windows"]["w_full"]["max_alt_loss_cm"] for r in rids]
    c_tilt = metrics["T4_roll_classic"]["windows"]["w_full"]["max_tilt_deg"]

    l1 = ax.plot(holds, tilts, "o-", color=C_RED, lw=2.0, ms=6, label="Max Total Tilt (deg)")
    l2 = ax.plot(holds, rolls, "s--", color=C_VERM, lw=1.7, ms=5.5, label="Peak Bank Roll (deg)")
    l3 = ax.axhline(c_tilt, color=C_BLUE, ls=":", lw=1.4, label=f"Classic-Keep Tilt ({c_tilt:.1f}°)")
    for x, y in zip(holds, tilts):
        off = (2, -16) if x == 80 else (0, 8)
        ax.annotate(f"{y:.1f}°", (x, y), xytext=off, textcoords="offset points", ha="center", fontsize=8, color=C_RED, fontweight="bold")
    ax.set_xlabel(r"Downstream Stale-Command Hold $\Delta t_{\mathrm{hold}}$ (ms)")
    ax.set_ylabel("Peak Attitude Angle (deg)", color=C_RED)
    ax.set_xticks(holds)
    ax.set_xlim(-6, 88)
    ax.set_ylim(0, max(max(tilts), max(rolls)) * 1.15)

    ax_r = ax.twinx()
    ax_r.spines["right"].set_visible(True)
    l4 = ax_r.plot(holds, losses, "^-.", color=C_NAVY, lw=1.8, ms=6, label="Max Alt. Loss (cm)")
    for x, y in zip(holds, losses):
        if x == 80:
            off = (-32, 4)
        elif x == 60:
            off = (2, -15)
        else:
            off = (0, 8)
        ax_r.annotate(f"{y:.1f} cm", (x, y), xytext=off, textcoords="offset points", ha="center", fontsize=7.6, color=C_NAVY, fontweight="bold")
    ax_r.set_ylabel("Max Altitude Loss (cm)", color=C_NAVY)
    ax_r.set_ylim(-25, max(losses) * 1.25)
    ax_r.grid(False)

    hs = l1 + l2 + [l3] + l4
    ax.legend(hs, [h.get_label() for h in hs], loc="upper left", fontsize=7.6, framealpha=0.92)
    ax.set_title(r"(c) Monotonic Over-Roll & Altitude Loss vs. $\Delta t_{\mathrm{hold}}$")

    # (d) Delivery Latency & Overwritten MCNN Samples Audit (incl. Native 0ms Contention)
    ax = axs[1, 1]
    x_idx = np.arange(len(holds))
    lat_ms = [metrics[r]["t4_delivery"]["delivery_latency_ms"] for r in rids]
    ov_cnt = [metrics[r]["t4_delivery"]["overwritten_mcnn_samples"] for r in rids]
    w = 0.36
    b1 = ax.bar(x_idx - w / 2, lat_ms, width=w, color=C_BLUE, label=r"Delivery Latency $t_{\mathrm{apply}}-t_{\mathrm{publish}}$ (ms)")
    for i, v in enumerate(lat_ms):
        ax.text(i - w / 2, v + 1.5, f"{v:.0f}", ha="center", va="bottom", fontsize=8, color=C_BLUE, fontweight="bold")
    ax.set_ylabel("Delivery Latency (ms)", color=C_BLUE)
    ax.set_ylim(0, max(lat_ms) * 1.28)
    ax.set_xticks(x_idx)
    ax.set_xticklabels([f"{h} ms\n(Native)" if h == 0 else f"{h} ms" for h in holds])
    ax.set_xlabel(r"Configured Downstream Hold $\Delta t_{\mathrm{hold}}$")

    ax_r2 = ax.twinx()
    ax_r2.spines["right"].set_visible(True)
    b2 = ax_r2.bar(x_idx + w / 2, ov_cnt, width=w, color=C_RED, alpha=0.88, label="Relay-Dropped MCNN Samples (never applied)")
    for i, v in enumerate(ov_cnt):
        ax_r2.text(i + w / 2, v + 0.5, f"{v}", ha="center", va="bottom", fontsize=8, color=C_RED, fontweight="bold")
    ax_r2.set_ylabel("Relay-Dropped MCNN Samples (count)", color=C_RED)
    ax_r2.set_ylim(0, max(ov_cnt) * 1.28)
    ax_r2.grid(False)

    dual_ms = metrics["T4_roll_hold0"]["t4_delivery"]["dual_pub_overlap_ms"]
    dual_cyc = int(round(dual_ms / 4.0))
    ax.annotate(
        f"Native uORB dual-pub race:\n{dual_ms:.0f} ms ({dual_cyc} cycles) overlap\nbefore allocator disable",
        xy=(0 - w / 2, lat_ms[0] + 2.0),
        xytext=(0.02, max(lat_ms) * 0.56),
        fontsize=7.4, color=C_NAVY, fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.22", facecolor="#FFF8E7", edgecolor=C_ORANGE, lw=0.9),
        arrowprops=dict(arrowstyle="->", color=C_NAVY, lw=0.9),
    )
    ax.legend([b1, b2], [b1.get_label(), b2.get_label()], loc="upper left", fontsize=7.5, framealpha=0.92)
    ax.set_title("(d) Delivery Latency & Dropped MCNN Samples (incl. Native Audit)")

    fig.suptitle("T4: Control Authority Delivery Anomaly — Stale Differential Command Hold Sweep", fontsize=12, fontweight="bold")
    save_fig(fig, "mcnn_t4_authority_delivery")


# =====================================================================
# Figure 5: Global Overview & 4-Step Counterfactual Attribution Ladder
# =====================================================================
def plot_overview_attribution(metrics: dict[str, Any], traces: dict[str, dict[str, np.ndarray]]) -> None:
    fig, axs = plt.subplots(2, 2, figsize=(12.8, 8.8), constrained_layout=True)

    # (a) Global T1-T4 Comparison Bar Chart (Classic-Keep vs MCNN-Takeover Peak Tilt & Alt Loss)
    ax = axs[0, 0]
    pairs = [
        ("T1\nTurn", "T1_turn_w0_classic", "T1_turn_w0_mcnn"),
        ("T1\nWind", "T1_wind_w80_classic", "T1_wind_w80_mcnn"),
        ("T2\nWind", "T2_wind80_classic", "T2_wind80_mcnn"),
        ("T2\nCoM", "T2_com35_classic", "T2_com35_mcnn"),
        ("T3-A\nStale", "T3A_stale_d20_moving_classic", "T3A_stale_d20_moving_mcnn"),
        ("T3-B\nFreeze", "T3B_gap_classic", "T3B_gap_240ms"),
        ("T4\nHold80", "T4_roll_classic", "T4_roll_hold80"),
        ("Comp.\nT1-T4", "ATTR_step4_classic", "ATTR_step0_compound"),
    ]
    x = np.arange(len(pairs))
    w = 0.36
    c_tilts = [metrics[c]["windows"]["w_full"]["max_tilt_deg"] for _, c, _ in pairs]
    n_tilts = [metrics[n]["windows"]["w_full"]["max_tilt_deg"] for _, _, n in pairs]
    ax.bar(x - w / 2, c_tilts, width=w, color=C_BLUE, label="Classic-Keep Oracle")
    ax.bar(x + w / 2, n_tilts, width=w, color=C_RED, label="Native MCNN-Takeover")
    for i, (_, c_id, n_id) in enumerate(pairs):
        ct, nt = c_tilts[i], n_tilts[i]
        ax.text(i - w / 2, ct + 2.5, f"{ct:.0f}°", ha="center", va="bottom", fontsize=7.4, color=C_BLUE, fontweight="bold")
        tag = f"{nt:.0f}°\nCRASH" if metrics[n_id]["outcome"]["status"] == "GROUND_IMPACT_CRASH" else f"{nt:.0f}°"
        ax.text(i + w / 2, nt + 2.5, tag, ha="center", va="bottom", fontsize=7.2, color=C_RED, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([p[0] for p in pairs], fontsize=8.0)
    ax.set_ylabel("Peak Total Tilt Angle (deg)")
    ax.set_ylim(0, max(n_tilts) * 1.26)
    ax.set_title("(a) Global T1–T4 Twin-Execution Comparison (Peak Tilt)")
    ax.legend(loc="upper right", fontsize=8.0, framealpha=0.92)

    # Attribution ladder definitions
    ladder = [
        ("ATTR_step0_compound", "Step 0: Compound (T1+T2+T3+T4)", C_RED, "-"),
        ("ATTR_step1_strip_t4", "Step 1: Strip T4 (0 ms hold)", C_VERM, "-"),
        ("ATTR_step2_strip_t4_t3", "Step 2: Strip T4, T3 (fresh ref)", C_ORANGE, "-"),
        ("ATTR_step3_strip_t4_t3_t2", "Step 3: Strip T4, T3, T2 [CF Trim]", C_TEAL, "--"),
        ("ATTR_step4_classic", "Step 4: Classic-Keep Oracle", C_BLUE, "-"),
    ]

    # (b) 4-Step Attribution Tilt Time Series
    ax = axs[0, 1]
    ax.axvline(0.0, color="black", ls=":", lw=1.0)
    for rid, lbl, col, ls in ladder:
        d, m = traces[rid], metrics[rid]
        msk = clip_trace_to_event(d, m, -0.30, 3.2)
        pk = m["windows"]["w_full"]["max_tilt_deg"]
        ax.plot(d["t_rel_s"][msk], d["tilt_deg"][msk], color=col, ls=ls, lw=1.85, label=f"{lbl} ({pk:.1f}°)")
        if m["outcome"]["status"] == "GROUND_IMPACT_CRASH":
            mark_event(ax, d, m, d["tilt_deg"], col, dx=0.10, dy=-18.0)
    ax.set_title("(b) 4-Step Counterfactual Attribution Ladder: Tilt Angle")
    ax.set_xlabel(r"Time Relative to Handover $t - t_{\mathrm{sw}}$ (s)")
    ax.set_ylabel("Total Tilt Angle (deg)")
    ax.set_xlim(-0.30, 3.25)
    ax.legend(loc="upper right", fontsize=7.4, framealpha=0.92)

    # (c) 4-Step Attribution Altitude Change Δh(t)
    ax = axs[1, 0]
    ax.axvline(0.0, color="black", ls=":", lw=1.0)
    ax.axhline(0.0, color=C_GRAY, ls="-", lw=0.7, alpha=0.6)
    for rid, lbl, col, ls in ladder:
        d, m = traces[rid], metrics[rid]
        h0 = m["entry"]["h_m"]
        dh = (d["h_m"] - h0) * 100.0
        msk = clip_trace_to_event(d, m, -0.30, 3.4)
        loss = m["windows"]["w_full"]["max_alt_loss_cm"]
        ax.plot(d["t_rel_s"][msk], dh[msk], color=col, ls=ls, lw=1.85, label=f"{lbl} (loss {loss:.1f} cm)")
        if m["outcome"]["status"] == "GROUND_IMPACT_CRASH":
            mark_event(ax, d, m, dh, col, dx=0.12, dy=20.0)
    ax.set_title(r"(c) 4-Step Counterfactual Attribution Ladder: Altitude $\Delta h(t)$")
    ax.set_xlabel(r"Time Relative to Handover $t - t_{\mathrm{sw}}$ (s)")
    ax.set_ylabel(r"$\Delta h$ (cm)")
    ax.set_xlim(-0.30, 3.45)
    ax.legend(loc="lower left", fontsize=7.4, framealpha=0.92)

    # (d) Attribution Step-Down Quantitative Bar Summary
    ax = axs[1, 1]
    sx = np.arange(len(ladder))
    s_names = ["Step 0\nRaw\nT1–T4", "Step 1\n-T4\n(0ms)", "Step 2\n-T4,-T3\n(Fresh)", "Step 3\n-T4,-T3,-T2\n[CF Trim]", "Step 4\nClassic\nOracle"]
    s_tilt = [metrics[r]["windows"]["w_full"]["max_tilt_deg"] for r, _, _, _ in ladder]
    s_loss = [metrics[r]["windows"]["w_full"]["max_alt_loss_cm"] for r, _, _, _ in ladder]
    s_vz = [abs(metrics[r]["windows"]["w_full"]["min_v_up_m_s"]) for r, _, _, _ in ladder]

    w = 0.36
    b1 = ax.bar(sx - w / 2, s_tilt, width=w, color=C_RED, alpha=0.9, label="Max Tilt (deg)")
    for i, v in enumerate(s_tilt):
        ax.text(i - w / 2, v + 1.5, f"{v:.1f}°", ha="center", va="bottom", fontsize=7.8, color=C_RED, fontweight="bold")
    ax.set_ylabel("Peak Total Tilt Angle (deg)", color=C_RED)
    ax.set_ylim(0, max(s_tilt) * 1.28)
    ax.set_xticks(sx)
    ax.set_xticklabels(s_names, fontsize=8.0)

    ax_r = ax.twinx()
    ax_r.spines["right"].set_visible(True)
    b2 = ax_r.bar(sx + w / 2, s_loss, width=w, color=C_NAVY, alpha=0.88, label="Max Alt. Loss (cm)")
    for i, v in enumerate(s_loss):
        ax_r.text(i + w / 2, v + 1.5, f"{v:.1f}", ha="center", va="bottom", fontsize=7.8, color=C_NAVY, fontweight="bold")
    ax_r.set_ylabel("Max Altitude Loss (cm)", color=C_NAVY)
    ax_r.set_ylim(0, max(s_loss) * 1.28)
    ax_r.grid(False)

    ax.legend([b1, b2], [b1.get_label(), b2.get_label()], loc="upper right", fontsize=8.0, framealpha=0.92)
    ax.set_title("(d) Marginal Factor Reduction across Attribution Steps")

    fig.suptitle("PX4 mc_nn_control Handover Failures: Global T1–T4 Overview & 4-Step Attribution", fontsize=12, fontweight="bold")
    save_fig(fig, "mcnn_overview_attribution")


def main() -> None:
    metrics, traces = load_all()
    plot_t1(metrics, traces)
    plot_t2(metrics, traces)
    plot_t3(metrics, traces)
    plot_t4(metrics, traces)
    plot_overview_attribution(metrics, traces)
    print(f"Generated 5 PNG+PDF figure pairs in {FIG_DIR}")


if __name__ == "__main__":
    main()

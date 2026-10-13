# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A research harness on an NVIDIA Jetson AGX Thor (aarch64, Ubuntu 24.04, ROS 2 Jazzy, Gazebo Harmonic). It studies handover between PX4's classic multicopter controller and the RAPTOR neural controller (C → N → C), and interventions on controller internal state (reset / hold / snapshot+restore / inject). All flight is **headless SITL only**. Project docs and most comments are in Chinese.

Current project status: **P1 complete** as of 2026-10-13 (`docs/THOR_P1_REPORT.md`, frozen batch `data/p1-20261013-batch-02/`; batch-01 is a retained FAIL record). P0 complete as of 2026-10-12 (closure record `data/p0-closure-20261012/acceptance.json`, rationale in the closing section of `docs/THOR_P0_FINAL_REPORT.md`); the 2026-10-10 P0 FAIL audit is kept unchanged as history. Next phase is P2 (state interventions), not started. No real flight. Joint recovery's position reference is the controller's active `trajectory_setpoint` (user-confirmed 2026-10-12); `config/p1.json` uses `active_controller_target`, which additionally uses RAPTOR's logged internal-target captures while RAPTOR owns the actuators (RAPTOR's target is not published on `trajectory_setpoint`); re-verified on all P0 batch-05 runs with unchanged verdicts. The fixed NED reference is reported only as `fixed_reference_comparison`.

## Repository vs. Lab

- `uav_lab/` is the local, **git-ignored** Lab: PX4 checkouts (`uav_lab/.local/checkouts/px4-{classic,raptor}`), px4_msgs, px4-ros2-interface, XRCE Agent, ROS overlays (`uav_lab/workspaces/{classic,raptor}`), venv (`uav_lab/.local/venv`). Pinned versions are in `environment.lock`. Never download, migrate, or wipe Lab resources.
- The repo holds the research sources, the tools that inject them into the Lab, configs, patches, raw experiment data, and docs.

### How research code reaches PX4

Research code is **not** edited inside the Lab checkouts directly. Instead:

1. `research/state/*.hpp` (state ops engine, uORB bridge, `state` CLI, sample clock, timing, actuator gate) and `research/state/*.msg` (uORB messages) live in this repo.
2. `tools/apply_research.py` copies them into the RAPTOR checkout (`src/lib/handover_research/`, `msg/`) and applies narrow string-anchored edits to `mc_rate_control`, `mc_pos_control`, `mc_raptor`, rate/position control headers, and the POSIX daemon (both variants). It then calls `tools/apply_preparation.py` (replaces RAPTOR's lockstep scheduler with `research/platform/lockstep_scheduler.cpp`, gz_bridge mutex/callback-counter fixes in both variants).
3. Edits must be **idempotent**: each `edit()` returns early if the new text is already present and raises if the anchor is missing. When adding an edit, keep that property; `tests/check_apply_idempotence.py` verifies two applications leave every source byte unchanged. Pitfall: never anchor a new edit *inside* text inserted by an earlier edit — that breaks the earlier edit's "new text present" check, so the next run re-inserts it once and then looks stable (the idempotence test still passes on the already-duplicated file). Anchor after the earlier block, or give the earlier edit a marker check; after adding edits, also confirm each inserted snippet occurs exactly once.
4. All research code is guarded by `#ifdef __PX4_POSIX` and gated at runtime by the PX4 param `MC_RAPTOR_RSH` (default off). State targets: `raptor` (GRU hidden 16 + previous action, dim 26), `rate` (rate integrator, dim 3), `velocity` (velocity integrator, dim 3).
5. After changing Lab sources, `tools/export_patches.py` regenerates `patches/raptor-final.patch`, `patches/raptor-final-untracked.tar.gz`, `patches/classic-final.patch`. On a *clean* pinned RAPTOR checkout apply `raptor-final.patch` + the untracked tarball only (it already includes RouteObservability; do not stack `raptor-existing.patch`).

## Commands

Environment: `source tools/lab-env.sh [classic|raptor]` (also exposed as `uav_lab/env.sh`). It deliberately scrubs inherited ROS/Conda/Python/Gazebo env vars, then sources Jazzy, the variant's overlay, and the Lab venv. Use `uav_lab/.local/venv/bin/python` for project Python.

Experiments (each launches PX4 + Gazebo + XRCE Agent, checks DDS both ways and Agent reconnection, flies, lands, parses ULog; exit 0 = pass):

```bash
./tools/experiment health
./tools/experiment classic_hover | raptor_hover | handover_c_n_c | handover_c_to_n | handover_n_to_c \
    | repeated_handover | state_reset | state_hold | state_restore | state_injection
./tools/experiment state_restore --config config/p0.json --output data/my-new-p0-restore
./tools/experiment classic_hover --startup-only --output data/my-startup-classic   # readiness only, never arms
./tools/experiment analyze data/<run-dir>
```

P1 (`config/p1.json`, kinds `p1_c_to_n`, `p1_n_to_c`, `p1_baseline_classic`, `p1_baseline_raptor`, `--condition S1|S2|S3`): before the subject event the outgoing controller tracks one runner-published `trajectory_setpoint` ramp (classic via OFFBOARD, RAPTOR via its external setpoint input); at the event the stream stops and the incoming controller uses its original mechanism (RAPTOR mode-entry reset hold, classic AUTO_LOITER). Off-origin phases emit `p1_phase_*` events, not `hover_*`, so `analyze.py` does not judge them as hover windows.

```bash
./tools/experiment p1_c_to_n --condition S3 --config config/p1.json --output data/my-p1-run
uav_lab/.local/venv/bin/python tools/p1_metrics.py data/my-p1-run          # -> p1-metrics.json
uav_lab/.local/venv/bin/python tools/p1_batch.py data/<batch> --prefix <prefix> [--pause-after S1]   # --resume continues
uav_lab/.local/venv/bin/python tools/p1_audit.py data/<batch>              # -> batch-audit.json
uav_lab/.local/venv/bin/python tools/p1_report.py data/<batch>             # figures -> docs/figures/p1
```

`tools/experiment` picks the `classic` env for `health`/`classic_hover`, `raptor` for everything else, then dispatches to `tools/health.py`, `tools/analyze.py`, or `tools/run_experiment.py`.

Rebuild (what `tools/prepare_lab.sh` does after venv/colcon setup):

```bash
uav_lab/.local/venv/bin/python tools/apply_research.py
(source tools/lab-env.sh raptor  && make -C "$PX4_SOURCE_DIR" -j8 px4_sitl_raptor)
(source tools/lab-env.sh classic && make -C "$PX4_SOURCE_DIR" -j8 px4_sitl_default)
```

Tests:

```bash
# Python (25 tests); single test: append ::test_name
uav_lab/.local/venv/bin/python -m pytest -q tests/test_readiness.py tests/test_recovery.py tests/test_executor_acceptance.py tests/test_output_chain.py tests/test_p0_closure.py tests/test_p1.py
uav_lab/.local/venv/bin/python -m pytest -q tests/test_recovery.py::test_missing_data_does_not_count_as_continuous

# Header-only C++ units, with sanitizers (as recorded in data/p0-20261010/commands/)
g++ -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined tests/sample_clock_test.cpp -o uav_lab/.local/sample_clock_test && uav_lab/.local/sample_clock_test
g++ -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined tests/state_ops_test.cpp -o uav_lab/.local/state_ops_test && uav_lab/.local/state_ops_test

# Source-injection idempotence (touches Lab checkouts)
python3 tests/check_apply_idempotence.py
```

`tests/lockstep_lifetime_test.cpp` compiles the real scheduler source against stub headers in `tests/lockstep_support/` and must be linked with `-Wl,--wrap=pthread_mutex_lock`. `tests/crash_trace.c` is an optional LD_PRELOAD backtrace helper for the owned PX4 process; `tests/ros_probe/` is a small ROS 2 package.

## Experiment runner architecture (`tools/run_experiment.py`)

- One `Experiment` object per run. A file lock serializes runs on the device. Defaults: PX4 instance 21, MAV system id 22, ROS domain 71, Agent UDP 18888 (`config/experiment.json`). The runner only manages processes it spawned; it never adopts an existing PX4.
- PX4 shell commands go through per-run `cli/px4-<module>` symlinks with `--instance` (logged to `logs/commands.log`). State operations use the in-PX4 `state <raptor|rate|velocity> <read|snapshot|reset|hold|restore|inject|release>` command.
- ROS topics are `/fmu/{in,out}/<name>` with a `_v<N>` suffix when the px4_msgs type has `MESSAGE_VERSION`. `GZ_IP=127.0.0.1` is pinned.
- Readiness gating (`tools/readiness.py`) requires valid raw/selected baro, valid local position, and continuously advancing publications. `--capture-raw-sensors` is diagnostic only; it can change startup behavior.
- Phase boundaries use native PX4 timestamps (via `listener`), not DDS/Agent UTC, which DDS rewrites.
- Analysis: `tools/analyze.py` (ULog → `metrics.json`, `validation.json`, plots) → `tools/p0_metrics.py` (executor scopes `whole_run` / `active` / `neural_actuator_authority`, verdicts `PASS` / `PASS_WITH_WARNINGS` / `FAIL`) and `tools/recovery.py` (joint position/velocity/angular-rate recovery; `SETTLED` / `NOT_SETTLED` / `INSUFFICIENT_OBSERVATION`; any gap >20 ms breaks continuity).
- Output chain (RAPTOR only): every layer is latest-value (uORB `actuator_motors` queue 1 → coalesced ESC work item → single-slot Gazebo motor command consumed per physics step), so "every action executed" is not a valid requirement. The ESC bridge writes the selected `timestamp_sample` into the `gz::msgs::Actuators` header and counts uORB generation gaps (`research_output.skipped_publication_total`). `research/gz/ResearchMulticopterMotorModel.*` is gz-sim 8.11.0's motor model (originals in `research/gz/upstream-8.11.0/`) plus a per-step trace only; `apply_preparation.py` builds it as a PX4 gz plugin and generates `Tools/simulation/research_models/x500/model.sdf` outside the `Tools/simulation/gz` submodule (so candidate identity hashes it). The runner points RAPTOR runs at that model and sets `HANDOVER_GZ_MOTOR_TRACE=<run>/gz-motor`. `tools/output_chain.py <run>` → `output-chain.json`. Applied-command age has a structural floor of one physics step (4 ms) under lockstep.
- A batch re-hashes `tools/`, `research/`, `config/`, the Lab diffs/untracked files, binaries, policy and research plugin before every item: do not edit those while a batch runs, or it stops with `IDENTITY_DRIFT`.
- Batch/audit tools: `tools/preparation_batch.py` (pre-registered cold starts + scenarios, stops at the first failure, keeps `NOT_RUN`), `tools/preparation_trace.py`, `tools/preparation_audit.py <batch-dir>` (independent re-check of a finished batch from raw run evidence → `batch-audit.json`), `tools/p0_closure.py` (P0 closure record from post-fix batch audits), `tools/p0_acceptance.py`, `tools/reanalyze_p0.py`, `tools/acceptance.py` (hard-coded final directories for the 2026-10-09 matrix).

## Data and evidence rules

- `--output` directories must not already exist. Each run keeps `flight.ulg`, `config.json`, `metadata.json` (source commit, diff summary, binary/policy hashes), `events.jsonl`, `telemetry.jsonl`, `logs/`, `metrics.json`, `validation.json`. Only `data/*/rootfs/` and `data/*/cli/` are ignored.
- Never delete, overwrite, or selectively hide failed or diagnostic runs. Never re-run a newer analyzer in place on an old run directory; use `tools/reanalyze_p0.py` into a new directory.
- Never splice passes from different batches or candidate builds into one acceptance result. A fixed build gets a new batch (e.g. `data/preparation-20261011/batch-03/`).
- Do not change frozen thresholds, sim step/deadlines, or policy weights without explicit instruction. Known scope limits: native RAPTOR runs at ~125 Hz under 250 Hz Gazebo while training was 100 Hz; the neural window starts and ends under classic takeoff/landing; executor timing covers observe+control, not just the network forward pass.

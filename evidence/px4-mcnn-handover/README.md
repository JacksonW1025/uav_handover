# PX4 Official `mc_nn_control` Online Handover (C → N) Evidence Archive

This directory contains the self-contained, clean-room experimental evidence archive for online Classical → Neural (`C → N`) control handover on official upstream **PX4 Autopilot `mc_nn_control`** (`src/modules/mc_nn_control/`, feedforward TFLite-Micro MLP) running headless **Gazebo Harmonic x500 SITL**.

All main mechanism runs (`V0`, `T1`, `T2`, `T3-A`, `T3-B`, `T4`, `ATTR`) align the pre-switch heading to **`NED yaw = +90°` (nose East = ENU `0°` equilibrium of official `mc_nn_control`)** and rotate trajectories/wind into the body-aligned East-forward frame to completely eliminate the `+90°` yaw-reference confound. **`T3-C`** explicitly isolates the upstream ignored-yaw-reference anomaly by contrasting `NED yaw = 0°` (PX4 default North takeoff heading) against `NED yaw = +90°` under identical kinematics.

## 1. Pinned Provenance & Frozen Configuration

- **Upstream PX4 Autopilot Commit**: `f364b94f088165ebdc324e7edfae14767beb5bad` (`https://github.com/PX4/PX4-Autopilot.git`)
- **Simulator**: `Gazebo Sim, version 8.14.0` (headless `gz sim -s -r --seed 42`)
- **Fixed Single Seed**: `42` (zero multi-seed repetition; 50 runs total = 3 V0 calibration/equivalence runs + 47 single-seed mechanism runs)
- **Cruise Altitude**: `4.0 m` (`z_NED = -4.0 m`)
- **Aligned Heading (`yaw_ref_deg`)**: `+90.0°` NED (East = ENU `0°`) for all main runs; `0.0°` NED (North) for T3-C ignored-yaw controls
- **Unmodified Official Neural Model & Rescaling**:
  - `control_net.cpp` SHA-256: `70f48109434addab550252b5a75965745f6161e09a60ac7c54a86a322885a47c`
  - `actions_rescale.hpp` SHA-256: `daf9944acdb5bda762ef9da3672733c065477c2e18950d22d75ae44650395fd9`
  - Embedded TFLite flatbuffer (`15088` bytes) SHA-256: `c5334ceac6d1ed6cc30be6b995904bcba21552198be3519ecbb45ee136153364`
- **Compiled PX4 SITL Binaries (stored locally in scratch, hashes archived)**:
  - `vanilla` (100% unmodified upstream): `51b2545177a3fd9a6ac4b6cd8a0fa2fefb2efcc2052a25cffbf321b4bf2dc5eb`
  - `obs` (strictly read-only observation hooks): `d63f616f1aab8ee770d3db9aca34c2ad85c07762002e3eb9f2ccb5981f446f8e`
  - `cf_probe` (opt-in counterfactual trim-alignment diagnostic probe only): `758a16d53eeafea99272797dd659afe821b8c55d729952c60daa7e6b08db5a25`

### Globally Frozen Official PX4 Parameters (Calibrated Once on x500 Hover, Never Retuned Across T1–T4)

| Parameter | Frozen Value |
|---|---|
| `COM_ARM_WO_GPS` | `0` |
| `COM_OF_LOSS_T` | `2.0` |
| `COM_RCL_EXCEPT` | `4` |
| `MC_NN_EN` | `1` |
| `MC_NN_MANL_CTRL` | `0` |
| `MC_NN_MAX_RPM` | `22000` |
| `MC_NN_MIN_RPM` | `1000` |
| `MC_NN_THRST_COEF` | `1.5` |
| `NAV_DLL_ACT` | `0` |
| `SDLOG_MODE` | `1` |
| `SDLOG_PROFILE` | `1` |
| `THR_MDL_FAC` | `0.8` |

### Zero-Perturbation Instrumentation Verification (`V0` Silent Hover, `NED yaw = +90°`)

| Comparison | Vanilla Peak Tilt | Instrumented Peak Tilt | `max|Δh|` | `max|Δxy|` | Clean Landing |
|---|---:|---:|---:|---:|---|
| `vanilla` vs. `obs` (direct) | 1.79° | 1.39° | 1.36 cm | 3.99 cm | Both `LANDED_CLEAN` |
| `vanilla` vs. `obs` + Gazebo Relay (`0 ms`) | 1.79° | 1.36° | 1.79 cm | 3.90 cm | Both `LANDED_CLEAN` |

## 2. Directory Structure

```text
evidence/px4-mcnn-handover/
├── README.md                    # This file
├── metrics.json                 # Single-source metrics computed solely from traces/*.csv.gz
├── provenance.json              # Upstream commit, model/binary/ULog SHA-256 hashes, frozen params
├── manifest.sha256              # Complete SHA-256 manifest of every file in this archive
├── traces/                      # 50 lossless native-250-Hz unsmoothed gzipped CSV traces
├── figures/                     # 5 publication-grade figures (300 DPI PNG + vector PDF)
└── scripts/
    ├── mcnn_readonly_observer.hpp    # Strictly read-only C++ observer header
    ├── px4_readonly_obs.patch        # Strictly read-only observation patch (Commander, mc_nn_control, GZMixingInterfaceESC)
    ├── px4_cf_trim_probe.patch       # Opt-in counterfactual trim-alignment diagnostic probe patch
    ├── gz_motor_relay_plugin/        # Clean-room Gazebo Harmonic motor relay & aerodynamic wind plugin
    ├── gen_sdf.py                    # Clean-room x500 SDF & world generator (wind / payload / CoM / relay)
    ├── run_sitl.py                   # Single-run deterministic SITL harness (MAVLink + official Zenoh + yaw_ref rotation)
    ├── run_campaign.py               # Master single-seed campaign runner (47 runs across T1-T4, T3-C, ATTR)
    ├── metrics_core.py               # Pure offline metric computation library
    ├── extract.py                    # Raw ULog + observer + Gazebo relay -> traces/*.csv.gz + metrics.json
    ├── verify.py                     # Completely offline verification gate (Gates 1A, 1B, 2, 3A, 3B)
    ├── plot.py                       # Single-source figure generator (zero smoothing, zero hard-coded values)
    └── gen_report.py                 # Single-source README & docs/handover/PX4_MCNN_HANDOVER.md generator
```

## 3. Completely Offline Verification & Reproduction

No Gazebo, PX4, or raw `.ulg` files are required to verify every number, figure, and gate in this archive (use Python 3 with `numpy` and `matplotlib`, e.g. `/usr/bin/python3` on Ubuntu 24.04):

```bash
# 1. Run all offline verification gates (Gate 1A/1B heading & twin-prefix, Gate 2 outcomes, Gate 3A <1e-6 recomputation, Gate 3B SHA-256 manifest)
/usr/bin/python3 evidence/px4-mcnn-handover/scripts/verify.py

# 2. Regenerate all 5 PNG + PDF figures directly from traces/*.csv.gz and metrics.json
/usr/bin/python3 evidence/px4-mcnn-handover/scripts/plot.py

# 3. Regenerate this README and docs/handover/PX4_MCNN_HANDOVER.md from metrics.json and provenance.json
/usr/bin/python3 evidence/px4-mcnn-handover/scripts/gen_report.py
```

Full technical analysis and embedded figures are in [`docs/handover/PX4_MCNN_HANDOVER.md`](../../docs/handover/PX4_MCNN_HANDOVER.md).

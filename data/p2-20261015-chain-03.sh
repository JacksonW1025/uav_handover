#!/bin/bash
cd /home/car/uav_handover
PY=uav_lab/.local/venv/bin/python
$PY tools/p2_batch.py data/p2-20261015-batch-s3 --prefix p2-20261015-s3 --groups "p2_c_to_n:S3:N0:5,p2_c_to_n:S3:N1:5,p2_c_to_n:S3:N2:5,p2_c_to_n:S3:N2g:5,p2_baseline_raptor:S3:B:5" --purpose "P2 step 2 (S3, 1.0 m/s): N0/N1/N2 x5 plus N2g x5 (step-1 best N2 is already in the set; N2g separates the GRU part) and the speed-matched RAPTOR S3 baseline x5 (1.05 m/s command, capture 1.00-1.04 m/s). Exploratory budget." || { echo CHAIN_STOP s3; exit 1; }
$PY tools/p2_batch.py data/p2-20261015-batch-nc --prefix p2-20261015-nc --groups "p2_n_to_c:S3:C0:5,p2_n_to_c:S3:C2:5,p2_baseline_classic:S3:B:3" --purpose "P2 step 3 (N->C S3 negative control): C0 original classic takeover and C2 velocity integrator coordinated with RAPTOR's last output, x5 each, and the classic S3 baseline x3 as in-batch reference. Exploratory budget." || { echo CHAIN_STOP nc; exit 1; }
./tools/experiment p2_crash_probe --config config/p2.json --output data/p2-20261015-crash-probe-01 > data/p2-20261015-crash-probe-01.log 2>&1; echo "CRASH_PROBE_EXIT $?"
$PY tools/p2_batch.py data/p2-20261015-dev-06 --prefix p2-20261015-dev06 --groups "p2_baseline_raptor:S1:B:1,p2_c_to_n:X1.5:N0:1,p2_baseline_raptor:X1.5:B:1" --purpose "Development (not acceptance): clean restart right after the crash probe, then smoke test of the exploration profile (6 m reposition) at 1.5 m/s." || { echo CHAIN_STOP dev06; exit 1; }
echo CHAIN_DONE

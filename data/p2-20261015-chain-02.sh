#!/bin/bash
cd /home/car/uav_handover
PY=uav_lab/.local/venv/bin/python
$PY tools/p2_batch.py data/p2-20261015-batch-s1b --prefix p2-20261015-s1b --groups "p2_c_to_n:S1:N0:5,p2_c_to_n:S1:N2g:5,p2_c_to_n:S1:N2s:5,p2_baseline_raptor:S1:B:3" --purpose "P2 step 1b (S1 hover): N0/N2g/N2s x5 and RAPTOR S1 baseline x3 (in-batch baseline for the elimination ratio) on the frozen candidate. Exploratory budget, not a statistical test." || { echo CHAIN_STOP s1b; exit 1; }
$PY tools/p2_batch.py data/p2-20261015-dev-05 --prefix p2-20261015-dev05 --config config/p2-dev-s3cal.json --groups "p2_baseline_raptor:S3:B:2,p2_baseline_raptor:S3h:B:1" --purpose "Development (not acceptance): calibrate the RAPTOR S3 baseline command speed so that its capture speed lies in 1.00-1.04 m/s (1.05 and 1.07 m/s commands)." || { echo CHAIN_STOP dev05; exit 1; }
echo CHAIN_DONE

#!/usr/bin/env bash
set -euo pipefail
cd /home/car/uav_handover
source tools/lab-env.sh raptor
export HANDOVER_CPU_AFFINITY='px4=8-11;gazebo=12-13;agent=6-7;runner=4-5'
export HANDOVER_PX4_BINARY='/home/car/uav_handover/data/handover-t1-entryready-20261115-v1/private-build/px4'
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1
exec python /home/car/handover-experiments-20261116/t2-live/runner.py --arm "$1"

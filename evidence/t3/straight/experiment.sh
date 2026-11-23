#!/usr/bin/env bash
set -euo pipefail
cd /home/car/uav_handover
source tools/lab-env.sh raptor
export HANDOVER_CPU_AFFINITY='px4=8-11;gazebo=12-13;agent=6-7;runner=4-5'
unset HANDOVER_PX4_BINARY
export PYTHONDONTWRITEBYTECODE=1
export OPENBLAS_NUM_THREADS=1
exec python /tmp/handover3h-t3-20261116/fixed_phase_runner.py "$@"

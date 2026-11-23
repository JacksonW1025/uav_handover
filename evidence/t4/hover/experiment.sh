#!/usr/bin/env bash
set -euo pipefail
cd /home/car/uav_handover
source tools/lab-env.sh raptor
export HANDOVER_CPU_AFFINITY='px4=8-11;gazebo=12-13;agent=6-7;runner=4-5'
export OPENBLAS_NUM_THREADS=1
exec python /tmp/handover3h-thor-20261116/t4-active-release/runner.py "$@"

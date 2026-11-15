#!/usr/bin/env bash
set -euo pipefail
artifact_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "${HANDOVER_RESEARCH_ROOT:?set research root}"
source tools/lab-env.sh raptor
export HANDOVER_CPU_AFFINITY='px4=8-11;gazebo=12-13;agent=6-7;runner=4-5'
export OPENBLAS_NUM_THREADS=1
exec python "$artifact_dir/runner.py" "$@"

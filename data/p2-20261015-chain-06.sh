#!/bin/bash
cd /home/car/uav_handover
grep SigIgn /proc/self/status
PY=uav_lab/.local/venv/bin/python
./tools/experiment p2_crash_probe --config config/p2.json --output data/p2-20261015-crash-probe-01 > data/p2-20261015-crash-probe-01.log 2>&1; echo "CRASH_PROBE_EXIT $?"
$PY tools/p2_batch.py data/p2-20261015-dev-06 --prefix p2-20261015-dev06 --groups "p2_baseline_raptor:S1:B:1,p2_c_to_n:X1.5:N0:1,p2_baseline_raptor:X1.5:B:1" --purpose "Development (not acceptance): clean restart right after the crash probe, then smoke test of the exploration profile (6 m reposition) at 1.5 m/s." || { echo CHAIN_STOP dev06; exit 1; }
echo CHAIN_DONE

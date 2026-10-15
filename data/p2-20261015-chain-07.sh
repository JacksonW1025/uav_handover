#!/bin/bash
cd /home/car/uav_handover
grep SigIgn /proc/self/status
PY=uav_lab/.local/venv/bin/python
$PY tools/p2_batch.py data/p2-20261015-batch-nc-02 --prefix p2-20261015-nc2 --flight-failures-are-results --groups "p2_n_to_c:S3:C0:5,p2_n_to_c:S3:C2:5,p2_baseline_classic:S3:B:3" --purpose "P2 step 3 (N->C S3 negative control), new batch after data/p2-20261015-batch-nc stopped on a C2 flight failure: C0 and C2 x5 each and the classic S3 baseline x3. User-approved rule (2026-10-15): pre-registered flight failures are recorded as results; infrastructure failures stop." || { echo CHAIN_STOP nc2; exit 1; }
$PY tools/p2_batch.py data/p2-20261015-batch-explore --prefix p2-20261015-x --exploration --best-treatment N2 --purpose "P2 step 4 exploration: raise speed 1.5 -> 2.0 -> 2.5 -> 3.0 m/s with C->N N0 x3 and RAPTOR own-brake baseline x2 per level; stop escalating at the first level with a pre-registered flight failure; N->C C0 x3 at the highest level; best step-1 treatment (N2) x3 at the failed level. Flight failures are results; infrastructure failures stop." || { echo CHAIN_STOP explore; exit 1; }
echo CHAIN_DONE

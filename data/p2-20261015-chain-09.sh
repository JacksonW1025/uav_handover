#!/bin/bash
cd /home/car/uav_handover
grep SigIgn /proc/self/status
PY=uav_lab/.local/venv/bin/python
$PY tools/p2_batch.py data/p2-20261015-batch-explore-02 --prefix p2-20261015-x2 --exploration --best-treatment N2 --purpose "P2 step 4 exploration (new batch after data/p2-20261015-batch-explore stopped on an abort-induced output-chain bracketing error): raise speed 1.5 -> 2.0 -> 2.5 -> 3.0 m/s with C->N N0 x3 and RAPTOR own-brake baseline x2 per level; stop escalating at the first level with a pre-registered flight failure; N->C C0 x3 at the highest level; best step-1 treatment (N2) x3 at the failed level. Flight failures are results; infrastructure failures stop." || { echo CHAIN_STOP explore2; exit 1; }
echo CHAIN_DONE

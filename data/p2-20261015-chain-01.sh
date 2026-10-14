#!/bin/bash
# Equivalence-02 then, only if equivalent, the S1 batch A (same frozen candidate).
cd /home/car/uav_handover
PY=uav_lab/.local/venv/bin/python
G=$($PY -c "import json;print(json.load(open('config/p2.json'))['p2']['equivalence']['groups'])")
$PY tools/p2_batch.py data/p2-20261015-equivalence-02 --prefix p2-20261015-eq02 --groups "$G" --purpose "Equivalence of the frozen P2 candidate with MC_RAPTOR_RINI=0/MC_RAPTOR_NCO=0 (repeat of the stopped data/p2-20261014-equivalence as a new batch): P1 C->N S1 x3, RAPTOR S1 baseline x2 (config/p1.json), P0 state_restore and state_injection x1 (config/p0.json). Criteria pre-registered in config/p2.json p2.equivalence." || { echo CHAIN_STOP equivalence batch; exit 1; }
(cd tools && ../$PY p2_equivalence.py ../data/p2-20261015-equivalence-02) || { echo CHAIN_STOP not equivalent; exit 1; }
$PY tools/p2_batch.py data/p2-20261015-batch-s1a --prefix p2-20261015-s1a --groups "p2_c_to_n:S1:N0:5,p2_c_to_n:S1:N1:5,p2_c_to_n:S1:N2:5,p2_c_to_n:S1:Nstar:5,p2_baseline_raptor:S1:B:3" --purpose "P2 step 1a (S1 hover): RAPTOR mode-entry treatments N0/N1/N2/N* x5 and RAPTOR S1 baseline x3 on the frozen candidate. Exploratory budget, not a statistical test." || { echo CHAIN_STOP s1a; exit 1; }
echo CHAIN_DONE

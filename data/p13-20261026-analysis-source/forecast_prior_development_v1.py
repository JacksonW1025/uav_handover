import sys,json
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p13.pack import create
from p13.isolated import predict
from p12.score import score
from p9_model import write
out=R/'data/p13-20261026-development-predictions-v1';out.mkdir(exist_ok=False)
for i in range(1,9):
 p=next((R/'data/p13-20261026-development').glob(f'dev{i:02d}-*'));a=p/'analysis-v1';d=out/p.name;d.mkdir()
 create(p/'run',a/'packed',d/'packed');predict(d/'packed',R/'data/p13-20261026-preparation/models',d/'prediction');r=score(d/'prediction',d/'packed',a/'measured/measurement.json',d/'score');print('PREDICTED_DEV',p.name,flush=True)
write(out/'receipt.json',{'schema':'p13-prior-development-causal-recompute-1','records':8,'causal_inputs':'past only; actual future measurements hidden by bwrap; development validation, not formal holdout','new_SITL':0})

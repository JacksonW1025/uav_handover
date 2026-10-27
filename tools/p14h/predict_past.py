"""Past-cutoff initial+predeclared release policy, no future measurements."""
import sys,json,copy,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from p14h.common import *
from p14h.model import forecast
from p14h.delivery import Word

def planned_cell(d,side):
 d=copy.deepcopy(d);i=d['initial'];b=d['plan']['windows_profile_s'][0][1];reads=[i['profile_s']+.004*k for k in range(1,1000) if (i['call_index']+k-1)%2==0];boundary=next(x for x in reads if x>=b+.0045);P=boundary-.004 if side=='BEFORE' else boundary+.0003;d['plan']['p14h_cells']=[{'index':0,'publication_s':P,'delivery_s':P,'nominal_target_boundary_s':boundary}];return d

def compute(inp,out):
 out.mkdir();limit(60);d=json.load(open(inp));P=dict(np.load(R/'data/p13-20261026-freeze/models/policy.npz'));rows=[]
 for side in ['BEFORE','AFTER']:
  q=planned_cell(d,side);r=forecast(q,{},P,word=Word(),observer_library=R/'data/p14r-20261027/offline-build-v2/libop.bin');np.savez_compressed(out/(side+'.npz'),**{k:v for k,v in r.items() if isinstance(v,np.ndarray)});x={k:v for k,v in r.items() if not isinstance(v,np.ndarray)};x.update(policy=side,initial_path=str(inp),data_role='newdiagnosticinitial past prefix; analyst exposed outcome, retrospective; no futuretrueword/stateinforecast',cell=q['plan']['p14h_cells']);write(out/(side+'.json'),x);rows.append(side)
 write(out/'result.json',{'sides':rows,'future_actual_used':False,'unknown_timing':'nominalnextallowedboundary withcommon4.5mslead; realhostarmtime/transport/ordercanmovebranch, conditionalnotallfuturecoverage','fullP':'savedobservable but notsilentlyfed asrestoredfullEKF; heldinitialsourcefusedtargeterror baseline'})

def main():
 if sys.argv[1]=='child':compute(Path(sys.argv[2]),Path(sys.argv[3]));return
 out=register(sys.argv[2],'H2 actualpastcutoff conditionaltwo-side model, no realfutureword');run([PY,Path(__file__),'child',Path(sys.argv[1]).resolve(),out/'worker/result'],out/'worker',cpu=60,wall=80,scope='mechanism analysis sourcepastpredictions')
if __name__=='__main__':main()

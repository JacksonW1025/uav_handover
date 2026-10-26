"""Original frozen experimental execution, independent deterministic analysis v4.
No tools/research/config/binary/model changes. Only unstarted IDs via old driver.
"""
import sys,json
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path[:0]=[str(R/'tools'),str(Path(__file__).parent)]
import p13.campaign as C
from physics_scope_v4 import validate
from p9_model import write,sha
from p9_run import append
import p2_batch

def analyze(target,kind):
 from p12c_platform.workflow import process
 from p13.physics import analyze as physical
 from p13.pack import create
 from p13.isolated import predict
 from p12.score import score
 a=target/'analysis-v1';m=process(target/'run',a,R/'data/p12-cont-20261026-freeze/models',predict=False);legacy=physical(target/'run',a/'physics')
 try:r=validate(target,R/'data/p13-20261026-physics-scope-v4'/target.name)
 except BaseException as e:
  append(C.P/'attempts.jsonl',{'event':'STOP_CRITICAL','id':target.name,'budget_class':kind,'queue':kind,'time':p2_batch.now(),'reason':'new physical/data/phase error after independent scope repair: '+repr(e),'no_retry':True});raise
 create(target/'run',a/'packed',a/'packed-physical');predict(a/'packed-physical',C.Z/'models',a/'prediction');score(a/'prediction',a/'packed-physical',a/'measured/measurement.json',a/'score');write(target/'analysis-result-v4.json',{'schema':'p13-analysis-result-4','engineering':json.load(open(a/'engineering.json'))['status'],'physics_research_phase':r['decision'],'legacy_physics_fullrun_preserved':legacy['status'],'scope_source_sha256':sha(Path(__file__).parent/'physics_scope_v4.py'),'task_outcome':m['task_outcome'],'censored':m['censored'],'experimental_layer_unchanged':True});return m
C.analyze=analyze
if __name__=='__main__':C.main()

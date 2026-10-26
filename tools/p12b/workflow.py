"""P12b explicit pre-read audit, installed solver diagnostic and unchanged isolated models."""
import subprocess,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];PY=ROOT/'uav_lab/.local/venv/bin/python'
def process(run,out,models):
 out.mkdir(parents=True,exist_ok=False)
 def tool(name,args,label):
  with (out/(label+'.log')).open('w') as log:
   subprocess.run(['taskset','-c','0-3',str(PY),str(ROOT/'tools'/name),*map(str,args)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
 sync=out/'observation/synchronized.npz'
 for s,args,label in [('p12/observe.py',[run,'--output',out/'observation'],'observation'),('p12b/audit.py',[run,'--output',out/'native'],'native'),('p12/execution.py',[run,'--output',out/'execution'],'execution'),('p12c/target_replay.py',[sync,'--config',run/'config.json','--output',out/'target'],'target'),('p11/synchronize.py',[run,'--output',out/'send-read'],'send-read'),('p12c/pack.py',[run,'--sync',sync,'--output',out/'packed'],'pack'),('p11/pack.py',['measure',run,'--sync',sync,'--output',out/'measured'],'measure'),('p12c/isolated.py',['--packed',out/'packed','--models',models,'--output',out/'prediction'],'prediction'),('p12/score.py',['--predictions',out/'prediction','--packed',out/'packed','--measurement',out/'measured/measurement.json','--output',out/'score'],'score'),('p12c/validate.py',['--run',run,'--analysis',out,'--output',out/'engineering.json'],'engineering')]:tool(s,args,label)
 traces=[p for p in (run/'gz-motor').glob('dart-solver-*.bin') if p.stat().st_size>0]
 cfg=json.loads((run/'config.json').read_text())
 if cfg.get('p12b',{}).get('solver_observe'):
  # CLI processes may record RNG setter calls only. Audit every nonempty file;
  # select the unique physics file by observed frame types, not by result.
  from p12b.solver import read,analyze
  worlds=[p for p in traces if any(t==3 for t,*_ in read(p))]
  if len(worlds)!=1:raise RuntimeError('unique actual World solver trace missing')
  result=analyze(worlds[0],out/'solver')
  if result['status']!='PASS':raise RuntimeError('independent solver connection audit failed')
  seeds=[]
  import struct
  for p in traces:
   for typ,step,wall,sim,raw in read(p):
    if typ==6:seeds.append({'trace':str(p),'seed':struct.unpack('<Q',raw)[0]})
  expected=json.loads((run/'metadata.json').read_text()).get('sim_seed')
  if expected is None:expected=json.loads((run/'metadata.json').read_text()).get('sim_seed_requested')
  write_seed={'schema':'p12b-actual-seed-1','metadata_seed':expected,'setter_calls':seeds,'source':'passive gz::math::v7::Rand::Seed(unsigned) after original call','scope':'actual Gazebo RNG setter; not a universal PX4/EKF deterministic seed'}
  (out/'actual-seed.json').write_text(json.dumps(write_seed,indent=2)+'\n')
  if expected is None or expected not in [r['seed'] for r in seeds]:raise RuntimeError('case seed not verified in actual simulator RNG setter')
 return json.loads((out/'measured/measurement.json').read_text())
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--models',type=Path,required=True);a=p.parse_args();process(a.run,a.output,a.models)

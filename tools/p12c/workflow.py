"""Frozen formal known-input audits and isolated predictions. Never starts SITL."""
import subprocess,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];PY=ROOT/'uav_lab/.local/venv/bin/python'
def process(run,out,models):
 out.mkdir(parents=True,exist_ok=False)
 def tool(name,args,label):
  with (out/(label+'.log')).open('w') as log:
   subprocess.run(['taskset','-c','0-3',str(PY),str(ROOT/'tools'/name),*map(str,args)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
 sync=out/'observation/synchronized.npz'
 for s,args,label in [('p12/observe.py',[run,'--output',out/'observation'],'observation'),('p12/audit.py',[run,'--output',out/'native'],'native'),('p12/execution.py',[run,'--output',out/'execution'],'execution'),('p12c/target_replay.py',[sync,'--config',run/'config.json','--output',out/'target'],'target'),('p11/synchronize.py',[run,'--output',out/'send-read'],'send-read'),('p12c/pack.py',[run,'--sync',sync,'--output',out/'packed'],'pack'),('p11/pack.py',['measure',run,'--sync',sync,'--output',out/'measured'],'measure'),('p12c/isolated.py',['--packed',out/'packed','--models',models,'--output',out/'prediction'],'prediction'),('p12/score.py',['--predictions',out/'prediction','--packed',out/'packed','--measurement',out/'measured/measurement.json','--output',out/'score'],'score'),('p12c/validate.py',['--run',run,'--analysis',out,'--output',out/'engineering.json'],'engineering')]:tool(s,args,label)
 return json.loads((out/'measured/measurement.json').read_text())
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--models',type=Path,required=True);a=p.parse_args();process(a.run,a.output,a.models)

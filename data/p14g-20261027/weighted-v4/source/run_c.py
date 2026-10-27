import sys,json,time,shutil,tempfile,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from p14g.common import *

def main():
 out=Path(sys.argv[1]).resolve();register(out,'C source proxy candidate:180CPU point+420wall set budget, beforefuture scoring',point_CPU_s=180,set_wall_s=420,total_CPU_upper_s=600,models=['held','fading past rate','source-small-persistent','source-small-iid']);tmp=Path(tempfile.mkdtemp(prefix='p14g-c-'));inp=tmp/'input';inp.mkdir();writable=tmp/'output';writable.mkdir()
 for n in cases():shutil.copyfile(B/'inputs-v1'/n/'input.json',inp/(n+'.json'))
 shutil.copyfile(R/'data/p13-20261026-freeze/models/policy.npz',inp/'policy.npz');shutil.copyfile(OLD/'offline-build-v2/libop.bin',inp/'libop.bin');cmd=['bwrap','--ro-bind','/','/','--tmpfs',str(R/'data'),'--tmpfs',str(R/'export'),'--unshare-net','--unshare-pid','--proc','/proc','--bind',str(writable),str(writable),'--chdir',str(R),str(PY),str(R/'tools/p14g/predict.py'),str(inp),str(writable/'predictions')];t=time.perf_counter()
 with (out/'child.log').open('w') as f:
  try:rc=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=210).returncode
  except subprocess.TimeoutExpired:rc='POINT_WALL_LIMIT'
 write(out/'isolation.json',{'command':cmd,'rc':rc,'wall_s':time.perf_counter()-t,'inputs':{p.name:sha(p) for p in inp.iterdir()},'future_data_visible':False,'tmp':str(tmp)});assert rc==0
 shutil.copytree(writable/'predictions',out/'predictions')
 # Separate manager reserves the rest of the predeclared C budget explicitly.
 sets=out/'sets';sets.mkdir();jobs=[];small=protocol()['C']['parameter_boxes']['small']
 for dynamic,mode in [(False,'persistent'),(False,'per_fusion'),(True,'persistent')]:
  for fiber in ['d02','d03']:
   for a in [0,.25,.5,.75]:jobs.append(dict(panel='joint',fiber=fiber,segment=[a,a+.25],variant='default',scale=0,horizon_s=.32,dynamic=dynamic,innovation_budget=dict(small,mode=mode)))
 write(sets/'jobs-before.json',jobs);rows=[]
 for n,job in enumerate(jobs):
  left=420-sum(r['wall_s'] for r in rows)
  if left<=1:write(sets/'unstarted.json',jobs[n:]);break
  jf=sets/f'job-{n:03d}.json';write(jf,job);rr=child([str(R/'tools/p14g/batch_sets.py'),'child',str(jf),str(sets/f'{n:03d}')],sets/f'{n:03d}',cpu=90,wall=min(90,left));rr.update(n=n,job=job);rows.append(rr);write(sets/f'execution-{n:03d}.json',rr);print('C_SET',n,rr['rc'],flush=True)
 write(sets/'execution.json',rows)
if __name__=='__main__':main()

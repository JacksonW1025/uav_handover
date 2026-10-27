import sys,json,time,shutil,tempfile,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from p14g.common import *

def main():
 out=Path(sys.argv[1]).resolve();pool=[{'id':f'{n}-resume{offset:+03d}','case':n,'offset_ms':offset} for n in cases() for offset in [-8,-4,-2,0,2,4,8]];register(out,'H3: freeze pool,ties, finite competing-model sets before anyfuture score; source noA NORMAL aliases notnewtests',pool=pool,words=['PRE4ms','PRE6ms-phase2ms','PRE10ms-delay4ms','POST4ms'],CPU_s=450,wall_s=480,normal_aliases='same physical input with no A; collapse7aliases intoone test before calculation');tmp=Path(tempfile.mkdtemp(prefix='p14g-select-'));inp=tmp/'input';inp.mkdir();dest=tmp/'output';dest.mkdir()
 for n in cases():shutil.copyfile(B/'inputs-v1'/n/'input.json',inp/(n+'.json'))
 for source,name in [(R/'data/p13-20261026-freeze/models/policy.npz','policy.npz'),(OLD/'offline-build-v2/libop.bin','libop.bin')]:shutil.copyfile(source,inp/name)
 write(inp/'pool.json',pool);cmd=['bwrap','--ro-bind','/','/','--tmpfs',str(R/'data'),'--tmpfs',str(R/'export'),'--unshare-net','--unshare-pid','--proc','/proc','--bind',str(dest),str(dest),'--chdir',str(R),str(PY),str(R/'tools/p14g/select.py'),str(inp),str(dest/'ranking')];t=time.perf_counter()
 with (out/'child.log').open('w') as f:
  try:rc=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=480).returncode
  except subprocess.TimeoutExpired:rc='D_WALL_LIMIT'
 write(out/'isolation.json',{'rc':rc,'wall_s':time.perf_counter()-t,'command':cmd,'input_hashes':{p.name:sha(p) for p in inp.iterdir()},'actual_future_hidden':True,'tmp':str(tmp)});assert rc==0;shutil.copytree(dest/'ranking',out/'ranking')
if __name__=='__main__':main()

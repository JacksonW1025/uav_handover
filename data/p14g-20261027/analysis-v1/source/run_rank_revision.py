import sys,json,time,shutil,tempfile,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from p14g.common import *
def main():
 out=Path(sys.argv[1]).resolve();register(out,'post-exposure H3 uniform andLPsemantic baseline correction; no outcome input orseedsearch',old_rank_sha256=sha(B/'D-v2/ranking/ranking.json'),CPU_s=30,old_baselines_preserved=True);tmp=Path(tempfile.mkdtemp(prefix='p14g-rankfix-'));inp=tmp/'input';inp.mkdir();dest=tmp/'output';dest.mkdir()
 for n in cases():shutil.copyfile(B/'inputs-v1'/n/'input.json',inp/(n+'.json'))
 for p,n in [(B/'D-v2/ranking/ranking.json','ranking.json'),(B/'protocol-seal-v1.json','protocol-seal.json'),(R/'data/p13-20261026-freeze/models/policy.npz','policy.npz'),(OLD/'offline-build-v2/libop.bin','libop.bin')]:shutil.copyfile(p,inp/n)
 cmd=['bwrap','--ro-bind','/','/','--tmpfs',str(R/'data'),'--tmpfs',str(R/'export'),'--unshare-net','--unshare-pid','--proc','/proc','--bind',str(dest),str(dest),'--chdir',str(R),str(PY),str(R/'tools/p14g/ranking_revision.py'),str(inp),str(dest/'ranking')];t=time.perf_counter()
 with (out/'child.log').open('w') as f:rc=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=40).returncode
 write(out/'isolation.json',{'rc':rc,'wall_s':time.perf_counter()-t,'cmd':cmd,'future_hidden':True,'tmp':str(tmp)});assert rc==0;shutil.copytree(dest/'ranking',out/'ranking')
if __name__=='__main__':main()

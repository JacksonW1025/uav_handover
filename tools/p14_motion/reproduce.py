"""Independent isolated point reproduction and conditional tube prefix audit."""
import sys,json,shutil,subprocess,tempfile
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p14.common import sha,write
from p14_motion.tube import run

def main():
 out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=False);base=ROOT/'data/p14-motion-20261027';case='p13-F4-b1-A';tmp=Path(tempfile.mkdtemp(prefix='p14-motion-repro-'));inp=tmp/'input';inp.mkdir();child=tmp/'child';child.mkdir()
 for name in ['models.json','policy.npz']:shutil.copyfile(ROOT/'data/p13-20261026-freeze/models'/name,inp/name)
 shutil.copyfile(base/'inputs-v3'/case/'task-input-nav.json',inp/('case-'+case+'.json'))
 cmd=['bwrap','--ro-bind','/','/','--tmpfs',str(ROOT/'data'),'--tmpfs',str(ROOT/'export'),'--unshare-net','--unshare-pid','--proc','/proc','--bind',str(child),str(child),'--chdir',str(ROOT),'taskset','-c','0-3',str(ROOT/'uav_lab/.local/venv/bin/python'),str(ROOT/'tools/p14_motion/predict.py'),str(inp),str(child/'predictions')]
 with (out/'child.log').open('w') as f:rc=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT).returncode
 write(out/'isolation.json',{'command':cmd,'rc':rc,'temporary_evidence':str(tmp),'new_SITL':0});assert rc==0
 equal={}
 for file in (child/'predictions'/case).glob('*.npz'):
  a=np.load(file);b=np.load(base/'point-v2/predictions'/case/file.name);equal[file.name]=all(np.array_equal(a[k],b[k],equal_nan=True) for k in a.files)
 case='p13-F2-b1-AB-short';doc=json.load(open(base/'inputs-v3'/case/'edge-input.json'));P=dict(np.load(inp/'policy.npz'));fresh,state=run(doc,P,.001,end=doc['initial']['profile_s']+.064,compress_rank=-512,group=True)
 old=json.load(open(base/'tubes-final-v2/03-p13-F2-b1-AB-short-r0.001-joint-group1-obs0-joinbox0/tube.json'));same=fresh['rows']==old['rows'][:16]
 write(out/'reproduction.json',{'point_arrays_exact_equal':equal,'tube_first16_rows_exact_equal':same,'new_SITL':0,'future_data_visible_in_point_child':False,'scope':'four variant arrays of one preselected case +16 source moving tube calls; implementation reproducibility, not independent real-world validation'})
 assert all(equal.values()) and same
 print('REPRODUCED',equal,'tube16',same)

if __name__=='__main__':main()

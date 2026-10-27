"""One fully isolated OFFLINE deterministic reforecast, compare stored arrays."""
import sys,json,shutil,subprocess,tempfile
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p14.common import OUT,records,sha,write

def main():
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--case',default='p13-F4-b1-A');p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 x=next(r for r in records() if r['id']==a.case);tmp=Path(tempfile.mkdtemp(prefix='p14-repro-offline-'));inp=tmp/'input';inp.mkdir();child=tmp/'child';child.mkdir()
 for f in ['models.json','policy.npz']:shutil.copyfile(ROOT/'data/p13-20261026-freeze/models'/f,inp/f)
 doc=json.load(open(x['packed']/'prediction-input.json'));doc['model_sha256']=sha(inp/'models.json');write(inp/f'case-{a.case}.json',doc)
 cmd=['bwrap','--ro-bind','/','/','--tmpfs',str(ROOT/'data'),'--tmpfs',str(ROOT/'export'),'--unshare-net','--unshare-pid','--proc','/proc','--bind',str(child),str(child),'--chdir',str(ROOT),'taskset','-c','0-3',str(ROOT/'uav_lab/.local/venv/bin/python'),str(ROOT/'tools/p14/predict.py'),str(inp),str(child/'prediction')]
 with (out/'child.log').open('w') as f:rc=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT).returncode
 if rc:write(out/'failed.json',{'rc':rc,'command':cmd,'temp':str(tmp)});raise RuntimeError('offline isolated child failed')
 shutil.copytree(child/'prediction'/a.case,out/'prediction');matches={}
 for name in ['G','M14']:
  old=np.load(OUT/'candidate-v1/predictions'/a.case/(name+'.npz'));new=np.load(out/'prediction'/(name+'.npz'));matches[name]=all(np.array_equal(old[k],new[k],equal_nan=True) for k in old.files)
 write(out/'reproduction.json',{'case':a.case,'command':cmd,'rc':rc,'arrays_exact_equal':matches,'new_SITL':0,'future_measurements_copied':False,'temporary_evidence':str(tmp)})
 assert all(matches.values());print('OFFLINE_REPRODUCED',matches)
if __name__=='__main__':main()

"""Offline only. Copy past docs, hide historic measurements, run sealed model."""
import json,sys,shutil,subprocess,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p14.common import records,write,sha,OUT

def main():
 out=Path(sys.argv[1]).resolve();out.mkdir(exist_ok=False)
 temp=Path(tempfile.mkdtemp(prefix='p14-offline-only-'));inp=temp/'inputs';inp.mkdir();child=temp/'outputs';child.mkdir()
 modeldir=ROOT/'data/p13-20261026-freeze/models'
 for f in ['models.json','policy.npz']:shutil.copyfile(modeldir/f,inp/f)
 index=[]
 for r in records():
  f=r['packed']/'prediction-input.json';doc=json.load(open(f));doc['model_sha256']=sha(inp/'models.json')
  write(inp/f"case-{r['id']}.json",doc);index.append({'id':r['id'],'group':r['group'],'source':str(f.relative_to(ROOT)),'source_sha256':sha(f)})
 sources={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'tools/p14').glob('*.py')}
 write(out/'candidate-seal.json',{'schema':'p14-candidate-seal-1','before_compute':True,'models':['G','M14'],'fit':False,'all_new_results_retrospective':True,'sources':sources,'protocol_sha256':sha(ROOT/'config/p14-offline.json'),'model_sha256':sha(inp/'models.json'),'policy_sha256':sha(inp/'policy.npz'),'inputs':index})
 cmd=['bwrap','--ro-bind','/','/','--tmpfs',str(ROOT/'data'),'--tmpfs',str(ROOT/'export'),'--unshare-net','--unshare-pid','--proc','/proc','--bind',str(child),str(child),'--chdir',str(ROOT),'taskset','-c','0-3',str(ROOT/'uav_lab/.local/venv/bin/python'),str(ROOT/'tools/p14/predict.py'),str(inp),str(child/'predictions')]
 t=time.monotonic()
 with (out/'child.log').open('w') as log:rc=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT).returncode
 write(out/'isolation.json',{'command':cmd,'returncode':rc,'seconds':time.monotonic()-t,'temporary_evidence':str(temp),'future_measurements_copied':False,'new_SITL':0})
 if rc:raise RuntimeError('isolated OFFLINE prediction failed; evidence retained')
 shutil.copytree(child/'predictions',out/'predictions');print('P14_OFFLINE_PREDICTION_COMPLETE',len(index),flush=True)
if __name__=='__main__':main()

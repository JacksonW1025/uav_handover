import sys,json,tempfile,shutil,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p14.common import sha,write

def main():
 out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=False);tmp=Path(tempfile.mkdtemp(prefix='p14-motion-offline-'));inp=tmp/'inputs';inp.mkdir();child=tmp/'out';child.mkdir()
 base=ROOT/'data/p14-motion-20261027/inputs-v3'
 for p in base.glob('*/task-input-nav.json'):shutil.copyfile(p,inp/f'case-{p.parent.name}.json')
 for n in ['models.json','policy.npz']:shutil.copyfile(ROOT/'data/p13-20261026-freeze/models'/n,inp/n)
 write(out/'seal.json',{'sources':{str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'tools/p14_motion').glob('*.py')},'protocol':sha(ROOT/'config/p14-motion-offline.json'),'inputs':{p.name:sha(p) for p in inp.iterdir()},'new_SITL':0})
 cmd=['bwrap','--ro-bind','/','/','--tmpfs',str(ROOT/'data'),'--tmpfs',str(ROOT/'export'),'--unshare-net','--unshare-pid','--proc','/proc','--bind',str(child),str(child),'--chdir',str(ROOT),'taskset','-c','0-3',str(ROOT/'uav_lab/.local/venv/bin/python'),str(ROOT/'tools/p14_motion/predict.py'),str(inp),str(child/'predictions')];st=time.monotonic()
 with (out/'child.log').open('w') as f:rc=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT).returncode
 write(out/'isolation.json',{'command':cmd,'rc':rc,'elapsed_s':time.monotonic()-st,'temp_evidence':str(tmp),'future_measurements_copied':False,'new_SITL':0})
 if rc:raise RuntimeError('isolated offline model error, evidence retained')
 shutil.copytree(child/'predictions',out/'predictions');print('OFFLINE_POINTS_COMPLETE')
if __name__=='__main__':main()

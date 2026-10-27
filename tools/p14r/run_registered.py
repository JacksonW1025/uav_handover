"""Sealed model,5 valid new records, future-hidden offline prediction.
This preserves all prior diagnostic outputs and does not create independent
prospective task0 evidence from outcome-exposed initial-prefix calculations.
"""
import sys,json,shutil,tempfile,subprocess,time
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p14.common import write,sha
def main():
 out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=False);tmp=Path(tempfile.mkdtemp(prefix='p14r-final-'));inp=tmp/'input';inp.mkdir();child=tmp/'output';child.mkdir();b=R/'data/p14r-20261027';seal=json.load(open(b/'stage2-model-seal.json'));core=['model.py','exact_observer.py','op.py','delivery.py','predict_registered.py'];assert all(sha(R/'tools/p14r'/n)==seal['files']['tools/p14r/'+n] for n in core)
 for n in ['d02','d03','d04','d05','d06']:
  dest=inp/n;dest.mkdir();version='source-inputs-v3' if n in ['d02','d03','d04'] else 'source-inputs-v4';shutil.copyfile(b/version/n/'input.json',dest/'input.json');shutil.copyfile(R/'data/p13-20261026-freeze/models/policy.npz',dest/'policy.npz')
 shutil.copyfile(b/'offline-build-v2/libop.bin',inp/'libop.bin')
 code='''import sys,subprocess,json,time
from pathlib import Path
import numpy as np
R=Path('/home/car/uav_handover');sys.path.insert(0,str(R/'tools'))
from p14r.model import forecast
from p14.common import write
inp,out=map(Path,sys.argv[1:]);out.mkdir();assert not any((R/'data').iterdir()) and not any((R/'export').iterdir())
for folder in sorted(x for x in inp.iterdir() if x.is_dir()):
 target=out/folder.name;subprocess.run([str(R/'uav_lab/.local/venv/bin/python'),str(R/'tools/p14r/predict_registered.py'),str(folder),str(target),str(inp/'libop.bin')],check=True)
 P=dict(np.load(folder/'policy.npz'));doc=json.load(open(folder/'input.json'));st=time.perf_counter();r=forecast(doc,{},P);np.savez_compressed(target/'old-complement.npz',**{k:v for k,v in r.items() if isinstance(v,np.ndarray)});row={k:v for k,v in r.items() if not isinstance(v,np.ndarray)};row.update(name='old-complement',elapsed_s=time.perf_counter()-st);write(target/'old-complement.json',row);print('REGISTERED_CASE_DONE',folder.name,flush=True)
''';script=tmp/'child.py';script.write_text(code)
 write(out/'before-compute.json',{'core_still_matches_pre_d05_d06_seal':core,'seal_hash':sha(b/'stage2-model-seal.json'),'inputs':{str(p.relative_to(inp)):sha(p) for p in inp.rglob('*') if p.is_file()},'script':sha(script),'exposure':'three passive identification/replication records; two targeted diagnostic validation after model sealing, outcomes exposed before this past-only forecast. No independent prospective/population accuracy claim','models_per_case':9,'independent_record_denominator':5,'parameters_from_future':False})
 cmd=['bwrap','--ro-bind','/','/','--tmpfs',str(R/'data'),'--tmpfs',str(R/'export'),'--unshare-net','--unshare-pid','--proc','/proc','--bind',str(child),str(child),'--chdir',str(R),'taskset','-c','0-3',str(R/'uav_lab/.local/venv/bin/python'),str(script),str(inp),str(child/'predictions')];st=time.perf_counter()
 with (out/'child.log').open('w') as log:rc=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT).returncode
 write(out/'isolation.json',{'command':cmd,'rc':rc,'elapsed_s':time.perf_counter()-st,'evidence_tmp':str(tmp),'future_data_visible':False});assert rc==0
 shutil.copytree(child/'predictions',out/'predictions')
if __name__=='__main__':main()

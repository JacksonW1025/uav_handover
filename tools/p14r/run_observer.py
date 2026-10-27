"""Past-only autonomous source-observer comparisons in a future-data sandbox."""
import sys,json,time,tempfile,shutil,subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p14.common import write,sha

CHILD='''import sys,json,time
from pathlib import Path
import numpy as np
R=Path('/home/car/uav_handover');sys.path.insert(0,str(R/'tools'))
from p14r.model import forecast
from p14r.delivery import Word
from p14.common import write
inp,out=map(Path,sys.argv[1:]);out.mkdir();P=dict(np.load(inp/'policy.npz'));M=json.load(open(inp/'models.json'))['M2'];rows=[]
assert not any((R/'data').iterdir()) and not any((R/'export').iterdir())
for f in sorted(inp.glob('case-*.json')):
 doc=json.load(open(f));case=f.stem[5:];target=out/case;target.mkdir()
 for variant,library,delay in [('old-complement',None,0),('source-OP-held-fusion',inp/'libop.bin',0),('source-OP-joint-delay',inp/'libop.bin',.004),('empirical-source-OP',inp/'libop.bin',0)]:
  st=time.perf_counter();r=forecast(doc,M,P,variant='empirical_same_observer' if variant=='empirical-source-OP' else 'source',word=Word(0,delay),observer_library=library)
  np.savez_compressed(target/(variant+'.npz'),**{k:v for k,v in r.items() if isinstance(v,np.ndarray)})
  row={k:v for k,v in r.items() if not isinstance(v,np.ndarray)};row.update(case=case,model=variant,elapsed_s=time.perf_counter()-st);write(target/(variant+'.json'),row);rows.append(row);print(case,variant,len(r['trace']),r['stop'],flush=True)
write(out/'summary.json',rows)
'''
def main():
 out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=False);tmp=Path(tempfile.mkdtemp(prefix='p14r-op-'));inp=tmp/'inputs';inp.mkdir();child=tmp/'child';child.mkdir()
 for p in (R/'data/p14r-20261027/source-inputs-v2').glob('*/input.json'):shutil.copyfile(p,inp/('case-'+p.parent.name+'.json'))
 for name in ['models.json','policy.npz']:shutil.copyfile(R/'data/p13-20261026-freeze/models'/name,inp/name)
 shutil.copyfile(R/'data/p14r-20261027/offline-build-v2/libop.bin',inp/'libop.bin');script=tmp/'child.py';script.write_text(CHILD)
 write(out/'before-compute.json',{'question':'source causal output-buffer/correction vs old complementary observer; angular source vs empirical with same source observer','variants':4,'input_hashes':{p.name:sha(p) for p in inp.iterdir()},'code_hashes':{str(p.relative_to(R)):sha(p) for p in (R/'tools/p14r').glob('*.py')},'script':sha(script),'exposure':'all passive data diagnostic; no independent prospective claim','parameter_rule':'held past fusion residual and causal physical prefix only; no future actual input copied','thresholds':'protocol-v1 unchanged','first_affected_queue':'latest generated motor command, consumed command separate'})
 cmd=['bwrap','--ro-bind','/','/','--tmpfs',str(R/'data'),'--tmpfs',str(R/'export'),'--unshare-net','--unshare-pid','--proc','/proc','--bind',str(child),str(child),'--chdir',str(R),'taskset','-c','0-3',str(R/'uav_lab/.local/venv/bin/python'),str(script),str(inp),str(child/'predictions')]
 st=time.perf_counter()
 with (out/'child.log').open('w') as log:rc=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT).returncode
 write(out/'isolation.json',{'command':cmd,'rc':rc,'elapsed_s':time.perf_counter()-st,'temporary_evidence':str(tmp),'future_data_hidden':True})
 if rc:raise RuntimeError('offline source observer failure retained')
 shutil.copytree(child/'predictions',out/'predictions')
if __name__=='__main__':main()

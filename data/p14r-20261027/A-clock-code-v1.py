"""Prototype retained in data so running SITL candidate tools stay unchanged."""
import sys,json,time,tempfile,shutil,subprocess,hashlib
from pathlib import Path
import numpy as np
R=Path('/home/car/uav_handover');sys.path.insert(0,str(R/'tools'))
from p14.common import write,sha
base=R/'data/p14r-20261027';out=base/'A-clock-v1';out.mkdir(exist_ok=False);tmp=Path(tempfile.mkdtemp(prefix='p14r-clock-'));inp=tmp/'input';inp.mkdir();child=tmp/'child';child.mkdir()
cases=['p13-F2-b1-AB-short','p13-F4-b1-A','p13-F4-b1-AB-medium']
for case in cases:
 doc=json.load(open(R/'data/p14-motion-20261027/inputs-v3'/case/'edge-input.json'));doc['initial']=json.load(open(base/'B-joint-support-v1'/case/'initial.json'))['initial'];write(inp/(case+'.json'),doc)
shutil.copyfile(R/'data/p13-20261026-freeze/models/policy.npz',inp/'policy.npz');shutil.copyfile(R/'data/p13-20261026-freeze/models/models.json',inp/'models.json')
code='''import sys,json,time
from pathlib import Path
import numpy as np
R=Path('/home/car/uav_handover');sys.path.insert(0,str(R/'tools'))
from p14r.model import forecast
from p14r.delivery import WORDS
from p14.common import write
inp=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir();P=dict(np.load(inp/'policy.npz'));M=json.load(open(inp/'models.json'))['M2'];rows=[]
assert not any((R/'data').iterdir()) and not any((R/'export').iterdir())
for f in sorted(inp.glob('*.json')):
 if f.name=='models.json':continue
 doc=json.load(open(f));a,b=doc['plan']['full_source_windows_profile_s'][:2];end=max(a[1]+2,b[1]+.5)
 for n,word in enumerate(WORDS):
  st=time.perf_counter();r=forecast(doc,M,P,limit=end,word=word);tr=r['trace'];stale=tr[:,34].astype(bool);caps=np.flatnonzero(stale&np.r_[False,~stale[:-1]]);res=np.flatnonzero(~stale&np.r_[False,stale[:-1]])
  target=out/f.stem;target.mkdir(exist_ok=True);np.savez_compressed(target/('word'+str(n)+'.npz'),trace=tr,states=r['states'],inputs=r['inputs'])
  row={'case':f.stem,'word':n,'poll_phase_s':word.poll_phase_s,'transport_s':word.transport_s,'capture':tr[caps,0].tolist(),'resume':tr[res,0].tolist(),'stop':r['stop'],'elapsed_s':time.perf_counter()-st,'initial_scope':'actualjoint A-pre past only; no future clock/cache','future_actual_used':False};write(target/('word'+str(n)+'.json'),row);rows.append(row)
write(out/'summary.json',rows)
'''
script=tmp/'child.py';script.write_text(code);write(out/'before-compute.json',{'cases':cases,'words':8,'input_sha256':{p.name:sha(p) for p in inp.iterdir()},'source_sha256':{str(p.relative_to(R)):sha(p) for p in [R/'tools/p14r/model.py',R/'tools/p14r/delivery.py']},'child_sha256':sha(script),'future_data':'hidden','new_starts':1})
cmd=['bwrap','--ro-bind','/','/','--tmpfs',str(R/'data'),'--tmpfs',str(R/'export'),'--unshare-net','--unshare-pid','--proc','/proc','--bind',str(child),str(child),'--chdir',str(R),'taskset','-c','0-3',str(R/'uav_lab/.local/venv/bin/python'),str(script),str(inp),str(child/'predictions')]
with (out/'child.log').open('w') as log:rc=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT).returncode
write(out/'isolation.json',{'command':cmd,'rc':rc,'tmp':str(tmp),'future_actual_copied':False});assert rc==0
shutil.copytree(child/'predictions',out/'predictions');print('A_CLOCK_WORDS_COMPUTED',len(cases)*8)

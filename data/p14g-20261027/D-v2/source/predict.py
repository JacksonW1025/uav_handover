"""Future-hidden point model and test selection computations (no raw paths)."""
import sys,json,time,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from p14g.model import forecast
from p14g.observer import Observer
from p14g.delivery import Word
from p14g.common import write,limit

def main():
 inp,out=map(Path,sys.argv[1:3]);limit(180);out.mkdir();P=dict(np.load(inp/'policy.npz'));lib=inp/'libop.bin'
 for f in sorted(inp.glob('d*.json')):
  name=f.stem;d=json.load(open(f));target=out/name;target.mkdir();models=[('held',Word(),False)]+[(f'fading-{order}-{phase}-{delay}',Word(phase,delay,producer_order=order),True) for order in ['PRE','POST'] for phase in [0.,.002] for delay in [0.,.004]]
  for label,word,fading in models:
   packet=copy.deepcopy(d)
   if not fading:packet['initial']['p14g_innovation']['mode']='held'
   start=time.perf_counter();r=forecast(packet,{},P,word=word,observer_library=lib);np.savez_compressed(target/(label+'.npz'),**{k:v for k,v in r.items() if isinstance(v,np.ndarray)});summary={k:v for k,v in r.items() if not isinstance(v,np.ndarray)};summary.update(elapsed_s=time.perf_counter()-start,word=vars(word),input_source='past initial+plan only');write(target/(label+'.json'),summary)
  print('C_PREDICTED',name,flush=True)
if __name__=='__main__':main()

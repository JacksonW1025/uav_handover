"""Frozen conditional source model over8 persistent legal-order representatives.
Unknown switching is NOT covered by the finite union; clock brackets/state
conditions in clock_reach are separate. This tool reads only past input+policy.
"""
import sys,json,time
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p14.common import write,sha
from p14r.model import forecast
from p14r.delivery import Word

def main():
 inp,out,lib=map(Path,sys.argv[1:]);out.mkdir(parents=True,exist_ok=False);P=dict(np.load(inp/'policy.npz'));doc=json.load(open(inp/'input.json'));rows=[]
 write(out/'before-compute.json',{'input_hash':sha(inp/'input.json'),'library_hash':sha(lib),'policy_hash':sha(inp/'policy.npz'),'model':'M14R-source-OP-held-fusion-1','finite_words':8,'future_measurements':False,'scope':'no observed future trigger/native/cache word; persistent PRE/POST producer order and target transport condition. Not all changing schedules.'})
 for order in ['PRE','POST']:
  for phase in [0.,.002]:
   for delay in [0.,.004]:
    st=time.perf_counter();word=Word(phase,delay,producer_order=order);r=forecast(doc,{},P,observer_library=lib,word=word);name=f'{order}-phase{phase}-jointdelay{delay}';np.savez_compressed(out/(name+'.npz'),**{k:v for k,v in r.items() if isinstance(v,np.ndarray)});row={k:v for k,v in r.items() if not isinstance(v,np.ndarray)};row.update(name=name,elapsed_s=time.perf_counter()-st,word=vars(word),joint_delay_interpretation='changes BOTH target transport and observer publication delay; not isolated cache causation');write(out/(name+'.json'),row);rows.append(row)
 write(out/'summary.json',rows)
if __name__=='__main__':main()

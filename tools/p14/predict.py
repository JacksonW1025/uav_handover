"""Runs inside namespace with data/export hidden, sanitized initial docs only."""
import sys,json,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p14.model import forecast
from p14.common import write,sha

def main():
 inp=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(exist_ok=False)
 if any((ROOT/'data').iterdir()) or any((ROOT/'export').iterdir()):raise RuntimeError('future visible')
 params=json.load(open(inp/'models.json'));P=dict(np.load(inp/'policy.npz'))
 for f in sorted(inp.glob('case-*.json')):
  doc=json.load(open(f));case=out/f.stem.removeprefix('case-')
  case.mkdir();meta={'schema':'p14-prediction-1','models':{},'retrospective':True,'filesystem_future_data_visible':False,'input_sha256':sha(f)}
  for name in ['G','M14']:
   start=time.perf_counter();r=forecast(doc,params['M2'],P,name);tr=r.pop('trace');nt=r.pop('native_us')
   np.savez_compressed(case/(name+'.npz'),trace=tr,native_us=nt);meta['models'][name]=dict(r,compute_s=time.perf_counter()-start)
  write(case/'prediction.json',meta);print(case.name,{k:v['stop'] for k,v in meta['models'].items()},flush=True)
if __name__=='__main__':main()

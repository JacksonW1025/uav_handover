"""Isolated source+observer point calculations. Data tree must be hidden."""
import sys,json,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p14.common import write,sha
from p14_motion.core import forecast

def main():
 inp=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(exist_ok=False)
 if any((ROOT/'data').iterdir()) or any((ROOT/'export').iterdir()):raise RuntimeError('historic future data visible')
 M=json.load(open(inp/'models.json'))['M2'];P=dict(np.load(inp/'policy.npz'))
 variants=['source','empirical_same_observer','source_no_gyro_filter','source_no_att_delay']
 for f in sorted(inp.glob('case-*.json')):
  doc=json.load(open(f));name=f.stem.removeprefix('case-');case=out/name;case.mkdir();meta={'retrospective':True,'future_data_visible':False,'input_sha256':sha(f),'models':{}}
  for variant in variants:
   st=time.perf_counter();r=forecast(doc,M,P,variant);arrays={k:r.pop(k) for k in ['trace','states','inputs','native_us']};np.savez_compressed(case/(variant+'.npz'),**arrays);meta['models'][variant]=dict(r,compute_s=time.perf_counter()-st)
  if name=='p13-F2-b1-AB-short':
   for scenario in ['native_plateau','extra_command_delay']:
    st=time.perf_counter();r=forecast(doc,M,P,scenario=scenario);arrays={k:r.pop(k) for k in ['trace','states','inputs','native_us']};np.savez_compressed(case/(scenario+'.npz'),**arrays);meta['models'][scenario]=dict(r,compute_s=time.perf_counter()-st,scenario=scenario)
  write(case/'prediction.json',meta);print('POINT_DONE',name,{k:v['stop'] for k,v in meta['models'].items()},flush=True)
if __name__=='__main__':main()

"""Last bounded representation check: scaled important directions retained exactly.
No further candidate search: three fixed F2 sets, one compression algorithm.
"""
import sys,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p14_motion.tube import run
from p14.common import write,sha
def main():
 out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);doc=json.load(open(ROOT/'data/p14-motion-20261027/inputs-v2/p13-F2-b1-AB-short/edge-input.json'));P=dict(np.load(ROOT/'data/p13-20261026-freeze/models/policy.npz'))
 tests=[('physical-scenario',1,False),('micro-scenario',.001,False),('observed-conditioned',1,True)]
 write(out/'before-compute.json',{'reason':'uncompressedmicro64ms remainsnarrow, SVD24 andfullrankbothloseprecision; test one direction-preserving compressed representation. Mixed physical units also require scaled selection.','tests':tests,'keep_initial':True,'keep_additional_directions':512,'discarded':'rowL1 diagonal outer enclosure','no_more_search_after_this':True,'sources':{str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'tools/p14_motion').glob('*.py')}})
 res=[]
 for name,scale,conditioned in tests:
  r,s=run(doc,P,scale,'joint',end=doc['plan']['full_source_windows_profile_s'][1][1]+2,compress_rank=-512,conditioned=conditioned);write(out/name/'tube.json',r);res.append({'id':name,'first_precision':r['first_precision_loss'],'domain':r['first_domain_loss'],'last':r['last_completed_t'],'elapsed_s':r['elapsed_s'],'peak_rss_kib':r['peak_rss_kib']});np.savez_compressed(out/name/'successor-local.npz',**{k+'_center':v.c for k,v in s.items()},**{k+'_generators':v.pad() for k,v in s.items()});print('DIRECTIONS',name,r['last_completed_t'],r['first_domain_loss'],flush=True)
 write(out/'summary.json',res)
if __name__=='__main__':main()

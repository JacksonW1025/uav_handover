"""Finite pre-recorded structural check after rank24 zero-radius growth.
No plant/score tuning. Same F2 point and predeclared 64ms/full-edge horizon.
"""
import sys,json,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p14_motion.tube import run
from p14.common import write,sha
def main():
 out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);base=ROOT/'data/p14-motion-20261027';doc=json.load(open(base/'inputs-v2/p13-F2-b1-AB-short/edge-input.json'));P=dict(np.load(ROOT/'data/p13-20261026-freeze/models/policy.npz'))
 tests=[{'id':'fullrank-zero','scale':0,'rank':999,'conditioned':False},{'id':'fullrank-micro','scale':.001,'rank':999,'conditioned':False},{'id':'fullrank-observed-conditioned','scale':1,'rank':999,'conditioned':True},{'id':'uncompressed-micro-64ms','scale':.001,'rank':None,'conditioned':False}]
 write(out/'before-compute.json',{'reason':'rank24 joint loses domain almost same22calls for micro andzero; investigate outer-enclosure compression rather than attribute to source motion','fixed_tests':tests,'conditioned_definition':'same physical1cm/.1deg/filter1rad domain, observed LP/attitude/gyro-delay/bias/h/previous/mean components now conditioned within1e-6; hypothetical observation-conditioned model set, not actual EKF membership','no_new_candidates_or_data':True,'sources':{str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'tools/p14_motion').glob('*.py')}})
 rows=[]
 for t in tests:
  end=doc['initial']['profile_s']+.064 if t['rank'] is None else doc['plan']['full_source_windows_profile_s'][1][1]+.5
  r,s=run(doc,P,t['scale'],'joint',end,t['rank'],t['conditioned']);write(out/t['id']/'tube.json',r);rows.append({'test':t,'last_completed_t':r['last_completed_t'],'precision':r['first_precision_loss'],'domain':r['first_domain_loss'],'elapsed_s':r['elapsed_s'],'peak_rss_kib':r['peak_rss_kib']});print('STRUCTURE',t['id'],r['last_completed_t'],r['first_domain_loss'],flush=True)
 write(out/'summary.json',rows)
if __name__=='__main__':main()

"""Check the reduced affine attempt's first omitted source angular connection.
Not a new predictor or a search: one fixed nominal member, same16 calls.
"""
import sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p14.common import write
from p11.observe import network,inputs
from p11.models import speeds
from p12.execution import step
from p13.physical_model import source_step,mass

def main():
 P=dict(np.load(ROOT/'data/p13-20261026-freeze/models/policy.npz'));p=np.array([0.,0.,-3.]);v=np.array([1.8,0,.1]);q=np.array([1.,0,0,0]);w=np.zeros(3);f=np.full(4,770.);pending=f.copy();h=np.zeros(16);previous=np.full(4,.45);mean=previous.copy();count=0;lp=p.copy();lv=v.copy();rows=[]
 for k in range(1,17):
  nxt=step(f,pending,.004)
  _,_,qn,wn=source_step(p,v,q,w,f,nxt,.004)
  rows.append({'call':k,'source_next_omega_norm':float(np.linalg.norm(wn)),'source_next_quaternion_delta_norm':float(np.linalg.norm(qn-q)),'assumed_omega':0.,'assumed_level_attitude':'identity','commands':pending.tolist(),'filter':f.tolist()})
  # Continue the exact reduced nominal, deliberately not feeding source angular
  # motion back: test compatibility of its external fixed-pose hypothesis.
  v[2]+=.004*(9.8-8.54858e-6*np.sum(f*f)/mass);p+=.004*v;f=nxt
  if k%2==0:lp=p.copy();lv=v.copy()
  t=.004*k;r=np.array([1.8*t-t*t,0,-3.]);s=np.array([1.8-2*t,0,0]);mean=(count*mean+previous)/(count+1)
  hn,raw,action=network(P,h,np.r_[inputs(lp,lv,q,w,r,s,0.),mean])
  if k%2==0:h=hn;count=0
  else:count+=1
  previous=action;pending=speeds(action)
 first=next((r for r in rows if r['source_next_omega_norm']>1e-12),None)
 write(Path(sys.argv[1]),{'schema':'p14-first-source-extension-1','nominal_member':'same fixed affine-attempt point with zero uncertainty','rows':rows,'first_nonzero_source_angular_step':first,'result':'FIXED_LEVEL_ZERO_OMEGA_NOT_SOURCE_INVARIANT' if first else 'NO_COUNTEREXAMPLE_IN_FIXED_HORIZON','meaning':'the narrow correlated result is genuine for its reduced conditioned map, but cannot be promoted to the real closed-loop source by keeping pose frozen. Need to propagate angular/gyro/EKF/cache jointly. This is not a counterexample to other joint-set methods.','new_candidates':0,'new_SITL':0})
if __name__=='__main__':main()

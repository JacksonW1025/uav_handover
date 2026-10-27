"""Source analytic discrete adjoint for all-prefix safety-output importance.
A fixed8-row sketch is a priority heuristic, never a nonlinear inclusion proof.
"""
import sys,json,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from p14g.common import *

def output_matrix(s,layout):
 N=max(v[1] for v in layout.values());C=np.zeros((4,N));tol=np.sin(np.pi/4)*np.radians(2.5)
 # derivative of Rzz=1-2(qx²+qy²); physical and cached attitude separate.
 for row,key in [(0,'q'),(1,'att')]:
  a,b=layout[key];q=s[key].c;C[row,a+1:a+3]=-4*q[1:3]/tol
 for row,k,h in [(2,'p','H0'),(3,'lp','LP_H0')]:
  C[row,layout[k][0]+2]=10.;C[row,layout[h][0]]=-10.
 return C

def backward_importance(matrices,F,terminal):
 Z=[None]*(len(matrices)+1);Z[-1]=terminal
 for k in range(len(matrices)-1,-1,-1):Z[k]=(F[k]+Z[k+1])@matrices[k]
 # For reduction aftercallj, include currentoutputF[j-1] plusallfutureZj.
 importance=[Z[0]]+[F[k-1]+Z[k] for k in range(1,len(Z))]
 return Z,importance

def main():
 out=Path(sys.argv[1]);register(out,'H2: source analytic192call backward safety sketch, all prefixes not onlyterminal',CPU_limit_s=300,seed=14271027,rows=8);limit(300);start=time.perf_counter()
 from p14r.affine import install
 install(True)
 from p14.affine import A
 A.radius=lambda self:np.zeros_like(self.c);A.bounds=lambda self:(self.c.copy(),self.c.copy())
 from p14r.tube import run
 name=sys.argv[2] if len(sys.argv)>2 else 'd02';d=doc(name);P=dict(np.load(R/'data/p13-20261026-freeze/models/policy.npz'));J=[];Cs=[];layout={};stages=[];keys=[]
 def hook(stage,k,t,s):
  nonlocal layout,keys
  if stage=='pre':
   keys=sorted(s);offset=0;layout={}
   for key in keys:layout[key]=[offset,offset+len(s[key].c)];offset+=len(s[key].c)
   ctx=s['p'].ctx;ctx.tangent=True;ctx.n=offset;ctx.initial_n=0;ctx.tags=['tangent']*offset;ctx.monomials={}
   for key in keys:
    a,b=layout[key];g=np.zeros((b-a,offset));g[np.arange(b-a),np.arange(a,b)]=1;s[key]=A(ctx,s[key].c,g)
  else:
   assert sorted(s)==keys;J.append(np.vstack([s[key].pad() for key in keys]));Cs.append(output_matrix(s,layout));stages.append({'call':k,'t':t,'q':s['q'].c.tolist(),'att':s['att'].c.tolist()});s['p'].ctx.tags=['tangent']*s['p'].ctx.n
  return s
 result,_=run(d,P,0,end=d['initial']['profile_s']+.768,compress_rank=None,group=True,observer_library=OLD/'offline-build-v2/libop.bin',liveness=True,tangent_hook=hook);N=J[0].shape[0];rng=np.random.default_rng(14271027);F=[rng.choice([-1.,1.],size=(8,4))/np.sqrt(8)@c for c in Cs];terminal=np.zeros((8,N));terminal[:,layout['v'][0]+2]=rng.choice([-1.,1.],size=8)/(np.sqrt(8)*.15);Z,importance=backward_importance(J,F,terminal)
 e=rng.normal(size=N)*1e-7;acc=np.zeros(8);x=e.copy()
 for k,A0 in enumerate(J):x=A0@x;acc+=F[k]@x
 acc+=terminal@x;err=float(max(abs(acc-Z[0]@e)));assert err<1e-10
 np.savez_compressed(out/'weights.npz',**{'W'+str(k):z for k,z in enumerate(importance)})
 write(out/'result.json',{'calls':len(J),'layout':layout,'N':N,'sketch_rows':8,'all_prefix_outputs':['physical Rzz','cached Rzz','COM pz-H0','LP pz-LPH0'],'terminal_output':'down W','adjoint_identity_max_abs':err,'elapsed_s':time.perf_counter()-start,'fixed_rng':14271027,'phase_semantics':'post-output derivativeCk multipliespost-state. Zpre=(Fk+Znext)Ak; post-reductionimportanceWj=F_(j-1)+Zj, includescurrentandallfutureoutputs. Priorv1 Cpost-onpre offsetinvalidforrequestedobjective.','stages':stages,'source_derivative':'analytic chain; no finite difference/Jacobian sampling certificate','limitations':['nominal clip/sign/commit branch only; sensitivity weights are a heuristic for all-prefix output impact','full nonlinear residual/box of discarded directions retained inactualtube','local real-NED/source-float gap and future EKF/SERVO/FP certification unchanged'],'domain':result['first_domain_loss']});print('WEIGHTS_DONE',len(J),time.perf_counter()-start)
if __name__=='__main__':main()

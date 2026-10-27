"""Finite source-analytic tangent + explicitly conditional remainder storage.
No finite difference/sample Jacobian; nonlinear enclosure remains tube results.
P is propagated by a thin observability factor, preserving joint cross terms.
"""
import sys,json,time
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p14.common import write,sha

def main():
 out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False)
 write(out/'before-compute.json',{'horizon_calls':16,'modes':['fresh initial flow','strict capture copy operator','fresh-reference resume replacement'],'source_derivative':'analytic affine first-order chain, tangent-only radius/noise disabled; not a nonlinear certificate. Analytic nonlinear budgets are separate C tube calculations.','storage':'P_k=C_k^T C_k+A_k^T P_next A_k, thin factor; direct identity+cross-term check. Remainder Young bound explicit, no decreasing-energy claim from maximum eigenvalue','CPU_budget_s':600,'source':sha(Path(__file__))})
 from p14r.affine import install
 install(False)
 from p14.affine import A
 A.radius=lambda self:np.zeros_like(self.c)
 A.bounds=lambda self:(self.c.copy(),self.c.copy())
 from p14r.tube import run
 doc=json.load(open(R/'data/p14r-20261027/source-inputs-v3/d02/input.json'));P=dict(np.load(R/'data/p13-20261026-freeze/models/policy.npz'));matrices=[];layout={};center=[];st=time.perf_counter()
 def hook(stage,k,t,s):
  nonlocal layout
  keys=sorted(s)
  if stage=='pre':
   offset=0;layout={}
   for key in keys:layout[key]=[offset,offset+len(s[key].c)];offset+=len(s[key].c)
   C=s[keys[0]].ctx;C.tangent=True;C.n=offset;C.tags=['tangent']*offset;C.initial_n=0;C.monomials={}
   for key in keys:
    a,b=layout[key];g=np.zeros((b-a,offset));g[np.arange(b-a),np.arange(a,b)]=1;s[key]=A(C,s[key].c,g)
  else:
   assert sorted(s)==keys
   J=np.vstack([s[key].pad() for key in keys]);matrices.append(J);center.append({'call':k,'t':t,'LP':s['lp'].c.tolist(),'q':s['q'].c.tolist(),'h':s['h'].c.tolist()});s[keys[0]].ctx.tags=['tangent']*s[keys[0]].ctx.n
  return s
 result,_=run(doc,P,0,end=doc['initial']['profile_s']+.064,group=True,compress_rank=None,observer_library=R/'data/p14r-20261027/offline-build-v2/libop.bin',tangent_hook=hook)
 N=matrices[0].shape[0];C=np.zeros((13,N));row=0
 for key,sc in [('p',.1),('v',.15),('q',.01),('w',.1)]:
  a,b=layout[key];C[row:row+b-a,a:b]=np.eye(b-a)/sc;row+=b-a
 # Finite horizon all-prefix output storage; thin factor avoids dense cubic P.
 factors=[None]*(len(matrices)+1);factors[-1]=C.copy()
 for k in range(len(matrices)-1,-1,-1):factors[k]=np.vstack([C,factors[k+1]@matrices[k]])
 rng=np.random.default_rng(142710);checks=[]
 for k,J in enumerate(matrices):
  e=rng.normal(size=N)*1e-5;V0=np.linalg.norm(factors[k]@e)**2;V1=np.linalg.norm(factors[k+1]@(J@e))**2;Q=np.linalg.norm(C@e)**2;checks.append(abs(V0-V1-Q))
 # Actual event jump matrices, same full ambient state, continuous body/history.
 jumps={}
 for mode in ['capture','resume']:
  J=np.eye(N)
  for target,source in [('r','lp'),('capture_p','lp')] if mode=='capture' else [('r',None),('rv',None),('ty',None)]:
   a,b=layout[target];J[a:b]=0
   if source:
    u,v=layout[source];J[a:b,u:v]=np.eye(b-a)
  if mode=='capture':
   a,b=layout['rv'];J[a:b]=0
   # yaw is a separate analytic state function of estimated quaternion.
   q=np.array(doc['initial']['attitude']);from p14_motion.algebra import Context,yaw
   ctx=Context();ctx.tangent=True;qa=A(ctx,q,np.eye(4));ctx.n=4;dy=yaw(qa).g[0];a,b=layout['ty'];u,v=layout['att'];J[a:b]=0;J[a,u:v]=dy
  L=factors[-1]@J;cross=float(np.linalg.norm(L[:,layout['p'][0]:layout['p'][1]].T@L[:,layout['h'][0]:layout['h'][1]]));jumps[mode]={'continuous_body_filter_history_rows_unchanged':all(np.array_equal(J[a:b],np.eye(N)[a:b]) for key,(a,b) in layout.items() if key in ['p','v','q','w','h','previous','mean','f','pending']),'cross_block_p_h_terminal':cross};np.savez_compressed(out/(mode+'-jump.npz'),J=J)
 np.savez_compressed(out/'storage.npz',**{f'A{k}':J for k,J in enumerate(matrices)},**{f'L{k}':L for k,L in enumerate(factors)},C=C)
 initial_cross=np.linalg.norm(factors[0][:,layout['p'][0]:layout['p'][1]].T@factors[0][:,layout['h'][0]:layout['h'][1]])
 write(out/'result.json',{'rows':len(matrices),'dimension':N,'layout':layout,'elapsed_s':time.perf_counter()-st,'backward_storage_identity_max_abs':max(checks),'P0_p_h_cross_norm':float(initial_cross),'event_jumps':jumps,'nonlinear_connection':'for certified local residual r, V_next <=(1+alpha)(V_k-||Ce||²)+(1+1/alpha)||L_next r||². C tube supplies real-map outer residuals only until its domain/precision loss. Future EKF/physics/float32 defects not supplied by tangent test.','prefix_safety':'check each margin m_k against support of G_k, not terminal energy alone; D monotone and no reset','actual_nonlinear_certificate':False,'reason':'joint correlated model tube loses information before full event; constant fused-target error budget unproved; numerical tangent/LAPACK validation is not proof of nonlinear global contraction','center':center,'run_domain':result['first_domain_loss']})
if __name__=='__main__':main()

"""Finite full-output post-state pullback metric, no random row sketch.
Exact for frozen linear branch; nonlinear/source-float defects are separate.
"""
import sys,json,time,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from p14h.common import *

def compute(out,name):
 out.mkdir();limit(600);start=time.perf_counter()
 from p14r.affine import install
 install(True)
 from p14.affine import A
 A.radius=lambda self:np.zeros_like(self.c);A.bounds=lambda self:(self.c.copy(),self.c.copy())
 from p14r.tube import run as tube
 from p14g.weights import output_matrix
 d=json.load(open(R/json.load(open(R/'config/p14h/protocol-v1.json'))['cases'][name]['input']));P=dict(np.load(R/'data/p13-20261026-freeze/models/policy.npz'));Js=[];Cs=[];layout={};keys=[]
 def hook(stage,k,t,s):
  nonlocal layout,keys
  if stage=='pre':
   keys=sorted(s);off=0;layout={}
   for key in keys:layout[key]=[off,off+len(s[key].c)];off+=len(s[key].c)
   ctx=s['p'].ctx;ctx.tangent=True;ctx.n=off;ctx.initial_n=0;ctx.tags=['tangent']*off;ctx.monomials={}
   for key in keys:
    a,b=layout[key];g=np.zeros((b-a,off));g[np.arange(b-a),np.arange(a,b)]=1;s[key]=A(ctx,s[key].c,g)
  else:Js.append(np.vstack([s[k].pad() for k in keys]));Cs.append(output_matrix(s,layout));s['p'].ctx.tags=['tangent']*s['p'].ctx.n
  return s
 result,_=tube(d,P,0,end=d['initial']['profile_s']+.768,compress_rank=None,group=True,observer_library=R/'data/p14r-20261027/offline-build-v2/libop.bin',liveness=True,tangent_hook=hook);N=Js[0].shape[0];terminal=np.zeros((N,N));a=layout['v'][0]+2;terminal[a,a]=1/.15**2;Qs=[None]*(len(Js)+1);Qs[-1]=terminal;Wpost=[None]*(len(Js)+1)
 for k in range(len(Js)-1,-1,-1):
  Wpost[k+1]=Cs[k].T@Cs[k]+Qs[k+1];Qs[k]=Js[k].T@Wpost[k+1]@Js[k]
 Wpost[0]=Qs[0];rng=np.random.default_rng(14281027);e=rng.normal(size=N)*1e-8;x=e.copy();cost=0
 for j,J in enumerate(Js):x=J@x;cost+=float(np.linalg.norm(Cs[j]@x)**2)
 cost+=float(x@terminal@x);error=abs(float(e@Qs[0]@e)-cost);assert error<1e-14
 np.savez_compressed(out/'metric.npz',**{'P'+str(j):p for j,p in enumerate(Wpost)})
 write(out/'result.json',{'calls':len(Js),'N':N,'layout':layout,'full_prefix_outputs':['physicalRzz','cachedRzz','COMheight','LPheight'],'terminal':'verticalW','source_condition':'nominal source branch with clip,commit,cache/clock word fixed; exact tangent; not full nonlinear futurecoverage','W':'e^T Pk e, Qpre[k]=Jk^T(Cpostk^TCpostk+Qpre[k+1])Jk, Ppost[k+1]=Cpostk^TCpostk+Qpre[k+1]','forward_backward_energy_absolute_error':error,'epsilon_regularization':0,'PSD_semidefinite_not_full_state_norm':True,'nonlinear_error_relation':'sqrt(Wnext)<=sqrt(e^T J^T Pnext J e)+norm(Pnext^1/2 r); r budget/source-float and model mismatch not certified. All saved margins require their own included r/clockbranches.','first_source_domain_loss':result['first_domain_loss'],'elapsed_s':time.perf_counter()-start,'no_eight_row_cancellation':True,'temporary_hh':'source weight proxy still explicit; full future h after next observe represented, transient actionhh uses action-output relation, not independent deletion'})
 print('GRAMIAN_DONE',name,len(Js),time.perf_counter()-start)

def main():
 if sys.argv[1]=='child':compute(Path(sys.argv[2]),sys.argv[3]);return
 out=register(sys.argv[1],'C: one motivated full-output Gramian replacing cancellation-prone8row sketch; sameGdomain/threshold and all8cells; conditional metric notglobalproof',CPU_limit_for_two_metrics=1200,all8tube_limit=1440,one_structural_variant=True)
 for n in ['d02','d03']:
  record=run([PY,Path(__file__),'child',out/n/'result',n],out/n,cpu=600,wall=660,scope='theory fullprefix W');print(n,record['rc'],flush=True)
if __name__=='__main__':main()

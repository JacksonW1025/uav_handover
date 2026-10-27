"""Finite source OP scalar velocity/position transfer, not a wholeflight model.
Fused-target innovations are inputs, not made bounded by the source itself.
Shared input roots persist through the full buffer+integral recurrence.
"""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from p14g.common import *
from p14r.op import Op
from p14r.observer import FUSION

def update(x,u,n,g,h,dt):
 v=x[:n];p=x[n:2*n];vi,pi=x[-2:];vn=np.r_[v[1:],v[-1]];pn=np.r_[p[1:],p[-1]+dt*v[-1]];ev=u[0]-vn[0];ep=u[1]-pn[0];vi+=ev;pi+=ep;vn+=g*ev+.1*g*g*vi;pn+=h*ep+.1*h*h*pi;return np.r_[vn,pn,vi,pi]

def main():
 out=Path(sys.argv[1]);register(out,'C source exactreal scalar buffer-integral transfer, future input budgets remainconditions');limit(10);d=doc('d02');lib=OLD/'offline-build-v2/libop.bin';o=Op(lib,d['initial']['observer']);f=np.frombuffer(o.snapshot(),FUSION,count=1)[0];c=f['core'];n=int(c['ids'][2]);g=float(c['data'][36]/np.clip(c['data'][37],c['data'][36],10));h=float(c['data'][36]/np.clip(c['data'][38],c['data'][36],10));N=2*n+2;A=np.column_stack([update(np.eye(N)[:,j],np.zeros(2),n,g,h,.008) for j in range(N)]);Bmat=np.column_stack([update(np.zeros(N),np.eye(2)[:,j],n,g,h,.008) for j in range(2)]);C=np.zeros((2,N));C[0,n-1]=1;C[1,2*n-1]=1;rows=[];power=np.eye(N);persistent=np.zeros((N,2));iid=[];rho=np.exp(-.008/.25);fading=np.zeros((N,2))
 for k in range(1,126):
  persistent=A@persistent+Bmat;iid=[A@G for G in iid]+[Bmat];fading=A@fading+rho**(k-1)*Bmat
  rows.append({'fusion_calls':k,'time_s':.008*k,'persistent_v_p_component_gains':np.sum(abs(C@persistent),axis=1).tolist(),'independent_v_p_component_gains':np.sum(abs(np.column_stack([C@G for G in iid])),axis=1).tolist(),'fading_same_origin_gains':np.sum(abs(C@fading),axis=1).tolist()})
 # Source C++ numerical probe with same IMU/q/bias and exogenousvelocity offset.
 p=Op(lib,d['initial']['observer']);start=d['initial']['observer']['latest_completed_update_sample_us'];fused=d['initial']['observer']['latest_fusion_publication_sample_us'];baseq,basev,basegeo,_=o.outputs();u=.01;errs=[];x=np.zeros(N)
 for k in range(1,65):
  t=start+4000*k
  for obj in [o,p]:obj.advance(t,[0,0,0],[0,0,-.0392])
  if t-fused>=8000:
   fused=t;vf=basev.copy();vf[0]+=u;o.fuse(t-d['initial']['observer_parameters']['fusion_delay_us'],baseq,basev,basegeo,d['initial']['observer_parameters']['gyro_bias'],d['initial']['observer_parameters']['accel_bias']);p.fuse(t-d['initial']['observer_parameters']['fusion_delay_us'],baseq,vf,basegeo,d['initial']['observer_parameters']['gyro_bias'],d['initial']['observer_parameters']['accel_bias']);x=update(x,np.array([u,0]),n,g,h,.008);actual=float(p.outputs()[1][0]-o.outputs()[1][0]);errs.append(abs(actual-x[n-1]))
 write(out/'result.json',{'ring_length':n,'state_dimension':N,'gains':{'velocity':g,'position':h},'equations':'shift buffers; e=u-oldest; i_next=i+e; buffer_v+=g_v*e_v+.1*g_v²*i_v_next, same p; current=last. NED globalchart only.','mathematical_relation':'delta x_k=A^k delta x0+sum A^(k-1-j)B delta u_j. Common-generator input correlations survive; independent rowL1 is a different condition.','future_input_unknown':'source OP does not certify bounds on arbitrary future EKFtarget/bias/IMU/modelerrors','source_Cpp_velocity_probe_max_abs':max(errs),'spectral_radius_numeric_not_proof':float(max(abs(np.linalg.eigvals(A)))),'rows':rows,'scope':'conditional scalar source transfer withsame orientation/IMU/bias input, not freezingattitude inmainfullfeedbacktube; mainBretainsallangles andhistory. Numericvalues notoutwardIEEEcertified.','new_flight':0});np.savez_compressed(out/'transfer.npz',A=A,B=Bmat,C=C);o.close();p.close()
if __name__=='__main__':main()

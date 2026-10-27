"""Source-derived conditional all-prefix COM height reserve, not required loss.
No empirical maximum is made a hard budget. Actual SERVO/joint/FP and observer
bridges remain distinct obligations. This is useful even when tilt proof fails.
"""
import sys,json,math
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p14.common import write,sha
from p13.physical_model import mass,Ir,I,pos
from p14r.model import forecast

def reserve(L,D,W,A,dt,N,eta=0):
 j=np.arange(N+1);upper=L+W*j*dt+.5*A*dt*dt*j*(j+1)+j*eta;maximum=np.maximum.accumulate(np.maximum(D,upper));return upper,maximum

def main():
 out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);fmin,fmax=150.,1000.;V=8.;Omega=np.sqrt(3)*8;dt=.004;r=.00186913101803548;kt=8.54858e-6;cd=8.06428e-5;km=.016;delta=abs(3.8464910483993325e-7-2.6115851691700804e-5)/2;rho=float(np.max(np.linalg.norm(pos,axis=1)));rel=V+Omega*rho;drag=4*cd*fmax*rel;T=4*kt*fmax*fmax;tau_T=4*rho*kt*fmax*fmax;tau_drag=rho*drag+4*1e-6*fmax*rel;tau_yaw=km*T;df=(1-np.exp(-dt/.0125))*(fmax-fmin);spin=4*Ir*fmax/10;spin_dot=4*Ir*df/(10*dt);dI=8*delta*fmax/10;Imin=float(min(np.diag(I)-(np.sum(abs(I),axis=1)-abs(np.diag(I))))-4*delta);Imax=float(max(np.sum(abs(I),axis=1))+4*delta);assert Imin>0
 alpha=(tau_T+tau_drag+tau_yaw+spin_dot+dI*Omega+Omega*(Imax*Omega+spin))/Imin
 A_base=9.8+drag/mass+r*(alpha+Omega**2);A_com=A_base+r*(alpha+Omega**2);eta=.5*r*Omega**2*dt**2
 doc=json.load(open(R/'data/p14r-20261027/source-inputs-v3/d02/input.json'));P=dict(np.load(R/'data/p13-20261026-freeze/models/policy.npz'));point=forecast(doc,{},P,observer_library=R/'data/p14r-20261027/offline-build-v2/libop.bin');result=json.load(open(R/'data/p14r-20261027/C-continue-v1/result.json'));row=next(x for x in result['rows'] if x['call']==140);L=row['L_interval_m'][1];D=row['D_upper_m'];W=float(point['states'][140,5]+row['v_radius_m_s']);U,DD=reserve(L,D,W,A_com,dt,125,eta);valid=np.flatnonzero(DD<=1);N=int(valid[-1]) if len(valid) else None
 # These checks are algebraic directions, not sampled dynamics certification.
 assert np.all(np.diff(DD)>=0) and DD[0]>=D and np.all(DD>=U)
 j=32;independent_fixed_target=np.array([.01,-.015,.005])
 write(out/'result.json',{'formula':'L_j<=L0+j*dt*W0+0.5*A_down*dt²*j*(j+1)+j*eta_position; D_j<=max(D0,max_{0<=i<=j} L_upper_i). Sufficient reserve only, not necessary loss or optimal recovery time.','source_parameters':{'mass':mass,'inertia_Gershgorin_min':Imin,'inertia_norm_upper':Imax,'filter_range':[fmin,fmax],'dt':dt,'velocity_norm_bound':V,'omega_norm_bound':float(Omega),'air_drag_total_bound_N':float(drag),'source_angular_accel_bound_rad_s2':float(alpha),'body_down_accel_bound_m_s2':float(A_base),'COM_down_velocity_increment_bound_m_s2':float(A_com),'position_geometry_defect_per_step_m':float(eta)},'assumptions':['contact-free source four-servo ideal-joint physical kernel, rotor scaled speeds in150..1000 and original convex filter','physical q unit, tilt<=80deg, |v|<=8m/s and each |omega_component|<=8rad/s, zero wind and no unmodelled force','fixed COM-body lever; real future joint/SERVO residual/float32 defect must be separately bounded and added, not taken from observed maxima','future remains in this domain; does not prove domain invariance or tilt<=45','LP output innovation/origin/cache bridge not supplied by COM inequality'],'example_input':{'checkpoint':'C-continue-v1/result.json call140, one named quarter/d02clock conditional source region','profile_s':row['t'],'L_upper_m':L,'D_upper_m':D,'W_upper_m_s':W},'example_output':{'max_integer_prefix_with_sufficient_height_reserve':N,'duration_s':N*dt if N is not None else None,'for_128ms':{'loss_upper_m':float(U[j]),'D_upper_m':float(DD[j]),'height_reserve_m':float(1-DD[j])},'all125prefixes':{'L_upper':U.tolist(),'D_upper':DD.tolist()}},'scope':'nonempty calculable conditional all-prefix height test and interval constraint. Not whole task safety, no actual trajectory future certification from empirical fit.','source_sha256':{str(p.relative_to(R)):sha(p) for p in [R/'tools/p13/physical_model.py',Path(__file__)]},'new_SITL':0})
 print('SOURCE_HEIGHT_BOUND',A_com,'T',N*dt if N is not None else None)
if __name__=='__main__':main()

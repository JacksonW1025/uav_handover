import json,sys
from pathlib import Path
import numpy as np
from scipy.optimize import minimize_scalar
from scipy.spatial.transform import Rotation
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p13.physics import read,BODY,rot
from p12c.features import load
from p11.models import R as matrix
from p9_model import write,sha
S=np.array([[0,1,0],[1,0,0],[0,0,-1]]);B=np.diag([1,-1,-1]);series=[];sources=[]
for name in ['dev01-F2-NORMAL','dev02-F2-A','dev03-F4-AB','dev04-F4-REPAIR']:
 p=R/'data/p13-20261026-development'/name;d=load(p/'run',p/'analysis-v1');b,_=read(p/'run/gz-motor/physics-p13-body.bin',BODY,b'P13BODY1');b=b[b['phase']==1];ii=np.flatnonzero((d['t']>=0)&(d['t']<=25))[::5];j=np.searchsorted(b['wall_ns'],d['run_wall_ns'][ii],side='right')-1;M=S@rot(b['base_q'][j])@B;E=np.array([matrix(q) for q in d['attitude'][ii]])@np.transpose(M,(0,2,1));yaw=Rotation.from_matrix(E).as_euler('xyz')[:,2];t=d['t'][ii];series.append((t,yaw,yaw[0]));sources.append({'id':name,'rows':len(t),'body_sha256':sha(p/'run/gz-motor/physics-p13-body.bin'),'initial_yaw_offset_deg':float(np.degrees(yaw[0]))})
def cost(tau):return sum(np.mean((y-y0*np.exp(-t/tau))**2) for t,y,y0 in series)
f=minimize_scalar(cost,bounds=(.2,30),method='bounded');out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);write(out/'observer-fit.json',{'schema':'p13-initial-yaw-offset-decay-fit-1','source':'first4 development, all4 retained, angle-offset time series not outcomes; no formal data','sources':sources,'yaw_offset_tau_s':float(f.x),'per_record_mean_squared_angle_objective':float(f.fun),'no_flight_causal_claim':True,'no_new_SITL':True,'future_error_bound':'UNPROVEN; empirical observer candidate, not source EKF reproduction','initial_position_frame':'physical NED axes retained; do not rotate position by yaw estimator attitude bias','mean_record_RMS_deg':float(np.degrees(np.sqrt(f.fun/4)))});print('TAU',f.x,'RMSdeg',np.degrees(np.sqrt(f.fun/4)))

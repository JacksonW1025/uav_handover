"""One preregistered source-shaped error-state trial on all4 diagnostic data."""
import sys,json,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from scipy.spatial.transform import Rotation
from p14h.common import *
from p14r.observer import read,FUSION
from p13.physics import read as pread,BODY,rot
from p13.physical_model import S,B as BODYB
from p14r.op import Op
from p14_motion.core import mul,conjugate

def normalize(q):return np.asarray(q)/np.linalg.norm(q)
def log(q):return Rotation.from_quat(normalize(q)[[1,2,3,0]]).as_rotvec()
def main():
 out=register(sys.argv[1],'one causal inertial-error/aiding-rate model, all4diagnostic completeavailablewindows, no outcomesselected',spec_sha256=sha(R/'config/p14h/feedback-trial-v1.json'));limit(60);terms={k:[] for k in ['theta','v','p']};source=[]
 for n,review in [(1,'review-d01-v1'),(2,'review-d02-v3'),(3,'review-d03-v1'),(4,'review-d04-v3')]:
  target=next((B/'runs').glob(f'p14h-d{n:02d}-*'));doc=json.load(open(B/review/'source-initial/input.json'));i=doc['initial'];par=i['observer_parameters'];E0=normalize(par['fusion_attitude_alignment']);ep0=np.array(par['fusion_position_error_NED']);bg=np.array(par['sensor_gyro_bias'])-par['gyro_bias'];ba=np.array(par['sensor_accel_bias'])-par['accel_bias'];epoch=i['observer']['cutoff_wall_ns']-i['profile_s']*1e9;A,b=doc['plan']['windows_profile_s'][0];f,h=read(target/'run/gz-motor/observer-fusion.bin',FUSION,b'P14RFUS1',True);f=f[(f['core']['kind']==3)&(f['core']['wall_ns']>=epoch+(A-.5)*1e9)&(f['core']['wall_ns']<=epoch+(b+2)*1e9)];phy,_=pread(target/'run/gz-motor/physics-p13-body.bin',BODY,b'P13BODY1');phy=phy[(phy['phase']==1)&(phy['valid']==63)];lookup={int(x['sim_ns']//1000):x for x in phy};op=Op(R/'data/p14r-20261027/offline-build-v2/libop.bin',i['observer']);rows=[]
  for frame in f:
   z=frame['core'];t=int(z['sample_us']);x=lookup.get(t)
   if x is None:continue
   Q=S@rot(x['base_q'][None,:])[0]@BODYB;q=Rotation.from_matrix(Q).as_quat()[[3,0,1,2]];v=S@x['base_v'];p=S@x['base_p'];qhat=normalize(z['data'][64:68]);E=normalize(mul(qhat,conjugate(q)));ev=z['data'][68:71]-v;ep=op.sub(z['geo'][3:6],op.add(par['world_geo'],p));rows.append({'t':t,'q':q,'qhat':qhat,'E':E,'ev':ev,'ep':ep,'v':v})
  for x,y in zip(rows,rows[1:]):
   dt=(y['t']-x['t'])*1e-6
   if not .004<=dt<=.02:continue
   Q=Rotation.from_quat(x['qhat'][[1,2,3,0]]).as_matrix();E=Rotation.from_quat(x['E'][[1,2,3,0]]).as_matrix();specific=(y['v']-x['v'])/dt-np.array([0,0,9.8]);drives={'theta':Q@bg,'v':(E-np.eye(3))@specific+Q@ba,'p':x['ev']};obs={'theta':log(mul(y['E'],conjugate(x['E'])))/dt,'v':(y['ev']-x['ev'])/dt,'p':(y['ep']-x['ep'])/dt};features={'theta':log(mul(x['E'],conjugate(E0))),'v':x['ev'],'p':x['ep']-ep0}
   for key in terms:terms[key].append({'case':n,'sample_us':x['t'],'x':features[key].tolist(),'driver':drives[key].tolist(),'observed_derivative':obs[key].tolist(),'dt':dt})
  source.append({'case':n,'rows':len(rows),'input_sha256':sha(B/review/'source-initial/input.json'),'fullP_is_not_error_radius':True});op.close()
 rates={};diagnostics={}
 for key,z in terms.items():
  X=np.array([r['x'] for r in z]);D=np.array([r['driver'] for r in z]);Y=np.array([r['observed_derivative'] for r in z]);den=float(np.sum(X*X));unc=float(np.sum(X*(D-Y))/(den+1e-8));rate=float(np.clip(unc,0,50));rates[key]=rate;diagnostics[key]={'rows':len(z),'x_squared_sum':den,'unconstrained_rate':unc,'rate':rate,'clamped':unc!=rate,'noaiding_driver_RMSE':float(np.sqrt(np.mean((D-Y)**2))),'new_empirical_RMSE':float(np.sqrt(np.mean((D-rate*X-Y)**2))),'identifiable_empirically_not_certified':den>1e-8};write(out/(key+'-fit-data.json'),z)
 model={'schema':'P14H-feedback-error-state-1','rates_per_s':rates,'state':'E/ev/ep, anchors andlastdelayedbodyvel, causalbodyIMUcoupling, sourceOP exact plus heldbias, no futuretrue','source':'empirical reduced aiding-rate fit, not fullEKF or OPtau theorem','true_future_budget':'UNKNOWN','fit_spec':str(R/'config/p14h/feedback-trial-v1.json'),'fit_sources':source,'fit_diagnostics':diagnostics,'exposure':'all4 diagnosticsdevelopment, noneindependent; no further candidate/rate search'};write(out/'model.json',model);print('FEEDBACK_FIT',rates,diagnostics)
if __name__=='__main__':main()

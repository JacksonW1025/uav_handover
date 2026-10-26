"""Observed step-phase mechanical proxies with explicit common-window boundaries.
No claim of electrical energy or exact continuous rotor torque/work measurement.
"""
import sys,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p13.physics import read,BODY,ROTOR
from p12c.features import load
from p9_model import write,sha

def costs(target,start_s,end_s):
 run=target/'run';a=target/'analysis-v1';d=load(run,a);epoch=round(d['run_wall_ns'][0]-d['t'][0]*1e9);lo=round(epoch+start_s*1e9);hi=round(epoch+end_s*1e9);b,_=read(run/'gz-motor/physics-p13-body.bin',BODY,b'P13BODY1');pre=b[b['phase']==0];post=b[b['phase']==1];result=[]
 for k in range(4):
  x,_=read(run/f'gz-motor/physics-p13-rotor-{k}.bin',ROTOR,b'P13ROTR1');j=np.searchsorted(pre['step'],x['step']);assert np.array_equal(pre['step'][j],x['step']);p0=pre['wall_ns'][j];p1=post['wall_ns'][j];complete=(p0>=lo)&(p1<=hi);possible=(p1>lo)&(p0<hi);dt=x['dt_ns']/1e9
  # Revolute velocity used to integrate this step is post-solver, observed again
  # in the next Pre before physics mutates it. Last row is unknown unless outside.
  nextgood=np.r_[np.diff(x['step'])==1,False];jointpost=np.r_[x['joint'][1:]*10,np.nan]
  if np.any(complete&~nextgood) or np.any(possible&~nextgood):raise RuntimeError('post-joint cost missing next-step witness')
  def integral(values):
   return {'lower':float(np.sum(values[complete]*dt[complete])),'upper':float(np.sum(values[possible]*dt[possible])),'complete_steps':int(complete.sum()),'boundary_uncertain_steps':int(np.sum(possible&~complete))}
  first=max(0,int(np.searchsorted(x['wall_ns'],lo,side='right')-1));last=int(np.searchsorted(x['wall_ns'],hi,side='right'));seq=x['command'][first:last];tv=float(abs(np.diff(seq)).sum())
  result.append({'motor':k,'command_TV_rad_s':tv,'post_joint_squared_rad2_s':integral(jointpost**2),'force_phase_joint_squared_rad2_s':integral((x['joint']*10)**2),'thrust_impulse_Ns':integral(abs(x['thrust'])),'proxy_scope':'joint² of post-solver step velocity and optional force-phase version; thrust magnitude uses force phase. Uncertain host-window boundary physical steps have interval[0,dt], never fabricated fractional time.'})
 # Controller tracking integral in sample time: same accepted control calls, not host intervals.
 idx=np.flatnonzero((d['t']>=start_s)&(d['t']<=end_s));doc=json.load(open(a/'packed/prediction-input.json'));plan=doc['plan'];table=np.array(plan['profile']['table']);j=np.clip(np.floor((d['t'][idx]-plan['profile']['table_t0_s'])/.004+1e-8).astype(int),0,len(table)-1);err=np.linalg.norm(d['position'][idx,:2]-table[j,:2],axis=1);tt=d['sample_us'][idx].astype(np.float64)/1e6;track=float(np.trapezoid(err,tt)) if hasattr(np,'trapezoid') else float(np.trapz(err,tt))
 sums={'command_TV_rad_s':sum(x['command_TV_rad_s'] for x in result),'post_joint_squared_rad2_s':{k:sum(x['post_joint_squared_rad2_s'][k] for x in result) for k in ['lower','upper']},'thrust_impulse_Ns':{k:sum(x['thrust_impulse_Ns'][k] for x in result) for k in ['lower','upper']},'LP_horizontal_tracking_integral_m_s':track}
 return {'schema':'p13-mechanical-costs-2','case':target.name,'window_common_profile_s':[start_s,end_s],'window_epoch':'same original task0 host/native committed anchor, no peak/capture realignment','per_motor':result,'sum':sums,'not_electrical_energy':True,'cost_revision':'v1 force-phase step-held own costs preserved; v2 adds post-solver joint phase and brackets host-window cut steps instead of full-step overcount','raw_body_sha256':sha(run/'gz-motor/physics-p13-body.bin')}

def pair(AB,RP,end_s):
 a=costs(AB,0,end_s);b=costs(RP,0,end_s);delta={'command_TV_rad_s':b['sum']['command_TV_rad_s']-a['sum']['command_TV_rad_s'],'LP_horizontal_tracking_integral_m_s':b['sum']['LP_horizontal_tracking_integral_m_s']-a['sum']['LP_horizontal_tracking_integral_m_s']}
 for k in ['post_joint_squared_rad2_s','thrust_impulse_Ns']:delta[k]={'lower':b['sum'][k]['lower']-a['sum'][k]['upper'],'upper':b['sum'][k]['upper']-a['sum'][k]['lower']}
 return {'schema':'p13-common-window-cost-pair-2','AB':a,'REPAIR':b,'REPAIR_minus_AB':delta,'meaning':'both restricted to common valid window; own full task reported separately, no censored/full subtraction'}
if __name__=='__main__':
 AB=Path(sys.argv[1]);RP=Path(sys.argv[2]);end=float(sys.argv[3]);out=Path(sys.argv[4]);out.parent.mkdir(parents=True,exist_ok=True);write(out,pair(AB,RP,end));print('COST PAIR',end)

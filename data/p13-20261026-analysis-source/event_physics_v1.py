"""P13 event states retain callback/LP plus independent direct physical snapshots."""
import sys,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'));sys.path.insert(0,str(Path(__file__).parent))
from event_tables_base_v1 import create
from p13.physics import read,BODY,ROTOR,rot
from p12c.features import load
from p9_model import write,sha

def process(target,out):
 out.mkdir(parents=True,exist_ok=False);run=target/'run';a=target/'analysis-v1';create(run,a,out/'controller');base=json.load(open(out/'controller/event-states.json'));d=load(run,a);doc=json.load(open(a/'packed/prediction-input.json'));plan=doc['plan'];epoch=round(float(d['run_wall_ns'][0])-d['t'][0]*1e9)
 b,_=read(run/'gz-motor/physics-p13-body.bin',BODY,b'P13BODY1');b=b[b['phase']==1];j0=np.searchsorted(b['wall_ns'],epoch,side='right')-1;assert j0>=0 and b['valid'][j0]==63;H0=b['origin_p'][j0,2];C0=b['com_p'][j0,2];L=H0-b['origin_p'][:,2];LC=C0-b['com_p'][:,2];D=np.maximum.accumulate(np.where(b['wall_ns']>=epoch,np.maximum(L,0),0));DC=np.maximum.accumulate(np.where(b['wall_ns']>=epoch,np.maximum(LC,0),0));tt=(b['wall_ns'].astype(np.int64)-epoch)/1e9
 if base['rows'][-1]['status']=='NOT_REACHED' and not base['censored']:
  # Nominal terminal label may fall <one control step after the last Run.
  x=dict(base['rows'][-1]);x.update(status='LAST_VALID_PREFIX_TERMINAL',requested_profile_s=plan['nominal_horizon_profile_s'],observed_profile_s=float(min(d['t'][-1],plan['nominal_horizon_profile_s'])));base['rows'][-1]=x
 rows=[]
 for row in base['rows']:
  row=dict(row);t=row.get('observed_profile_s',row.get('requested_profile_s'));state=row.get('state')
  if t is None or row['status'] in ['NOT_PLANNED','NOT_REACHED','MISSING_CAPTURE']:rows.append(row);continue
  i=max(0,int(np.searchsorted(d['t'],t,side='right')-1));cut=int(d['run_wall_ns'][i]);j=int(np.searchsorted(b['wall_ns'],cut,side='right')-1)
  if j<0 or b['valid'][j]!=63:raise RuntimeError('missing past direct physical event state')
  x=b[j];v_origin=x['base_v']+np.cross(x['base_omega'],x['origin_p']-x['base_p']);M=rot(x['base_q'][None,:])[0];theta=np.degrees(np.arccos(np.clip(M[2,2],-1,1)))
  row['physical']={'physics_step':int(x['step']),'physics_time_ns':int(x['sim_ns']),'physical_post_wall_ns':int(x['wall_ns']),'controller_sample_us':int(d['sample_us'][i]),'state_to_controller_host_age_us':(cut-int(x['wall_ns']))/1000,'physical_sim_to_controller_sample_us':int(d['sample_us'][i])-int(x['sim_ns']//1000),'stage':'PostUpdate after integration, latest completed before controller Run; initial/full states never callback difference','COM_H_m':float(x['com_p'][2]),'origin_H_m':float(x['origin_p'][2]),'COM_L_m':float(LC[j]),'COM_D_m':float(DC[j]),'origin_L_m':float(L[j]),'origin_D_m':float(D[j]),'origin_current_margin_m':float(1-L[j]),'origin_historic_margin_m':float(1-D[j]),'origin_failed_ever':bool(D[j]>1),'COM_W_m_s':float(-x['com_v'][2]),'origin_W_m_s':float(-v_origin[2]),'COM_v_world_ENU_m_s':x['com_v'].tolist(),'origin_v_world_ENU_m_s':v_origin.tolist(),'body_q_FLU_to_ENU':x['base_q'].tolist(),'body_omega_world_ENU_rad_s':x['base_omega'].tolist(),'body_tilt_deg':float(theta),'COM_position_ENU_m':x['com_p'].tolist(),'model_origin_ENU_m':x['origin_p'].tolist(),'LP_and_callback_separate':'see controller state; physical values retain source/time independent of LP criterion'}
  rows.append(row)
 complete_events=all(e.get('status')=='NOT_PLANNED' or e.get('status')=='CAPTURE_REACHED' and (e.get('resume_status')=='READ_AND_FRESH_CONFIRMED' or base['censored']) for e in base['events'])
 full=(tt>=0)&(tt<=base['valid_experiment_end_profile_s']);mechanical=[]
 for k in range(4):
  x,_=read(run/f'gz-motor/physics-p13-rotor-{k}.bin',ROTOR,b'P13ROTR1');t=(x['wall_ns'].astype(np.int64)-epoch)/1e9;use=(t>=0)&(t<=base['valid_experiment_end_profile_s']);xx=x[use];dt=xx['dt_ns']/1e9;mechanical.append({'motor':k,'interval_s':[0,base['valid_experiment_end_profile_s']],'command_total_variation_rad_s':float(abs(np.diff(xx['command'])).sum()),'joint_squared_integral_rad2_s':float(np.sum((xx['joint']*10)**2*dt)),'thrust_impulse_Ns':float(np.sum(xx['thrust']*dt)),'not_electrical_energy':True})
 result={'schema':'p13-direct-event-states-1','case':target.name,'source_body_sha256':sha(run/'gz-motor/physics-p13-body.bin'),'initial_physical_H_origin_m':float(H0),'initial_physical_H_COM_m':float(C0),'L_D_baseline':'common task0 latest past physical state, identical reference rule across arms; L may recover, D monotone nonnegative and historical failure irreversible; LP frozen task criterion keeps original A-window baseline','events':base['events'],'rows':rows,'event_witness_completeness':complete_events,'task_outcome':base['task_outcome'],'censored':base['censored'],'valid_end_s':base['valid_experiment_end_profile_s'],'physical_full':{'rows':int(full.sum()),'origin_D_m':float(D[full].max()),'COM_D_m':float(DC[full].max()),'max_tilt_deg':float(np.degrees(np.arccos(np.clip(rot(b['base_q'][full])[:,2,2],-1,1))).max()),'max_W_COM_m_s':float((-b['com_v'][full,2]).max())},'mechanical_proxies':mechanical,'theory':'sampled physical state available; continuous membership and future solver/cache conditions not thereby proved'}
 write(out/'event-states.json',result);np.savez_compressed(out/'physical-prefix.npz',profile_s=tt,H_COM=b['com_p'][:,2],H_origin=b['origin_p'][:,2],W_COM=-b['com_v'][:,2],W_origin=-(b['base_v']+np.cross(b['base_omega'],b['origin_p']-b['base_p']))[:,2],L= L,D=D,COM_L=LC,COM_D=DC)
 print(target.name,result['physical_full'],'witnesses',complete_events)
if __name__=='__main__':process(Path(sys.argv[1]),Path(sys.argv[2]))

"""Independent analysis layer for finished P13 records; immutable raw/runtime inputs."""
import json,sys
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'));sys.path.insert(0,str(Path(__file__).parent))
from p13.physics import read,BODY,ROTOR,rot
from p12c.features import load
from p11.models import tilt,R as matrix
from p9_model import write,sha
from event_physics_v1 import process as events

def crossing(t,x,threshold):
 j=np.flatnonzero(x>threshold)
 return None if not len(j) else {'last_nonwitness_or_first_time_s':float(t[max(0,int(j[0])-1)]),'first_sampled_witness_s':float(t[j[0]]),'scope':'sampled witness bracket; no claim all continuous prefixes checked without further domain/integrator certificate'}

def review(target,out):
 out.mkdir(parents=True,exist_ok=False);events(target,out/'events');a=target/'analysis-v1';run=target/'run';d=load(run,a);doc=json.load(open(a/'packed-physical/prediction-input.json')) if (a/'packed-physical').exists() else json.load(open(a/'packed/prediction-input.json'));plan=doc['plan'];m=json.load(open(a/'measured/measurement.json'));ev=json.load(open(out/'events/event-states.json'));valid_end=ev['valid_end_s'];epoch=round(d['run_wall_ns'][0]-d['t'][0]*1e9)
 b,h=read(run/'gz-motor/physics-p13-body.bin',BODY,b'P13BODY1');pre=b[b['phase']==0];post=b[b['phase']==1];j=np.searchsorted(pre['step'],post['step'][:-1]+1);pairs=(j<len(pre));j=j[pairs];pp=post[:-1][pairs];ok=(pp['valid']==63)&(pre['valid'][j]==63);continuity={k:float(np.max(abs(pre[k][j[ok]]-pp[k][ok]))) for k in ['origin_p','origin_q','base_p','base_q','base_v','base_omega','com_p','com_v','link_com_p','link_com_v']}
 continuity['phase_sim_delta_equals_dt']=bool(np.array_equal(pre['sim_ns'][1:]-post['sim_ns'][:-1],pre['dt_ns'][1:]));continuity['same_prepost_sim_label']=bool(np.array_equal(pre['sim_ns'],post['sim_ns']));continuity['present_all_files_sha256']={str(p.relative_to(R)):sha(p) for p in (run/'gz-motor').glob('physics-p13*.bin')}
 t=(post['wall_ns'].astype(np.int64)-epoch)/1e9;use=(t>=0)&(t<=valid_end);x=post[use];t=t[use];M=rot(x['base_q']);theta=np.degrees(np.arccos(np.clip(M[:,2,2],-1,1)));omega=np.einsum('nji,nj->ni',M,x['base_omega']);speeds=np.linalg.norm(x['com_v'],axis=1);H=x['origin_p'][:,2];HC=x['com_p'][:,2];W=-x['com_v'][:,2];i0=max(0,int(np.searchsorted(post['wall_ns'],epoch,side='right')-1));L=post['origin_p'][i0,2]-H;D=np.maximum.accumulate(np.maximum(0,L));LC=post['com_p'][i0,2]-HC;DC=np.maximum.accumulate(np.maximum(0,LC))
 tests={'origin_height':(H>=.7)&(H<=8),'COM_height':(HC>=.7)&(HC<=8.5),'theta80deg':theta<=80,'COM_velocity_norm8':speeds<=8,'body_omega_component8':np.max(abs(omega),axis=1)<=8,'quaternion_unit':abs(np.linalg.norm(x['base_q'],axis=1)-1)<=1e-10,'physical_valid':x['valid']==63}
 domain={}
 for k,v in tests.items():
  bad=np.flatnonzero(~v);domain[k]={'sampled_projection':'PASS' if not len(bad) else 'OUTSIDE','first_exit_profile_s':None if not len(bad) else float(t[bad[0]])}
 rotor_domain=[]
 for k in range(4):
  z,hh=read(run/f'gz-motor/physics-p13-rotor-{k}.bin',ROTOR,b'P13ROTR1');tz=(z['wall_ns'].astype(np.int64)-epoch)/1e9;z=z[(tz>=0)&(tz<=valid_end)];limits=(z['command']>=0)&(z['command']<=1000)&(z['filter_before']>=0)&(z['filter_before']<=1000)&(abs(z['joint']*10)<=1100)&(np.linalg.norm(z['wind'],axis=1)<=1e-12);rotor_domain.append({'motor':k,'rows':len(z),'projected_domain':'PASS' if limits.all() else 'OUTSIDE','scaled_joint_abs_max':float(max(abs(z['joint']*10))),'wind_norm_max':float(max(np.linalg.norm(z['wind'],axis=1)))})
 cache={k:(d['sample_us'].astype(np.int64)-d[k].astype(np.int64)) for k in ['lp_sample','att_sample']};common=(d['t']>=0)&(d['t']<=valid_end)
 domain_report={'schema':'p13-record-domain-1','id':target.name,'initial_physical_state':'KNOWN_DIRECT at stored physical sample time; joint/body/controller stages distinct','recorded_projection':domain,'rotor_projection':rotor_domain,'cache_age_us_ranges':{k:[int(v[common].min()),int(v[common].max())] for k,v in cache.items()},'full_domain_membership':'UNKNOWN_FUTURE_SOLVER_MODE_FREE_VELOCITY_RESIDUAL_AND_CONTINUOUS_INVARIANCE','first_full_domain_unknown_profile_s':0.,'unobserved_or_not_certified':{'free_velocity':'not in light new trace, only old solver subset','lambda_A_eta_modes':'old heavy evidence reused, not directly logged in this run','contacts':'observed geometry far from plane can support source geometric absence, not mode trace or numerical proof of all continuous states','future_joint_residual':'observed now from full geometry, future reachability bound NOT_PROVEN','estimator_filter_internal_state':'physical/LP/cache measurements available, complete EKF covariance/noise/internal filters not snapshot-restored','continuous_prefix':'sampled projections do not themselves prove invariance'},'A4':'NOT_PROVEN_EXCLUDED'}
 write(out/'domain.json',domain_report);write(out/'continuity.json',{'schema':'p13-record-continuity-1','id':target.name,'metrics':continuity,'scope':'full file read/length/hash and phase/state checks; errors0 alone not all IO failures or powerloss durability proof'})
 preds={};predbase=a/'prediction';packbase=a/'packed-physical'
 if not predbase.exists():predbase=R/'data/p13-20261026-development-predictions-v1'/target.name/'prediction';packbase=predbase.parent/'packed'
 if predbase.exists():
  di=json.load(open(packbase/'prediction-input.json'));meta=json.load(open(predbase/'prediction.json'));dt=d['t'];truth_angle=np.array([tilt(q) for q in d['attitude']]);Bstart=plan['full_source_windows_profile_s'][1][0] if run.joinpath('config.json').exists() and json.load(open(run/'config.json'))['p13']['new_task'] else plan['full_source_windows_profile_s'][1 if json.load(open(run/'config.json'))['p11']['source']['condition'].endswith('h45-g0.55') else 2][0]
  for name,inf in meta['models'].items():
   tr=np.load(predbase/(name+'.npz'))['trace'];pt=tr[:,0];good=np.isfinite(tr).all(axis=1);tr=tr[good];pt=pt[good];sel=(dt>=max(0,pt[0]))&(dt<=min(valid_end,pt[-1]));targets=dt[sel];anglep=np.interp(targets,pt,tr[:,7]);err=anglep-truth_angle[sel];ph=np.column_stack([np.interp(targets,pt,tr[:,j]) for j in range(12,28)]);hv=np.linalg.norm(ph-d['h_after'][sel],axis=1)
   bidx=int(np.searchsorted(dt,Bstart,side='right')-1);eval_t=float(dt[bidx]);breached=Bstart<=valid_end;covered=pt[0]<=eval_t<=pt[-1];bx=None
   if breached and covered:
    ht=np.array([np.interp(eval_t,pt,tr[:,j]) for j in range(12,28)]);lp=np.array([np.interp(eval_t,pt,tr[:,j]) for j in range(42,45)]);lv=np.array([np.interp(eval_t,pt,tr[:,j]) for j in range(45,48)]);bx={'planned_B_start_s':Bstart,'evaluated_controller_profile_s':eval_t,'LP_position_error_m':(lp-d['position'][bidx]).tolist(),'LP_velocity_error_m_s':(lv-d['velocity'][bidx]).tolist(),'h_error_l2':float(np.linalg.norm(ht-d['h_after'][bidx])),'tilt_error_deg':float(np.interp(eval_t,pt,tr[:,7])-truth_angle[bidx])}
   r={'common_prefix_controller_rows':int(sel.sum()),'observed_controller_rows':int(common.sum()),'full_prediction':inf.get('stop') is None and pt[-1]>=plan['horizon_profile_s']-.0041,'stop':inf.get('stop'),'tilt_time_error_max_abs_deg':float(max(abs(err))) if len(err) else None,'hidden_error_l2_max':float(max(hv)) if len(hv) else None,'first_predicted_tilt_witness':crossing(pt,tr[:,7],45),'first_observed_LP_tilt_witness':crossing(dt[common],truth_angle[common],45),'B_before_status':'NOT_REACHED' if not breached else ('COVERED' if covered else 'UNKNOWN_PREDICTION_PREFIX_ENDED'),'B_before_errors':bx,'compute_s':inf['compute_s']}
   if name=='M5':
    pu=(pt>=0)&(pt<=valid_end);pz=tr[pu,52];pw=tr[pu,53];pu_t=pt[pu];ppcom=np.interp(t,pu_t,-pz) if len(pu_t) else np.full(len(t),np.nan);pww=np.interp(t,pu_t,pw) if len(pu_t) else np.full(len(t),np.nan);sc=(t>=pt[0])&(t<=pt[-1]);r['COM_H_time_error_max_m']=float(np.max(abs(ppcom[sc]-HC[sc]))) if sc.any() else None;r['COM_W_time_error_max_m_s']=float(np.max(abs(pww[sc]-W[sc]))) if sc.any() else None
    if bx is not None:
     j=max(0,int(np.searchsorted(t,eval_t,side='right')-1));bx.update(COM_H_error_m=float(-np.interp(eval_t,pt,tr[:,52])-HC[j]),COM_W_error_m_s=float(np.interp(eval_t,pt,tr[:,53])-W[j]))
   preds[name]=r
 write(out/'prediction-prefix.json',{'schema':'p13-record-prefix-1','id':target.name,'models':preds,'physical_first_origin_D_witness':crossing(t,D,1),'physical_first_COM_D_witness':crossing(t,DC,1),'scoring':'existing sealed v2 component/OR/UNKNOWN unchanged; extra diagnostics do not change labels or align predicted peaks','no_time_shift':True,'new_starts':0})
 np.savez_compressed(out/'physics.npz',t=t,H=H,HC=HC,L=L,D=D,LC=LC,DC=DC,W=W,theta=theta,omega=omega)
 write(out/'receipt.json',{'schema':'p13-record-analysis-receipt-1','id':target.name,'analysis_source_sha256':sha(Path(__file__)),'raw_body_sha256':sha(run/'gz-motor/physics-p13-body.bin'),'status':'COMPLETE_ANALYSIS','experimental_result_unchanged':True,'data_domain_UNKNOWN_is_not_engineering_failure':True})
 return ev
if __name__=='__main__':review(Path(sys.argv[1]),Path(sys.argv[2]))

"""Assemble fixed-case evidence, conditional map edges and static figures.
No new fit, score thresholds, flight or canonical P14 write.
"""
import sys,json,subprocess
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p14.common import write,sha,records
from p12c.features import load
from p14_motion.core import forecast,mul,conjugate

BASE=ROOT/'data/p14-motion-20261027'
def local_region(region,qnom):
 """Log chart outer enclosure, conditional unit quaternion + positive chart.

 Log(deltaq)=2 vec(deltaq)+r, ||r|| <=2(asin(a)-a), a>=||vec||.
 Existing columns are shared across every state; only chart remainder is new.
 """
 c=region['q_center'];G=region['q_generators'];qinv=conjugate(qnom)
 L=np.column_stack([mul(qinv,np.eye(4)[j]) for j in range(4)])
 center=L@c;gen=L@G;r=np.linalg.norm(abs(center[1:])+np.sum(abs(gen[1:]),axis=1))
 positive=center[0]-np.sum(abs(gen[0]))>0
 if not positive or r>=1:return None,{'chart':'UNAVAILABLE','vector_radius':float(r)}
 rem=2*(np.arcsin(r)-r)+1e-12
 result=dict(region);result['local_SO3_center']=2*center[1:];result['local_SO3_generators']=2*gen[1:];result['local_SO3_remainder_component_rad']=np.full(3,rem)
 return result,{'chart':'right local log about moving nominal','vector_radius':float(r),'nonlinear_component_remainder_rad':float(rem),'positive_quaternion_chart':True,'unit_group_condition':True}

def storage(region):
 keys=['p','v','w','h','previous','mean','f','d1','d2','op','ov','lp','lv']
 scales={'p':.1,'v':.15,'w':.1,'h':.5,'previous':.1,'mean':.1,'f':10.,'d1':.1,'d2':.1,'op':.1,'ov':.15,'lp':.1,'lv':.15}
 G=np.vstack([region[k+'_generators']/scales[k] for k in keys]);norm=np.linalg.norm(G,axis=0);nonzero=norm>0;weights=norm[nonzero]/norm[nonzero].sum();H=G[:,nonzero]/np.sqrt(weights)
 Q=H@H.T;ev=np.linalg.eigvalsh(Q)
 return {'state_projection':keys,'dimension':len(Q),'generators':G.shape[1],'rank_numerical':int(sum(ev>max(ev)*1e-12)),'lambda_max':float(max(ev)),'trace':float(np.trace(Q)),'ellipsoid_support_to_zonotope_max_ratio':float(max(np.sqrt(np.maximum(0,np.diag(Q)))/np.maximum(np.sum(abs(G),axis=1),1e-100))),'formula':'weights_j=||scaled g_j||/sum||scaled g||, Q=sum g_j g_j^T / weights_j; joint zonotope subset ellipsoid e^T Q^dagger e<=1 by weighted Cauchy','contraction_or_complete_storage_certificate':False}

def main():
 out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=False);(out/'edge-regions').mkdir();fig=ROOT/'docs/figures/p14-motion';fig.mkdir(parents=True,exist_ok=True)
 analysis=json.load(open(BASE/'analysis-v2/summary.json'));tubes=json.load(open(BASE/'tubes-final-v2/summary.json'));rr={r['id']:r for r in records()};P=dict(np.load(ROOT/'data/p13-20261026-freeze/models/policy.npz'));M=json.load(open(ROOT/'data/p13-20261026-freeze/models/models.json'))['M2']
 compact=[]
 for a in analysis:
  r=rr[a['id']];d=load(r['target']/'run',r['analysis']);doc=json.load(open(BASE/'inputs-v3'/a['id']/'task-input-nav.json'));models={}
  for name,m in a['models'].items():
   sc=m['score'];models[name]={'risk':sc['risk'],'comparisons':[sc[k] for k in ['risk_comparison','height_risk_comparison','task_risk_comparison']],'peak_deg':sc['tilt_peak_deg'],'full_prefix_errors':m['errors'],'first':m['first'],'stages':m['stages'],'event_windows':sc['event_windows'],'compute_s':sc['compute_s']}
  edge_doc=json.load(open(BASE/'inputs-v3'/a['id']/'edge-input.json'));nom=forecast(edge_doc,M,P);np.savez_compressed(out/(a['id']+'-edge-nominal.npz'),**{k:nom[k] for k in ['trace','states','inputs','native_us']})
  for scope,trace in [('task0',np.load(BASE/'point-v2/predictions'/a['id']/'source.npz')['trace']),('A_pre_conditional',nom['trace'])]:
   st=trace[:,34].astype(bool);caps=np.flatnonzero(st&np.r_[False,~st[:-1]]);res=np.flatnonzero(~st&np.r_[False,st[:-1]])
   write(out/a['id']/(scope+'-event-times.json'),{'scope':scope,'capture_profile_s':trace[caps,0].tolist(),'resume_profile_s':trace[res,0].tolist(),'actual_diagnostic_only':a['actual_stage_events'],'future_actual_clock_word_used':False})
  compact.append({'id':a['id'],'models':models,'known_command':a['known_command'],'raw_gyro':a['raw_gyro_reconstruction'],'actual_events':a['actual_stage_events']})
 write(out/'point-evidence.json',compact)
 # A full conditional edge plus actual attempt to consume its successor at B.
 chosen=next(x for x in tubes if x['name'].startswith('03-'));evidence=ROOT/chosen['evidence_path'];full=json.load(open(evidence/'tube.json'));doc=json.load(open(BASE/'inputs-v3'/chosen['case']/'edge-input.json'));nom=forecast(doc,M,P,limit=full['planned_end_t']);stages={}
 i=doc['initial'];qa=np.array(i['attitude']);qp=np.array(i['physical_q']);alignment=mul(qa,conjugate(qp));rad=json.load(open(ROOT/'config/p14-motion-offline.json'))['initial_scenario_radii'];align_angle=np.degrees(2*np.arccos(np.clip(abs(alignment[0])/np.linalg.norm(alignment),-1,1)))+np.degrees(2*np.sqrt(3)*rad['attitude_rad']*.001)
 norm_error=2*abs(float(qa@qa)-1);norm_tilt_budget=np.degrees(np.arccos(np.clip(1-norm_error,-1,1)))
 for label,reg in full['regions'].items():
  raw=dict(np.load(evidence/'regions'/(label+'.npz')));k=reg['metrics']['call'];local,chart=local_region(raw,nom['states'][k,6:10]);prefix=[x for x in full['rows'] if x['t']<=reg['t']];valid=full['first_domain_loss'] is None or reg['t']<full['first_domain_loss']['t'];prefix_margin={'tilt_margin_deg':45-max(x['tilt_upper_deg'] for x in prefix),'physical_tilt_margin_deg':45-max(x['tilt_upper_deg'] for x in prefix),'cached_attitude_tilt_margin_deg_conservative':45-max(x['tilt_upper_deg'] for x in prefix)-align_angle-norm_tilt_budget,'attitude_alignment_angle_bound_deg':float(align_angle),'known_nonunit_attitude_norm_budget_deg':float(norm_tilt_budget),'height_margin_m':1-max(x['D_upper_m'] for x in prefix),'height_point':'true COM, not LP task-height estimate','all_discrete_prefixes':len(prefix),'between_samples':'requires acceleration/angular-rate enclosure, not certified here'}
  if local is not None:np.savez_compressed(out/'edge-regions'/(label+'.npz'),**local)
  stages[label]={'t':reg['t'],'metrics':reg['metrics'],'prefix_margin':prefix_margin,'within_model_domain':valid,'local_chart':chart,'storage_projection':storage(raw),'data_path':str((evidence/'regions'/(label+'.npz')).relative_to(ROOT)),'sha256':sha(evidence/'regions'/(label+'.npz'))}
 edge={'schema':'conditional-moving-event-map-edge-1','id':'N-stop-capture-hold-resume-recover-F2-example','scientific_role':'analysis-condition result, not actual closed-loop certificate','input':{'control_owner':'neural','case':chosen['case'],'initial':str((BASE/'inputs-v3'/chosen['case']/'edge-input.json').relative_to(ROOT)),'initial_sha256':sha(BASE/'inputs-v3'/chosen['case']/'edge-input.json'),'radius_scale':.001,'initial_set':'local3D physical/observer angle; joint generators; radii from precompute protocol','event_A':doc['plan']['full_source_windows_profile_s'][0],'event_B':doc['plan']['full_source_windows_profile_s'][1],'repair':False,'clock':'one declared 4ms sample/native, 8msLP PH1 word; initial latest pending target slot empty','unknown_future_timing':'not covered; alternate point scenarios only','model_error':'zero extra plant/estimator-model defect conditional model; actual SERVO/EKF coverage NOT ASSERTED','global_H0_NED_z':full['H0_NED_z'],'historical_D0_m':full['initial_D0_m']},'output':{'nominal':str((out/(chosen['case']+'-edge-nominal.npz')).relative_to(ROOT)),'stages':stages,'last_domain_time':full['first_domain_loss'],'first_precision_loss':full['first_precision_loss'],'full_requested_2s_recovery':'NOT_ENCLOSED','cost':{'seconds':full['elapsed_s'],'peak_rss_kib':full['peak_rss_kib'],'generator_columns':full['final_generators']}},'edge_composition':{'operator':'carry SAME center/generator identities, observer/history/mean/count/queue/clock/H0/D into B stop; no reset or independent refactor','B_stop_reached':True,'B_capture_enclosed':False,'reason':'outer tube leaves declared domain before B timeout capture','three_or_four_events':'iterate the same typed input/output; TOP propagates; refinement/certified model domains required, no uniform length claim','rebox_control':next(x['evidence_path'] for x in tubes if x['name'].startswith('07-'))},'evidence_classes':{'source_real_math':'analytic nonlinear remainders + shared-copy/linear operators','finite_numeric':'11 corrected finite tube runs and 4 fixed retrospective point cases','actual_records':'physical/cache/gyro/clip support, not initial-set membership','unverified':'DART future defect, EKF corrections, timing branches, libm/gamma budgets and continuous intersample coverage'}}
 write(out/'map-edge.json',edge)
 # Correlation-preserving translation quotient is an exact model symmetry,
 # not a claim that independent EKF-origin errors cancel.
 shifted=json.loads(json.dumps(doc));shift=np.array([.01,-.01,.01]);i=shifted['initial']
 for key in ['physical_COM_p','position','target_p']:i[key]=(np.array(i[key])+shift).tolist()
 i['physical_H0_NED_z']+=shift[2];table=np.array(shifted['plan']['profile']['table']);table[:,:3]+=shift;shifted['plan']['profile']['table']=table.tolist();translated=forecast(shifted,M,P,limit=full['regions']['resume_plus_p5']['t']);baseline=forecast(doc,M,P,limit=full['regions']['resume_plus_p5']['t']);n=min(len(translated['trace']),len(baseline['trace']));e={'physical_p_shift_error_m':float(np.max(abs(translated['states'][:n,:3]-baseline['states'][:n,:3]-shift))),'action_max_error':float(np.max(abs(translated['trace'][:n,8:12]-baseline['trace'][:n,8:12]))),'SO3_quaternion_component_error':float(np.max(abs(translated['states'][:n,6:10]-baseline['states'][:n,6:10])))}
 write(out/'translation-quotient.json',{'shift':shift,'numeric_check':e,'real_math':'p,LP,target,H0 and entire planned positions co-translate; p-r and L=pz-H0 invariant, forces independent of absolute p','float32_target_cast':'not exactly translation equivariant in actual numeric source; displayed residual remains and needs a cast budget','use':'quotient common frame translation in map; attach shared origin generator to output','not_allowed':'do not identify independent EKF local-origin/attitude-yaw errors with this common translation; remaining micro-radii still tiny'})
 plot(analysis,tubes,fig,rr)
 write(out/'machine-conclusion.json',{'new_SITL':0,'launcher_calls':0,'old_budget_used':0,'new_main_predictor':'one source+minimal-observer motion connection, no new fitting','point_cases':4,'all_new_scores':'retrospective','moving_nominal_angle_absorbed':True,'first_actual_model_gap':'unknown output predictor fusion/attitude/cache time process and future timing; known-command source accurate on 2 complete event records, not universal','first_wide_set_gap':'action/GRU affine nonlinear/reduction loss after 2 calls; not nominal angular drift','conditional_complete_A_and_p5_recovery':True,'real_initial_set_coverage':False,'complete_2s_or_two_capture_edges':False,'A4':'NOT_PROVEN_EXCLUDED','data_sufficiency':'gyro delay states can be reconstructed from prefix under source reset/device assumptions; EKF/output ring/correction state not fully recoverable','primary_domain_result':'1cm scenario loses information at8ms; micro scenario retains fullhold/resume/.5s, then joint feedback remainders grow','formal_certificate':False,'finite_legal_sequence_interface':'typed transition, historyD and allinternalstates carry; precision and domain checked per edge'})

def plot(analysis,tubes,fig,rr):
 f,ax=plt.subplots(2,2,figsize=(11,7),layout='constrained')
 for a,axis in zip(analysis,ax.flat):
  r=rr[a['id']];d=load(r['target']/'run',r['analysis']);j=d['t']>=0;ang=np.degrees(np.arccos(np.clip(1-2*(d['attitude'][:,1]**2+d['attitude'][:,2]**2),-1,1)))
  axis.plot(d['t'][j],ang[j],label='recorded attitude cache',lw=1.4)
  for name in ['source','empirical_same_observer']:
   z=np.load(BASE/'point-v2/predictions'/a['id']/(name+'.npz'))['trace'];axis.plot(z[:,0],z[:,7],label=name,lw=1)
  axis.axhline(45,color='r',ls=':');axis.set(title=a['id'],xlabel='task profile seconds',ylabel='tilt degrees');axis.legend(fontsize=7)
 f.savefig(fig/'moving-nominal.png',dpi=160);plt.close(f)
 f,ax=plt.subplots(2,2,figsize=(11,7),layout='constrained')
 for num,label in [('03-','shared original directions'),('06-','independent box each call'),('08-','normalize outer quaternion'),('07-','rebox at B join')]:
  r=next(x for x in tubes if x['name'].startswith(num));full=json.load(open(ROOT/r['evidence_path']/'tube.json'));rows=full['rows'];t=np.array([x['t'] for x in rows])-full['start_t']
  for axis,key in zip(ax.flat,['SO3_error_upper_deg','action_width_max','v_radius_m_s','D_upper_m']):axis.semilogy(t,np.maximum(1e-10,[x[key] for x in rows]),label=label);axis.set(xlabel='seconds from A-pre conditional initial set',ylabel=key);axis.grid(alpha=.2)
 for axis in ax.flat:axis.legend(fontsize=7)
 f.savefig(fig/'tube-structure.png',dpi=160);plt.close(f)
 clip=json.load(open(BASE/'clipping-v1/summary.json'))['rows'];labels=[];values=[]
 for case in ['p13-F2-b1-AB-short','p13-F4-b1-A','p13-F4-b1-AB-medium','p13-F2-b1-REPAIR-short','p13-F4-b1-REPAIR-medium']:
  x=next(x for x in clip if x['id']==case);labels.append(case.replace('p13-',''));values.append(x['phases']['A_hold']['velocity_max_abs_axes'])
 values=np.array(values);f,axis=plt.subplots(figsize=(9,4),layout='constrained');x=np.arange(len(labels))
 for j,label in enumerate(['target-frame forward','target-frame left','up']):axis.bar(x+(j-1)*.25,values[:,j],.25,label=label)
 axis.axhline(1,color='r',ls=':');axis.set(xticks=x,xticklabels=labels,ylabel='actual preclip velocity error m/s');axis.tick_params(axis='x',rotation=12);axis.legend();f.savefig(fig/'clipping-mechanism.png',dpi=160);plt.close(f)

if __name__=='__main__':main()

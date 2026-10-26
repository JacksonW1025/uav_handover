from analysis_paths_v1 import analysis_dir
"""Initial and fixed pre-A differences to assigned block NORMAL, no selection."""
import json,sys
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'));from p11.models import R as matrix
from p9_model import write,sha
angle=lambda a,b:float(np.degrees(np.arccos(np.clip((np.trace(matrix(a).T@matrix(b))-1)/2,-1,1))))
norm=lambda a,b:float(np.linalg.norm(np.asarray(a)-np.asarray(b)))
def create(aggregate,out):
 out.mkdir(parents=True,exist_ok=False);rows=[r for r in json.load(open(aggregate/'cases.json'))['rows'] if r['status']=='FINISH'];per=[]
 for row in rows:
  e=json.load(open(R/'data/p13-20261026-formal-analysis-v3'/row['id']/'events/event-states.json'));A=next(x for x in e['rows'] if x['label']=='A_before');per.append({'id':row['id'],'family':row['family'],'block':row['block'],'arm':row['arm'],'initial':row['initial'],'A_before':A})
 for r in per:
  n=next((v for v in per if v['family']==r['family'] and v['block']==r['block'] and v['arm']=='NORMAL'),None)
  if n is None:r['NORMAL_comparison_status']='NORMAL_PENDING';continue
  i,j=r['initial'],n['initial'];r['initial_minus_NORMAL']={k:norm(i[k],j[k]) for k in ['position','velocity','omega','h','previous','history','rotor_filter','pending_command','physical_COM_p','physical_COM_v','physical_omega']};r['initial_minus_NORMAL'].update(controller_SO3_deg=angle(i['attitude'],j['attitude']),physical_SO3_deg=angle(i['physical_q'],j['physical_q']),history_count_difference=i['history_count']-j['history_count'],call_index_difference=i['call_index']-j['call_index'],native_sample_phase_difference_us=(i['native_us']-i['sample_us'])-(j['native_us']-j['sample_us']))
  a,b=r['A_before'].get('state'),n['A_before'].get('state');pa,pb=r['A_before'].get('physical'),n['A_before'].get('physical')
  if not a or not b:r['preA_comparison_status']='NOT_REACHED_OR_MISSING';continue
  z={k:norm(a[k],b[k]) for k in ['position_ned_m','velocity_ned_m_s','angular_velocity_body_rad_s','h_before','previous_action_before','history_mean_before','last_completed_filter_after_rad_s','last_completed_scaled_joint_rad_s','last_consumed_command_rad_s']};z.update(SO3_deg=angle(a['attitude_quaternion'],b['attitude_quaternion']),history_count_difference=a['history_count_before']-b['history_count_before'],sample_native_phase_difference_us=(r['A_before']['sample_us']-r['A_before']['native_us'])-(n['A_before']['sample_us']-n['A_before']['native_us']),lp_age_difference_us=a['lp_age_us']-b['lp_age_us'],att_age_difference_us=a['attitude_age_us']-b['attitude_age_us'])
  if pa and pb:z.update({k:pa[k]-pb[k] for k in ['COM_H_m','COM_W_m_s','origin_H_m','origin_W_m_s','body_tilt_deg']})
  r['preA_minus_NORMAL']=z;r['preA_discrete_relation']={k:bool(a[k]==b[k]) for k in ['actual_GRU_commit','pre_read_initialized','force_sync_initialized','force_sync_pre','index_pre','gate_applicable','gate_permit','actual_valid_read']}
 summary={}
 for fam in ['F2','F4']:
  ff=[r for r in per if r['family']==fam and 'preA_minus_NORMAL' in r];keys=sorted(set(k for r in ff for k in r['preA_minus_NORMAL']));summary[fam]={'n':len(ff),'preA_ranges':{k:{'min':min(r['preA_minus_NORMAL'][k] for r in ff),'max':max(r['preA_minus_NORMAL'][k] for r in ff)} for k in keys},'discrete_equal_count':{k:sum(r['preA_discrete_relation'][k] for r in ff) for k in ff[0]['preA_discrete_relation']} if ff else {}}
 write(out/'covariates.json',{'schema':'p13-preA-initial-covariates-1','rows':per,'summary':summary,'selection_or_normalization':False,'reference':'same assigned block NORMAL at fixed common pre-A coordinate, retain actual controller/physical times; no time shift or count normalization','exact_snapshot':False,'complete_theory_initial_set_membership':'UNKNOWN for latent EKF/queue/future mode/geometry/numeric conditions; directly observed initial physical projection separately checked','frozen_model_initial_sensitivity':'data/p13-20261026-diagnostics/initial-sensitivity-summary-v2','source_sha256':sha(Path(__file__))})
if __name__=='__main__':create(Path(sys.argv[1]),Path(sys.argv[2]))

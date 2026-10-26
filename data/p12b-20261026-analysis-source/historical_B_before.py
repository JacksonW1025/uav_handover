"""Historical P12 same-block comparisons; not new P12b flights or strict same-initial proof."""
from pathlib import Path
import sys,json,numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'));sys.path.insert(0,str(Path(__file__).parent))
from event_tables import create
from p12c.features import load,compare
from p11.score import so3
O=R/'data/p12b-20261026-delivery/historical-B-before';O.mkdir(exist_ok=False);results=[]
for phase in [1,2]:
 states={};data={}
 for branch in ['AB','B']:
  ident=f'b2-ph{phase}-{branch}';p=R/'data/p12-cont-20261026-formal'/ident;create(p/'run',p/'analysis',O/ident);doc=json.load(open(O/ident/'event-states.json'));states[branch]=next(r['state'] for r in doc['rows'] if r['label']=='B_before');data[branch]=load(p/'run',p/'analysis')
 a=states['AB'];b=states['B'];delta={k:a[k]-b[k] for k in ['world_current_loss_m','world_historical_max_loss_m','world_current_height_margin_m','world_history_margin_m','world_down_velocity_callback_difference_m_s','LP_down_velocity_m_s','horizontal_task_tracking_error_m','tilt_deg']}
 for key in ['h_before','previous_action_before','history_mean_before','last_completed_filter_after_rad_s','last_completed_scaled_joint_rad_s','last_consumed_command_rad_s']:
  z=np.array(a[key])-np.array(b[key]);delta[key+'_l2']=float(np.linalg.norm(z));delta[key+'_max_component']=float(abs(z).max())
 delta['SO3_deg']=float(so3(np.asarray(a['attitude_quaternion'])[None],np.asarray(b['attitude_quaternion'])[None])[0]);results.append({'source':'old frozen P12 block2, now seen historical diagnostic','phase':phase,'AB_B_before':a,'B_alone_B_before':b,'differences':delta,'pre_A_covariates':compare(data['AB'],data['B'],[12.395,12.895]),'strict_pair':False,'new_SITL_starts':0,'causality':'initial/cache differences retained; historical conditional association only, not a new cross-block replication'})
(O/'comparison.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps([{'phase':r['phase'],'differences':r['differences']} for r in results],indent=2))

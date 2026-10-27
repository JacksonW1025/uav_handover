"""Same conditional output-model interface: never reinitialize history/D/queue."""
import copy,numpy as np

def successor_snapshot(old,edge):
 e=edge['successor'];s=copy.deepcopy(old)
 for k in ['position','velocity','attitude','output_plant_state','publisher_last_profile_s','timestamp','timestamp_sample','local_position_sample','attitude_sample','last_valid_read_us','target_yaw']:s[k]=e[k]
 s.update(profile_s=edge['full_prefix'][-1][0],angular_velocity=e['omega'],gru_after=e['h'],previous_action_after=e['previous'],history=e['mean'],history_count=e['count'],call_index=e['index'],stale=e['stale'],network_target_position=e['reference_p'],network_target_velocity=e['reference_v'],controller_pending=e['read_pending'],LP_W_m_s=e['W'],tilt_deg=edge['full_prefix'][-1][4]);s['direct']['external_seen_pre']=e['external_seen']
 for k,x in enumerate(s['execution']):x['filter_after']=e['filter'][k]
 return s

def reserve(W,b):
 if b<=0:raise ValueError('positive upward deceleration guarantee required')
 return max(0,W)**2/(2*b)

def map_metadata(s,edge):
 return dict(input_clock=dict(sample=s['timestamp_sample'],native=s['timestamp'],index=s['call_index']),conditional_model='L15 output dynamics, full NN/history; not real physical coverage guarantee',full_prefix_margins=dict(tilt_deg=45-edge['peak_tilt_deg'],LP_m=1-edge['peak_LP_D_m']),successor=edge['successor'],LP_D_latched=True,unknown_obligations=['LP-to-physical and future estimator/transport error','current executing filter age and unknown transportation pending','nonlinear/roundoff budgets for sets'],actual_safe_label='NOT_ISSUED',compute_CPU_s=edge['model_CPU_s'])

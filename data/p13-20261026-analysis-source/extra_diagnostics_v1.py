"""After final aggregate: deterministic auxiliary diagnostics, zero new flights."""
import sys,json
from pathlib import Path
from collections import Counter
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path[:0]=[str(R/'tools'),str(Path(__file__).parent)]
from history_prediction_v2 import create as history
from cache_physics_gap_v1 import create as cache
from recovery_prediction_v1 import create as recover
from p9_model import write,sha

def desc(x):
 a=np.array([v for v in x if v is not None]);return {'n':len(a),'mean':float(a.mean()),'min':float(a.min()),'max':float(a.max())} if len(a) else {'n':0}
out=R/'data/p13-20261026-extra-diagnostics-v1';out.mkdir(parents=True,exist_ok=False);cases=json.load(open(R/'data/p13-20261026-results-v2/cases.json'))['rows'];assert len(cases)==66 and all(x['status']=='FINISH' for x in cases);hs=[];cs=[];rs=[];cross=[];phase=[]
for x in cases:
 ident=x['id'];tar=R/'data/p13-20261026-formal'/ident;hpath=R/'data/p13-20261026-history-v2'/ident;history(tar,hpath);hs.append(json.load(open(hpath/'history-prediction.json')));cs.append(cache(tar,R/'data/p13-20261026-cache-physics-v1'/ident));rs.append({'id':ident,'models':recover(tar,R/'data/p13-20261026-recovery-v1'/ident)});cross.append(json.load(open(R/'data/p13-20261026-crossing-v2'/ident/'crossing.json')));phase.append(json.load(open(R/'data/p13-20261026-phase-v2'/ident/'diagnostic.json')));print('EXTRAS',ident,flush=True)
models={}
for name in ['M3','M4','M5']:
 hh=[x['models'][name] for x in hs];rr=[x['models'][name] for x in rs];part={}
 for comp in ['tilt','height']:
  cc=[v for x in cross for v in x['rows'] if v['model']==name and v['component']==comp];paired=[v['predicted_minus_observed_first_time_error_interval_s'] for v in cc if v['predicted_minus_observed_first_time_error_interval_s'] is not None];part[comp]={'all_flights':len(cc),'observed_witness_count':sum(v['observed_first_witness'] is not None for v in cc),'predicted_forward_witness_count':sum(v['forward_prediction_first_witness'] is not None for v in cc),'observed_witness_no_predicted_witness_full_prediction':sum(v['observed_first_witness'] is not None and v['forward_prediction_first_witness'] is None and v['prediction_complete'] for v in cc),'paired_time_error_interval_lower_s':desc([v[0] for v in paired]),'paired_time_error_interval_upper_s':desc([v[1] for v in paired]),'paired_prediction_later_than_observed_intervals':sum(v[0]>0 for v in paired)}
 models[name]={'history_mean_before_l2_error_max_per_flight':desc([x['mean_before_error_l2_max'] for x in hh]),'B_before_status':dict(Counter(x['B_before']['status'] for x in hh)),'B_before_mean_error_l2':desc([x['B_before']['mean_error_l2'] for x in hh if x['B_before']['status']=='COVERED']),'B_before_D_error_m':desc([x['B_before'].get('COM_task0_D_error_m' if name=='M5' else 'plant_vs_LP_task0_D_error_m') for x in hh if x['B_before']['status']=='COVERED']),'count_before_mismatch_calls':sum(sum(v for k,v in x['count_before_difference_counts'].items() if k!='0') for x in hh),'predicted_final_recovery_status':dict(Counter(x['status'] for x in rr)),'paired_recovery_time_error_s':desc([x['time_error_s'] for x in rr]),'first_crossing':part}
cache_summary={k:{'per_flight_min':desc([v[k]['min'] for v in cs]),'per_flight_max':desc([v[k]['max'] for v in cs])} for k in ['physical_latest_past_host_age_us','source_sample_minus_physics_sample_us','LP_z_bias_drift_from_first_m','LP_W_bias_drift_from_first_m_s','LPatt_minus_direct_physical_SO3_deg','gyro_filtered_vs_direct_body_omega_l2_rad_s','M5_predicted_plant_finite_difference_minus_reported_W_m_s']};cache_summary.update(M5_initial_z_bias_m=desc([v['M5_fixed_initial_z_bias_m'] for v in cs]),M5_initial_v_bias_m_s=desc([v['M5_fixed_initial_v_bias_m_s'] for v in cs]))
write(out/'summary.json',{'schema':'p13-extra-diagnostics-1','records':66,'models':models,'cache_vs_physical':cache_summary,'actual_recovery_time_from_own_final_capture_is_separate':True,'history_exact_sample_alignment_not_profile_shift':True,'heldout_model_and_score_changes':False,'first_crossing_Awindow_baseline_vs_task0_separate':True,'new_SITL':0,'source_sha256':sha(Path(__file__))});print('EXTRA_DIAGNOSTICS_COMPLETE66',flush=True)

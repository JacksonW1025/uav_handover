"""Post-hoc mechanism/availability audit. No fit, admission or SITL operations."""
import sys,json,math
from pathlib import Path
import numpy as np
sys.path.insert(0,'tools')
from p11.analyze import at
from p11.score import so3,summary
from p11.models import R,G
from p9_model import write
ROOT=Path('.');formal=ROOT/'data/p11-20261025-formal';out=ROOT/'data/p11-20261026-analysis';plan=json.loads((ROOT/'config/p11.json').read_text());valid={};docs={};measure={};per={}
for row in plan['rows']:
 case=formal/row['id'];f=case/'result.json'
 if not f.exists() or not json.loads(f.read_text()).get('p11_valid_scientific_result'):continue
 d=dict(np.load(case/'packed/measurement.npz'));doc=json.loads((case/'packed/prediction-input.json').read_text());m=json.loads((case/'measured/measurement.json').read_text());valid[row['id']]=d;docs[row['id']]=doc;measure[row['id']]=m
 t=d['profile_s'];start=doc['plan']['common_first_gap_profile_s'];sel=t>=start;table=np.array(doc['plan']['profile']['table']);j=np.clip(np.floor((t-doc['plan']['profile']['table_t0_s'])/.004+1e-8).astype(int),0,len(table)-1);track=np.linalg.norm(d['position'][:,:2]-table[j,:2],axis=1)
 caps=np.flatnonzero(np.r_[False,d['stale'][1:]&~d['stale'][:-1]])
 captures=[{'profile_s':float(t[i]),'velocity_error_horizontal_m_s':float(np.linalg.norm(d['velocity'][i,:2]-d['target_v'][i,:2])),'h_preservation_before_inference_max_abs':float(np.max(abs(d['h_before'][i]-d['h_after'][i-1]))),'previous_preservation_max_abs':float(np.max(abs(d['previous'][i]-d['action'][i-1]))),'native_commit':bool(d['committed'][i])} for i in caps if t[i]>=start and t[i]<=doc['plan']['stream_end_profile_s']]
 finite=np.all(np.isfinite(d['truth_pv']),axis=1)&np.all(np.isfinite(d['truth_q']),axis=1)&sel
 qg=np.array([-G*R(q)[:2,2]/R(q)[2,2] for q in d['attitude'][finite]])
 per[row['id']]={'split':row['split'],'branch':row['branch'],'censored':m['censored'],'captures':captures,'tracking_to_original_plan':{'max_horizontal_error_m':float(track[sel].max()),'integral_horizontal_error_m_s':float(np.trapz(track[sel],t[sel])),'observed_duration_s':float(t[sel][-1]-t[sel][0]),'integral_is_lower_bound':m['censored']},'action_total_variation_L2':float(np.linalg.norm(np.diff(d['action'][sel],axis=0),axis=1).sum()),'hold_truth_difference':{'position_norm_m':summary(np.linalg.norm(d['position'][finite]-d['truth_pv'][finite,:3],axis=1)),'velocity_norm_m_s':summary(np.linalg.norm(d['velocity'][finite]-d['truth_pv'][finite,3:6],axis=1)),'SO3_deg':summary(so3(d['attitude'][finite],d['truth_q'][finite])),'qgeom_minus_net_truth_acc_m_s2':summary(np.linalg.norm(qg-d['truth_pv'][finite,6:8],axis=1)),'interpretation':'different held callback/estimator ages; not instantaneous unbiased estimator error or q causal share'},'whole':m['whole'],'joint_recovery':m['joint_recovery_after_final_capture']}
limits={'p':.1,'v':.15,'SO3':2.5,'action':.1,'h':.5};pairs=[];repair=[];response=[]
def matching(a,b,pre):
 d=valid[a];n=valid[b];m={'p':float(np.linalg.norm(at(d,pre,'position')-at(n,pre,'position'),axis=1).max()),'v':float(np.linalg.norm(at(d,pre,'velocity')-at(n,pre,'velocity'),axis=1).max()),'SO3':float(so3(at(d,pre,'attitude'),at(n,pre,'attitude')).max()),'action':float(np.abs(at(d,pre,'action')-at(n,pre,'action')).max()),'h':float(np.linalg.norm(at(d,pre,'h_after')-at(n,pre,'h_after'),axis=1).max()),'previous_L2':float(np.linalg.norm(at(d,pre,'previous')-at(n,pre,'previous'),axis=1).max())};m['matched']=all(m[k]<=v for k,v in limits.items());return m
for family in [f'F{i}' for i in range(1,7)]:
 for rep in [1,2]:
  ids={b:f'{family}-r{rep}-{b}' for b in ['NORMAL','A','B','AB','REPAIR']};available={b:i for b,i in ids.items() if i in valid}
  if not available:continue
  first=docs[next(iter(available.values()))]['plan']['common_first_gap_profile_s'];pre=np.arange(first-.5,first,.004)
  if 'NORMAL' in available:
   for b,i in available.items():
    if b=='NORMAL':continue
    match=matching(i,ids['NORMAL'],pre);pairs.append({'case':i,'normal':ids['NORMAL'],**match,'complete_cluster':len(available)==5})
    d=valid[i];n=valid[ids['NORMAL']];end=min(d['profile_s'][-1],n['profile_s'][-1]);grid=np.arange(first,end,.004);last_resume=max([a[1] for a in docs[i]['plan']['windows_profile_s']],default=first);metrics={}
    for field,key,threshold in [('position','p',.05),('velocity','v',.1),('action','action',.05),('h_after','h',.1),('attitude','SO3',2.)]:
     x=so3(at(d,grid,field),at(n,grid,field)) if key=='SO3' else np.linalg.norm(at(d,grid,field)-at(n,grid,field),axis=1)
     hit=np.flatnonzero(x>threshold);ok=x<=threshold;band=np.convolve(ok.astype(int),np.ones(500,dtype=int),'valid') if len(ok)>=500 else np.array([]);found=np.flatnonzero((band==500)&(grid[:len(band)]>=last_resume));rec=float(grid[found[0]]) if len(found) else None
     metrics[key]={'peak':float(x.max()),'peak_profile_s':float(grid[np.argmax(x)]),'first_deviation_profile_s':float(grid[hit[0]]) if len(hit) else None,'threshold':threshold,'first_2s_band_after_last_resume_s':rec,'not_recovered_at_observed_end':bool(x[-1]>threshold),'status':'APPROX_MATCHED' if match['matched'] else 'PRESTATE_MISMATCH_RAW_ONLY'}
    response.append({'case':i,'normal':ids['NORMAL'],'metrics':metrics,'end_s':float(end),'censored':measure[i]['censored']})
  if 'AB' in available and 'REPAIR' in available:
   match=matching(ids['REPAIR'],ids['AB'],pre);a=measure[ids['AB']];r=measure[ids['REPAIR']];repair.append({'AB':ids['AB'],'REPAIR':ids['REPAIR'],'prestate':match,'primary':[a['frozen_flight_outcome']['outcome'],r['frozen_flight_outcome']['outcome']],'task':[a['task_outcome'],r['task_outcome']],'max_tilt_deg':[a['whole']['max_tilt_deg'],r['whole']['max_tilt_deg']],'altitude_loss_m':[a['whole']['max_altitude_loss_m'],r['whole']['max_altitude_loss_m']],'censored':[a['censored'],r['censored']],'cost_note':'censored AB peak and integrated tracking are lower bounds; full repair trajectory available. Do not compare truncated integrals as whole-task costs.'})
result={'schema':'p11-mechanisms-1','cases':per,'available_normal_contrasts':pairs,'available_normal_contrasts_n':len(pairs),'matched_available_normal_contrasts':sum(x['matched'] for x in pairs),'repair_AB_pairs':repair,'repair_AB_pairs_n':len(repair),'matched_repair_AB_pairs':sum(x['prestate']['matched'] for x in repair),'incremental_response':response,'exclusions':'frozen thresholds unchanged; incomplete clusters remain incomplete; pairwise availability separated from complete-cluster metric; no reclassification of70'}
write(out/'mechanisms.json',result);print({k:result[k] for k in ['available_normal_contrasts_n','matched_available_normal_contrasts','repair_AB_pairs_n','matched_repair_AB_pairs']})

#!/usr/bin/env python3
"""Frozen all-assignment analysis; no achieved-phase/survival selection or SITL."""
import argparse,json,sys,itertools,hashlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p9_model import sha,write
from p11.score import so3
from p11.observe import multiply
from p12c.features import load,compare
from world_height import world_height
FORMAL=ROOT/'data/p12-cont-20261026-formal';PREP=ROOT/'data/p12-cont-20261026-preparation'
def summary(x):
 x=np.asarray(x,dtype=float)
 if not len(x):return {'n':0}
 return {'n':len(x),'min':float(x.min()),'max':float(x.max()),'mean':float(x.mean()),'sd':float(x.std(ddof=1)) if len(x)>1 else None}
def at(d,grid,key):
 j=np.searchsorted(d['t'],grid,side='right')-1
 if np.any(j<0):raise RuntimeError('missing common prehistory')
 return d[key][j]
def analyze(out):
 out.mkdir(parents=True,exist_ok=False);plan=json.loads((ROOT/'config/p12-cont.json').read_text());results={};data={};raw=[];inodes={};initial={};scores={}
 for row in plan['rows']:
  name=row['id'];case=FORMAL/name
  if not (case/'result.json').exists():continue
  r=json.loads((case/'result.json').read_text());results[name]=r
  if not r['evidence_ok']:continue
  run=case/'run';a=case/'analysis';d=load(run,a);data[name]=d
  doc=json.loads((a/'packed/prediction-input.json').read_text());first=doc['plan']['common_first_gap_profile_s'];i=(d['t']>=first-.5)&(d['t']<first)
  initial[name]={'window_profile_s':[first-.5,first],'rows':int(i.sum()),'mean':{k:np.mean(d[k][i],axis=0).tolist() for k in ['position','velocity','attitude','omega','truth_pv','h_before','previous','mean','exec_filter_after','exec_scaled_joint','exec_command']},'classes':{k:sorted(np.unique(d['sample_us'][i].astype(np.int64)-d[k][i].astype(np.int64)).tolist()) for k in ['lp_sample','att_sample','native_us']},'commit_count':int(d['committed'][i].sum()),'execution_age_us':summary(((d['run_wall_ns'][i,None].astype(np.int64)-d['exec_end_ns'][i].astype(np.int64))/1000).ravel()),'not_same_initial_state':True}
  m=json.loads((a/'measured/measurement.json').read_text());n=json.loads((a/'native/native-audit.json').read_text());sc=json.loads((a/'score/score.json').read_text());scores[name]=sc
  r['measurement']=m;r['captures']=n['captures'];r['assigned_phase']=row['phase'];r['branch']=row['branch'];r['block']=row['block'];r['family']=row['family']
  windows=doc['plan']['windows_profile_s'];reached=[];event_log=[json.loads(x) for x in (run/'events.jsonl').read_text().splitlines()];epoch=d['run_wall_ns'][0]-d['t'][0]*1e9
  for w in windows:
   started=any(e['event']=='p5_gap_started' and np.max(abs(np.asarray(e['planned_profile_s'])-w))<1e-6 for e in event_log)
   captures=[c for c in n['captures'] if w[0]<=(np.mean(c['capture_host_interval_ns'])-epoch)/1e9<w[1]+.1]
   resumed=bool(np.any(d['read_valid']&(d['t']>=w[1])&(d['t']<w[1]+.2)))
   reached.append({'planned_profile_s':w,'status':'CAPTURE_REACHED' if started and captures else 'STARTED_CAPTURE_NOT_CONFIRMED' if started else 'NOT_REACHED','actual_captures':captures,'resume_read_confirmed':resumed})
  r['event_reach']=reached
  # Absolute Gazebo height uses common task start; never re-zero at capture/resume.
  j0=max(0,int(np.searchsorted(d['t'],0,side='right')-1));active=(d['t']>=first)&(d['t']<=doc['plan']['nominal_horizon_profile_s'])
  r['absolute_world_height']=world_height(d['truth_pv'][:,2],d['t'],d['sample_us'],d['truth_pv_sample'],first,doc['plan']['nominal_horizon_profile_s'],m['censored'])
  pths=[run/'flight.ulg',run/'telemetry.jsonl',run/'resources.jsonl',run/'p11-sends.jsonl',*sorted((run/'gz-motor').glob('*.bin')),*sorted((run/'rootfs/log').glob('**/*.ulg'))]
  for p in pths:
   if not p.exists():continue
   st=p.stat();key=(st.st_dev,st.st_ino)
   if key not in inodes:inodes[key]=sha(p)
   raw.append({'path':str(p.relative_to(ROOT)),'bytes':st.st_size,'allocated_bytes':st.st_blocks*512,'inode':st.st_ino,'device':st.st_dev,'sha256':inodes[key]})
 groups=[];pair_diagnostics=[]
 for block in range(1,5):
  for phase in [1,2]:
   rows=[r for r in plan['rows'] if r['block']==block and r['phase']==phase];names={r['branch']:r['id'] for r in rows}
   if not all(n in data for n in names.values()):groups.append({'block':block,'phase':phase,'status':'INCOMPLETE','missing':[n for n in names.values() if n not in data]});continue
   ds={b:data[n] for b,n in names.items()};doc=json.loads((FORMAL/names['AB']/'analysis/packed/prediction-input.json').read_text());start=doc['plan']['common_first_gap_profile_s'];nominal=doc['plan']['nominal_horizon_profile_s']
   for branch in ['NORMAL1','A','B','AB','REPAIR']:
    pair_diagnostics.append({'block':block,'phase':phase,'arms':[names['NORMAL0'],names[branch]],**compare(ds['NORMAL0'],ds[branch],[start-.5,start]),'strict_pair':False,'inclusion':'all assigned results retained; no selection by diagnostic limits'})
   end=min(nominal,*[d['t'][-1] for d in ds.values()]);grid=np.arange(start,end,.004);N={k:(at(ds['NORMAL0'],grid,k)+at(ds['NORMAL1'],grid,k))/2 for k in ['position','velocity','action','h_after','truth_pv']}
   response={};nonadd={}
   for branch in ['A','B','AB','REPAIR']:
    response[branch]={k:summary(np.linalg.norm(at(ds[branch],grid,k)-N[k],axis=1)) for k in ['position','velocity','action','h_after']}
   for k in ['position','velocity','action','h_after']:
    x=at(ds['AB'],grid,k)-at(ds['A'],grid,k)-at(ds['B'],grid,k)+N[k];nonadd[k]=summary(np.linalg.norm(x,axis=1))
   for label,sl in [('world_position_m',slice(0,3)),('world_velocity_native_fd_m_s',slice(3,6))]:
    x=at(ds['AB'],grid,'truth_pv')[:,sl]-at(ds['A'],grid,'truth_pv')[:,sl]-at(ds['B'],grid,'truth_pv')[:,sl]+N['truth_pv'][:,sl]
    nonadd[label]=summary(np.linalg.norm(x,axis=1))
    nonadd[label]['scope']='position from direct pose; velocity is callback finite difference using native dt, not direct simulator twist; no mixed-unit norm'
   # SO3 ordered product uses each NORMAL separately; do not average quaternions.
   ordered=[]
   for nb in ['NORMAL0','NORMAL1']:
    qn=at(ds[nb],grid,'attitude');rel={}
    for branch in ['A','B','AB']:rel[branch]=np.array([multiply(q*np.array([1,-1,-1,-1]),r) for q,r in zip(qn,at(ds[branch],grid,'attitude'))])
    prod=np.array([multiply(q,r) for q,r in zip(rel['A'],rel['B'])]);ordered.append(summary(so3(prod,rel['AB'])))
   whole={b:results[n]['measurement']['whole'] for b,n in names.items()};complete=all(not results[n]['censored'] for n in names.values());contrasts={}
   for metric in ['max_tilt_deg','max_altitude_loss_m']:
    y={b:float(w[metric]) for b,w in whole.items()};normal=(y['NORMAL0']+y['NORMAL1'])/2
    contrasts[metric]={'A-N':y['A']-normal,'B-N':y['B']-normal,'AB-N':y['AB']-normal,'AB-A-B+N':y['AB']-y['A']-y['B']+normal,'REPAIR-AB':y['REPAIR']-y['AB'],'full_peak_estimable':complete,'censored_values':'observed lower bounds if incomplete, not full peak effects'}
   # Repair cost only over same observed absolute time window, separately complete results.
   er=min(nominal,ds['AB']['t'][-1],ds['REPAIR']['t'][-1]);gr=np.arange(start,er,.004);table=np.asarray(doc['plan']['profile']['table']);tt=doc['plan']['profile']['table_t0_s']+.004*np.arange(len(table));ref=table[np.clip(np.searchsorted(tt,gr,side='right')-1,0,len(table)-1),:3]
   cost={b:float(.004*np.sum(np.sum((at(ds[b],gr,'position')-ref)**2,axis=1))) for b in ['AB','REPAIR']}
   groups.append({'block':block,'phase':phase,'family':rows[0]['family'],'status':'COMPLETE_RANDOMIZED_GROUP','strict_same_initial_pair':False,'whole':whole,'task':{b:results[n]['task_outcome'] for b,n in names.items()},'flight':{b:results[n]['flight_outcome']['outcome'] for b,n in names.items()},'all_assignments_included':True,'common_observed_window_profile_s':[start,end],'full_common_window':complete,'responses':response,'nonadditive_continuous_AB_minus_A_minus_B_plus_N':nonadd,'SO3_ordered_A_then_B_two_normal_bases':ordered,'peak_contrasts':contrasts,'repair_common_window':{'profile_s':[start,er],'tracking_squared_integral_m2s':cost,'full_task_separately_reported':True}})
 criteria=json.loads((PREP/'frozen-experimental-protocol.json').read_text())['comparability']['continuous_diagnostic_limits']
 for pair in pair_diagnostics:
  c=pair['continuous'];values={'position_l2_m':c['position']['max_l2'],'velocity_l2_m_s':c['velocity']['max_l2'],'SO3_deg':c['SO3_deg']['max'],'hidden_l2':c['h_before']['max_l2'],'previous_component':c['previous']['max_component'],'history_component':c['mean']['max_component'],'filter_component_rad_s':c['exec_filter_after']['max_component']}
  pair['continuous_diagnostic_pass']={k:v<=criteria[k] for k,v in values.items()};pair['same_observed_discrete_stages']=not any(pair['discrete'].values());pair['theory_set_membership']='NOT_PROVEN_FULL_FEEDBACK';pair['analysis_inclusion']='RETAINED_IN_ASSIGNED_BLOCK; no threshold relaxation or post-treatment matching'
 estimates={}
 for family,phase in itertools.product(['F2','F4'],[1,2]):
  valid=[g for g in groups if g.get('family')==family and g['phase']==phase and g['status']=='COMPLETE_RANDOMIZED_GROUP']
  for metric in ['max_tilt_deg','max_altitude_loss_m']:
   for contrast in ['A-N','B-N','AB-N','AB-A-B+N','REPAIR-AB']:
    vals=[g['peak_contrasts'][metric][contrast] for g in valid if g['peak_contrasts'][metric]['full_peak_estimable']];s=summary(vals)
    if len(vals)==3:s['t2_95_interval']=[s['mean']-4.302653*s['sd']/np.sqrt(3),s['mean']+4.302653*s['sd']/np.sqrt(3)]
    s['scope']='F2 three chronological blocks, F4 one descriptive block; exploratory t2 interval assumes block-contrast normality; incomplete full peaks excluded from estimand with denominator explicit, not removed from ITT risk analysis';estimates[f'{family}/phase{phase}/{metric}/{contrast}']=s
 denoms={}
 for model in ['M2','M3','M4','single_clock','no_history','no_filter','uncorrelated_capture']:
  vals=[s['models'][model] for s in scores.values()];denoms[model]={'flight_samples':len(vals),'risk_labels':{k:{label:sum(v.get(k)==label for v in vals) for label in sorted({v.get(k) for v in vals},key=str)} for k in ['risk_comparison','height_risk_comparison','task_risk_comparison']},'full_peak_denominator':sum(v.get('peak_abs_error_deg') is not None for v in vals),'full_peak_abs_error_deg':summary([v['peak_abs_error_deg'] for v in vals if v.get('peak_abs_error_deg') is not None])}
 starts=[json.loads(s) for s in (PREP/'attempts.jsonl').read_text().splitlines() if json.loads(s)['event']=='START_INTENT'];formal=[s for s in starts if s['budget_class']=='formal']
 conclusion={'schema':'p12-cont-conclusion-analysis-2','budget':{'old':9,'new_preparation':len(starts)-len(formal),'formal_starts':len(formal),'valid_formal':sum(r['evidence_ok'] for r in results.values()),'cumulative':9+len(starts),'new_caps':[12,48,60],'cumulative_cap':69},'complete_randomized_groups':sum(g['status']=='COMPLETE_RANDOMIZED_GROUP' for g in groups),'strict_pairs':0,'experimental_design':'pre-frozen all-assignment randomized blocked; real initial differences retained','theory':{'full_feedback':'NOT_PROVEN','relations':'capture/decel reference/switched filter/conditional servo residual','A4':'NOT_PROVEN_EXCLUDED'},'formal_risk_outcomes':{b:{label:sum(r['branch']==b and r['task_outcome']==label for r in results.values()) for label in ['SUCCESS','FAILURE','UNKNOWN_CENSORED']} for b in ['NORMAL0','NORMAL1','A','B','AB','REPAIR']},'controlled_catchup':'NOT_RUN_UNVALIDATED; natural clock words retained, no causal strength conclusion','models':'frozen M2/M3 baselines and M4 sample-window logic with scorev2; no holdout refit','ci':'queried after publication separately'}
 ledger_status=[]
 for row in plan['rows']:
  hits=[x for x in formal if x['id']==row['id']];result=results.get(row['id'])
  ledger_status.append({'id':row['id'],'family':row['family'],'block':row['block'],'assigned_phase':row['phase'],'branch':row['branch'],'status':'VALID_FINISHED' if result and result.get('evidence_ok') else 'INVALID_INFRASTRUCTURE_INTERRUPTED' if (FORMAL/row['id']/'interruption.json').exists() else 'REJECTED_FROZEN_AUDIT' if any(x['event']=='STOP' and x.get('id')==row['id'] for x in [json.loads(v) for v in (PREP/'attempts.jsonl').read_text().splitlines()]) else 'STARTED_OUTCOME_UNCERTAIN' if hits else 'NOT_STARTED','input_sha256':row['config_sha256']})
 conclusion['invalid_formal']=[x['id'] for x in ledger_status if x['status']=='INVALID_INFRASTRUCTURE_INTERRUPTED'];conclusion['rejected_frozen_audit']=[x['id'] for x in ledger_status if x['status']=='REJECTED_FROZEN_AUDIT'];conclusion['pending_unstarted']=[x['id'] for x in ledger_status if x['status']=='NOT_STARTED'];conclusion['execution_status']='STOPPED_AT_NEW_FROZEN_AUDIT_ERROR_NO_BYPASS';conclusion['all_assignment_ledger']=ledger_status;conclusion['analysis_version']='v2 coordinate/units correction; frozen native/score/plan/parameters unchanged';conclusion['raw_evidence_unchanged']=True
 write(out/'startup-exclusion-ledger.json',ledger_status)
 for n,v in [('cases',results),('initial-covariates',initial),('prestate-diagnostics',pair_diagnostics),('randomized-groups',groups),('block-estimates',estimates),('prediction-denominators',denoms),('conclusion',conclusion),('raw-data-manifest',{'files':raw,'unique_inodes':len(inodes),'large_raw_local_only':True})]:write(out/(n+'.json'),v)
 print(json.dumps({'budget':conclusion['budget'],'complete_groups':conclusion['complete_randomized_groups'],'invalid_formal':conclusion['invalid_formal'],'status':'ANALYSIS_V2_WRITTEN'}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();analyze(a.output)

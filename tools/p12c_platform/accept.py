#!/usr/bin/env python3
"""Three prospective gates; no fitted correction, achieved-phase selection or retries."""
import json,sys
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p9_model import write
from p12c.features import load,compare
from p11.models import tilt
P=R/'data/p12c-20261026-preparation';D=R/'data/p12c-20261026-development'
def task_features(parent):
 d=load(parent/'run',parent/'analysis');plan=json.load(open(parent/'analysis/packed/prediction-input.json'))['plan'];tt=d['t'];table=np.asarray(plan['profile']['table']);j=np.clip(np.floor((tt-plan['profile']['table_t0_s'])/.004+1e-8).astype(int),0,len(table)-1);d['track']=np.linalg.norm(d['position'][:,:2]-table[j,:2],axis=1);d['tilt']=np.array([tilt(q) for q in d['attitude']]);i0=max(0,int(np.searchsorted(tt,0,side='right')-1));d['L_world']=d['truth_pv'][:,2]-d['truth_pv'][i0,2] # H0-H = z-z0
 d['L_LP']=d['position'][:,2]-d['position'][i0,2];d['W']=d['velocity'][:,2];m=json.load(open(parent/'analysis/measured/measurement.json'));end=min(plan['nominal_horizon_profile_s'],float(tt[-1]))
 if m.get('failure'):
  epoch=float(d['run_wall_ns'][0]-tt[0]*1e9);end=min(end,(m['failure']['monotonic_ns']-epoch)/1e9)
 return d,plan,m,end

def metrics(a,b,lo,hi):
 sel=(a['t']>=lo)&(a['t']<=hi);t=a['t'][sel]
 if not len(t):raise RuntimeError('empty common valid prefix')
 out={'window_s':[lo,hi],'rows':int(sel.sum()),'alignment':'absolute task axis, interpolate shared fields, no peak/capture alignment'}
 for k in ['tilt','L_world','L_LP','W','track']:out[k]=float(np.max(abs(a[k][sel]-np.interp(t,b['t'],b[k]))))
 return out

def dynamic_pass(m,s):return m['tilt']<=s['tilt_deg'] and m['L_world']<=s['world_loss_m'] and m['L_LP']<=s['LP_loss_m'] and m['W']<=s['LP_down_velocity_m_s'] and m['track']<=s['tracking_error_m']

def main(output):
 if output.exists():raise FileExistsError(output)
 spec=json.load(open(P/'noninterference-spec.json'));rows=json.load(open(P/'protocol.json'))['rows'];records={};hard={};candidates=[]
 for r in rows:
  parent=D/r['id'];result=json.load(open(parent/'result.json'));eng=json.load(open(parent/'analysis/engineering.json'));candidates.append(json.load(open(parent/'candidate.json')));hard[r['id']]=result['evidence_ok'] and eng['status']=='PASS';records[r['id']]=task_features(parent)
 hard['same_candidate_all12']=all(x==candidates[0] for x in candidates);pairs=[];dynamic={};suff={};natural=[]
 for cls in ['NORMAL','SAFE_EVENT','BOUNDARY']:
  rr=[r for r in rows if r['class']==cls];full={False:0,True:0};discord=[]
  for block in [1,2]:
   x=next(r for r in rr if r['block']==block and not r['observe']);y=next(r for r in rr if r['block']==block and r['observe']);a,plan,ma,ea=records[x['id']];b,_,mb,eb=records[y['id']];first=plan['common_first_gap_profile_s'];pre=compare(a,b,[first-.5,first]);sc=spec['prestate_scales'];c=pre['continuous'];initial_ok=c['position']['max_l2']<=sc['position_l2_m'] and c['velocity']['max_l2']<=sc['velocity_l2_m_s'] and c['SO3_deg']['max']<=sc['SO3_deg'] and c['h_before']['max_l2']<=sc['hidden_l2'] and c['exec_filter_after']['max_l2']<=sc['filter_l2_rad_s'] and c['absolute_world_height_m']['max']<=sc['absolute_height_m'];common=metrics(a,b,max(0,float(a['t'][0]),float(b['t'][0])),min(ea,eb));passed=dynamic_pass(common,spec['dynamic_scales']);both=not ma['censored'] and not mb['censored'];full[False]+=not ma['censored'];full[True]+=not mb['censored'];direction=(ma['task_outcome'],mb['task_outcome'],ma['censored'],mb['censored']);discord.append(direction)
   # Compare all reached planned capture AND resume witnesses; absent future remains unknown.
   cap=[]
   for row,d,par,me,end in [(x,a,D/x['id'],ma,ea),(y,b,D/y['id'],mb,eb)]:
    n=json.load(open(par/'analysis/native/native-audit.json'));epoch=float(d['run_wall_ns'][0]-d['t'][0]*1e9);event=[]
    for aa,bb in plan['windows_profile_s']:
     hits=[float(np.mean(c0['capture_host_interval_ns'])-epoch)/1e9 for c0 in n['captures'] if not c0['activation'] and aa<=(float(np.mean(c0['capture_host_interval_ns'])-epoch)/1e9)<bb+.1];res=np.flatnonzero((d['t']>=bb)&d['read_valid']&~d['stale']&(d['t']<=end));event.append({'window':[aa,bb],'capture':hits[0] if len(hits)==1 and hits[0]<=end else None,'resume':float(d['t'][res[0]]) if len(res) else None})
    cap.append(event)
   timing=[]
   for u,v in zip(*cap):
    for k in ['capture','resume']:
     if u[k] is not None and v[k] is not None:timing.append(abs(u[k]-v[k]))
   timing_ok=not timing or max(timing)<=spec['dynamic_scales']['capture_resume_time_s'];key=f'{cls}-b{block}';dynamic[key]=passed and timing_ok;suff[key+'_initial']=bool(initial_ok);pairs.append({'class':cls,'block':block,'off':x['id'],'on':y['id'],'common_all_valid':common,'pre_A_covariates':pre,'initial_domain':bool(initial_ok),'complete_both':both,'classification':direction,'event_witnesses_off_on':cap,'capture_resume_differences_s':timing,'full_task_comparison':'ELIGIBLE' if both else 'UNKNOWN_CENSORED_VS_COMPLETE_OR_BOTH_PREFIX','no_phase_or_survival_filter':True})
  if cls!='BOUNDARY':suff[cls+'_complete_all']=full[False]==full[True]==2;suff[cls+'_scientifically_safe_all']=all(x[0]==x[1]=='SUCCESS' for x in discord)
  else:
   suff['BOUNDARY_complete_off_and_on']=full[False]>=1 and full[True]>=1
   suff['BOUNDARY_complete_pair']=any(p['class']=='BOUNDARY' and p['complete_both'] for p in pairs)
   # Same-direction disagreement in both assigned blocks is unresolved, not proof of interference.
   asym=[(x[0]!=x[1] or x[2]!=x[3]) for x in discord];suff['BOUNDARY_no_repeated_same_direction_discordance']=not (all(asym) and discord[0]==discord[1])
  for on in [False,True]:
   z=[r for r in rr if r['observe']==on];a,_,_,ea=records[z[0]['id']];b,_,_,eb=records[z[1]['id']];natural.append({'class':cls,'on':on,'ids':[r['id'] for r in z],'same_arm_spread_different_assigned_seeds':metrics(a,b,max(0,float(a['t'][0]),float(b['t'][0])),min(ea,eb)),'scope':'reported, never used to enlarge equivalence scales'})
 led=[json.loads(x) for x in (P/'attempts.jsonl').read_text().splitlines()];starts=[r for r in led if r['event']=='START_INTENT'];hard['exactly12_unique']=len(starts)==len({r['id'] for r in starts})==12;hard['no_critical_stop']=not any(r['event']=='STOP_CRITICAL' for r in led)
 statuses={'hard_semantics':'PASS' if all(hard.values()) else 'FAIL','dynamic_effect':'PASS' if all(dynamic.values()) else 'NOT_EQUIVALENT_WITHIN_FIXED_SCALES','evidence_sufficiency':'PASS' if all(suff.values()) else 'INSUFFICIENT'};released=all(v=='PASS' for v in statuses.values());result={'schema':'p12c-platform-acceptance-1','engineering_status':'PASS' if released else 'NOT_RELEASED','gates':statuses,'hard_tests':hard,'dynamic_tests':dynamic,'sufficiency_tests':suff,'pairs':pairs,'natural_variation':natural,'new_preparation_starts':12,'formal_starts':0,'old_total_starts':56,'no_posthoc_correction':True,'scope':'finite minimal-platform engineering domain, not population equivalence or zero disturbance versus original controller','theory_gate':{'status':'NOT_PROVEN_FULL_FEEDBACK','experimental_stop':False},'formal_release':'freeze commit/push/readback required' if released else 'STOP_FORMAL_NO_ADDITIONAL_PREPARATION'};write(output,result);print(json.dumps({'status':result['engineering_status'],'gates':statuses,'suff':suff,'dynamic':dynamic},indent=2));return result
if __name__=='__main__':main(P/'acceptance.json')

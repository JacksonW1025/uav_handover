"""Full retrospective scores and process errors; no parameter selection."""
import sys,json,collections,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p14.common import records,write,sha,OUT
from p12.score import score
from p12c.features import load
from p11.models import tilt
from p11.score import so3

def stats(x):
 x=np.asarray(x);return None if not len(x) else {'n':len(x),'RMSE':float(np.sqrt(np.mean(x*x))),'max_abs':float(np.max(abs(x)))}
def crossing(t,x,lim):
 j=np.flatnonzero(x>lim)
 return None if not len(j) else [float(t[max(0,j[0]-1)]),float(t[j[0]])]

def stages(d,plan,id,end):
 w=plan['full_source_windows_profile_s'];a=w[0];b=w[-1] if len(w)>2 and 'F2' in id else w[1]
 t=d['t'];s=d['stale'].astype(bool);caps=np.flatnonzero(s&np.r_[False,~s[:-1]]);res=np.flatnonzero(~s&np.r_[False,s[:-1]])
 def event(gap):
  c=[i for i in caps if gap[0]<=t[i]<=gap[1]+.3];c=c[0] if c else None
  rr=[i for i in res if c is not None and i>c];rr=rr[0] if rr else None
  return {'capture':None if c is None else float(t[c]),'resume':None if rr is None else float(t[rr])}
 A=event(a);B=event(b);st={'pre_A':[0,a[0]],'A_stop_to_end':[a[0],a[1]],'B_before':[b[0]-.004,b[0]],'tail':[plan['stream_end_profile_s'],end]}
 for name,e,gap,nextstart in [('A',A,a,b[0]),('B',B,b,plan['stream_end_profile_s'])]:
  if e['capture'] is not None and e['resume'] is not None:st[name+'_hold']=[e['capture'],e['resume']];st[name+'_recovery']=[e['resume'],nextstart]
 return st,{'A':A,'B':B,'B_plan':b[0]}

def main():
 out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);rows=[];newpred=OUT/'candidate-v1/predictions'
 for r in records():
  id=r['id'];a=r['analysis'];measured=json.load(open(r['measured']));doc=json.load(open(r['packed']/'prediction-input.json'))
  s=score(newpred/id,r['packed'],r['measured'],out/id/'score-new')
  base=score(r['prediction'],r['packed'],r['measured'],out/id/'score-baselines-v2')
  oldscore=r['prediction'].parent/'score/score.json';old=json.load(open(oldscore)) if oldscore.exists() else None
  old_equal=None if old is None else all(base['models'][m]==old['models'][m] for m in base['models'])
  d=load(r['target']/'run',a);t=d['t'];end=min(measured['observed_profile_end_s'],doc['plan']['nominal_horizon_profile_s']);windows,ev=stages(d,doc['plan'],id,end)
  angle=np.array([tilt(q) for q in d['attitude']]);allmodels=dict(base['models'],**s['models']);process={}
  for name in allmodels:
   pdir=newpred/id if name in ['G','M14'] else r['prediction'];tr=np.load(pdir/(name+'.npz'))['trace'];good=np.all(np.isfinite(tr),axis=1);bad=np.flatnonzero(~good);tr=tr[:bad[0]] if len(bad) else tr;pt=tr[:,0]
   sel=(t>=max(0,pt[0]))&(t<=min(end,pt[-1]));tt=t[sel];truthidx=np.flatnonzero(sel)
   at=np.interp(tt,pt,tr[:,7]);pv=np.column_stack([np.interp(tt,pt,tr[:,k]) for k in range(42,48)])
   hh=np.column_stack([np.interp(tt,pt,tr[:,k]) for k in range(12,28)]);aa=np.column_stack([np.interp(tt,pt,tr[:,k]) for k in range(8,12)])
   errors={'tilt_deg':at-angle[sel],'LP_H_m':-pv[:,2]+d['position'][sel,2],'LP_W_m_s':pv[:,5]-d['velocity'][sel,2],
    'hidden_l2':np.linalg.norm(hh-d['h_after'][sel],axis=1),'action_l2':np.linalg.norm(aa-d['action'][sel],axis=1)}
   limits={'tilt_deg':5,'LP_H_m':.1,'LP_W_m_s':.15,'hidden_l2':.5,'action_l2':.1}
   proc={'prefix':{k:stats(v) for k,v in errors.items()},'first_obvious':{k:crossing(tt,abs(v),limits[k]) for k,v in errors.items()},'stages':{},
    'observed_tilt_crossing':crossing(t[(t>=0)&(t<=end)],angle[(t>=0)&(t<=end)],45),
    'predicted_tilt_crossing':crossing(pt,tr[:,7],45),'stop':allmodels[name]['prediction_stop'],'nominal_horizon_s':doc['plan']['horizon_profile_s'],'computed_until_s':float(pt[-1]),'B_before':None}
   for k,(start,finish) in windows.items():
    mask=(tt>=start)&(tt<finish);proc['stages'][k]={'window':[start,finish],'rows':int(mask.sum()),'errors':{e:stats(v[mask]) for e,v in errors.items()},'status':'COVERED_PREFIX' if mask.any() else ('NOT_REACHED' if t[-1]<start else 'UNKNOWN_PREDICTION_ENDED')}
   bt=ev['B_plan'];j=np.searchsorted(tt,bt,side='left')-1
   if t[-1]>=bt and 0<=j<len(tt) and pt[-1]>=bt:
    jj=truthidx[j];start=0;predz=np.interp(tt,pt,tr[:,44]);oz=d['position'][sel,2]
    pl=predz-np.interp(start,pt,tr[:,44]);ol=oz-np.interp(start,t,d['position'][:,2])
    proc['B_before']={'time_s':float(tt[j]),'L_error_m':float(pl[j]-ol[j]),'D_error_m':float(max(0,pl[:j+1].max())-max(0,ol[:j+1].max())),'W_error_m_s':float(errors['LP_W_m_s'][j]),'hidden_l2_error':float(errors['hidden_l2'][j]),'tilt_error_deg':float(errors['tilt_deg'][j])}
   process[name]=proc
  write(out/id/'process.json',{'id':id,'events_diagnostic_only':ev,'models':process,'no_posthoc_shift':True})
  rows.append({'id':id,'group':r['group'],'original_score_models_equal':old_equal,'models':allmodels,'process':process})
  print('SCORED',id,flush=True)
 summary={}
 for group in ['development','formal']:
  rr=[r for r in rows if r['group']==group];summary[group]={}
  for name in ['M3','M4','M5','G','M14']:
   part={}
   for comp in ['tilt','height','task']:
    vals=[r['models'][name] for r in rr];key={'tilt':'risk_comparison','height':'height_risk_comparison','task':'task_risk_comparison'}[comp]
    part[comp]={'comparisons':dict(collections.Counter(v[key] for v in vals)),
     'observed_states':dict(collections.Counter(v['risk']['observed'][comp] for v in vals)),
     'predicted_states':dict(collections.Counter(v['risk']['predicted'][comp] for v in vals)),
     'actual_failure_n':sum(v['risk']['observed'][comp]=='FAILURE' for v in vals),
     'actual_failure_unknown_prediction_n':sum(v['risk']['observed'][comp]=='FAILURE' and v['risk']['predicted'][comp]=='UNKNOWN' for v in vals),
     'n':len(vals),'classifiable_n':sum(v['risk']['classification_eligible'][comp] for v in vals),
     'full_trajectory_n':sum(v['risk']['full_trajectory_eligible'][comp] for v in vals)}
   part['compute_seconds_total']=sum(r['models'][name]['compute_s'] for r in rr)
   part['event_windows']={str(window):{key:dict(collections.Counter(w[key] for r in rr for w in r['models'][name]['event_windows'] if w['window_s']==window)) for key in ['risk_comparison','height_risk_comparison','task_risk_comparison']} for window in [.5,2.]}
   part['max_prefix_errors']={key:max(r['process'][name]['prefix'][key]['max_abs'] for r in rr if r['process'][name]['prefix'][key]) for key in ['tilt_deg','LP_H_m','LP_W_m_s','hidden_l2','action_l2']}
   summary[group][name]=part
 write(out/'records.json',rows);write(out/'summary.json',{'schema':'p14-retrospective-evaluation-1','groups':summary,'all_new_scores_retrospective':True,'six_formal_blocks_only':True,'original_baseline_score_exact_models_matches':sum(r['original_score_models_equal'] is True for r in rows),'old_score_missing_n':sum(r['original_score_models_equal'] is None for r in rows),'new_SITL':0})
if __name__=='__main__':main()

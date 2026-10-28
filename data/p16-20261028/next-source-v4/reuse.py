"""Conditional cross-history transfer, no physical reset and no receiver truth.
Empirical intervals, no global safety certificate. G remains unchanged.
"""
import copy,math,numpy as np
from p16.quality import task
TOL=dict(v=.30,q_deg=3.,omega=.5,filter=30.,pending=30.,h=.4,previous=.15,mean=.15,future_resume_error=.15)
EPS_H=.20;EPS_T=3. # historical engineering envelope, not a future hardbound

def gate(donor,receiver,drop_state=False):
 if donor is None or receiver is None:return False,dict(reason='NO_PREDICTED_TIMEOUT_SEAM')
 structural=['operation','family','G','duration','phase','future_plan_hash']
 if any(donor[k]!=receiver[k] for k in structural):return False,dict(reason='OP_OR_SUFFIX_PLAN_MISMATCH')
 a,b=donor['states'],receiver['states'];dist={};reject=[]
 if not drop_state:
  for k in ['sample_phase_us','commit_phase','count','LP_phase_us','native_minus_sample_us']:
   if donor[k]!=receiver[k]:reject.append(k)
  for key in ['v','omega','h','previous','mean','future_resume_error']:
   dist[key]=float(np.linalg.norm(np.asarray(a[key])-np.asarray(b[key])))
  for key in ['filter','pending']:dist[key]=float(np.max(abs(np.asarray(a[key])-np.asarray(b[key]))))
  qa=np.asarray(a['q']);qb=np.asarray(b['q']);dist['q_deg']=float(np.degrees(2*np.arccos(np.clip(abs(qa@qb)/(np.linalg.norm(qa)*np.linalg.norm(qb)),-1,1))))
  reject.extend(k for k,value in dist.items() if value>TOL[k])
 return not reject,dict(reason='PREDICTED_CONDITIONAL_DOMAIN' if not reject else 'INHERITED_STATE_OR_TIMING_REJECT',distance=dist,tolerances=TOL,reject=reject,timing='conditional nominal word only; actual future words never supplied')

def interval_label(lo,hi,limit):
 if lo is not None and lo>limit:return 'FAIL'
 if hi is not None and hi<=limit:return 'SUCCESS'
 return 'UNKNOWN'

def apply(pool,initial,history,base,drop_state=False,drop_ledger=False):
 pred=copy.deepcopy(base);records=[]
 for c in pool:
  if c['id'] in history:continue
  recipient=initial[c['id']];options=[]
  for ident,observed in history.items():
   d=next(x for x in pool if x['id']==ident)
   if d['prefix']==c['prefix']:continue
   prior=initial[ident];passed,why=gate(prior.get('reuse_signature'),recipient.get('reuse_signature'),drop_state)
   if not observed.get('valid') or not (observed.get('capture_suffix') or {}).get('available',False) or not (observed.get('capture_suffix') or {}).get('branch_compatible',False):passed=False;why=dict(reason='NO_VALID_DONOR_SUFFIX')
   if not passed:records.append(dict(donor=ident,receiver=c['id'],accepted=False,condition=why));continue
   # Both G/R get the same own-query suffix outcome; receiver is prediction only.
   donor_suffix=observed['capture_suffix'];model_suffix=prior.get('capture_suffix');entry=recipient.get('capture_ledger');delta=(recipient.get('capture_suffix') or {}).get('delta_loss')
   if model_suffix is None or entry is None:continue
   if delta is None or model_suffix['delta_loss'] is None:continue
   future=max(0.,delta+donor_suffix['delta_loss']-model_suffix['delta_loss']);angle=recipient['capture_suffix']['peak_tilt']+donor_suffix['peak_tilt']-model_suffix['peak_tilt']
   L=0. if drop_ledger else entry['L'];D=0. if drop_ledger else entry['D'];pre=0. if drop_ledger else entry['prefix_tilt'];complete=bool(observed['complete'])
   dlo=max(D,L+max(0.,future-EPS_H));dhi=max(D,L+future+EPS_H) if complete else None;tlo=max(pre,angle-EPS_T);thi=max(pre,angle+EPS_T) if complete else None
   height=interval_label(dlo,dhi,1);tilt=interval_label(tlo,thi,45);label=task(tilt,height)
   candidate=dict(tilt=tilt,height=height,task=label,peak_loss=max(D,L+future),peak_tilt=max(pre,angle),interval=dict(height=[dlo,dhi],tilt=[tlo,thi]),label_source='conditional_reuse',donor=ident,not_certified_safe=True,empirical_envelope=[EPS_H,EPS_T],model_future_increment=future,task_accounting='max(D_before,L_before+delta_future)' if not drop_ledger else 'ABLATION_REMOVED_LEDGER')
   options.append((max(why.get('distance',{}).values(),default=0),ident,candidate,why))
  if options:
   _,ident,chosen,condition=min(options,key=lambda x:(x[0],x[1]));before=pred[c['id']];pred[c['id']].update(chosen);records.append(dict(donor=ident,receiver=c['id'],accepted=True,condition=condition,interval=chosen['interval'],before={k:before[k] for k in ['tilt','height','task']},after={k:chosen[k] for k in ['tilt','height','task']},classification_changed=any(before[k]!=chosen[k] for k in ['tilt','height','task']),receiver_truth_used=False))
 return pred,records

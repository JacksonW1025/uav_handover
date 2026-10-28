"""Explicit P16 plan/initial adapter for the archived ordinary hybrid EE model.
Plant source is the delivered core.py, not P15. Only known initial+plan enter.
"""
import sys,copy,json,importlib.util,math,time
from pathlib import Path
import numpy as np
from p16.common import R,sha
MAT=R/'research/p16-mac-materials-20261028';OUT=MAT/'output';ENTRY=OUT/'greybox-baseline-audit-20261028/core.py'
sys.path.insert(0,str(ENTRY.parent))
spec=importlib.util.spec_from_file_location('p16_archived_core',ENTRY);core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
from p12.state import Controller,EventTarget
from p11.models import speeds,tilt
DT=.004

def parameters():return json.load(open(OUT/'model-search-20261028/h2_strict_singles.json'))['model']
def controller(init,phase):
 if np.linalg.norm(init['target_v'])<=1e-5:return Controller(init,False,phase)
 # Original constructor imposes an old admission restriction. The source update
 # supports moving fresh references. Copy exactly, never zero target_v/history.
 c=Controller.__new__(Controller);assert init['force_sync']==2
 for name,key in [('h','h'),('previous','previous'),('mean','history')]:setattr(c,name,np.asarray(init[key],float).copy())
 c.count=int(init['history_count']);c.index=int(init['call_index']);c.force_sync=2;c.last_sample=int(init['sample_us']);c.phase=phase;c.pending=None;c.target=EventTarget(False)
 c.target.external_seen=bool(init['external_seen']);c.target.r=np.asarray(init['target_p'],float).copy();c.target.s=np.asarray(init['target_v'],float).copy();c.target.yaw=float(init['target_yaw']);c.target.stale=bool(init['stale']);c.target.last_read=init['last_read_us'];return c

def state(p,v,q,w,lp,lv,aq,f,pending,ctl,t,sample,native,lastsend,initial):
 return dict(p=p.tolist(),v=v.tolist(),q=q.tolist(),omega=w.tolist(),LP_p=lp.tolist(),LP_v=lv.tolist(),att=aq.tolist(),filter=f.tolist(),pending=pending.tolist(),h=ctl.h.tolist(),previous=ctl.previous.tolist(),mean=ctl.mean.tolist(),count=ctl.count,index=ctl.index,force_sync=ctl.force_sync,phase=ctl.phase,stale=bool(ctl.target.stale),target_p=ctl.target.r.tolist(),target_v=ctl.target.s.tolist(),target_yaw=ctl.target.yaw,last_read_age_us=native-ctl.target.last_read if ctl.target.last_read is not None else None,read_pending=None if ctl.pending is None else [np.asarray(x).tolist() for x in ctl.pending],sample_us=int(sample),native_us=int(native),sample_phase_us=int(sample%8000),native_minus_sample_us=int(native-sample),profile_s=float(t),clock_origin=dict(profile_s=initial['profile_s'],sample_us=initial['sample_us'],native_us=initial['native_us']),publisher_last_profile_s=lastsend,LP_phase_us=initial['lp_phase_us'])

def forecast(doc,model=None):
 assert set(doc)=={'id','family','prefix','phase','initial','plan'}
 st=time.process_time();model=parameters() if model is None else model;init=doc['initial'];plan=doc['plan'];table=np.asarray(plan['profile']['table']);profile=plan['profile'];yaw=profile['yaw'];t0=init['profile_s'];sample0=init['sample_us'];native0=init['native_us'];get=lambda k:np.array(init[k],float)
 p=get('position');v=get('velocity');q=get('attitude');q/=np.linalg.norm(q);w=get('omega');lp=p.copy();lv=v.copy();aq=q.copy();ctl=controller(init,doc['phase']);f=get('rotor_filter');pending=get('pending_command');H0=-p[2];D=0.;trace=[];branches=[];stale=True;stop=None;lastsend=-1e30;entry=None;capture=None
 A=plan['A_start'];Aend=A+plan['A_duration'];B=Aend+plan['G'];Bend=B+plan['B_duration'];end=plan['horizon'];streamend=plan['stream_end']
 for k in range(int(np.ceil((end-t0)/DT))+1):
  t=t0+k*DT;sample=sample0+4000*k;native=native0+4000*k
  if k and entry is None and t>=B:entry=state(p,v,q,w,lp,lv,aq,f,pending,ctl,t-DT,sample-4000,native-4000,lastsend,init)
  if k:
   oldq=q.copy();p,v,q,w,_=core.plant(p,v,q,w,f,model);f=core.motor_step(f,pending,DT)
   if sample%8000==init['lp_phase_us']:lp=p.copy();lv=v.copy()
   aq=oldq;message=None
   if 0<=t<streamend and not ((doc['prefix']=='AB' and A<=t<Aend) or B<=t<Bend) and t-lastsend>=.02-1e-10:
    j=min(len(table)-1,max(0,int(np.floor((t-profile['table_t0_s'])/DT+1e-8))));message=(table[j,:3],table[j,3:],yaw);lastsend=t
   action,info=ctl.step(native,sample,lp,lv,aq,w,message,core.reference.P)
   if action is not None:pending=speeds(action)
   if ctl.target.stale!=stale:
    branches.append(dict(t=t,stale=bool(ctl.target.stale),index=ctl.index));stale=ctl.target.stale
    if stale and B<=t<Bend:capture=state(p,v,q,w,lp,lv,aq,f,pending,ctl,t,sample,native,lastsend,init)
  L=lp[2]+H0;D=max(D,L);th=tilt(aq);trace.append([t,L,D,lv[2],th,*lp,*lv])
  if not np.isfinite(np.r_[p,v,q,w]).all() or np.linalg.norm(v)>15 or max(abs(w))>15 or th>85:stop='DOMAIN_EXIT';break
 z=np.asarray(trace);scope=z[:,0]>=A;baseline=float(np.interp(A,z[:,0],z[:,7]));loss=max(0.,float(z[scope,7].max()-baseline));pre=scope&(z[:,0]<B);after=z[:,0]>=B
 if entry is None:entry=state(p,v,q,w,lp,lv,aq,f,pending,ctl,t,sample,native,lastsend,init)
 Lbefore=float(entry['LP_p'][2]-baseline);Dbefore=max(0.,float(z[pre,7].max()-baseline)) if pre.any() else 0.;prefix_tilt=float(z[pre,4].max()) if pre.any() else 0.
 delta=max(0.,float(z[after,7].max()-entry['LP_p'][2])) if after.any() else None;aftertilt=float(z[after,4].max()) if after.any() else None
 entry.update(L=Lbefore,D=Dbefore,prefix_tilt=prefix_tilt,prefix_failed=prefix_tilt>45 or Dbefore>1)
 signature=None
 if capture is not None:
  j=min(len(table)-1,max(0,int(np.floor((Bend-profile['table_t0_s'])/DT+1e-8))));capture['future_resume_error']=(table[j,:3]-np.asarray(capture['p'])).tolist()
  signature=dict(operation='active timeout RTGT0 capture r=p,s=0; retain GRU/history/execution',family=doc['family'],G=plan['G'],duration=plan['B_duration'],phase=doc['phase'],sample_phase_us=capture['sample_phase_us'],commit_phase=capture['index']%2,count=capture['count'],LP_phase_us=capture['LP_phase_us'],native_minus_sample_us=capture['native_minus_sample_us'],future_plan_hash=plan['suffix_plan_hash'],timing_assumption='source nominal4ms/native/sample and20ms publisher, no future real word',states=capture)
 from p16.quality import label,task
 complete=stop is None;a=label(float(z[scope,4].max()),45,complete);b=label(loss,1,complete)
 result=dict(id=doc['id'],peak_tilt=float(z[scope,4].max()),peak_loss=loss,tilt=a,height=b,task=task(a,b),model_complete=complete,stop=stop,prefix_failed_before_B=entry['prefix_failed'],prefix_before_B=entry,suffix=dict(delta_loss=delta,peak_tilt=aftertilt),reuse_signature=signature,branches=branches,CPU_s=time.process_time()-st,source_model='strict EE ordinary nonlinear hybrid greybox from delivered core.plant; explicit source Controller',future_actual_inputs=False)
 return result,z

def legacy_fixture(row,initial=None,model=None):
 inp=core.sanitize(row);init=copy.deepcopy(inp['initial'] if initial is None else initial);old=core.reference.DOCS[row['family']]['plan'];plan=dict(profile=old['profile'],A_start=13.255,A_duration=.36,G=row['gap_s'],B_duration=.36,horizon=old['horizon_profile_s'],stream_end=old['stream_end_profile_s'],suffix_plan_hash='legacyfixture')
 return forecast(dict(id=row['id'],family=row['family'],prefix=row['branch'],phase=row['phase'],initial=init,plan=plan),model)

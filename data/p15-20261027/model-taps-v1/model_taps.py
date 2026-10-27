"""L15: full neural/history finite directional rollout using existing M2 empirical
plant. Observation-output state is the live state; no assertion LP==physicalCOM.
This is a search model with a declared output-dynamics approximation, not safety.
"""
import copy,time
import numpy as np
from p11.models import plant,speeds,tilt
from p12.state import Controller
from p12.execution import step
DT=.004

def initial(s):
 return dict(h=s['gru_after'],previous=s['previous_action_after'],history=s['history'],history_count=s['history_count'],call_index=s['call_index'],force_sync=2,sample_us=s['timestamp_sample'],target_p=s['network_target_position'],target_v=s['network_target_velocity'],target_yaw=s['target_yaw'],stale=s['stale'],external_seen=bool(s['direct']['external_seen_pre']),last_read_us=s['last_valid_read_us'])

def rollout(s,c,context,parameters,P,update=None):
 st=time.process_time();i=initial(s)
 # Target state is moving external reference when fresh. Controller base rejects
 # moving initial targets despite supporting them thereafter; initialize exact
 # source fields directly, without zeroing the actual target or history.
 ctl=Controller.__new__(Controller);ctl.h=np.array(i['h']);ctl.previous=np.array(i['previous']);ctl.mean=np.array(i['history']);ctl.count=i['history_count'];ctl.index=i['call_index'];ctl.force_sync=2;ctl.last_sample=i['sample_us'];ctl.phase=1;ctl.pending=None if s.get('controller_pending') is None else tuple(np.asarray(x) for x in s['controller_pending'])
 from p12.state import EventTarget
 ctl.target=EventTarget(False);ctl.target.r=np.array(i['target_p']);ctl.target.s=np.array(i['target_v']);ctl.target.yaw=i['target_yaw'];ctl.target.stale=i['stale'];ctl.target.external_seen=i['external_seen'];ctl.target.last_read=i['last_read_us']
 internal=s.get('output_plant_state',{});p=np.array(internal.get('p',s['position']));v=np.array(internal.get('v',s['velocity']));q=np.array(internal.get('q',s['attitude']));q/=np.linalg.norm(q);w=np.array(internal.get('w',s['angular_velocity']));lp=np.array(s['position']);lv=np.array(s['velocity']);aq=np.array(s['attitude']);f=np.array([x['filter_after'] for x in s['execution']]);pending=speeds(ctl.previous)
 H0=context['H0_LP'];D=float(context.get('D_LP',0));failed=context.get('prefix_failed',False);a0=context['A_start'];A=context['A_duration'];b0=a0+A+c['G'];b1=b0+c['D'];now0=s['timestamp'];sample0=s['timestamp_sample'];t0=s['profile_s'];end=context['task_end'] if context.get('full_task_forecast') else min(context['task_end'],b1+1.0);table=np.asarray(context['reference_table']);table0=context['table_t0'];lastsend=s.get('publisher_last_profile_s') if s.get('publisher_last_profile_s') is not None else t0-.02;trace=[];branches=[];tapped=[];clips=0;Bpre=None;first_action=None
 M=parameters['plant'];correction=0. if update is None else float(update.get('vertical_acceleration_residual',0))
 steps=max(0,(round((end-t0)*1e9)+3_999_999)//4_000_000)
 for k in range(steps+1):
  t=t0+k*DT;sample=sample0+k*4000;native=now0+k*4000
  if k:
   oldq=q.copy();p,v,q,w,acc=plant(p,v,q,w,f,M)
   # Frozen local update is an acceleration discrepancy in LP output dynamics,
   # applied only in measured recovery mode; never a whole-task label offset.
   if update is not None and a0+A<=t<b0:
    v[2]+=DT*correction;p[2]+=.5*DT*DT*correction
   f=step(f,pending,DT)
   if sample%8000==s['local_position_sample']%8000:lp=p.copy();lv=v.copy()
   aq=oldq
   inside=(c['prefix']=='AB' and a0<=t<a0+A) or b0<=t<b1 or any(a<=t<b for a,b in context.get('additional_windows',[]))
   msg=None
   if t<context.get('stream_end',context['task_end']) and not inside and t-lastsend>=.02-1e-10:
    j=min(len(table)-1,max(0,int((t-table0)/DT+1e-7)));msg=(table[j,:3],table[j,3:],context['yaw']);lastsend=t
   action,info=ctl.step(native,sample,lp,lv,aq,w,msg,P)
   if action is not None:pending=speeds(action)
   if b0<=t and Bpre is None:Bpre=dict(t=t,L=float(lp[2]+H0),D=D,W=float(lv[2]),q=aq.tolist(),omega=w.tolist(),h=ctl.h.tolist(),previous=ctl.previous.tolist(),mean=ctl.mean.tolist(),count=ctl.count,filter=f.tolist(),pending_command=pending.tolist(),call_index=ctl.index,stale=ctl.target.stale,last_read_us=int(ctl.target.last_read))
   if native>=ctl.target.last_read+200000 and not inside:pass
   if info.get('stale')!=locals().get('last_stale',s['stale']):branches.append(dict(t=t,stale=info.get('stale'),index=ctl.index,native_us=native,sample_us=sample));last_stale=info.get('stale')
   if info.get('input') is not None:
    clips+=int(np.any(abs(info['input'][:3])>=.49999) or np.any(abs(info['input'][12:15])>=.99999));tapped.append(np.r_[t,p,v,q,lp,lv,aq,w,info['input'],ctl.h,ctl.previous,ctl.mean,ctl.count,ctl.index,f,pending,ctl.target.r,ctl.target.s])
   if t>=b1 and first_action is None:first_action=ctl.previous.tolist()
  L=float(lp[2]+H0);D=max(D,L);th=float(tilt(aq));failed=failed or th>45 or D>1;trace.append([t,L,D,float(lv[2]),th,*w])
  if not np.isfinite(np.r_[p,v,q,w]).all() or max(abs(w))>8 or tilt(q)>80 or np.linalg.norm(v)>8:break
 z=np.array(trace);peak_tilt=float(z[:,4].max());peakD=float(z[:,2].max());endstate=dict(position=lp.tolist(),velocity=lv.tolist(),attitude=aq.tolist(),output_plant_state=dict(p=p.tolist(),v=v.tolist(),q=q.tolist(),w=w.tolist()),publisher_last_profile_s=lastsend,timestamp=native,timestamp_sample=sample,local_position_sample=sample-((sample-s['local_position_sample'])%8000),attitude_sample=sample-4000,last_valid_read_us=int(ctl.target.last_read),target_yaw=ctl.target.yaw,external_seen=ctl.target.external_seen,L=float(z[-1,1]),D=D,W=float(z[-1,3]),q=q.tolist(),omega=w.tolist(),h=ctl.h.tolist(),previous=ctl.previous.tolist(),mean=ctl.mean.tolist(),count=ctl.count,filter=f.tolist(),pending_command=pending.tolist(),read_pending=None if ctl.pending is None else [np.asarray(x).tolist() for x in ctl.pending],last_read_us=int(ctl.target.last_read),stale=ctl.target.stale,index=ctl.index,reference_p=ctl.target.r.tolist(),reference_v=ctl.target.s.tolist(),prefix_failure_latch=failed)
 Bz=z[z[:,0]>=b0];Btilt=float(Bz[:,4].max()) if len(Bz) else peak_tilt;BD=float(Bz[:,2].max()) if len(Bz) else peakD;BbeforeD=Bpre['D'] if Bpre else D;Bscore=max(Btilt/45,max(0,BD-BbeforeD)/max(.1,1-BbeforeD));return dict(analysis_taps=tapped,candidate=c,peak_tilt_deg=peak_tilt,peak_LP_D_m=peakD,score=Bscore,whole_prefix_score_v1=max(peak_tilt/45,peakD),score_projection='C: Bforward absolute tilt and newD/remainingmargin; oldApeak and failurelatch retained separately',B_peak_tilt_deg=Btilt,B_new_D_m=max(0,BD-BbeforeD),Bpre=Bpre,successor=endstate,full_prefix=z.tolist(),first_resume_action=first_action,clip_calls=clips,decision_direction= dict(W_initial=s['LP_W_m_s'],W_Bpre=Bpre['W'] if Bpre else None,L_initial=float(s['position'][2]+H0),L_Bpre=Bpre['L'] if Bpre else None),model_CPU_s=time.process_time()-st,scope='empirical output-dynamics nominal; no full EKF/COM equivalence/guaranteed coverage; no future actual inputs',stop='DOMAIN_EXIT' if z[-1,0]<end-DT else None,branches=branches)

def rank(snapshot,pool,context,parameters,P,method,rng,used=(),update=None):
 pool=[c for c in pool if c['id'] not in used] or pool;start=time.process_time();rows=[]
 for c in pool:
  if method in ['M0','M1']:score=float(rng.random());prediction=None
  elif method=='M2':
   # Fixed cheap non-directional baseline: displacement and residual magnitude.
   v=float(np.linalg.norm(snapshot['velocity'][:2]));score=v*c['D']/.5+abs(snapshot['LP_W_m_s'])*c['D']+snapshot['tilt_deg']/45+max(0,context.get('D_LP',0));prediction=None
  else:
   prediction=rollout(snapshot,c,context,parameters,P,update);score=prediction['score']
  rows.append(dict(candidate=c,score=float(score),prediction=prediction))
 rows.sort(key=lambda x:(-round(x['score'],9),x['candidate']['id']))
 return dict(selected=rows[0]['candidate'],rows=rows,method=method,CPU_s=time.process_time()-start,information='completed live LP/att/gyro/history/execution plus plan; no future COM or outcomes',not_safety_classification=True)

from pathlib import Path
import sys,json,time,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parent.parent;OLD=PROJECT/'output/offline-adjoint-20261028'
sys.path.insert(0,str(OLD/'upstream/tools'))
sys.path.insert(0,str(ROOT/'upstream/tools'))
from p11.models import plant,speeds,tilt
from p11.observe import inputs,network
from p12.state import Controller,EventTarget
from p12.execution import step as motor_step
P=dict(np.load(OLD/'upstream/data/p11-20261025-formal/models/policy.npz'))
M=json.loads((OLD/'upstream/data/p11-20261025-formal/models/models.json').read_text())['M2']
DOCS={
 'F2':json.loads((OLD/'upstream/data/p13-20261026-formal/p13-F2-b1-AB-short/analysis-v1/packed/prediction-input.json').read_text()),
 'F4':json.loads((ROOT/'upstream/data/p13-20261026-formal/p13-F4-b1-B-short/analysis-v1/packed/prediction-input.json').read_text())}
DT=.004
def forecast(r):
 b=r['B_before'];s=b['state'];doc=DOCS[r['family']];profile=doc['plan']['profile'];table=np.array(profile['table']);yaw=profile['yaw'];t0=b['observed_profile_s'];sample0=b['sample_us'];native0=b['native_us'];state=lambda key:np.array(s[key],float)
 p=state('position_ned_m');v=state('velocity_ned_m_s');q=state('attitude_quaternion');q/=np.linalg.norm(q);w=state('angular_velocity_body_rad_s');lp=p.copy();lv=v.copy();aq=q.copy();h=state('h_before');prev=state('previous_action_before');hist=state('history_mean_before')
 xx=np.r_[inputs(p,v,q,w,state('target_p_ned_m'),state('target_v_ned_m_s'),yaw),hist]
 hnew,raw,action=network(P,h,xx);reconstruction_error=float(np.max(np.abs(action-state('action_after'))))
 ctl=Controller.__new__(Controller);ctl.h=hnew if s['actual_GRU_commit'] else h;ctl.previous=state('action_after');ctl.mean=hist;ctl.count=0 if s['actual_GRU_commit'] else s['history_count_before'];ctl.index=s['index_pre']+1;ctl.force_sync=2;ctl.last_sample=sample0;ctl.phase=r['phase'];ctl.pending=None
 ctl.target=EventTarget(r['branch']=='REPAIR');ctl.target.r=state('target_p_ned_m');ctl.target.s=state('target_v_ned_m_s');ctl.target.yaw=yaw;ctl.target.stale=False;ctl.target.external_seen=True
 tt=profile['table_t0_s']+np.arange(len(table))*DT;eligible=tt<=t0+1e-9;distance=np.linalg.norm(table[:,:3]-ctl.target.r,axis=1)+.1*np.linalg.norm(table[:,3:]-ctl.target.s,axis=1);distance[~eligible]=np.inf;idx=int(np.argmin(distance));lastsend=float(tt[idx]);age=np.clip(t0-lastsend,0,.04);ctl.target.last_read=native0-round(age*1e6)
 f=speeds(ctl.previous);pending=f.copy();lp_phase=(sample0-s['lp_age_us'])%8000;H0=s['LP_current_loss_m']-p[2];D=s['LP_historical_loss_m'];Bstart=13.255+.36+r['gap_s'];Bend=Bstart+.36;end=doc['plan']['horizon_profile_s'];streamend=doc['plan']['stream_end_profile_s'];trace=[];branches=[];stale=False;stop=None;has_B=r['branch'] in ['B','AB','REPAIR']
 for k in range(int(np.ceil((end-t0)/DT))+1):
  t=t0+k*DT;sample=sample0+4000*k;native=native0+4000*k
  if k:
   oldq=q.copy();p,v,q,w,acc=plant(p,v,q,w,f,M);f=motor_step(f,pending,DT)
   if sample%8000==lp_phase:lp=p.copy();lv=v.copy()
   aq=oldq;message=None
   if t<streamend and not (has_B and Bstart<=t<Bend) and t-lastsend>=.02-1e-10:
    j=min(len(table)-1,max(0,int(np.floor((t-profile['table_t0_s'])/DT+1e-8))));message=(table[j,:3],table[j,3:],yaw);lastsend=t
   action,info=ctl.step(native,sample,lp,lv,aq,w,message,P)
   if action is not None:pending=speeds(action)
   if ctl.target.stale!=stale:branches.append(dict(t=t,stale=ctl.target.stale));stale=ctl.target.stale
  L=lp[2]+H0;D=max(D,L);th=tilt(aq);trace.append([t,L,D,lv[2],th,*lp,*lv])
  if not np.isfinite(np.r_[p,v,q,w]).all() or np.linalg.norm(v)>15 or max(abs(w))>15 or th>85:
   stop='DOMAIN_EXIT';break
 z=np.array(trace);out=dict(id=r['id'],family=r['family'],arm=r['arm'],block=r['block'],prediction=float(D),predicted_failure=bool(D>1),actual=float(r['LP_max_loss_m']),actual_censored=r['censored'],actual_height_status='FAILURE' if r['LP_max_loss_m']>1 else 'UNKNOWN' if r['censored'] else 'SUCCESS',initial_D=s['LP_historical_loss_m'],initial_L=s['LP_current_loss_m'],initial_W=s['LP_down_velocity_m_s'],initial_tilt=s['tilt_deg'],nominal_last_read_age_s=float(age),reference_match_distance=float(distance[idx]),current_action_reconstruction_error=reconstruction_error,stop=stop,branches=branches,simulated_until=float(z[-1,0]))
 return out,z
def main():
 rows=json.loads((OLD/'upstream/data/p13-20261026-results-v3/cases.json').read_text())['rows'];rows=[r for r in rows if r['B_before']['status']=='OBSERVED'];results=[];traces={};start=time.perf_counter()
 for r in sorted(rows,key=lambda r:r['id']):
  out,z=forecast(r);results.append(out);traces[r['id']]=z;print(out['id'],round(out['prediction'],3),round(out['actual'],3),out['actual_height_status'],out['stop'],flush=True)
 complete=[x for x in results if not x['actual_censored']];positive=[x for x in results if x['actual_height_status']=='FAILURE'];negative=[x for x in results if x['actual_height_status']=='SUCCESS']
 summary=dict(n=len(results),complete_n=len(complete),complete_mae=float(np.mean([abs(x['prediction']-x['actual']) for x in complete])),complete_rmse=float(np.sqrt(np.mean([(x['prediction']-x['actual'])**2 for x in complete]))),height_false_negatives=sum(not x['predicted_failure'] for x in positive),height_positive_n=len(positive),height_false_positives=sum(x['predicted_failure'] for x in negative),height_negative_n=len(negative),domain_exits=sum(x['stop'] is not None for x in results),cpu_wall_s=time.perf_counter()-start)
 (ROOT/'h2_source_results.json').write_text(json.dumps(dict(summary=summary,results=results,protocol_sha256=hashlib.sha256((ROOT/'h2_protocol.json').read_bytes()).hexdigest()),indent=2));np.savez_compressed(ROOT/'h2_source_traces.npz',**traces);print('SUMMARY',summary,flush=True)
if __name__=='__main__':main()

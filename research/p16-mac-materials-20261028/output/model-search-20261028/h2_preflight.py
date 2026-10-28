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
 initial=r['initial'];doc=DOCS[r['family']];profile=doc['plan']['profile'];table=np.array(profile['table']);yaw=profile['yaw'];t0=initial['profile_s'];sample0=initial['sample_us'];native0=initial['native_us'];state=lambda key:np.array(initial[key],float)
 p=state('position');v=state('velocity');q=state('attitude');q/=np.linalg.norm(q);w=state('omega');lp=p.copy();lv=v.copy();aq=q.copy()
 ctl=Controller(initial,r['branch']=='REPAIR',r['phase'])
 f=state('rotor_filter');pending=state('pending_command');lp_phase=initial['lp_phase_us'];H0=-p[2];D=0.;Bstart=13.255+.36+r['gap_s'];Bend=Bstart+.36;end=doc['plan']['horizon_profile_s'];streamend=doc['plan']['stream_end_profile_s'];trace=[];branches=[];stale=True;stop=None;lastsend=-1e30;has_B=r['branch'] in ['B','AB','REPAIR'];has_A=r['branch'] in ['A','AB','REPAIR']
 for k in range(int(np.ceil((end-t0)/DT))+1):
  t=t0+k*DT;sample=sample0+4000*k;native=native0+4000*k
  if k:
   oldq=q.copy();p,v,q,w,acc=plant(p,v,q,w,f,M);f=motor_step(f,pending,DT)
   if sample%8000==lp_phase:lp=p.copy();lv=v.copy()
   aq=oldq;message=None
   if 0<=t<streamend and not ((has_A and 13.255<=t<13.615) or (has_B and Bstart<=t<Bend)) and t-lastsend>=.02-1e-10:
    j=min(len(table)-1,max(0,int(np.floor((t-profile['table_t0_s'])/DT+1e-8))));message=(table[j,:3],table[j,3:],yaw);lastsend=t
   action,info=ctl.step(native,sample,lp,lv,aq,w,message,P)
   if action is not None:pending=speeds(action)
   if ctl.target.stale!=stale:branches.append(dict(t=t,stale=ctl.target.stale));stale=ctl.target.stale
  L=lp[2]+H0;D=max(D,L);th=tilt(aq);trace.append([t,L,D,lv[2],th,*lp,*lv])
  if not np.isfinite(np.r_[p,v,q,w]).all() or np.linalg.norm(v)>15 or max(abs(w))>15 or th>85:
   stop='DOMAIN_EXIT';break
 z=np.array(trace);scope=z[:,0]>=doc['plan']['common_first_gap_profile_s'];baseline=float(np.interp(doc['plan']['common_first_gap_profile_s'],z[:,0],z[:,7]));D=max(0.,float(z[scope,7].max()-baseline));out=dict(id=r['id'],family=r['family'],arm=r['arm'],block=r['block'],prediction=float(D),predicted_failure=bool(D>1),actual=float(r['LP_max_loss_m']),actual_censored=r['censored'],actual_height_status='FAILURE' if r['LP_max_loss_m']>1 else 'UNKNOWN' if r['censored'] else 'SUCCESS',initial_D=0.,initial_L=0.,initial_W=float(initial['velocity'][2]),initial_tilt=float(tilt(initial['attitude'])),predicted_tilt=float(z[scope,4].max()),actual_tilt=r['LP_peak_tilt_deg'],stop=stop,branches=branches,simulated_until=float(z[-1,0]))
 return out,z
def main():
 rows=json.loads((OLD/'upstream/data/p13-20261026-results-v3/cases.json').read_text())['rows'];results=[];traces={};start=time.perf_counter()
 for r in sorted(rows,key=lambda r:r['id']):
  out,z=forecast(r);results.append(out);traces[r['id']]=z;print(out['id'],round(out['prediction'],3),round(out['actual'],3),out['actual_height_status'],out['stop'],flush=True)
 complete=[x for x in results if not x['actual_censored']];positive=[x for x in results if x['actual_height_status']=='FAILURE'];negative=[x for x in results if x['actual_height_status']=='SUCCESS']
 summary=dict(n=len(results),complete_n=len(complete),complete_mae=float(np.mean([abs(x['prediction']-x['actual']) for x in complete])),complete_rmse=float(np.sqrt(np.mean([(x['prediction']-x['actual'])**2 for x in complete]))),height_false_negatives=sum(not x['predicted_failure'] for x in positive),height_positive_n=len(positive),height_false_positives=sum(x['predicted_failure'] for x in negative),height_negative_n=len(negative),domain_exits=sum(x['stop'] is not None for x in results),cpu_wall_s=time.perf_counter()-start)
 (ROOT/'h2_preflight_results.json').write_text(json.dumps(dict(summary=summary,results=results,protocol_sha256=hashlib.sha256((ROOT/'h2_preflight_protocol.json').read_bytes()).hexdigest()),indent=2));np.savez_compressed(ROOT/'h2_preflight_traces.npz',**traces);print('SUMMARY',summary,flush=True)
if __name__=='__main__':main()

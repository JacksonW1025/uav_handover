#!/usr/bin/env python3
"""Prospective empirical-Lyapunov search score; reads only closed SITL evidence.
--run FLIGHT --out NEW_DIR [--classic-event lyapunov_classic_capture_requested]
Acquisition uses G_mean_100_120_160 ONLY. Physical results never feed that score.
"""
import argparse, csv, gzip, hashlib, json, sys
from pathlib import Path
import numpy as np
from pyulog import ULog
ROOT=Path('/home/car/uav_handover');sys.path.insert(0,str(ROOT/'tools'))
import handover_explore.analyze as m
HORIZONS=(.100,.120,.160); WEIGHTS=np.array([1.,1.,.25]); DECAY=.5

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def write(p,x):p.write_text(json.dumps(m.clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def vector(d,k,n=3):return np.column_stack([d[f'{k}[{j}]'] for j in range(n)]).astype(float)
def tilt(q):
 q=q/np.linalg.norm(q,axis=1,keepdims=True)
 return np.degrees(np.arccos(np.clip(1-2*(q[:,1]**2+q[:,2]**2),-1,1)))
def dump_csv(path,cols):
 with gzip.open(path,'wt') as f:
  w=csv.writer(f);w.writerow(cols);w.writerows(zip(*cols.values()))
def first(t,b):return float(t[np.flatnonzero(b)[0]]) if np.any(b) else None
def coverage(t):return dict(n=len(t),max_gap_s=float(np.diff(t).max()) if len(t)>1 else None,median_period_s=float(np.median(np.diff(t))) if len(t)>1 else None)
def score(run,out,classic_event=None):
 out.mkdir(parents=True,exist_ok=False)
 a=m.analyze(run);write(out/'original-analysis.json',a)
 u=ULog(str(run/'flight.ulg'));d={z.name:z.data for z in u.data_list if z.multi_id==0};events=m.lines(run/'events.jsonl');p=d['research_p11'];o=d['research_actuator']
 classic=classic_event is not None
 if not classic:
  b=next(b for b in a['boundaries'] if b.get('direction')=='C→N' and 'owner_boundary' in b)
  start=b['owner_boundary']['timestamp_us'];end=b['subject_end_us'];reason=b['subject_end_reason'];request=b['request_native_lower_us']
 else:
  event=next(e for e in events if e['event']==classic_event);request=m.native_event(event,p)
  nav=m.transitions(d['vehicle_status'],'nav_state','nav_state_timestamp' if 'nav_state_timestamp' in d['vehicle_status'] else 'timestamp')
  start=next(x['timestamp_us'] for x in nav if x['to']==4 and x['timestamp_us']>=request)
  ends=[(m.native_event(e,p),e['event']) for e in events if e['event'] in ['explore_subject_finished','failure','landing_requested']]
  end,reason=min((t,label) for t,label in ends if t is not None and t>start)
  b=None
 pre=m.state(m.snapshot(d,start-1));result=dict(run=str(run),case=run.parent.name,controller='classic' if classic else 'neural',start_native_us=start,end_native_us=end,request_lower_us=request,request_to_start_s=(start-request)/1e6,end_reason=reason,pre_state=pre,pre_snapshot=m.snapshot(d,start-1),observed_duration_s=(end-start)/1e6,ulog_sha256=sha(run/'flight.ulg'),dropouts=len(u.dropouts),script_sha256=sha(Path(__file__)),scales=dict(velocity_m_s=2,tilt_deg=45,angular_rate_rad_s=2),weights=WEIGHTS.tolist(),decay_per_s=DECAY,horizons_s=HORIZONS,formula='V=(||v-vref||/2)^2+(tilt/45)^2+0.25*(||omega||/2)^2; G(H)=max(V(t)-exp(-0.5*(t-t0))*V0)',score_status='NOT_APPLICABLE_CLASSIC' if classic else 'PENDING',note='Empirical Lyapunov-inspired score, not a certificate, not an online pre-switch measurement; no physical peak enters acquisition.')
 for topic,columns in [('vehicle_attitude',['q']),('vehicle_local_position',['x','y','z'])]:
  z=d[topic];ts=z['timestamp'].astype(np.int64);mask=(ts>=start)&(ts<=end);t=(ts[mask]-start)/1e6
  if topic=='vehicle_attitude':
   th=tilt(vector(z,'q',4)[mask]);result['physical']=dict(peak_tilt_deg=float(th.max()),peak_tilt_s=float(t[np.argmax(th)]),first_tilt_gt45_s=first(t,th>45),first_tilt_ge45_s=first(t,th>=45),attitude_coverage=coverage(t))
   result['physical']['tilt_gt45_native_times_s']=t[th>45].tolist();dump_csv(out/'physical-attitude.csv.gz',dict(t_s=t,native_us=ts[mask],tilt_deg=th))
   for h in [1,2]:
    result['physical'][f'peak_tilt_first_{h}s']=float(th[t<=h].max());result['physical'][f'first_{h}s_truncated']=end-start<h*1e6
  else:
   pos=np.column_stack([z[k][mask] for k in ['x','y','z']]);loss=pos[:,2]-pre['position'][2];alt=-pos[:,2];radius=np.linalg.norm(pos[:,:2],axis=1)
   result['physical'].update(altitude_loss_entry_m=float(max(0,loss.max())),min_altitude_m=float(alt.min()),max_altitude_m=float(alt.max()),first_loss_gt1_s=first(t,loss>1),first_radius_ge10_s=first(t,radius>=10),first_altitude_ge8_s=first(t,alt>=8),first_altitude_le02_s=first(t,alt<=.2),position_coverage=coverage(t))
   dump_csv(out/'physical-position.csv.gz',dict(t_s=t,native_us=ts[mask],altitude_loss_entry_m=loss,altitude_m=alt,radius_m=radius))
   for h in [1,2]:result['physical'][f'loss_first_{h}s']=float(max(0,loss[t<=h].max()))
 z=d.get('research_angular_velocity',d['vehicle_angular_velocity']);ts=z['timestamp'].astype(np.int64);mask=(ts>=start)&(ts<=end);t=(ts[mask]-start)/1e6;rate=np.abs(vector(z,'xyz')[mask]).max(axis=1)
 result['physical'].update(max_abs_rate_rad_s=float(rate.max()),first_rate_ge8_s=first(t,rate>=8),rate_coverage=coverage(t))
 ph=result['physical'];result['physical_task']='FAILURE' if ph['first_tilt_gt45_s'] is not None or ph['first_loss_gt1_s'] is not None else ('OBSERVED_PASS' if u.dropouts==[] else 'UNKNOWN')
 result['native_windows']={str(h):m.enhanced_window(d,start,min(end,start+int(h*1e6))) for h in [1,2]};result['native_windows']['subject']=m.enhanced_window(d,start,end)
 if b:
  result['original_frozen']=b['frozen_primary_outcome'];result['original_task']=b['task_outcome'];result['original_evidence_missing']=b['missing']
 if not classic:
  pt=p['timestamp'].astype(np.int64);oi=np.searchsorted(o['actuator_timestamp'],pt,side='right')-1
  keep=(pt>=start)&(pt<=end)&(p['active']==1)&(p['native_step']==1)&(oi>=0)&(o['owner'][np.maximum(0,oi)]==1)
  t=(pt[keep]-start)/1e6;ev=np.linalg.norm(vector(p,'velocity')[keep]-vector(p,'network_target_velocity')[keep],axis=1);theta=tilt(vector(p,'attitude',4)[keep]);omega=np.linalg.norm(vector(p,'angular_velocity')[keep],axis=1)
  comp=np.column_stack([(ev/2)**2,(theta/45)**2,(omega/2)**2]);V=comp@WEIGHTS;margin=V-V[0]*np.exp(-DECAY*(t-t[0]))
  finite=np.isfinite(comp).all();complete=(t[0]<=.008001 and t[-1]>=.16-.008001 and max(np.diff(t[t<=.160001]))<=.020001)
  g={str(h):float(max(margin[t<=h+1e-9])) for h in HORIZONS}
  result.update(score_status='VALID' if finite and complete else 'INCOMPLETE',V0=float(V[0]),entry_ev_m_s=float(ev[0]),entry_tilt_deg=float(theta[0]),entry_omega_rad_s=float(omega[0]),first_score_sample_s=float(t[0]),V_coverage=coverage(t),G_by_horizon=g,G_mean_100_120_160=float(np.mean(list(g.values()))) if finite and complete else None,G_median_100_120_160=float(np.median(list(g.values()))) if finite and complete else None,first_G_gt005_s=first(t,margin>.05))
  result['simple_scores']={str(h):dict(ev=float(ev[t<=h+1e-9][-1]),tilt=float(theta[t<=h+1e-9][-1]),omega=float(omega[t<=h+1e-9][-1]),sample_s=float(t[t<=h+1e-9][-1])) for h in HORIZONS}
  dump_csv(out/'V-native.csv.gz',dict(t_s=t,native_us=pt[keep],ev_m_s=ev,tilt_deg=theta,omega_rad_s=omega,V=V,growth_margin=margin,velocity_component=comp[:,0],tilt_component=comp[:,1],angular_component=comp[:,2]*.25))
 write(out/'score.json',result);return result
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--classic-event');args=ap.parse_args()
 r=score(args.run,args.out,args.classic_event);print(json.dumps({k:r.get(k) for k in ['case','score_status','G_mean_100_120_160','physical_task','physical']},ensure_ascii=False))

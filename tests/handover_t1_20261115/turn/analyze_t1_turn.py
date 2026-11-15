import os
import pathlib,json,sys,hashlib,csv
import numpy as np
from pyulog import ULog
ROOT=pathlib.Path(os.environ['HANDOVER_RESEARCH_ROOT']);BASE=ROOT/'data/handover-t1-turn-20261115-v1';sys.path.insert(0,str(ROOT/'tools'))
from output_chain import read_trace
from analyze import clean
from handover_explore.analyze import enhanced_window,joint_recovery,frozen,native_event
OUT=BASE/'analysis-v1';OUT.mkdir(exist_ok=False)
def vec(d,stem,n,i):return [float(d[f'{stem}[{j}]'][i]) for j in range(n)]
def row(d,i):return {k:clean(v[i]) for k,v in d.items()}
def last(d,t):return int(np.searchsorted(d['timestamp'],t,side='right')-1)
results={};curves={}
for arm in ['C','N']:
 f=BASE/arm/'flight';u=ULog(str(f/'flight.ulg'));d={x.name:x.data for x in u.data_list if x.multi_id==0};es=[json.loads(x) for x in (f/'events.jsonl').read_text().splitlines()];tr=next(x for x in es if x['event']=='t1_margin_trigger');t0=tr['end_bound_px4_us'];p=d['research_p11'];end=min(native_event(x,p) for x in es if x['event'] in ['explore_subject_finished','failure'] and native_event(x,p)>t0);l=d['vehicle_local_position'];a=d['vehicle_attitude'];o=d['research_actuator'];i=last(l,t0);ai=last(a,t0);w=d['vehicle_angular_velocity'];wi=last(w,t0)
 startz=float(l['z'][i]);lm=(l['timestamp']>=t0)&(l['timestamp']<=end);am=(a['timestamp']>=t0)&(a['timestamp']<=end);tilt=np.degrees(np.arccos(np.clip(1-2*(a['q[1]']**2+a['q[2]']**2),-1,1)));descent=l['z'][lm]-startz
 r=dict(arm=arm,trigger_native_us=t0,end_native_us=end,ulog_sha256=hashlib.sha256((f/'flight.ulg').read_bytes()).hexdigest(),ulog_dropouts=len(u.dropouts),trigger_state=dict(position=[float(l[x][i]) for x in ['x','y','z']],velocity=[float(l[x][i]) for x in ['vx','vy','vz']],q=vec(a,'q',4,ai),angular_velocity=vec(w,'xyz',3,wi),sample_age_us=int(t0-l['timestamp'][i])),metrics=enhanced_window(d,t0,end),attitude_budget={str(m):dict(crossed=bool((tilt[am]>m).any()),first_crossing_native_us=int(a['timestamp'][am][np.flatnonzero(tilt[am]>m)[0]]) if (tilt[am]>m).any() else None) for m in [35.,45.]},max_descent_from_trigger_m=float(descent.max()),normal_landing=any(x.get('event')=='ready' and x.get('condition')=='landing' for x in es),normal_disarm=any(x.get('event')=='ready' and x.get('condition')=='disarmed' for x in es),process_exits=[x for x in es if x['event']=='process_stopped'])
 sends=[json.loads(x) for x in (f/'explore-setpoints.jsonl').read_text().splitlines()];r['max_send_gap_ms']=float(np.diff([x['before_ns'] for x in sends]).max()/1e6)
 pm=(p['timestamp']>=t0)&(p['timestamp']<=end);r['p11']=dict(samples=int(pm.sum()),stale=int(p['stale'][pm].sum()),invalid_delta=int(np.maximum(np.diff(p['invalid_total'][pm].astype(np.int64)),0).sum()))
 m=d['research_memory'];mt=m['timestamp'];hist=(mt>=t0-1000000)&(mt<t0)&(m['native_step']==1);r['history_pre_1s']=dict(native_steps=int(hist.sum()),teacher_forced=int(m['teacher_forced'][hist].sum()),entry_modes=np.unique(m['entry_mode'][hist]).tolist())
 om=(o['actuator_timestamp']>=t0)&(o['actuator_timestamp']<=end);r['owner_values']=np.unique(o['owner'][om]).tolist()
 if arm=='N':
  oi=int(np.flatnonzero(om&(o['owner']==1))[0]);tp=int(o['actuator_timestamp'][oi]);r['first_neural_publication_us']=tp;r['first_command']=vec(o,'control',4,oi);r['last_classic_command']=vec(o,'control',4,oi-1)
  ix=np.flatnonzero((p['timestamp']>=t0)&(p['activation']==1));act=int(ix[0]);r['activation_p11']=row(p,act);r['first_publication_p11']=row(p,last(p,tp));r['first_native_p11']=row(p,int(np.flatnonzero((p['timestamp']>=int(p['timestamp'][act]))&(p['native_step']==1))[0]))
  entryix=np.flatnonzero((mt>=t0)&(mt<=tp));r['entry_memory_rows']=[row(m,int(j)) for j in entryix]
  vi=int(np.flatnonzero((p['timestamp']>=int(p['timestamp'][act]))&(p['external_valid']==1))[0]);r['first_valid_read_p11']=row(p,vi)
  r['motors']={}
  for j in range(4):
   motor_id,z,tail=read_trace(f/'gz-motor'/f'motor-{j}.bin');print('trace_fields',z.dtype.names) if arm=='N' and j==0 else None
   ss='applied_sample_us' if 'applied_sample_us' in z.dtype.names else 'sample_us'
   inds=np.flatnonzero((z['sim_us']>=tp)&(z[ss]>=tp));ix=int(inds[0]);r['motors'][str(j)]=dict(tail_bytes=tail,first_applied={n:clean(z[n][ix]) for n in z.dtype.names},previous={n:clean(z[n][ix-1]) for n in z.dtype.names})
  r['joint_recovery']=joint_recovery(d,tp,end,1);r['frozen']=frozen(enhanced_window(d,tp,end),r['joint_recovery'])
 else:r['joint_recovery']={'status':'NOT_APPLICABLE_NO_HANDOVER'}
 curves[arm]=dict(t=(l['timestamp'][lm]-t0)/1e6,descent=descent,vz=l['vz'][lm],ta=(a['timestamp'][am]-t0)/1e6,tilt=tilt[am])
 results[arm]=clean(r)
 with (OUT/(arm+'-curve.csv')).open('w') as fo:
  cw=csv.writer(fo);cw.writerow(['time_s','descent_m','vz_m_s']);cw.writerows(zip(curves[arm]['t'],descent,l['vz'][lm]))
(OUT/'measurements.json').write_text(json.dumps(clean(results),indent=2,ensure_ascii=False)+'\n')
c,n=results['C']['trigger_state'],results['N']['trigger_state'];q=np.array(c['q']);q2=np.array(n['q']);diff=dict(position_m=float(np.linalg.norm(np.array(c['position'])-n['position'])),velocity_m_s=float(np.linalg.norm(np.array(c['velocity'])-n['velocity'])),attitude_deg=float(np.degrees(2*np.arccos(np.clip(abs(np.dot(q,q2)),-1,1)))),angular_rate_rad_s=float(np.linalg.norm(np.array(c['angular_velocity'])-n['angular_velocity'])))
(OUT/'matching.json').write_text(json.dumps(diff,indent=2)+'\n')
import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
fig,ax=plt.subplots(3,1,figsize=(9,8),sharex=True)
for arm,z in curves.items():ax[0].plot(z['t'],z['descent'],label=arm);ax[1].plot(z['t'],z['vz'],label=arm);ax[2].plot(z['ta'],z['tilt'],label=arm)
for h in [35.,45.]:ax[2].axhline(h,ls='--',label=f'attitude budget {h}deg')
for a,y in zip(ax,['Descent from trigger (m)','NED vertical velocity (m/s)','Tilt (deg)']):a.set_ylabel(y);a.grid(alpha=.3);a.legend()
ax[-1].set_xlabel('PX4 native time from trigger (s)');fig.suptitle('T1 scaled tight turn: measured flights, test attitude budgets');fig.tight_layout();fig.savefig(OUT/'margin-comparison.png',dpi=160)
print(json.dumps({a:{k:r[k] for k in ['max_descent_from_trigger_m','attitude_budget','normal_landing','normal_disarm','p11','history_pre_1s']} for a,r in results.items()},indent=2));print('MATCH',diff)

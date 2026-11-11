"""Offline incremental mutation audit. Only PHYSICAL_END attempts; never writes raw runs."""
import sys,json,csv,argparse,traceback,hashlib
from pathlib import Path
import numpy as np
ROOT=Path('/home/car/uav_handover'); OUT=Path(__file__).resolve().parents[1]; BATCH=ROOT/'data/handover-mutation-20261111'
sys.path.insert(0,str(Path(__file__).parent))
import metrics_base as m
from legacy_supplement import supplement
from pyulog import ULog

def write(p,v):p.write_text(json.dumps(m.clean(v),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def fmt(x):
 if x is None:return '缺失'
 if isinstance(x,(float,np.floating)):return f'{x:.4f}'
 if isinstance(x,(list,tuple)):return '['+', '.join(fmt(v) for v in x)+']'
 return str(x)
def extra(r,flight):
 u=ULog(str(flight/'flight.ulg'));d={v.name:v.data for v in u.data_list if v.multi_id==0};r['ulog_final_timestamp_us']=int(u.last_timestamp)
 r['analyzer_revision']='mutation-v1';r['log_scope_note']='Only finalized logs after PHYSICAL_END. Subject peak is observed, not an unconstrained eventual peak.'
 for b in r.get('boundaries',[]):
  if 'owner_boundary' not in b:continue
  t=b['owner_boundary']['timestamp_us'];end=b['subject_end_us'];lower=b['request_native_lower_us']
  for s in [.25,.5,1,2]:
   w=m.enhanced_window(d,t,min(t+int(s*1e6),end))
   if w:w['truncated_by_next_boundary_or_subject_end']=end<t+s*1e6
   b['windows'][f'first_{s}s']=w
  q=d.get('research_target',{});ts=np.asarray(q.get('timestamp',[]));kind=np.asarray(q.get('kind',[]));act=np.asarray(q.get('activation',[]),bool)
  candidates=np.flatnonzero((ts>=lower)&(ts<=t+100000)&(kind==1)&act) if len(act) else []
  ca={'status':'UNKNOWN','candidate_count':len(candidates),'rows':[m.row(q,int(i)) for i in candidates],'prior_timeout_capture_rows':[m.row(q,int(i)) for i in np.flatnonzero((ts>=lower-500000)&(ts<lower)&(kind==1))]}
  if len(candidates)==1:
   row=ca['rows'][0];v=np.array(m.vector(row,'velocity'));vv=np.array(m.vector(row,'vehicle_velocity'));mode=int(row['mode']);expected=r['explore'].get('state_parameters',{}).get('MC_RAPTOR_RTGT')
   residual=float(abs(v[:2]-(vv[:2] if mode in (1,2) else 0)).max());ca.update(captured_vehicle_velocity_m_s=vv.tolist(),target_velocity_m_s=v.tolist(),mode=mode,expected_mode=expected,horizontal_match_residual_m_s=residual,status='VERIFIED' if mode==expected and residual<=1e-6 and v[2]==0 else 'NOT_VERIFIED')
  b['activation_capture_audit']=ca
  at=d.get('vehicle_attitude',{});tt=np.asarray(at.get('timestamp',[]));ix=np.flatnonzero((tt>=t)&(tt<=end))
  if len(ix):
   tilt=np.degrees(np.arccos(np.clip(1-2*(at['q[1]'][ix]**2+at['q[2]'][ix]**2),-1,1)));j=int(np.argmax(tilt));b['observed_peak']={'tilt_deg':float(tilt[j]),'after_owner_s':float((tt[ix[j]]-t)/1e6),'native_us':int(tt[ix[j]]),'limited_by_subject_end':True}
  b['log_truncation']={'subject_end_reason':b['subject_end_reason'],'last_ulog_us':int(u.last_timestamp),'subject_to_ulog_end_s':(int(u.last_timestamp)-end)/1e6,'no_observed_subject_closure':b['subject_end_reason'].startswith('ULog')}
 return m.clean(r)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--plots',action='store_true');args=ap.parse_args()
 ends={e['attempt_id']:e for e in m.lines(BATCH/'attempts.jsonl') if e.get('event')=='PHYSICAL_END'}
 for name,physical in ends.items():
  run=BATCH/name;flight=run/'flight';dest=OUT/'runs'/name;dest.mkdir(exist_ok=True)
  if (dest/'analysis.json').exists():continue
  # Interrupted 001 is an unevaluated prefix plus independent recovery, never a successful reproduction.
  if physical.get('execution_status')=='INFRASTRUCTURE_INTERRUPTED':
   r={'attempt_id':name,'source_run':str(flight),'physical_end':physical,'status':'INCOMPLETE','frozen_primary_status':'UNKNOWN','task_status':'UNKNOWN','boundaries':[],'explore':m.load(run/'config.json',{}).get('explore',{}),'interruption_recovery':m.load(ROOT/physical['recovery_record'],{}),'evidence_completion':{'complete':False,'missing':['Original runner interrupted before subject; no subject handover. Recovery is independent.']}}
   write(dest/'analysis.json',r);continue
  if not (flight/'metadata.json').exists() or not (run/'result.json').exists():continue
  try:
   r=extra(supplement(m.analyze(flight),flight),flight);r['attempt_id']=name;r['attempt']=m.load(run/'result.json');r['physical_end']=physical
   if r.get('boundaries'):
    m.trajectory_export(r,dest/'trajectory.json')
    if args.plots:m.plot(r,dest/'timeseries.png')
   write(dest/'analysis.json',r)
   print(name,r.get('frozen_primary_status'),r.get('task_status'),flush=True)
  except Exception as ex:
   write(dest/'analysis-error.json',{'error':repr(ex),'traceback':traceback.format_exc()});print('ERROR',name,repr(ex),flush=True)
 results=[m.load(p) for p in sorted((OUT/'runs').glob('*/analysis.json'))]
 from realized_outcomes import decorate
 results=decorate(results);write(OUT/'summary.json',results)
 rows=[];report=['# 069种子变异实验：离线独立分析','', '仅纳入PHYSICAL_END后的最终证据。基础设施中断不算安全样本；保护退出后未观测到落地不写成已落地。冻结主判据与任务判据保留并列，不调阈值。所有峰值是保护干预前的已观察峰值，不能推断无保护峰值。','', '同seed与同名义参考不保证同入口状态；RTGT、外部freeze/brake的比较不是严格因果配对。一个或少量seed、适应性选例不能推导总体事故率或安全界限。先比较实际速度、姿态、角速度、目标生效和物理电机接管。','']
 for r in results:
  name=r['attempt_id'];bs=[b for b in r.get('boundaries',[]) if 'owner_boundary' in b];comp=r.get('completion',{})
  report += [f'## {name}',f"证据={r['status']}；冻结={r.get('frozen_primary_status')}；任务={r.get('task_status')}；主体实际交接={len(bs)}；正常落地disarm={comp.get('normal_landing_disarm','未在原实验确认')}。"]
  report += [f"场景实现={r.get('scenario_realization')}；已实现物理冻结/任务={r.get('observed_physical_frozen_status')}/{r.get('observed_physical_task_status')}。原始证据限定判据保持不变。"]
  if r.get('interruption_recovery'):report += ['原实验在主体交接前中断；独立恢复确认落地和disarm，但不把恢复拼成原实验成功。']
  if not bs:rows.append({'attempt':name,'boundary':None,'frozen':r.get('frozen_primary_status','UNKNOWN'),'task':r.get('task_status','UNKNOWN'),'subject_end_reason':'No actual subject handover; interrupted prefix','scenario_realization':'NO_SUBJECT_HANDOVER','observed_physical_frozen':'UNKNOWN','observed_physical_task':'UNKNOWN'})
  for b in bs:
   pre=b.get('pre_takeover_state') or {};w=b['windows'];full=w['subject'] or {};ca=b.get('activation_capture_audit',{});track=b.get('reference_tracking',{})
   row={'attempt':name,'boundary':b['number'],'direction':b['direction'],'owner_us':b['owner_boundary']['timestamp_us'],'observed_subject_s':full.get('requested_duration_s'),'pre_position_ned_m':json.dumps(pre.get('position')),'pre_velocity_ned_m_s':json.dumps(pre.get('velocity')),'pre_angular_rate_rad_s':json.dumps(pre.get('angular_rate')),'frozen':b['frozen_primary_outcome']['status'],'task':b['task_outcome']['status'],'observed_peak_tilt_deg':full.get('max_tilt_deg'),'peak_after_owner_s':b.get('observed_peak',{}).get('after_owner_s'),'altitude_loss_entry_m':full.get('max_altitude_loss_m'),'below_active_reference_m':track.get('max_below_active_reference_m'),'max_angular_rate_component_rad_s':full.get('max_angular_rate_component_rad_s'),'saturation_continuous_s':full.get('motor_saturation_continuous_s'),'activation_status':ca.get('status'),'captured_vehicle_velocity_m_s':json.dumps(ca.get('captured_vehicle_velocity_m_s')),'native_target_velocity_m_s':json.dumps(ca.get('target_velocity_m_s')),'four_motors_observed':b.get('four_motors_observed'),'landing_observed':comp.get('landed_observed'),'disarm_observed':comp.get('disarmed_observed'),'subject_end_reason':b['subject_end_reason']}
   row.update(scenario_realization=b.get('scenario_realization'),observed_physical_frozen=b.get('observed_physical_frozen',{}).get('status'),observed_physical_task=b.get('observed_physical_task'),candidate_record_sha256=r.get('candidate_record_sha256'))
   for s in [.25,.5,1,2]:
    ww=w.get(f'first_{s}s') or {};row[f'tilt_first_{s}s']=ww.get('max_tilt_deg');row[f'observed_first_{s}s']=ww.get('requested_duration_s');row[f'truncated_first_{s}s']=ww.get('truncated_by_next_boundary_or_subject_end')
   rows.append(row)
   report += [f"- {b['direction']} owner={row['owner_us']}µs；四电机物理应用={row['four_motors_observed']}。入口位置={fmt(pre.get('position'))}m，速度={fmt(pre.get('velocity'))}m/s，角速度={fmt(pre.get('angular_rate'))}rad/s。",'- 首0.25/0.5/1/2秒峰倾角：'+ '/'.join(fmt(row[f'tilt_first_{s}s']) for s in [.25,.5,1,2])+'°；对应实际观察时长：'+'/'.join(fmt(row[f'observed_first_{s}s']) for s in [.25,.5,1,2])+'s。',f"- 已观测主体峰值={fmt(row['observed_peak_tilt_deg'])}°，发生在owner后{fmt(row['peak_after_owner_s'])}s。入口相对失高={fmt(row['altitude_loss_entry_m'])}m；低于实际活动目标最大={fmt(row['below_active_reference_m'])}m。最大单轴角速率={fmt(row['max_angular_rate_component_rad_s'])}rad/s；电机连续饱和={fmt(row['saturation_continuous_s'])}s。",f"- activation={ca.get('status')}；捕获机体速度={fmt(ca.get('captured_vehicle_velocity_m_s'))}；原生目标速度={fmt(ca.get('target_velocity_m_s'))}m/s。外部参考是否真正消费另见JSON的reference_evidence与first_neural_consumed_state。",f"- 冻结={row['frozen']} {b['frozen_primary_outcome'].get('reasons')}；任务={row['task']}；主体结束原因={row['subject_end_reason']}。"]
  report += ['证据缺口：'+('; '.join(r.get('evidence_completion',{}).get('missing',[])) or '无已识别缺口'),'']
 with (OUT/'cases.csv').open('w') as f:
  if rows:c=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)));c.writeheader();c.writerows(rows)
 (OUT/'report.zh.md').write_text('\n'.join(report)+'\n')
 comparison=[]
 for glob in ['069*','070*']:
  for p in (ROOT/'data/handover-100-20261110-analysis-v1/runs').glob(glob+'/analysis.json'):
   old=m.load(p);comparison.append({'source_analysis':str(p),'comparison_scope':'historical descriptive comparison, not causal pair or current candidate equivalence','attempt':old.get('attempt_id'),'boundaries':old.get('boundaries'),'frozen':old.get('frozen_primary_status'),'task':old.get('task_status')})
 write(OUT/'historical-069-070.json',comparison)
 plotrows=[r for r in rows if r.get('boundary') is not None]
 if args.plots and plotrows:
  rows_for_export=rows;rows=plotrows
  import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
  fig,ax=plt.subplots(figsize=(12,5));labels=[r['attempt'][:3] for r in rows];x=np.arange(len(rows))
  for s in [.25,.5,1,2]:ax.plot(x,[r[f'tilt_first_{s}s'] for r in rows],marker='o',label=f'first {s}s (possibly truncated)')
  ax.plot(x,[r['observed_peak_tilt_deg'] for r in rows],marker='s',label='observed subject peak');ax.axhline(45,color='red',ls='--',label='45 deg safety line');ax.set_xticks(x,labels,rotation=35,ha='right');ax.set_ylabel('Tilt (deg)');ax.legend(fontsize=7);fig.tight_layout();fig.savefig(OUT/'transient-comparison.png',dpi=150);plt.close(fig)
 from audit_end_windows import run as audit_end_windows
 audit_end_windows(results)
 from audit_mechanisms import run as audit_mechanisms
 audit_mechanisms(results)
 from audit_directions import run as audit_directions
 audit_directions(results)
 from audit_capture_stage import run as audit_capture_stage
 audit_capture_stage(results)
 print(json.dumps({'analyzed_attempts':len(results),'actual_boundaries':sum(len([b for b in r.get('boundaries',[]) if 'owner_boundary' in b]) for r in results),'physical_end_records':len(ends),'output':str(OUT)},ensure_ascii=False),flush=True)
if __name__=='__main__':main()

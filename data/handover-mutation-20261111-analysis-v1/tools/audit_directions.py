"""Target-yaw FLU direction evidence and a full-rate-vs-runner sampling audit."""
import json
from pathlib import Path
import numpy as np
from pyulog import ULog
import metrics_base as m
OUT=Path(__file__).resolve().parents[1]
def write(p,v):p.write_text(json.dumps(m.clean(v),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def run(results):
 rr=[];traces=[]
 for r in results:
  if not r['attempt_id'].startswith(('009_','010_','011_','012_','018_','019_','020_','021_')):continue
  b=r['boundaries'][0];first=b['first_neural_consumed_state'];yaw=first['target_yaw'];c=np.cos(yaw);s=np.sin(yaw);v=np.array(m.vector(first,'velocity'));tv=np.array(m.vector(first,'network_target_velocity'));e=v-tv;flu=np.array([c*e[0]+s*e[1],s*e[0]-c*e[1],-e[2]])
  f=Path(r['source_run']);d={x.name:x.data for x in ULog(str(f/'flight.ulg'),message_name_filter_list=['vehicle_attitude','research_p11']).data_list if x.multi_id==0};a=d['vehicle_attitude'];t=a['timestamp'].astype(np.int64);q=np.column_stack([a[f'q[{j}]'] for j in range(4)]);tilt=np.degrees(np.arccos(np.clip(1-2*(q[:,1]**2+q[:,2]**2),-1,1)));anchor=b['owner_boundary']['timestamp_us'];end=b['subject_end_us'];mask=(t>=anchor)&(t<=end);bad=np.flatnonzero(mask&(tilt>45));blocks=np.split(bad,np.flatnonzero(np.diff(bad)>1)+1) if len(bad) else []
  telemetry=[]
  # Match actual quaternion payload rather than treating DDS rewritten timestamp as native.
  for z in m.lines(f/'telemetry.jsonl'):
   bracket=m.host_bracket(d['research_p11'],z['monotonic_ns']);lo=(bracket or {}).get('native_lower_us');hi=(bracket or {}).get('native_upper_us')
   if lo is None or hi is None or hi<anchor-100000 or lo>min(end,anchor+1500000):continue
   near=np.flatnonzero((t>=lo-100000)&(t<=hi));res=np.max(np.abs(q[near]-np.array(z['q'])),axis=1);j=np.flatnonzero(res<=1e-7)
   telemetry.append({'sample':z,'host_to_native_bracket':bracket,'quaternion_match_native_us':[int(t[near[k]]) for k in j],'matched_attitude_age_bracket_us':[lo-int(t[near[j[-1]]]),hi-int(t[near[j[-1]]])] if len(j) else None,'matching_tolerance':1e-7})
  w=b['windows']['subject'];row={'attempt':r['attempt_id'],'execution_status':r.get('attempt',{}).get('execution_status'),'owner_us':anchor,'subject_end_us':end,'frozen':b['frozen_primary_outcome'],'task':b['task_outcome'],'target_yaw_rad':yaw,'target_yaw_deg':float(np.degrees(yaw)),'entry_velocity_ned_m_s':v.tolist(),'first_consumed_target_velocity_ned_m_s':tv.tolist(),'initial_velocity_error_target_flu_m_s':flu.tolist(),'clipping':b['reference_evidence']['input_clipping'],'peak':b['observed_peak'],'altitude_loss_m':w['max_altitude_loss_m'],'above45_intervals':[{'first_native_us':int(t[z[0]]),'last_native_us':int(t[z[-1]]),'first_after_owner_s':float((t[z[0]]-anchor)/1e6),'last_after_owner_s':float((t[z[-1]]-anchor)/1e6),'samples':len(z),'span_s':float((t[z[-1]]-t[z[0]])/1e6)} for z in blocks if len(z)],'runner_telemetry_near_peak':telemetry,'full_telemetry_max_tilt_deg':max(v['tilt_deg'] for v in m.lines(f/'telemetry.jsonl')),'normal_landing_disarm':r['completion']['normal_landing_disarm'],'scope':'Full-rate offline criterion is distinct from approximately 10Hz runner safety observation. Quaternion payload matching estimates stale attitude used by runner; host brackets do not alone give attitude timestamp.'};rr.append(row);traces.append((row,t,tilt))
 write(OUT/'direction-audit.json',rr)
 lines=['# 方向、边界变异与在线保护采样差异','','目标坐标按真实P11 target_yaw旋转，使用FLU约定：[cos(yaw)·eN+sin(yaw)·eE, sin(yaw)·eN−cos(yaw)·eE, −eD]。不能把世界X/Y直接当策略前/左轴。所有比较为实际不同入口状态的单次描述，不是严格因果配对。','']
 for r in rr:
  lines += [f"## {r['attempt']}",f"执行={r['execution_status']}，冻结={r['frozen']['status']}，任务={r['task']['status']}；正常落地={r['normal_landing_disarm']}。",f"实际目标yaw={r['target_yaw_deg']:.3f}°；入口NED速度={r['entry_velocity_ned_m_s']}；初始目标FLU速度误差={r['initial_velocity_error_target_flu_m_s']}。",f"主体峰={r['peak']['tilt_deg']:.3f}°@{r['peak']['after_owner_s']:.3f}s；失高={r['altitude_loss_m']:.3f}m；越45°区间={r['above45_intervals']}。",f"速度裁剪分量计数={r['clipping']['velocity_clipped_by_component']}；输入重建最大残差={r['clipping']['reconstruction_max_abs_residual']:.9g}；全telemetry最大倾角={r['full_telemetry_max_tilt_deg']:.3f}°。",'']
 for r in rr:
  if r['execution_status']=='PASS' and r['frozen']['status']=='FAILURE':
   lines += [f"执行完成但离线失败：{r['attempt']}，主体峰{r['peak']['tilt_deg']:.6f}°，越线区间{r['above45_intervals']}；telemetry峰{r['full_telemetry_max_tilt_deg']:.6f}°。",'']
 lines += ['## 011不可当方向安全例','011正常完成并落地，但原生姿态23个4ms样本超过45°，owner后0.316–0.404s，峰47.000°@0.360s，因此冻结和任务均失败。runner安全检查实际在tools/run_experiment.py约307–318行的>0.1s采样分支。日志中最高telemetry仅44.642°。相邻telemetry读取的旧姿态与有限检查频率一起漏过短峰；具体四元数匹配记录见JSON。不能把执行PASS代替离线安全判据，也不能把已恢复解释成没有越界。','','## 第3轮补点选择（已执行）','第3轮已执行新seed y负2.0、1.7局部补点、1.6/1.8新seed，以及经修正的真实active-timeout两例。未提高保护阈值。']
 (OUT/'direction-audit.zh.md').write_text('\n'.join(lines)+'\n')
 if rr:
  import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
  fig,axes=plt.subplots(2,1,figsize=(11,8),constrained_layout=True)
  for r,t,tilt in traces:
   ix=(t>=r['owner_us'])&(t<=min(r['subject_end_us'],r['owner_us']+1500000));axes[0].plot((t[ix]-r['owner_us'])/1e6,tilt[ix],label=r['attempt'])
   if r['attempt'].startswith('011'):
    axes[1].plot((t[ix]-r['owner_us'])/1e6,tilt[ix],label='native full-rate tilt')
    tel=[v for v in r['runner_telemetry_near_peak'] if len(v['quaternion_match_native_us'])==1];axes[1].scatter([(v['quaternion_match_native_us'][0]-r['owner_us'])/1e6 for v in tel],[v['sample']['tilt_deg'] for v in tel],label='runner telemetry: matched attitude source time',color='red',s=28)
    axes[1].scatter([((v['host_to_native_bracket']['native_lower_us']+v['host_to_native_bracket']['native_upper_us'])/2-r['owner_us'])/1e6 for v in tel],[v['sample']['tilt_deg'] for v in tel],label='runner telemetry: host sampling native bracket midpoint',color='orange',marker='x',s=36)
  for ax in axes:ax.axhline(45,color='black',ls='--');ax.set_ylabel('Tilt (deg)');ax.set_xlabel('Seconds after actual N owner');ax.grid(alpha=.2);ax.legend(fontsize=7);ax.set_xlim(0,1.2)
  axes[0].set_title('Direction / speed variants: subject only; abort-truncated traces');axes[1].set_title('011: online execution PASS, full-rate safety FAILURE');fig.savefig(OUT/'direction-and-sampling.png',dpi=160);plt.close(fig)
 return rr
if __name__=='__main__':run(m.load(OUT/'summary.json',[]))

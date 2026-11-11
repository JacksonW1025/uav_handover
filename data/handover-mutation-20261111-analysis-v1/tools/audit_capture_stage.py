"""Separate realized physical criteria from an unrealized fresh-to-timeout design."""
from pathlib import Path
import json
import numpy as np
from pyulog import ULog
import metrics_base as m
OUT=Path(__file__).resolve().parents[1]
def run(results):
 out=[]
 for r in results:
  if r.get('explore',{}).get('reference_kind')!='fresh_at_request_then_natural_timeout' and r.get('explore',{}).get('active_timeout_after_s') is None:continue
  f=Path(r['source_run']);d={x.name:x.data for x in ULog(str(f/'flight.ulg'),message_name_filter_list=['research_p11','research_target']).data_list if x.multi_id==0};p=d['research_p11'];t=p['timestamp'];target=d['research_target'];tt=target['timestamp'];b=r['boundaries'][0];start=b['owner_boundary']['timestamp_us'];end=b['subject_end_us'];lo=b['request_native_lower_us'];active=np.asarray(p['active'],bool);first=np.flatnonzero((t>=lo)&active)[0];caps=np.flatnonzero((tt>=lo)&(tt<=end)&(target['kind']==1));pre=int(first)-1;physical_frozen=m.frozen(b['windows']['subject'],b['frozen_joint_recovery'],r['completion']['safety_protection_triggered']);post_timeout=[int(i) for i in caps if not target['activation'][i] and tt[i]>=t[first]]
  row={'attempt':r['attempt_id'],'declared_reference_kind':r['explore']['reference_kind'],'declared_quiet_s':r['explore'].get('native_quiet_before_request_s'),'capture_rows':[m.row(target,int(i)) for i in caps],'first_active_row':m.row(p,int(first)),'last_inactive_row':m.row(p,pre),'actual_active_timeout_capture_count':len(post_timeout),'observed_physical_frozen':physical_frozen,'observed_physical_task':b['windows']['subject']['local_task_envelope'],'requested_scenario_status':r.get('scenario_realization','NOT_REALIZED' if not post_timeout else 'OBSERVED_ACTIVE_TIMEOUT'),'sequence_evidence':b.get('scenario_sequence_evidence'),'candidate_record_sha256':r.get('candidate_record_sha256'),'active_timeout_after_s':r['explore'].get('active_timeout_after_s'),'original_evidence_qualified_frozen_status':r['frozen_primary_status'],'original_evidence_qualified_task_status':r['task_status'],'normal_landing_disarm':r['completion']['normal_landing_disarm'],'peak':b['observed_peak'],'note':'No change to original evidence-qualified records. Physical outcomes apply only to the actually realized trajectory; verify the entire fresh-read then nonactivation-capture sequence before attributing active-timeout handling.'};out.append(row)
 (OUT/'capture-stage-audit.json').write_text(json.dumps(m.clean(out),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 lines=['# fresh→timeout计划与实际activation捕获：分开判定','','015–017没有实现计划中的在N已active后外部目标超时捕获。原始证据限定汇总保持不变；这里另列已实现物理轨迹的冻结/任务判据，禁止把实际activation通过解释为active-timeout通过。','']
 for r in out:
  lines += [f"## {r['attempt']}",f"声明接管前静默={str(r['declared_quiet_s'])+'s' if r['declared_quiet_s'] is not None else '未使用接管前静默'}；实际active-timeout捕获={r['actual_active_timeout_capture_count']}；场景={r['requested_scenario_status']}。",f"已实现物理冻结={r['observed_physical_frozen']['status']}；已实现物理任务={r['observed_physical_task']}；原始证据限定冻结/任务={r['original_evidence_qualified_frozen_status']}/{r['original_evidence_qualified_task_status']}；落地={r['normal_landing_disarm']}。",f"主体峰={r['peak']['tilt_deg']:.3f}°@{r['peak']['after_owner_s']:.3f}s。"]
  for c in r['capture_rows']:lines += [f"捕获native={c['timestamp']}µs，activation={c['activation']}，模式={c['mode']}，机体水平速度={[c['vehicle_velocity[0]'],c['vehicle_velocity[1]']]}，目标水平速度={[c['velocity[0]'],c['velocity[1]']]}。"]
  pre=r['last_inactive_row'];first=r['first_active_row'];lines += [f"最后inactive：timestamp={pre['timestamp']}，last_valid_read_us={pre['last_valid_read_us']}，stale={pre['stale']}。首个active：timestamp={first['timestamp']}，last_valid_read_us={first['last_valid_read_us']}，stale={first['stale']}。",'']
 lines += ['## 第2轮设计偏差与第3轮修正','当前tools/handover_100/runner.py:114–138在handover_reference=native时先关流，再请求N；quiet=0仅去掉等待，不让外部流跨越activation继续有效。015–017的原生日志直接证明该流程走activation。单调增加进入前quiet到0.10或0.18秒不能构成可靠active-timeout对照。因此第3轮没有继续该名义静默补点。第3轮另以active_timeout_after_s扩展编排，使用新的候选记录；必须检查N持权后fresh读取再activation=0捕获，不能与第1/2轮冒充完全同候选因果配对。']
 (OUT/'capture-stage-audit.zh.md').write_text('\n'.join(lines)+'\n')
 return out
if __name__=='__main__':
 from realized_outcomes import decorate
 run(decorate(m.load(OUT/'summary.json',[])))

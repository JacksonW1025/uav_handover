"""Build reviewed research-only local deliverables; never upload or alter source experiments."""
import json,hashlib,csv,shutil,zipfile,collections
from pathlib import Path
import numpy as np
from pyulog import ULog
import metrics_base as m
OUT=Path(__file__).resolve().parents[1];ROOT=Path('/home/car/uav_handover');BATCH=ROOT/'data/handover-mutation-20261111'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(4*1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def write(p,v):p.write_text(json.dumps(m.clean(v),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def main():
 results=m.load(OUT/'summary.json');assert len(results)==23;assert sum(bool(r.get('boundaries')) for r in results)==22
 ledger=m.lines(BATCH/'attempts.jsonl');starts=[e for e in ledger if e['event']=='START_INTENT'];ends=[e for e in ledger if e['event']=='PHYSICAL_END'];assert len(starts)==len(ends)==23
 integrity=m.load(BATCH/'final-execution-integrity.json');assert integrity['all_completed_candidates_unchanged'] and integrity['all_safety_limits_unchanged']
 candidates=[];raw=[];rows=[]
 for r in results:
  name=r['attempt_id'];run=BATCH/name;f=run/'flight';cp=run/'candidate-before.json';c=m.load(cp);canonical=hashlib.sha256(json.dumps(c,sort_keys=True).encode()).hexdigest() if c else None;canon_after=m.load(run/'candidate-after.json');candidates.append({'attempt':name,'file_bytes_sha256':sha(cp) if cp.exists() else None,'canonical_json_sha256':canonical,'before_after_equal':c==canon_after if canon_after else None,'project_head':(c or {}).get('project_head'),'candidate':c})
  files=[f/'flight.ulg',f/'telemetry.jsonl',f/'events.jsonl',f/'explore-setpoints.jsonl']+sorted((f/'gz-motor').glob('*.bin'))
  for path in files:
   if path.exists():raw.append({'attempt':name,'local_path':str(path),'bytes':path.stat().st_size,'sha256':sha(path),'included_in_delivery':False})
  if r.get('ulog_sha256'):assert next(x['sha256'] for x in raw if x['attempt']==name and x['local_path'].endswith('/flight.ulg'))==r['ulog_sha256']
  bs=[b for b in r.get('boundaries',[]) if 'owner_boundary' in b];b=bs[0] if bs else {};spec=r.get('explore',{});w=b.get('windows',{}).get('subject') or {};row={'编号':name,'轮次':spec.get('round'),'执行状态':r.get('attempt',{}).get('execution_status',r.get('physical_end',{}).get('execution_status')),'实际主体交接数':len(bs),'场景实现':r.get('scenario_realization'),'证据限定冻结':r.get('frozen_primary_status'),'证据限定任务':r.get('task_status'),'已实现物理冻结':r.get('observed_physical_frozen_status'),'已实现物理任务':r.get('observed_physical_task_status'),'峰倾角_deg':w.get('max_tilt_deg'),'峰时刻_owner后_s':b.get('observed_peak',{}).get('after_owner_s'),'失高_m':w.get('max_altitude_loss_m'),'低于活动参考_m':b.get('reference_tracking',{}).get('max_below_active_reference_m'),'主体观察_s':w.get('requested_duration_s'),'正常实验落地disarm':r.get('completion',{}).get('normal_landing_disarm',False),'独立恢复落地disarm':bool(r.get('interruption_recovery',{}).get('normal_recovery_landing_confirmed') and r.get('interruption_recovery',{}).get('disarmed_confirmed')),'四电机物理应用':b.get('four_motors_observed'),'candidate_canonical_sha256':canonical,'source_ulog':str(f/'flight.ulg'),'source_ulog_sha256':next((x['sha256'] for x in raw if x['attempt']==name and x['local_path'].endswith('/flight.ulg')),None)};rows.append(row)
 write(OUT/'raw-source-index.json',{'algorithm':'SHA-256 of exact file bytes; raw files stay on car and are not included in ZIP','files':raw})
 write(OUT/'candidate-versions.json',{'file_hash_algorithm':'SHA256(exact candidate-before.json file bytes); this is candidate_record_sha256 in cases.csv and summary.json','canonical_hash_algorithm':'SHA256(json.dumps(parsed_candidate, sort_keys=True).encode()) using Python default ensure_ascii=True and default separators; matches final-execution-integrity.json','groups':dict(collections.Counter(r['canonical_json_sha256'] for r in candidates)),'records':candidates,'only_changed_field':integrity['candidate_changed_fields']})
 with (OUT/'逐例完整表.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 table=['# 23次启动完整记录','','实际主体交接共22例；001独立恢复不并入原实验。SUCCESS/FAILURE/UNKNOWN保留各自证据范围。','', '|编号|执行|场景|原冻结/任务|物理冻结/任务|峰倾角°|失高m|正常落地|','|---|---|---|---|---|---:|---:|---|']
 for x in rows:
  table.append(f"|{x['编号']}|{x['执行状态']}|{x['场景实现']}|{x['证据限定冻结']}/{x['证据限定任务']}|{x['已实现物理冻结']}/{x['已实现物理任务']}|{x['峰倾角_deg']:.3f}|{x['失高_m']:.3f}|{x['正常实验落地disarm']}|" if x['峰倾角_deg'] is not None else f"|{x['编号']}|{x['执行状态']}|NO_SUBJECT_HANDOVER|UNKNOWN/UNKNOWN|UNKNOWN/UNKNOWN|—|—|原实验不确认；独立恢复确认|")
 (OUT/'逐例完整表.zh.md').write_text('\n'.join(table)+'\n')
 # Actual timeout and first-owner aligned traces; plot subject only, never cleanup.
 import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
 fig,axes=plt.subplots(3,1,figsize=(10,9),constrained_layout=True)
 for r in results[-2:]:
  b=r['boundaries'][0];f=Path(r['source_run']);d={z.name:z.data for z in ULog(str(f/'flight.ulg'),message_name_filter_list=['vehicle_attitude','vehicle_local_position','research_p11']).data_list if z.multi_id==0};start=b['owner_boundary']['timestamp_us'];end=b['subject_end_us'];caps=[x for x in r['target_capture_events'] if x['activation']==0 and start<=x['timestamp']<=end];capture=caps[-1]['timestamp'];label=r['attempt_id'][:3]+' RTGT'+str(caps[-1]['mode']);a=d['vehicle_attitude'];t=a['timestamp'].astype(np.int64);ix=(t>=start)&(t<=end);tilt=np.degrees(np.arccos(np.clip(1-2*(a['q[1]']**2+a['q[2]']**2),-1,1)));axes[0].plot((t[ix]-start)/1e6,tilt[ix],label=label);axes[1].plot((t[ix]-capture)/1e6,tilt[ix],label=label)
  p=d['research_p11'];t=p['timestamp'].astype(np.int64);ix=(t>=start)&(t<=end)&p['active'].astype(bool);axes[2].plot((t[ix]-capture)/1e6,np.hypot(p['network_target_velocity[0]'][ix],p['network_target_velocity[1]'][ix]),label=label+' consumed target');axes[2].plot((t[ix]-capture)/1e6,np.hypot(p['velocity[0]'][ix],p['velocity[1]'][ix]),ls='--',label=label+' actual vehicle')
 for ax in axes:ax.grid(alpha=.2);ax.legend(fontsize=8)
 axes[0].axhline(45,color='red',ls='--');axes[1].axhline(45,color='red',ls='--');axes[0].set(xlim=(0,2.5),ylabel='Tilt (deg)',xlabel='Seconds after actual N owner',title='022/023: subject only; not a strictly matched pair');axes[1].set(xlim=(-.3,1.5),ylabel='Tilt (deg)',xlabel='Seconds after actual nonactivation timeout capture');axes[2].set(xlim=(-.3,1.5),ylabel='Horizontal speed (m/s)',xlabel='Seconds after actual nonactivation timeout capture');fig.savefig(OUT/'actual-timeout-comparison.png',dpi=160);plt.close(fig)
 primary=collections.Counter(r['frozen_primary_status'] for r in results);physical=collections.Counter(r['observed_physical_frozen_status'] for r in results if r.get('boundaries'));execution=collections.Counter(x['执行状态'] for x in rows);landed=sum(x['正常实验落地disarm'] for x in rows);all4=all(x['四电机物理应用'] for x in rows if x['实际主体交接数']);assert len(rows)==23 and all4
 counts={'attempts':23,'actual_subject_handovers':22,'interrupted_no_subject':1,'execution_status':dict(execution),'original_evidence_qualified_frozen_all_attempts':dict(primary),'observed_physical_frozen_actual_subjects':dict(physical),'normal_experiment_landing_disarm':landed,'independent_recovery_landing':1,'all_22_four_motors_verified':all4,'candidate_versions':dict(collections.Counter(r['canonical_json_sha256'] for r in candidates))};write(OUT/'final-counts.json',counts)
 report='''# 069种子三轮变异：最终报告

## 1. 这次完成了什么

以历史069零速捕获越线案例为种子，进行了三轮探索性、纯headless SITL变异。共23次唯一启动、23次PHYSICAL_END，22次真实主体C→N交接。001在主体前因原runner中断，只保留为中断记录；独立LAND/disarm恢复确认，不能拼成复现成功。没有新加隐藏重试，没有真实飞行。

逐例参数、入口状态、0.25/0.5/1/2秒窗口、截断、目标证据、失高、速率与饱和见cases.csv、summary.json及《逐例完整表》。本报告只解释主要发现。

## 2. 结果必须分三层看

- 执行层：22个完整结果中，10个runner PASS、12个runner FAIL；另001中断。执行完成不代表安全。
- 已实现物理轨迹：22个实际交接中，15例冻结/任务失败，7例满足这两个判据。这只是自适应挑选案例的计数，不是失败概率或安全认证。
- 场景证据层：015–017没有实现原本声明的active-timeout。原始证据限定汇总保留15 FAILURE、5 SUCCESS、3 UNKNOWN（UNKNOWN包括001、016、017），不静默改判。016/017的实际activation轨迹满足物理判据，但不能证明active-timeout通过；015实际activation轨迹本身失败。

正常实验落地并disarm共10例，其中011、018、019虽然正常落地，仍是离线安全失败。其余12个保护中止例未观察到正常落地/disarm；只有发出LAND或收到ACK不能写成落地。001的独立恢复另外计算。

## 3. 找到了什么

### 3.1 零速捕获的邻域没有可靠的1.6m/s安全界

原seed名义1.6（003）峰44.185°，名义1.7（018）峰47.043°，名义1.8（004）峰45.976°。新seed名义1.6（019）峰45.100°，1.8（020）峰47.678°。003/019实际入口vx约1.565/1.572m/s，接近却跨过45°判据。单次通过不能变成安全速度上界，保护中止后的截断峰也不能用于推导平滑单调曲线。

### 3.2 三个执行PASS漏过了短时越线

011、018、019原生ULog峰分别47.000°、47.043°、45.100°。越45°样本区间分别为owner后0.316–0.404s、0.308–0.392s、0.336–0.356s。它们正常完成并落地，但冻结与任务都失败。

runner把安全判断放在约100ms遥测采样分支。其记录最高仅44.642°、44.604°、43.359°。四元数精确匹配显示，相邻被检查姿态跳过了短峰；011/018检查时姿态旧约16–24ms，019只有4–8ms，说明即使DDS较新，检查频率仍可能漏过20ms短峰。详见direction-audit.json与图。该45°保护不是逐4ms硬限幅，不能把“没有触发中止”当安全证据。

新seed的y负方向021峰47.926°并实际触发保护，说明011不是安全方向；这里只描述两个不同入口的结果，不把它们当严格配对。

### 3.3 方向、记忆和外部参考都不能单独当安全保证

009/010/011/012的主体峰为47.043/48.163/47.000/59.054°。真实目标yaw约95.5–95.8°，世界+Y接近策略前向，−Y接近后向，−X接近负左向；012对角初始FLU速度误差约[1.311,1.461]m/s，两个水平分量同时超过每轴1m/s输入裁剪范围。该证据说明方向与每轴裁剪相关，尚不能将策略内部非线性原因归结为某一个轴。

013 RINI1确实保留了GRU和previous_action，014 RINI4确实保留GRU并匹配新鲜classic_action，且进入前1秒250条teacher forcing证据齐全；残差均为0，但峰仍为48.427°、50.147°。记忆初始化改变不是这组零速目标失配的通用消除方法。

007外部freeze峰56.053°失败，008外部brake峰9.190°通过。两者参考在N owner前23.753/15.950ms就已发布，此时C仍持电机权，并分别还有5/3条C电机发布。没有经典控制器逐次输入读取trace，不能进一步声称精确消费时刻；也不能把这称作N独有的目标突变。007的原生activation事件不等于最终网络目标，N首个owner周期实际使用外部freeze；008使用外部brake。因此“用了外部参考”本身不是保证，内容和生效时序都重要。

### 3.4 真正active-timeout下，RTGT1与RTGT2出现不同结果

015–017虽然名义quiet=0，实际全部在activation捕获，未测试到active-timeout。第三轮为此使用单独记录的新编排：N已持权后保持有效外部流再停止；以下结论来自真实日志而非设计名。

- 022 RTGT1：N持权后有33次fresh有效外部读，发送payload匹配成立；owner后0.888s、最后有效读后204ms出现activation=0捕获。机体水平速度[1.98899,0.04733]m/s，目标变为[0,0]。主体峰49.168°，在owner后1.228s、timeout后0.340s，失高0.121m，冻结/任务失败，未确认落地。首0.5秒只有4.166°，风险是后续超时阶段，不是交接瞬间。
- 023 RTGT2：保留首次activation捕获，随后实际消费外部流；owner后0.892s、最后有效读后204ms发生第二次activation=0捕获。此时目标水平速度匹配机体[2.03884,0.04445]m/s。主体峰14.313°、失高0.047m，冻结/任务成功并正常落地。

两例均验证“N持权下fresh sender-match → 非activation捕获”的完整链，枚举了全部capture而非只取第一条。022没有对应初始activation捕获，023有；两例实际入口/捕获状态不同，因此这是一组符合实现机制的描述性对照，不是随机化或严格相同状态的因果证明。RTGT1只在activation匹配速度，RTGT2还覆盖active-timeout，这个阶段差别不能混淆。

## 4. 判据与证据边界

冻结主判据保持不变：倾角≥45°、单轴角速率≥8rad/s、水平半径≥10m、高度≥8m、接地高度≤0.2m、任一电机在≥0.999或≤0.001持续≥0.5s、10秒内未联合恢复，或runner安全中止。任务判据另列：倾角>45°或入口相对失高>1m。联合恢复仍使用冻结P0阈值，不以移动目标跟踪误差替换零速度恢复要求。

失高同时报告入口相对损失与低于实际活动参考的误差，不把有意下降或参考变化混为掉高。全部22个交接已核验四电机实际应用；没有持续电机饱和触发，主要观察到的是倾角越界。原始ULog、事件、telemetry和电机trace留在本机，交付包仅含报告、派生证据和本机路径/SHA索引。

主体截止于failure的P11原生时间下界、主体结束或下次owner边界。安全失败后的0.5/1/2秒窗口通常不足完整时长，不能当完整观察，也不能用尾段恢复或尾段更大峰值替换主体结果。保护后尾段单列subject-vs-cleanup-audit.json；例如004主体45.976°/尾段47.764°，005主体50.839°/尾段55.124°。所有峰都是已观察峰，不是无保护最终峰。

## 5. 候选版本与最终状态

本次存在两个候选记录版本，唯一变化字段是files/tools/handover_mutation/runner.py。第三轮保存了扩展前后runner、diff及validation；默认分支保持原行为，只有022/023启用新的active_timeout_after_s编排。原100runner、PX4、策略权重、物理与安全阈值未改。跨版本不冒充严格同candidate实验。

22个完整结果均before/after candidate一致。执行侧最终核验确认23个ULog存在、无仿真残留、host gate通过、Git HEAD为003cd249a0b1baa3ad78a25c18473657af39aa70，没有commit/push。001独立恢复记录完整。

候选hash有两种不同算法：cases.csv/summary.json的candidate_record_sha256是候选JSON原文件字节SHA-256；执行审计的candidate_record_sha256是Python json.dumps(..., sort_keys=True)默认序列化后的SHA-256。candidate-versions.json并列保存两者与准确算法，不能直接拿两类hash判漂移。

## 6. 结论

这三轮最重要的新增发现是：零速捕获风险延伸到1.6–1.8邻域且随入口/seed跨阈值；约100ms在线检查可能漏过离线可见短时越线；以及activation与active-timeout必须分阶段核验，RTGT1的activation通过不能外推到active-timeout。速度匹配在已测场景显著减小了倾角，但现有样本、两seed及自适应选例不足以给出总体安全保证。

没有为了追求更高峰值而放宽保护，也没有隐藏失败、拼接恢复或把未实现场景当成功。下一步若继续，应把在线检查覆盖率与真实超时场景单独预注册验证；本次不再增加实验。
'''
 (OUT/'FINAL_REPORT.zh.md').write_text(report)
 # Research-only evidence copies, no transfer helpers or tool responses.
 evidence=OUT/'delivery-evidence';evidence.mkdir(exist_ok=True)
 names=['final-execution-integrity.json','round-1-plan.json','round-2-plan.json','round-3-plan.json','attempts.jsonl','round-events.jsonl','head-before.txt','worktree-before.txt']
 for name in names:
  if (BATCH/name).is_file():shutil.copy2(BATCH/name,evidence/name)
 for sub in ['round-3-runner-extension','recovery-001-v1']:
  dest=evidence/sub;dest.mkdir(exist_ok=True)
  for name in (['runner-before.py','runner-after.py','runner.diff','validation.json'] if 'extension' in sub else ['result.json']):
   if (BATCH/sub/name).is_file():shutil.copy2(BATCH/sub/name,dest/name)
 (OUT/'README.zh.md').write_text('# 交付包阅读顺序\n\n1. FINAL_REPORT.zh.md：最终结论与限制。\n2. 逐例完整表.csv / .zh.md：23次启动完整记录。cases.csv提供更细的窗口/入口字段。\n3. summary.json：完整聚合分析，保留原证据限定判据并另列已实现物理结果。\n4. mechanism、capture-stage、direction及subject-vs-cleanup审计：目标/记忆/采样/尾段证据。\n5. raw-source-index.json：只存本机原始路径、字节数和SHA-256；不含原始ULog、telemetry或电机二进制。\n6. candidate-versions.json及delivery-evidence：两版候选、预注册计划、账本与最终执行核验。\n\n本包只含研究交付内容，不含上传工具或凭据。原始数据仍在car，不会随ZIP外传。分析重跑命令：OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 taskset -c 0-3 uav_lab/.local/venv/bin/python data/handover-mutation-20261111-analysis-v1/tools/analyze_mutations.py --plots。\n')
 include=['README.zh.md','FINAL_REPORT.zh.md','逐例完整表.csv','逐例完整表.zh.md','cases.csv','summary.json','final-counts.json','raw-source-index.json','candidate-versions.json','historical-069-070.json','mechanism-audit.json','mechanism-audit.zh.md','capture-stage-audit.json','capture-stage-audit.zh.md','direction-audit.json','direction-audit.zh.md','subject-vs-cleanup-audit.json','subject-vs-cleanup.zh.md','transient-comparison.png','direction-and-sampling.png','actual-timeout-comparison.png']
 files=[OUT/x for x in include]+[p for p in evidence.rglob('*') if p.is_file()]+[p for p in (OUT/'runs').glob('*/timeseries.png')]+[p for p in (OUT/'tools').glob('*.py')]
 files=sorted(set(files));assert all(p.exists() for p in files);manifest=[{'path':str(p.relative_to(OUT)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in files];write(OUT/'delivery-manifest.json',{'files':manifest,'raw_files_included':False,'original_raw_local_index':'raw-source-index.json'});files.append(OUT/'delivery-manifest.json')
 zip_path=OUT/'handover-mutation-20261111-delivery-v1.zip'
 with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for p in files:z.write(p,p.relative_to(OUT))
 with zipfile.ZipFile(zip_path) as z:assert z.testzip() is None;assert not any(n.endswith(('.ulg','.bin')) for n in z.namelist())
 write(OUT/'package-validation.json',{'zip_path':str(zip_path),'bytes':zip_path.stat().st_size,'sha256':sha(zip_path),'file_count':len(files),'crc_test':'PASS','raw_excluded':True,'uploaded':False,'counts':counts});print(json.dumps(m.load(OUT/'package-validation.json'),ensure_ascii=False),flush=True)
if __name__=='__main__':main()

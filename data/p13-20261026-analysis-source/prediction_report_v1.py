"""Detailed denominators and temporal diagnostics, no changes to frozen scores."""
import sys,json
from pathlib import Path
R=Path(__file__).resolve().parents[2]
f=lambda v:'—' if v is None else f'{v:.4f}'
def span(v):return '—' if not v.get('n') else f"{f(v['min'])}…{f(v['max'])} (n={v['n']})"
p=json.load(open(R/'data/p13-20261026-synthesis-v3/prediction-summary.json'));e=json.load(open(R/'data/p13-20261026-extra-diagnostics-v2/summary.json'));assert p['formal_flights']==e['records']==66
s='''# P13预测分母与时间过程补充

模型/参数/权重均在正式前封存。留出单位是六个新种子块、两个已声明条件，并非新平台或未知条件；每条件3块，块内11条相关飞行。M3/M4/M5及诊断替换不是独立飞行样本。第53项原始记录不重飞，只用完全相同封存模型、过去初态和事前计划在隔离环境补齐缺失预测/评分，原partial分析保留。

## 分类、完整轨迹和窗口分母

FAILURE可由有效前缀见证；SUCCESS必须完整；其余UNKNOWN。任务OR不能掩盖倾角/高度分项，UNKNOWN不是agreement。canonical v2分类限定实测覆盖范围；额外forward越界时间保留完整事前名义时域，未用后验终止改模型。

|模型|分项|agreement|danger miss|false alarm|UNKNOWN|可分类分母|总飞行|
|---|---|---:|---:|---:|---:|---:|---:|
'''
for n,m in p['models'].items():
 for part,c in m['whole_or_valid_witness_classification'].items():
  z=c['counts'];s+=f"|{n}|{part}|{z.get('AGREEMENT',0)}|{z.get('DANGER_MISS',0)}|{z.get('FALSE_ALARM',0)}|{c['UNKNOWN_retained']}|{c['classification_eligible']}|66|\n"
s+='\n|模型|完整预测|完整预测且实测完整（完整峰值分母）|函数计算秒范围|\n|---|---:|---:|---|\n'
for n,m in p['models'].items():s+=f"|{n}|{m['full_prediction_count']}|{m['full_observation_and_prediction_count']}|{span(m['compute_s'])}|\n"
s+='''
计算秒为同一Thor CPU0–3的Python单模型函数时间，隔离/加载总墙时另在每项isolation.json，不是PX4实际单次神经推理延迟。每个模型每条飞行的共同前缀误差，和只有双方完整才可比较的整程峰值分开；截断峰值只是下界。

.5/2秒窗口原始分项计数完整保存在prediction-summary.json和逐项score.json。窗口相互重叠、多个间隔共享NORMAL/A，不能增加有效飞行或块分母。全事件/保持/接回分析还覆盖这些短窗以外的后段。

## 同一绝对时间的前缀误差

下表为“每条飞行最大绝对误差”的范围；没有移动峰值、重置真实状态或后验对时。

|模型|量|每条最大误差范围|
|---|---|---|
'''
for n,m in p['models'].items():
 for k,v in m['full_prefix_error_max_per_flight'].items():s+=f'|{n}|{k}|{span(v)}|\n'
s+='\n## B前状态与历史\n\n|模型|B前覆盖状态计数|mean-before L2误差范围|历史D误差范围m|绝对count-before不一致调用数|\n|---|---|---|---|---:|\n'
for n,m in e['models'].items():s+=f"|{n}|{m['B_before_status']}|{span(m['B_before_mean_error_l2'])}|{span(m['B_before_D_error_m'])}|{m['count_before_mismatch_calls']}|\n"
s+='''
D为从task0保持的最大损高，未在A/B/capture/resume清零。M5的D误差是COM→COM；M3/M4没有独立物理COM状态，表中其D是plant→LP诊断，不混称COM误差。B前L/W/姿态/h/action/filter的全部逐项误差在synthesis-v3/records/time-process.json。mean/count/previous-before按真实源码顺序从封存初态与**预测动作**重建；绝对sample身份比较保留原profile时间差，不改名归一化count，不改原评分，也不把实际h/history送回预测器。

## 首次越界与恢复

|模型|分项|实测采样失败见证数|forward预测见证数|实测有见证、完整预测无见证|成对时间差下端范围s|上端范围s|
|---|---|---:|---:|---:|---|---|
'''
for n,m in e['models'].items():
 for comp,c in m['first_crossing'].items():s+=f"|{n}|{comp}|{c['observed_witness_count']}|{c['predicted_forward_witness_count']}|{c['observed_witness_no_predicted_witness_full_prediction']}|{span(c['paired_time_error_interval_lower_s'])}|{span(c['paired_time_error_interval_upper_s'])}|\n"
s+='''
这是第一采样见证的括号，不证明采样之间连续轨迹均已检查。height使用原LP共同A窗口基线；额外task0 LP/COM/原点D另存，不偷换原分类。无见证只有完整时才安全，否则UNKNOWN。时间差正值代表预测偏晚；不能只看峰值误差。

|模型|预测末段联合恢复状态|双方SETTLED的相对恢复时间误差范围s|
|---|---|---|
'''
for n,m in e['models'].items():s+=f"|{n}|{m['predicted_final_recovery_status']}|{span(m['paired_recovery_time_error_s'])}|\n"
s+='''
末段联合恢复沿用原P0位置.2m/速度.1m/s/角速度.1rad/s、连续2s、间隙>20ms重启连续性的规则，模型用**自己的预测末捕获/目标**与事前终点。时间相对各自capture，零差不证明capture绝对时间已对齐；绝对capture时刻另存。A到B前的W进入/离开.1m/s带只是额外过程描述，不冒充整状态联合恢复。

## LP/cache和真实物理状态的差别

物理Post为控制器Run前最近过去直接记录，保留其物理sim时间及host年龄；LP估计、gyro滤波、姿态cache有自身时间。以下差别不直接等于“同物理时刻估计器误差”，也不能把最近过去Post时间差叫作完整sensor→EKF→controller传输延迟。

|量|逐条最小值范围|逐条最大值范围|
|---|---|---|
'''
for k,v in e['cache_vs_physical'].items():
 if 'per_flight_min' in v:s+=f"|{k}|{span(v['per_flight_min'])}|{span(v['per_flight_max'])}|\n"
s+='''
真实LP/gyro/姿态差随过程变化。M5把初始LP/物理z和v偏差作为独立常量，位置差分与所报W还包含该近似和旋转几何残差；这是可定位的结构局限，没有在正式结果后重拟合。源码修正的一步物理核可以非常准，但完整已知命令开放重放仍离域；未来实际joint/姿态/速度替换只做定位，不进入前瞻成绩，不支持把漏判直接归因于求解残差。

phase-v3额外在固定共同内窗测试±.1s lag和幅值。它是后验定位，不替换上表未对时误差；小信号或lag搜索边缘明确标记不可辨识。所有旧模型、漏判、UNKNOWN和诊断版本保留。
'''
(R/'docs/THOR_P13_PREDICTION_RESULTS.md').write_text(s);print('PREDICTION_REPORT_COMPLETE')

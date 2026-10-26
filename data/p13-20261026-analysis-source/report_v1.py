"""Final report from completed audited records only; no simulation or refit."""
import sys,json
from pathlib import Path
from collections import Counter
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'));from p9_model import write,sha

def fmt(x,d=3):return '—' if x is None else f'{x:.{d}f}'
def ran(x,d=3):return '—' if not x.get('n') else f"{fmt(x['min'],d)}–{fmt(x['max'],d)}"
def report():
 agg=R/'data/p13-20261026-results-v2';syn=R/'data/p13-20261026-synthesis-v2';au=json.load(open(R/'data/p13-20261026-delivery-audit-v1/audit.json'));cs=json.load(open(agg/'cases.json'));cr=json.load(open(agg/'contrasts.json'))['rows'];gr=json.load(open(syn/'group-results.json'));ps=json.load(open(syn/'prediction-summary.json'))['models'];cov=json.load(open(R/'data/p13-20261026-covariates-v2/covariates.json'));cl=json.load(open(R/'data/p13-20261026-clocks-v2/clocks-and-execution.json'));rows=[r for r in cs['rows'] if r['status']=='FINISH'];groups={(x['family'],x['arm']):x for x in gr['rows']};effects={(x['family'],x['gap']):x for x in gr['effect_summary']};assert au['status']=='PASS' and len(rows)==66 and len(cr)==18
 repair=[r for r in rows if r['branch']=='REPAIR'];repairS=sum(r['task']=='SUCCESS' for r in repair);short=sum(r['single_success_combo_failure_pattern'] for r in cr if r['family']=='F2' and r['gap_label']=='short');dev=Counter(r['task'] for r in au['cases'] if r['budget_class']=='development');predmiss={n:{k:v['counts'].get('DANGER_MISS',0) for k,v in x['whole_or_valid_witness_classification'].items()} for n,x in ps.items()};costinc={k:sum((r['common_window_costs_v3']['REPAIR_minus_AB'][k]['lower']>0 if isinstance(r['common_window_costs_v3']['REPAIR_minus_AB'][k],dict) else r['common_window_costs_v3']['REPAIR_minus_AB'][k]>0) for r in cr) for k in ['aerodynamic_command_TV_rad_s','LP_horizontal_tracking_integral_m_s','post_joint_squared_rad2_per_s','thrust_impulse_Ns']}
 events=Counter(e['status'] for r in rows for e in r['event_statuses']);physOrigFail=sum(r['physical']['origin_D_m']>1 for r in rows);physCOMFail=sum(r['physical']['COM_D_m']>1 for r in rows);allholds=[e for r in cl['rows'] for e in r['actual_event_intervals'] if e.get('status')=='CAPTURE_REACHED'];hd=[e['actual_hold_profile_s'] for e in allholds if e.get('resume_status')=='READ_AND_FRESH_CONFIRMED'];allcaps=sum(len(json.load(open(agg/'holds'/r['id']/'hold-axes.json'))['rows']) for r in rows);cliprepair=[]
 for r in repair:
  for e in json.load(open(agg/'holds'/r['id']/'hold-axes.json'))['rows']:
   if e.get('rows') is not None:cliprepair.append(e)
 text=f'''# P13报告：真实物理状态、垂向恢复与组合边界

运行冻结=`4c122aaa9710b93699c52cbfc059653681ef4b31`，基线=`73d467beb70acf2c7413468f74be76e3b73c723a`。这是独立P13，旧P11/P12各轮失败、停止、冻结和未启动项未回写。

## 先回答七个问题

1. **新增信息解决了物理起点和时间接口卡点。** 现在直接取得五链接COM p/v、物理Pre/Post步时间、姿态/角速度、真实链接速度及施力阶段；旧回调差分速度不再充当物理初值。全量文件、连续重放及同物理步连接得到核验。完整EKF/运输队列仍非快照，不宣称严格同初态。
2. **接口在声明的固定观测平台上通过工程硬门。** 开发12/12、正式66/66均有终态及可信记录；正式安全截断{au['formal_censored']}条仍是有效失败前缀。不是66条都安全成功，也不是相对关闭观测平台的等价证明。最后header/fclose计错不完整的检测边界明示保留。
3. **源离散物理更新误差被具体定位，整段自主预测仍未闭合。** 修正FreeJoint基座/COM坐标更新的离线源核，一步误差接近浮点精度；开放重放仍约21–23秒离域。实际joint替换几乎不改变该离域，未来真实姿态/速度注入仅用于诊断。唯一新候选M5的正式倾角漏判{predmiss['M5']['tilt']}条，不能宣布普遍优于M3/M4。
4. **间隔改变B前残余状态及结果，但不是普遍单调边界。** F2短间隔在{short}/3个独立种子块出现NORMAL/A/B成功、AB失败且达到B；中长间隔逐块结果见下表。F4单A及部分B本身不稳定，不能包装成稳定单事件安全、组合才失败。B前L/W、历史D和h/action/filter必须联合看。
5. **修复{repairS}/{len(repair)}条任务成功；收益和代价分开。** 不调参的RTDEC2在全保持/接回/恢复及B前状态上比较。共同窗内修复相对AB的命令TV增加{costinc['aerodynamic_command_TV_rad_s']}/18、跟踪积分增加{costinc['LP_horizontal_tracking_integral_m_s']}/18、真实joint平方积分明确增加{costinc['post_joint_squared_rad2_per_s']}/18、推力冲量明确增加{costinc['thrust_impulse_Ns']}/18，增加项全部保留。截断AB不与完整修复直接相减整程积分。
6. **得到可计算的条件关系，未得到完整闭环保证。** 四SERVO有限rhs→冲量界、独立eta预算、执行上限的必要COM储备、含位置离散误差的全前缀恢复映射、完整保持与接回参考的修复参数交集均可复现。未来数值/模式、几何及EKF/cache/神经历史联合可达域尚未认证；A4仍NOT_PROVEN_EXCLUDED。
7. **下一步大部分应先离线。** 可继续认证四SERVO数值预算、完整源核多步敏感性、估计器/cache动态和相关多步储能。只有要辨识未覆盖的新模式、工作域或额外间隔时才需要另获授权的新飞行；本轮不追加、不启动P14。

## 完成度、门与版本

|层|结论|
|---|---|
|工程|固定轻量+缓冲物理平台PASS；源控制/事件/保护无非预期修改，字段/步序/重放/身份核验PASS|
|实验设计|PASS；2条件×3独立种子块×11臂，预先分块随机化，无结果替换、无事后相位/存活筛选|
|实际执行|开发12，正式66，合计78/84；额外6在正式前明确UNUSED。旧P12系列66另账，合计144，不包含更早P11|
|科学结果|正式{au['formal_science_outcomes']}；开发{dict(dev)}；科学失败均计数|
|预测|M3/M4保留，唯一M5封存在正式前；分项漏判/UNKNOWN保留，无留出调参|
|理论|有可计算条件关系；完整实际反馈NOT_PROVEN，工程PASS不替代理论PASS|
|CI|冻结提交连接器核验0 workflow run/0 check run/0 status；无可宣称的CI通过，最终发布另读状态回执|

实际PX4 SHA=`b6ea5a948b2ab0ed35f715ffa42fc9b09ec5dac33106691d7c573e02c98778d9`，motor插件=`21211d96e9d929b3d3f5a6dea32ba4d319dca82b353617105cefde4cc6fb58ea`，policy tar=`5327c83dc57f094ca1977a2533ebce318645be010e16b9354c96c337cd5c278b`。普通副本、依赖和配置hash见runtime-snapshot-v1；旧CLI链接不是旧二进制快照。正式前正常commit/push与远端回读回执保留，交付提交不回填成运行HEAD。

## 设计与可解释范围

两条件均1.8m/s，NED水平轴F2=15°、F4=45°（motion_axis_ned），固定PH1读取策略、A/B各.36s。新的6秒匀速P13任务长度12.51m，起点−6.255m，A计划13.255s；相对旧11.79m任务是显式新版本，逐项保留source_id。B计划分别14.165/14.815/15.615s，对应计划A接回→B停流间隔.55/1.2/2秒。B-only绝对时间与对应AB相同，所有臂参考轨迹与终点一致，删除事件不移动剩余事件。

读取策略是含缓存/交付影响的总处理机制；本轮固定PH1，不能声称估计了纯capture相位效应或PH1/PH2效应。修复仅从预定A sample门之后的非activation捕获启用，首次激活及预事件规则一致，没有hidden/history reset或网络参数写入；该门之后B及预定末段停流捕获也沿用同一修复规则。a=2m/s²未调。

初始与A前真实差异、cache阶段、绝对count/index、命令/filter/joint与时钟原样保留。每条件n=3独立种子块；每块11臂相关，三个间隔共享NORMAL/A，不把模型或重叠窗口算成新飞行。没有完整仿真/EKF/队列快照，因此这是小样本分块随机总效应证据，不能升格为严格同初态确定性因果证明或总体失败概率。

## 每臂结果：原判据与任务判据并列

任务OR为倾角>45°或LP损高>1m；原P5主判据还保留保护/角速率/饱和/着地与末段联合恢复要求。原LP主损高以共同A窗口为基线；物理COM/原点以及额外LP全历史诊断用共同task0基线，D从不在capture/resume重置，不能混为同一高度判据。

|条件/臂|任务成功/3|原判据成功/3|安全截断|LP峰倾角°范围|LP主损高m范围|物理原点D m范围|COM D m范围|
|---|---:|---:|---:|---|---|---|---|
'''
 for x in gr['rows']:
  text+=f"|{x['family']} {x['arm']}|{x['task_counts'].get('SUCCESS',0)}|{x['primary_counts'].get('SUCCESS',0)}|{x['censored']}|{ran(x['LP_peak_deg'])}|{ran(x['LP_loss_m'])}|{ran(x['physical_origin_D_m'])}|{ran(x['physical_COM_D_m'])}|\n"
 text+=f'''\n![全部预分配任务结果](figures/p13/task-outcomes.png)

物理task0诊断：原点D>1m共{physOrigFail}/66、COM D>1m共{physCOMFail}/66；它们是不同几何/来源的诊断，不能替代上述冻结LP分类。事件状态计数为{dict(events)}；NOT_PLANNED与NOT_REACHED分别保存，早停未达到B不当成功。全事件表还保留实际capture/resume、h/previous/mean/count、执行与待消费队列可观测边界。

## 间隔—B前状态—结果

|条件/间隔|单事件成功且组合失败块数/3|AB−B的COM W m/s范围|AB−B的当前原点L m范围|AB−B历史D m范围|AB−B hidden L2范围|
|---|---:|---|---|---|---|
'''
 for x in gr['effect_summary']:
  v=x['AB_minus_B_before'];text+=f"|{x['family']} {x['gap']}|{x['single_success_combo_failure_blocks']}|{ran(v['COM_W_m_s'])}|{ran(v['origin_L_m'])}|{ran(v['origin_D_m'])}|{ran(v['h_l2'])}|\n"
 text+='''
![F2 B前残余状态](figures/p13/B-before-F2.png)
![F4 B前残余状态](figures/p13/B-before-F4.png)

W恢复至零/转为上升时，历史D仍保留已损失的最大余量；当前L减小不能撤销过去失败。F4单事件附近的自然波动和初态差异、A后的恢复/历史残留及B后的新增响应必须同时看。非加性采用共同绝对任务时间和有序SO(3)乘积`R_N*(R_N^T R_A)*(R_N^T R_B)`，反序仅诊断；高度用AB−A−B+NORMAL。它是带初态/cache差异的原始分块残差，不能直接称纯神经记忆因果贡献。插值/最近过去调用不构成精确同态分叉。

![F2各块短间隔时程](figures/p13/short-gap-process-F2.png)
![F4各块短间隔时程](figures/p13/short-gap-process-F4.png)

## 初态、实际时序与重放

'''
 for fam,x in cov['summary'].items():
  v=x['preA_ranges'];text+=f"- {fam}，固定A前相对块内NORMAL：COM W差范围{fmt(v['COM_W_m_s']['min'])}–{fmt(v['COM_W_m_s']['max'])}m/s，COM H差{fmt(v['COM_H_m']['min'])}–{fmt(v['COM_H_m']['max'])}m，LP姿态SO(3)差最大{fmt(v['SO3_deg']['max'])}°，hidden L2差最大{fmt(v['h_before']['max'])}。原始连续/离散差和绝对身份见covariates-v2，未归一化count或平移时间。\n"
 text+=f'''\nsource sample与native实际增量、输出/GRU提交、同次pre-read initialized/force-sync/index和门状态逐项保存。本轮task期native平台边数{sum(r['native_platform_edges_task'] for r in cl['rows'])}，native跳进超过sample边数{sum(r['native_jump_over_sample_edges_task'] for r in cl['rows'])}；这不排除旧P11第70条合法词。实际capture至resume保持时长范围{fmt(min(hd),6)}–{fmt(max(hd),6)}秒；计划恢复间隔、实际A-resume→B-stop和B-capture不是同一量，clocks-v2保留原时间与采样阶段。

预事件任务坐标和bounded共同启动不改变h/history；直接物理起点已知，运输/完整EKF及未来solver域成员仍UNKNOWN。源filter已知命令连续重放最大误差{max(r['execution_filter_replay_max_rad_s'] for r in cl['rows']):.3g}rad/s；这不是自主闭环预测。输出链保持latest-value语义，不要求每个神经输出都被执行。

固定模型初态敏感性仅用开发7/8/9：物理COM W±.1m/s、同时LP/COM W±.1、h单分量±.001、filter±1的对称诊断，M3/M4/M5均封存不拟合。其余源误差/可达性未证明，不用该诊断校正正式初态或筛选配对。详见initial-sensitivity-v1及summary-v2。

## 修复保持、接回、代价与末段

修复{len(cliprepair)}个有记录保持段中，位置任轴裁剪段数{sum(e['position_clip_rows_all3']>0 for e in cliprepair)}，速度任轴裁剪段数{sum(e['velocity_clip_rows_all3']>0 for e in cliprepair)}；capture sample调用包含、resume实际读取调用排除，完整与截断前缀分别标记。捕获瞬时输入误差、整段限幅、接回目标/机体差、B前残留、任务终点及原P0联合恢复各有独立字段。

![共同窗口机械代价](figures/p13/repair-common-costs.png)

命令TV单位rad/s；真实求解joint平方积分rad²/s与10倍空气动力转速平方代理分开，推力冲量Ns，跟踪积分m·s。全部都不称电能。公共窗口取双方全部有效覆盖，保留切在物理步内部时的积分区间，未择近窗口、未把截断AB整程和完整修复整程相减。`contrasts.json`的legacy `full_costs_own_only`字段保留旧缩放结果；最终统一使用`common_window_costs_v3/own_covered_costs_v3`。

## 前瞻预测：分项、时程和正确分母

同一开发NORMAL上，源平均惯量→实际各向异性→FreeJoint离散核的共同前682步位置误差约4.16e-4→1.62e-7→2.06e-8m；相同45°错误见证尺度仍分别在11.40/20.65/21.33秒出现。旧50°与新80°停止域保留，未混作同一出域标准；M4强制物理初态的失败只诊断其LP/observer闭合，不能替代自主成绩。源结构得到修正，但长程保证和实际闭环预测没有因此自动成立。详见kernel-progression-v1。

M3/M4原版本保留；唯一M5为源垂向COM/轴投影阻力、初态和几何，角/水平及cache闭合仍继承经验M4。候选工作尝试和拒绝的yaw偏置拟合保留，最终结构/参数在dev9及正式66之前封存；后续源离散核只是诊断，未制造M6或重拟合M5。

|模型|完整预测/66|倾角agreement/可判分母|倾角漏判|高度agreement/可判分母|高度漏判|OR漏判|倾角逐时最大绝对误差°|LP缓存高度逐时最大误差m|
|---|---:|---:|---:|---:|---:|---:|---:|---:|
'''
 for n,x in ps.items():
  co=x['whole_or_valid_witness_classification'];text+=f"|{n}|{x['full_prediction_count']}|{co['tilt']['agreement_n']}/{co['tilt']['classification_eligible']}|{co['tilt']['counts'].get('DANGER_MISS',0)}|{co['height']['agreement_n']}/{co['height']['classification_eligible']}|{co['height']['counts'].get('DANGER_MISS',0)}|{co['task']['counts'].get('DANGER_MISS',0)}|{fmt(x['full_prefix_error_max_per_flight']['tilt_deg']['max'])}|{fmt(x['full_prefix_error_max_per_flight']['LP_cache_H_m']['max'])}|\n"
 text+='''
![预测分项与UNKNOWN](figures/p13/prediction-components.png)

已知失败见证可在有效前缀判FAILURE；完整覆盖且无失败才SUCCESS；安全但不完整、数值不确定或未建模均UNKNOWN。UNKNOWN不是agreement；完整峰值误差只在预测/实测均完整时有分母。任务OR正确不能掩盖倾角漏判，峰值接近不能掩盖逐时误差。整程、.5/2秒事件窗口、完整峰值、共同前缀及独立飞行/种子分母均分开。

synthesis-v2包含B前LP/COM L/W和h/action/filter误差；history-v2另从封存初态与预测动作重建mean/count/previous-before，按绝对sample身份核对并保留原profile时间差，未重命名计数。crossing-v2给倾角/原LP A基线高度第一采样越界括号、漏判/UNKNOWN及时间差区间；额外task0全历史基线另标。phase-v2仅在固定共同内窗诊断±.1秒lag及幅值，不替代原评分。cache-physics-v1把真实物理状态和LP/gyro/姿态缓存的时间与偏差分开，M5常量z/v偏置近似的局限保留。

## 理论结果、域与反例

详见[理论结果](THOR_P13_THEORY_RESULTS.md)。可计算结果包括：

- 源有限四SERVO在明确模式/域条件下，free joint≤104.2383rad/s、rhs L2≤408.4766rad/s、冲量L2≤.0108241Nms；使scaled执行误差≤1rad/s的一项充分eta预算约.09999959rad/s。无限force limit不用于有限界，eta独立于e_j重建。
- filter与执行上限给每个离散前缀的必要额外COM储备；W=.98、filter750的示例在声明预算下约.0643m，超过它不代表安全。
- 含离散位置预算的恢复映射显式传播L/D/W，并给B前与后段余量/间隔条件；全保持不裁剪、接回参考跳变及制动路程给条件修复参数交集。局部示例区间含a2，但源全盒保守界给空交集，缓存/实际可达域未认证，绝不称实际已证修复参数。
- 真实权重的非负比较构造在很少调用退化为动作绝对界；完整非负增益连接不能消除该保守性，需要联合相关集合/多步非对角储能。不是孤立GRU必须收缩或实际闭环发散证明。

直接物理初态和投影成员已可核对；每项domain.json给首次出投影域和不可观测字段。未来模式/free/matrix/eta、额外关节/浮点误差及连续域不变性未认证，完整成员从起点仍UNKNOWN，但物理起点本身不再UNKNOWN。不能把所有离散投影PASS写成完整失败轨迹有证书覆盖，不能用正式经验最大值填满未来假设。A4 NOT_PROVEN_EXCLUDED；旧时钟平台和全部失败保留。

## 测试、错误保留与复现

本地相关Python41项通过；实际构建、源码注入幂等、各片段唯一性、buffer ASAN/UBSAN宿主单元通过。首次链接选项失败及sandbox LeakSanitizer ptrace错误保留，宿主相同二进制通过，未混称首试通过。新增高度关系8项检查和离散恢复30项精确有理数核对通过；全量实际轨迹的原始输入/神经历史/filter连续重放及物理连接独立核验。

首条JSON scalar序列化错误、1e-8理想刚性FAIL、全部科学失败和分析v1/v2目录保留。普通分析修复单独版本化：scalar、真实joint单位/阶段、修复位置式Ev·T、离散窗口floor、COM/原点与全保持cache假设、capture调用包含；正式队列没有因此改参数、改组、替换或重跑。分析等待服务v1在实际聚合前停止并确认MainPID0，v2负责最终全量；物理formal服务未被该修复中断。

[复现与原始路径/hash索引](THOR_P13_REPRODUCE.md)列出离线命令、版本、完整本地数据及普通二进制。`delivery-audit-v1`核对唯一身份、顺序、预算、冻结SHA、旧23项历史hash、实际运行版和完整原始/派生hash，状态PASS。未删除旧日志或静默降采样，无追加飞行。冻结提交CI读取为NO_CI，最终正常发布/远端及CI回执独立记录，未把本地PASS冒充CI。
'''
 (R/'docs/THOR_P13_REPORT.md').write_text(text)
 write(R/'data/p13-20261026-final-analysis-v2/machine-conclusion.json',{'schema':'p13-machine-conclusion-1','freeze':'4c122aaa9710b93699c52cbfc059653681ef4b31','engineering':'PASS_FIXED_OBSERVED_PLATFORM','experiments':au['counts'],'formal_science_outcomes':au['formal_science_outcomes'],'F2_short_single_success_combo_failure_blocks':short,'independent_blocks_per_condition':3,'strict_same_initial_causal_proof':False,'repair_task_success':repairS,'repair_flights':len(repair),'common_window_cost_increase_counts':costinc,'model_component_danger_misses':predmiss,'theory':'COMPUTABLE_CONDITIONAL_SOURCE_RELATIONS_NO_COMPLETE_ACTUAL_FEEDBACK_CERTIFICATE','physical_initial':'KNOWN_DIRECT_TIMED_OBSERVATION','full_theory_membership':'UNKNOWN_MODE_NUMERIC_GEOMETRY_EKF_CACHE_HISTORY_FUTURE','A4':'NOT_PROVEN_EXCLUDED','actual_denied_pending_or_uncertain_execution':[],'optional6':'UNUSED_BEFORE_FORMAL','P14':'NOT_STARTED','CI':'NO_CI_FREEZE; FINAL_PUBLICATION_READBACK_SEPARATE','report_sha256':sha(R/'docs/THOR_P13_REPORT.md')});print('REPORT_COMPLETE',len(rows),short,repairS,predmiss)
if __name__=='__main__':report()

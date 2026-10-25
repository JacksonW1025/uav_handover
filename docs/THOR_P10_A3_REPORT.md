# P10-A3：源码驱动启动与误差兼容核查，NOT_PASSED

2026-10-25。**本文件为A3当前入口，机器入口为 [config/p10_a3.json](../config/p10_a3.json)。新增SITL启动、开发/正式/真实飞行均0，B/C/D均0且禁止启动。** 基线本地与远端均核到 `06c465f6f9f35b948d13456b94cb0305425e3699`。原A、A2、最终勘误及其NOT_PASSED、全部证书/失败结果原样保留。

A3取得源码驱动的完整参考与模块事件输入、可复查的真实启动观测绑定、确定的代理空历史初始化及严格有限前缀结论；**没有取得完整事件序列的集合证书或可用修复准入**。首个T0捕获使整个声明初集退出未饱和证书的截断域，已有P9数据也明确不满足A2的微小误差条件。不是因要求神经控制器精确状态等价或无条件整体安全而否决。

## 三层接口先固定

| 层 | 对象及边界 |
|---|---|
| 源码语义 | `run_experiment.py`原始`profile_cfg/reposition/profile_duration/p1_profile/p5_gap_windows/start_stream`经AST隔离执行；原native有效读取、strict stale/capture分支、target/recovery模块函数逐字提取进离线C++依赖桩。使用真实TargetProfile/RecoveryTarget/SampleClock头文件。只替代时钟、传输、参数与发布依赖，不导入runner或启动PX4。 |
| 代理自身 | 4 ms，22步88 ms延迟，q指数端点更新，p/v梯形离散更新，逐轴clip；固定外部target-yaw FLU坐标。空历史从第一实际生成目标所形成的e/d开始，启动不足22步时重复最早样本。它不是native同名FIFO、不是P9 8 ms预测器的精确重采样，也不是连续系统精确采样。 |
| 实际系统接口 | p/v取命名估计器状态，q按P9几何态度代理定义，历史由所映射状态和实际目标确定重建。GRU、previous action、推力/电机、估计误差、坐标/数值差异等影响进入离散残差w及输出/时钟条件，不能默认为0。无需把GRU等同于FIFO；但严格误差条件必须另证或被数据拒绝。 |

第三层的明确映射允许用日志反驳适用性；它并未证明真实机体加速度等于q。高度、全任务代价及真实采样间姿态独立于这些结论。

## 输入来自启动源码和已记录状态

主配置是已见的 **P9 dev-01**：1.8 m/s、NED轴 `[.965925826,.258819045,0]`、RTGT0/RTDEC2/RREC0、三次中断 `[0,.36]、[.66,1.02]、[2.24,2.6]`，其全部reposition、hold/ramp/cruise、末段减速/保持和5 s post-stream均保留。没有删除事件、缩短后段或换小静态例。

最终输入 [source-08](../data/p10-20261025-a3/source-08) 绑定原`p1_reference_origin`：

```
origin NED = (0.0269325338, 0.00996312127, -2.95094204)
yaw        = 1.6767029762268066 rad
首确认外部read = 53712000 us
其前一推理状态 = 53708000 us，active=1，stale=1，无本拍外部更新
命名local-position和attitude样本均为53704000 us
profile-start native bound = 53716000 us（已晚于首read，不能冒充stream t0）
```

传感器中心的NED p/v、四元数及其FLU映射都存入 [startup-observation.json](../data/p10-20261025-a3/source-08/startup-observation.json)，由旧ULog命名字段重建；没有将缺字段填0。该实际记录保证源侧观测中心非空。其附近有限横向位置/姿态观测也是源码允许的输入；**不声称真实闭环必然产生每个扰动成员或都满足w条件**。

此前离线候选`source-03/04`用了零origin/yaw；`source-05/06`虽绑定真实origin/yaw，但用了profile bound处已读流的观测。它们不能作为最终pre-stream绑定，完整保留并在差异账本拒绝。最终改用首确认read之前的实际观测，未调整相位或容差挽救证书；最早证书失效仍发生在首捕获。

声明时序是源码允许的callback/read/gyro子类：stream profile从0起，4 ms一次callback，执行原`start_stream`的浮点最小发送间隔及gap跳过/出口立即发送，再由同刻native读取。**没有手写20 ms理想发布器**；源比较可能产生20/24 ms间隔。真实runner普遍精确周期、历史monotonic t0与native epoch的精确对应均未证明。这个条件子类不等于重放旧飞行的所有实际时间。

RAPTOR激活后、首stream之前的模块状态由实际stale/active观测和源码reset/capture规则约束。离线prelude核激活捕获及其后的模块不变量：RTGT0、持续active且无fresh消息时，目标保持原capture；RREC0排除START，初始恢复inactive。5 s期间body/GRU演化不由代理虚构，prelude的压缩两点仅用于模块不变量检查，**不充当5 s机体/代理历史或计时完备性证明**。当前代理真正起点在声明stream状态，FIFO空；此前未知控制器影响通过初值和后续残差接口保留。

## 单一来源参考及独立oracle

[source.py](../tools/p10a3/source.py)隔离runner原函数，并将native以下片段按原文放入无SITL C++程序：有效字段读取、read时钟赋值、完整stale/fresh两分支、捕获reset、target/recovery transition。真实SampleClock在这些transition之后调用，duplicate不能撤销已发生的capture。RREC>0积分函数来源保留，但主类RREC0，不宣称覆盖全部恢复分支或额外START。

每行保存source输入、实际读取/保持目标、read-age、guard、capture/reset、armed、sample拒绝和顺序；另外记录源四元数与q输出lift。独立Python适配器核位置/速度/guard/模块标志；C++重放核包括yaw在内的实际输出。捕获p来自同一body输入，未换成自由跳后球。

完整7350行，profile 0…29.396 s，即首gap前12.895 s至其后16.501 s，最后一行是N→C边界；不证明随后classic返航/降落。源计划stream时长24.395 s，包含原末保持6 s；末次`native_bound_streaming` callback后在24.396 s停流，post-stream完整5 s。主事件：

| profile s | 事件 |
|---:|---|
| 0 | 首实际读取替换此前stale目标；RREC0无START |
| 13.096 / 13.256 | 首超时捕获 / 接回 |
| 13.748 / 13.916 | 第二捕获 / 接回 |
| 15.332 / 15.496 | 第三捕获 / 接回 |
| 24.596 | 末停流超时捕获 |

每次age=200000 us仍fresh，之后下一允许4 ms拍才stale。接回不清代理历史。末段及多事件完整保留，不能拿名义全段输出当全集合证明。

旧−5.002反例亦通过**同一原始`p1_profile`**在`tr−.002`求值：沿线Δr=10⁻⁶ m，v=−10⁻³ m/s，正确保留reposition尾部，而不是旧A2的恒定参考。

## 初始化与严格前缀拒判

令固定记录yaw的FLU横向轴为l。初始集合为实际观测中心加

```
p_l += .01*z_p，q_l += .1*z_q，|z_p|,|z_q| <= 1
v及其余坐标在记录中心；初始P余项半径 R0=1e-9
```

R0仅覆盖初始二进制映射/减法表示，独立精确核验其P范数上界约3.99e−15，未用它吸收未知控制器误差。源浮点可表示成员被该集合覆盖；不要求所有实数成员都恰为uORB float。初始e/d由**首次实际源目标**与当前body计算；启动不足88 ms时复用这个最早样本。47维扩维状态为`[p_l,v_l,q_l,e_(k−1),d_(k−1),…,e_(k−22),d_(k−22)]`，其最初22槽是启动填充，不是假想物理前史。共享z参数保留关联。

先固定这些源输入和初始化，再对原冻结模型横向kp/kv求新的P候选，未缩放旧P或调整物理域。独立有理数审计核：

```
.5 I < P < 30000 I
P - A(rho)' P A(rho) >= .5 I
rho = exp(-.05)，Taylor有理数区间两端核验，矩阵凹性覆盖整个区间
|E_p|²<=.00015 V，|E_v|²<=.0008 V，|E_q|²<=.4 V
sqrt(P[3,3])<5.5，sqrt(P[4,4])<5
```

新P的P[3,3]≈29.17246，不能沿用A2的5.4；5.5由严格列范数检查得到，不是放宽w。每步中心/两个生成元的差分残差合成P上界均≤10⁻⁸；R递推为`R+=5.5*目标位置误差+5*目标速度误差+10^-8+10^-7`，最后一项仍是**待兼容核查的旧条件**。初始及每前缀误差界严格核clip，只有未饱和时才应用该A。

结果：**3274个横向未饱和前缀**覆盖整个初始参数盒及声明扰动类。首捕获profile13.096 s、相对首gap .201 s时，T0将目标速度置零；集合的固定记录坐标横向速度误差严格位于：

```
[1.790328317381, 1.790349205627] m/s
R = 360141/10^9
```

下界平方大于`2*(cos(yaw)^2+sin(yaw)^2)`，故几何水平速度范数严格大于√2。无论捕获yaw如何，两个正交native速度误差分量不可能同时都≤1；**至少一个clip轴越域**。这是整个非零初集的必要域反证，不是取单条名义轨迹；native有限精度/输出外推仍属第三层接口。失败点之后不再用未饱和矩阵，位置reset后的全管也不宣称已证。输出 [audit-09](../data/p10-20261025-a3/audit-09/audit.json) 给出精确分数及域拒判。

全段带clip的名义轨迹仍独立复核离散更新残差，但后续集合结果为UNKNOWN。数值扫描没有承担区域证明。P9原域越界、原A/A2反例、共同严格扇区收缩的单位特征值障碍继续保留；这些均不证明系统倾角必败或所有Lyapunov方法不可能。

## 旧误差及时钟包络的兼容性

[compatibility.py](../tools/p10a3/compatibility.py)只读P9 dev-01旧ULog。p/v和target沿P6已核重建链；姿态按`research_timing.attitude_sample`精确匹配，禁止用不存在的中间态或缺字段0代替。只取连续24个4 ms样本、target-yaw不变且全部匹配的窗口，使22步延迟和下一步状态确定。

若A2 `||w||P≤10^-7`，必有`|w_q|≤sqrt(.4)*10^-7<.633*10^-7`。7196个可检查步骤**全部**违反这一必要条件。首反例：

```
sample 53800000 -> 53804000 us（距profile native bound 84000 us）
attitude samples 53796000 -> 53800000 us
q 0.048517093158193414 -> 0.04989637139524809
延迟clip(e)=0.00952804120943304，clip(d)=-0.018169238421605925
w_q≈0.0029981754082312293；最大 |w_q|≈0.14499322687658459
```

独立验证器对首3条及最大3条、共6条portable反例，从存储四元数与二进制三角系数重算有理数几何映射及rho区间，给出严格残差下界，远离舍入歧义。7196/7196是全样本诊断统计，不是连续区域证明。该反驳针对**明确的日志估计器/姿态代理映射**，不是未观测真实加速度；也不证明所有别的源码状态子类均空。经验最大残差没有被升为新硬界，未扩大w以获得通过。

实际推理样本全为4 ms；但确认为成功读取须同时满足active、subscription updated及`last_read==native status.timestamp>0`。inactive/invalid subscription或重复日志不能冒作时钟异常。日志证实范围不足以证明A3精确callback/read相位。目标数值范围可支持binary32 cast ULP前提，却不能把EP/EV解释为发布时钟或参考运动差异的包络。每消息的monotonic profile时间不能从稀疏事件精确恢复，记为不可查。

源侧四元数lift与代理q在名义全段有约6.58e−7的数值差异，显式记录在审计中；它是输出映射诊断，**不是w创新或严格集合误差界**。不把代理q指数插值当真实采样间倾角证明，也不把p/v梯形与q插值混成全状态连续流。

## 分项关卡、具体决策及下一步

| 关卡 | 结论 |
|---|---|
| 源码参考、guard/reset、初始化规则 | 声明有效传感器/调用子类内闭合，原函数/原分支逐步对照；实际历史monotonic精确对齐仍条件性。不是整个native控制器的形式化等价。 |
| 代理全段非零集合证书 | 未通过；严格前缀到首T0捕获，随后确定越未饱和域，饱和段UNKNOWN。 |
| 实际误差/clock接口 | 指定P9映射反驳旧w条件；4 ms数据存在，但精确相位和真实输出硬界未验证。 |
| 可用测试/修复准入 | 当前可算输出为拒绝此未饱和证书及旧w接口的套用。没有覆盖完整源码序列的安全准入或修复族。 |
| 总关卡 | **NOT_PASSED，B/C/D0。** |

最早实测接口失效是首个可对齐窗口53.800 s（profile bound后.084 s）；这是可检查窗口最早反例，**不是宣称更早步骤都满足界**。声明代理证书最早失效为profile13.096 s；两种时钟与结论不混淆。

新增能力在于：输入可追溯到原始启动函数和真实前读取状态，FIFO启动可检查；能对非零集合给出前缀截断域反证，且能用必要坐标界独立拒绝旧数据适用。相比单条回放，集合结论对所有两个参数及扰动全称成立；相比A2，避免靠假想历史和静态参考取得标签。尚无减少真实测试成本或改善修复的证据，不降为排序。

下一步仍值得有限的离线机制研究：保留本三事件/暖机/后段，研究T0捕获后的分段/扇区或多模式管；旧w量级已不适用，应先研究结构化、可证明的动力学/输出误差接口及状态相关域，再判断是否有非空实用类。不能单纯按经验最大残差放宽，不能换小例或删除首捕获。RTGT2/RREC>0可在相同源码接口下另行研究，但当前失败不能由新处理的结果替代。第二平台需重核源片段/依赖、原函数、实际初始样本/坐标、两个时钟和误差接口，再重证P及所有模式；不能搬数字宣布通过。

## 审计、复现、保存与发布

代码：[source](../tools/p10a3/source.py)、[生成器](../tools/p10a3/generate.py)、[兼容检查](../tools/p10a3/compatibility.py)、[独立验证器](../tools/p10a3/verify.py)、[计算关系测试](../tests/test_p10_a3.py)。独立验证器不导入生成器或诊断器；复用旧精确矩阵的PD和A构造基础，新的P不等式、初始化、差分、源重放及数据反例另核。C++oracle与适配器共享原始参考这一单一来源，分支缺失、错误guard、样本时钟和数值变异由独立对照测试识别；没有以两个同构手抄参考互相证明。

```bash
uav_lab/.local/venv/bin/python tools/p10a3/generate.py --actual --output /tmp/p10-a3-source-new
uav_lab/.local/venv/bin/python tools/p10a3/compatibility.py --output /tmp/p10-a3-data-new
uav_lab/.local/venv/bin/python tools/p10a3/verify.py /tmp/p10-a3-source-new --compatibility /tmp/p10-a3-data-new/compatibility.json --output /tmp/p10-a3-audit-new
uav_lab/.local/venv/bin/python -m pytest -q tests/test_p10_a.py tests/test_p10_a2.py tests/test_p10_review.py tests/test_p10_a3.py
```

独立复现目前需要本机原ULog、Lab源只读核验及g++；远端已发布portable源片段、命名观测、四元数反例和全部输入输出哈希，但不能声称远端缺原ULog时已独立重查其原始采样关联。第二平台复核需按原哈希取得这些只读输入或明确将原始关联记为未复核。

详细失败/差异账本、复现、测试与资源成本、旧文件未变性及发布回执见 [A3交付清单](../data/p10-20261025-a3/delivery.json)。开发中漏fresh分支、布尔transport输入、8 ms诊断假设、输出路径和候选初值绑定错误全部记录保留；这些是离线程序修正，没有修改冻结协议、启用停批续跑或发生新飞行基础设施异常。源oracle仅编译临时依赖桩程序，未改Lab/PX4/策略/安全保护。

P9的173正式启动、169主测量、102缺失、162诊断、164/169证据拒绝、v4停批后续跑流程偏离均保留，不包装整体PASS。提交只含A3新文件，正常push main，不force；远端和实际CI结果据回执报告，不把没有CI结果称为CI通过。

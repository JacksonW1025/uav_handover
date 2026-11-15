# PX4 RAPTOR 交接分类：代码与证据核验

日期：2026-11-15。对应[四类分类原文](HANDOVER_PROBLEM_TAXONOMY_20261115.md)，原文固定提交`0a88c03c4775f44b40f9734d3cfcaff13aa7e310`，此次未修改。以下按独立起因组织历史观察和新增验证，不把构造数值计作实飞结果。

## 证据状态总览

|类别/案例|观察与验证状态|仍缺什么，不应声称什么|
|---|---|---|
|T1旧紧弯两例|原始日志复核>50°；越线前两秒参考与物理应用正常|仍有历史/早期接续混杂，非完全隔离单因|
|T1新轻度制动C/N|两个真实新启动，均正常结束，未得到预期反例|负结果保留|
|T1新同步紧弯C/N|25.4626°/43.6290°；35°测试预算仅N越过，原45°均未越|首实际N动作参考匹配；更早一轮零目标内部推理仍使T3未完全排除|
|T2初始化/影子历史|历史干预和闭环输出，部分原始ULog独立复核|P3/P4原始日志与逐命令应用证据不足|
|T3初始空窗|历史F1三臂重复、近似初态、实际四电机审计|同seed局部机制，不是普遍因果证明|
|T3活动超时/恢复|历史实际事件与目标语义对照|022/023非严格同初态；P5为主动发送间隙|
|T4发布者回跳|历史ULog记录交替发布异常|缺同事件四电机消费与危险后果证明|
|T4下游旧命令保持|历史活动期间四电机物理步时效异常|非隔离的危险接管反例|
|T4源抽取组件|新增无飞行、显式callback延迟对照|只证组件语义，非默认故障|
|T4真实Gazebo单转子|新增两臂固定台架，注入额外8ms且实际物理步核实|无PX4、无飞行器、单转子；主动注入，不计作自然危险飞行|

本次新增飞行为T1四次，全部确认落地、disarm和进程退出；T4组件及固定台架不计为飞行。历史案例只复核，不重复计新增次数。完整证据仍按各自版本解释。

## 源码身份与共用执行链

分类原文固定于 `0a88c03c4775f44b40f9734d3cfcaff13aa7e310`，基线研究接口固定于 `ddeaddd2213fb8e79d6d008f2c26d7cd82cf52e2`；两者都不能替代历史飞行的候选身份。下表PX4行号指上游 `4ae21a5e569d3d89c2f6366688cbacb3e93437c9`，标为“基线”的行号才指本仓库。

|阶段|固定路径与行号|数据如何继续传递|
|---|---|---|
|模式请求|基线 `tools/run_experiment.py:223–227`；PX4 `src/modules/commander/Commander.cpp:1077–1087`|command100001携带目标nav状态，Commander调用模式意图并回复接受或拒绝|
|准入与实际模式|`src/modules/commander/UserModeIntention.cpp:44–89`；`Commander.cpp:2501–2542`|canRun等检查与仲裁产生实际nav_state；ACK不是电机交付完成|
|控制标志|`Commander.cpp:2761–2777`；`ModeUtil/setpoint_types.cpp:44–53`|当前模式对应setpoint类型生成vehicle_control_mode；DirectActuators不启用经典控制标志|
|神经路径|`src/modules/mc_raptor/mc_raptor.cpp:514–534,572–613,768–803,344–412,864–894`|进入/初始化→参考接受或缺参考捕获→状态观测和历史→策略计算→动作映射和电机发布|
|经典路径|`src/modules/mc_pos_control/MulticopterPositionControl.cpp:615`；`src/modules/mc_att_control/mc_att_control_main.cpp:376`；`src/modules/mc_rate_control/MulticopterRateControl.cpp:264`；`src/modules/control_allocator/ControlAllocator.cpp:366,744`|位置→姿态→角速→力矩→控制分配器；分配启用标志控制其发布|
|基线仲裁与owner记录|基线 `research/state/ActuatorGate.hpp:11–19`；`patches/raptor-final.patch:604–619`|共享锁核对最新allocation标志；发布后记录owner及消息时间，不是物理应用记录|
|输出与仿真桥|`src/lib/mixer_module/functions/FunctionMotors.hpp:62–79`；`src/lib/mixer_module/mixer_module.cpp:421–446`；`src/modules/simulation/gz_bridge/GZMixingInterfaceESC.cpp:65–90`|消息消费→输出功能和安全限制→Gazebo motor_speed消息；之后仍需各电机物理步消费证据|

因此应分别记录请求、ACK、nav_state、配置/flags、神经active、命令发布、桥发布、四电机应用和物理响应，不把它们合成一个“切换完成”时刻。原基线RINI为布尔保留开关，后期实验为多值模式；原基线没有后期四电机物理步审计链。

### 022/023与F1的实际运行身份

本次只读核查 `data/handover-mutation-20261111/{022_active_timeout_rtgt1-a1,023_active_timeout_rtgt2-a1}/candidate-before.json`、`candidate-after.json`及各自`flight/metadata.json`，并对照F1冻结归档 `cbaf3a53914efe26b2e00444f56f16935b760a27` 中 `data/handover-f1-sync-20261112-analysis-v1/source-identity.json`。两例运行前后candidate完全相同，metadata中的未跟踪源码哈希清单与candidate一致。两例与F1以下身份完全匹配：

- 研究仓库HEAD：`003cd249a0b1baa3ad78a25c18473657af39aa70`。
- PX4上游HEAD：`4ae21a5e569d3d89c2f6366688cbacb3e93437c9`。
- PX4 tracked diff SHA-256：`1713e9cfce597fb97bca1552c57805b62cbd14c7371b6a14f09d5220640218e7`。
- PX4二进制：`61d1d45fa2a8744874d6dece259f40735e70f00021e0cda7d93e5622ec20bc48`。
- 电机研究插件：`21211d96e9d929b3d3f5a6dea32ba4d319dca82b353617105cefde4cc6fb58ea`。
- 策略：`5327c83dc57f094ca1977a2533ebce318645be010e16b9354c96c337cd5c278b`。

同时核对Thor现存源码HEAD与上述diff一致，`mc_raptor.cpp` SHA-256为 `f6081a683ea77e327aca64608501c342970b8d173a60b8571a8fc2f9bfcfe7e5`，与F1记录相同。因此可用F1修改后源码定位022/023的共同控制逻辑，不必误套早期基线补丁行号。修改后版本参考接收位于829–857行、捕获逻辑1051–1089行、观测/推理1130/1140行、动作映射及发布1239–1290行。上表上游行号和这些修改后行号必须明确区分。

022原始ULog记录哈希为 `c6ae7d7133554050219e7cbab653a14693f5281534f2e5358513ed4e4f7fd204`；023为 `d3816469c53190862d1e5a932568d4f35b28f813121441981ff4fa9eed35fedd`。这次身份检查没有重放或重建二进制，也未仅凭身份一致断言两例和F1是相同实验：runner、参数、参考时序、入口和控制器历史仍需逐例核对。F1源身份摘要未逐项列出所有未跟踪文件的哈希，因此这里只声称对应显式身份字段匹配，不声称摘要本身足以逐文件证明所有源码相同。

## T1：接管后神经控制器安全裕度不足

### 结论与证据状态

分类依据为仓库根目录 `HANDOVER_PROBLEM_TAXONOMY_20261115.md`，固定提交 `0a88c03c4775f44b40f9734d3cfcaff13aa7e310`，不是沿用旧 X/H/P 三分类。

目前找到并从原始 ULog 重新核实了两条最有价值的 T1 候选：运动中交给神经控制，以及提前进入神经后执行相同紧弯。二者分别达到 51.068°、50.121°，全经典同路径为 29.909°。其活动窗没有参考 stale 或 invalid 增长，首个神经命令按正常一物理步延迟被四电机消费。这说明连续参考、模式准入成功和电机正常接收命令，并不自动保证后续机动留在原安全包络内。

**这两条是已观察到的真实风险候选，不是已隔离的单因 T1。** 原因具体：运动切入仍采用默认历史 reset；提前神经改变了运动历史和入口；尚无保持运动、参考与历史准备不变，仅增加安全余量的对照。已有紧弯时间尺度扫描改变运动需求，不等于增加同一恢复过程的空间余量。

### 1. 真实情况一：运动中接管，末段倾角越线

原始运行：`data/handover-explore-20261110/tight_turn_1p8-a1/flight/`。

- 轨迹：50 Hz 连续共享参考，经典 OFFBOARD 起始；平面五次插值紧弯节点为 t=0 原点、t=2 (2,0)、t=3 (3,1)、t=4 (2,2)、t=5 (1,1) 后保持；节点速度最高1.8 m/s，不代表全过程恒速。t≈2.5 s 请求 RAPTOR。
- 神经 owner 首发布 51.484 s；四电机均在 51.488 s 应用相同首条 sample，正常4 ms物理步延迟。
- 首发布前观测：p=[2.819284,-0.013503,-3.047745] m；v=[1.582201,0.664681,-0.137433] m/s；q=[0.643391,0.160576,-0.048757,0.746918]；角速度=[0.511686,-0.455166,0.018381] rad/s。各状态最后样本年龄显式记录，最大7.999 ms。此z是局部NED高度口径，不能直接称精确离地高度；dist_bottom_valid=0。
- 首秒最大倾角40.621°，前2秒43.406°；首次>45°为54.020 s，即owner后2.536 s；保护前主体峰51.068367°。它在后续紧弯/刹停处越界，不是接管第一帧直接翻倒。
- 主体最低局部高度约2.789 m、相对失高约0.260 m；这条实际触发的是倾角线，不是撞地或大幅失高。
- 参考发送最大间隔23.983666 ms。独立重读ULog，在51.484–54.088 s取652条P11记录：stale计数0、invalid累计增量0，326次native步。第一速度输入分量出现110个绝对值≥0.99999样本，另外两分量0；这是输入边界现象，不单独认定裁剪为根因。
- 首发布前后模块实际目标位置、速度保持相同：[2.761674,0.268795,-3.004670]和[0.984518,1.186290,0]。持续共享参考不等于进入reset那一刻从未捕获，激活阶段仍需要单独核验。
- 首次发布四电机命令从[0.749907,0.728676,0.750955,0.744190]变到[0.332263,0.510400,0.271091,0.605283]，最大单路阶跃0.479864。后续命令范围约0.188–0.972，没有达到冻结连续饱和门限。
- 发过正常LAND请求，但落地/disarm未确认；保护后尾峰52.323°不混入主体峰。

复核文件：`data/handover-explore-20261110-final-v1/19-tight_turn_1p8-a1-flight.json`、同名`.trajectory.json`、`tight-turn-three-way-evidence.json`，原始`flight.ulg`及`gz-motor/motor-{0,1,2,3}.bin`。

ULog SHA256：`e0c55fa9408e54ddb80e9e01f66e0c8462fdf5aacb22526ca22070ce0236de9f`。本次重新读取文件计算SHA与原记录一致，并从四元数重算上述峰值和首次越线时刻。

### 2. 真实情况二：先稳定进入神经，随后同轨迹仍越线

原始运行：`data/handover-explore-20261110/tight_control_raptor_preentered-a1/flight/`。

- 在悬停参考中正常C→N，等待3 s才开始同一紧弯，排除了“必须在运动中切入才触发”的解释。
- nav进入48.772 s；神经发布48.784 s；四电机首应用48.788 s。
- 进入前p=[0.014551,-0.017403,-2.995656] m，v=[0.004990,0.009221,-0.002682] m/s；角速度=[0.001269,0.000690,-0.003357] rad/s。进入后首1秒倾角峰仅1.818°。
- 紧弯profile开始52.168 s，首次>45°为56.672 s，即profile后4.504 s；保护前峰50.121262°。最早45.176°短峰只有24 ms，回落后再越线才触发在线保护。
- 本次重新读取52.168–57.320 s原生窗，1289条P11 stale=0，invalid增量0，644个native步；速度输入第一分量边界110个样本。
- 这条证明神经接管后的后续轨迹响应也是研究对象；不能由提前进入的成功悬停推断紧弯安全。
- 正常LAND已请求，落地/disarm未确认；保护后51.637°另列。

复核文件：`18-tight_control_raptor_preentered-a1-flight.json`、`.profile.trajectory.json`和`tight-turn-three-way-evidence.json`。ULog SHA256：`dce59e2570fab4b8121891b657fc6f82579818c51180fee27e34cad3c9fe9cdd`，本次重新核对一致。

经典对照：`data/handover-explore-20261110/tight_control_classic_only-a1/flight/`；峰29.909451°、确认落地disarm；ULog SHA256 `f24943e86600c060de4ea90a6783327d24d0d985eb7306755a1241f55f0e780e`。它是同设计路径、独立运行，不是同一完整状态快照分叉。

### 3. 独有数据流与实际飞行代码身份

这三次metadata共同固定：

- PX4上游提交 `4ae21a5e569d3d89c2f6366688cbacb3e93437c9`；项目HEAD `003cd249a0b1baa3ad78a25c18473657af39aa70`。
- PX4工作树研究差异SHA256 `1713e9cfce597fb97bca1552c57805b62cbd14c7371b6a14f09d5220640218e7`。
- 实际PX4 binary SHA256 `61d1d45fa2a8744874d6dece259f40735e70f00021e0cda7d93e5622ec20bc48`。
- policy SHA256 `5327c83dc57f094ca1977a2533ebce318645be010e16b9354c96c337cd5c278b`。

本次只读核对当前Lab的 `git diff --binary` 与binary，均与以上历史SHA完全一致。因此下列行号指实际研究补丁后的源文件，而非把上游未打补丁行号冒充飞行版本。

共同代码前缀：`uav_lab/.local/checkouts/px4-raptor/`。`src/modules/mc_raptor/mc_raptor.cpp` SHA256 `f6081a683ea77e327aca64608501c342970b8d173a60b8571a8fc2f9bfcfe7e5`。

|环节|实际源码行|意义|
|---|---|---|
|正常请求准入|`src/modules/commander/UserModeIntention.cpp:44–89`|查询canRun、禁止退出termination。不是预测这次机动最低高度或未来峰倾角。|
|模块激活|`mc_raptor.cpp:687–719`|nav对应注册模式，发布DIRECT_ACTUATORS配置，进入reset和历史模式。|
|参考接受|同文件829–857|所有位置/速度/yaw/yawspeed有限才更新实际目标及last-valid时间。|
|物理估计进入模块|同文件960–965|从局部位置消息取得位置和速度。|
|T1核心物理输入通路|同文件497–547|姿态转到目标系；位置/速度相对目标变换并逐轴裁剪；角速度、上一动作进入观测。|
|输入裁剪配置|`mc_raptor.hpp:154–155`|位置误差默认0.5 m、速度误差默认1.0 m/s；不是倾角保护。|
|策略闭环|`mc_raptor.cpp:1130–1140`|observe之后rl_tools::control生成策略动作。|
|实际命令|同文件1239–1290|动作映射、编号重排、原ActuatorGate仲裁、发布及owner记录。|
|参考连续编排|`tools/handover_explore/runner.py:17–35,38–56,59–69`|同一50 Hz流跨正常模式请求；提前N在轨迹开始前等待3 s。|
|紧弯与两对照|`tools/handover_explore/design.py:34–52,54–68`|相同节点/插值，切换时机不同。|

T1的独有起点不是某个消息失效分支，而是“实际状态+任务要求+剩余空间/姿态余量，与接收闭环恢复需求不匹配”。传播链：运动估计→相对目标观测→神经动态响应→电机→轨迹偏差消耗安全余量。上述观测使用相对目标位置，未直接提供离地余量；不同高度但相同相对运动可能产生相近输入。这是值得验证的机制，不等同于已证明本例由高度盲区造成。

固定上游参考链接仅用于理解共同语义，不替代上述实际补丁版本：
- [观测构造](https://github.com/PX4/PX4-Autopilot/blob/4ae21a5e569d3d89c2f6366688cbacb3e93437c9/src/modules/mc_raptor/mc_raptor.cpp#L344-L412)
- [模式准入](https://github.com/PX4/PX4-Autopilot/blob/4ae21a5e569d3d89c2f6366688cbacb3e93437c9/src/modules/commander/UserModeIntention.cpp#L43-L89)

### 4. 已有补充与尚缺的隔离对照

`data/handover-tail-20261111-analysis-v1/FINAL_REPORT.zh.md`记录十轮紧弯/Mission：全经典10条通过，紧弯15条越线；整体放慢15%/20%的已测紧弯均通过，整体放慢10%仍有相位3.2达到46.29°。这些加强“运动相位与机动需求影响风险”的线索，但改时间尺度同时改变速度、角速度和进入历史，不是单独提高安全余量。

|T1隔离项|当前状态|
|---|---|
|真实失败轨迹|有，上述两条原生日志与首电机链|
|相近任务全经典|有，同一轨迹，不是完整同态分叉|
|完整参考|活动主体窗有连续有效读取；进入reset早期仍应单列|
|历史相容性|原reset或提前N自然历史，未做固定物理入口的历史排除|
|下游应用正常|首命令四电机正常4 ms应用；不代表逐条命令均执行|
|同运动、同历史/参考而增加余量|缺失|
|单因T1完整案例|待补上述隔离项，不把T3的069/F1改名充数|

### 6. 本轮新增两次轻度制动：真实完成，但不是T1反例

上节“未启动”是补飞前检查记录；随后协调取得独占槽，已实际完成C/N两次SITL，未重试。目录 `data/handover-t1-margin-20261115-v1/`，飞行前已有 `PLAN.zh.md` 和 runner SHA；独立结果在 `analysis-v3/`。

|项目|继续经典C|正常接管N|
|---|---:|---:|
|触发时NED下降速度|0.4992m/s|0.4863m/s|
|触发后最大下降|0.271440m|0.274599m|
|全受测窗峰倾角|0.29275°|0.95511°|
|预定虚拟0.30m余量越线|否|否|
|预定虚拟0.60m余量越线|否|否|
|落地/disarm/所拥有进程退出|均确认|均确认|
|实际执行墙钟|75.550s|75.066s|

入口位置差0.08498m、速度向量差0.03415m/s、姿态差0.21678°、角速度差0.01434rad/s。两次都是4m名义起飞、约3m高度触发，小幅连续下降制动。没有为制造反例把0.30m平面事后缩小；经典和神经都容纳在预定余量内。这是一个明确的已测可恢复点，而不是危险条件。

H准备在两次触发前1s均记录125/125个native步骤teacher_forced，entry_mode=4。N激活的GRU范数1.7311、previous_action约[0.46356,0.46332,0.46346,0.46377]，已不是清零历史。仍要注意该准备对应经典发布身份，不能把所有历史自动宣称等于完整物理执行快照。

**具体隔离缺口：连续50Hz发布没有消除进入时的零速度捕获。** N激活52.356s清参考有效位，last_valid_read=0，实际速度vz≈0.48655但目标vz=0；52.368s首神经发布仍采用该捕获目标；四电机52.372s真正应用首条sample52.368s，其命令为[1,1,0.98630,1]。首条新完整参考也在52.372s才有效读取，故首个实际动作确实来自旧捕获计算。stale持续16ms、共4个P11记录；不是传输停止或人为断流。随后恢复正常，没有倾角或虚拟余量越线。此链是T3交叉观察，不能把该对照写成参考完全正确的纯T1。

恢复按实际神经P11目标和原冻结条件重算，进入联合回稳0.728s，随后2s连续确认；主物理安全窗通过。原始config继承了旧Mission文本字段及fixed reference注释，实际运行以本轮`t1`/`explore`和事件、参数为准，不把旧文字当新场景；原config保留，报告说明该来源。分析v1因read_trace返回值处理失败，仅写C曲线；v2误传恢复参考标记；均保留，v3修正为incoming=1的神经实际目标口径，作为最终结果。

复核：`analysis-v3/measurements.json`完整初态、首次计算、history rows、四电机实际应用；`matching.json`初态差；`C-curve.csv`、`N-curve.csv`；`margin-comparison.png`。`attempts.jsonl`恰有两个START_INTENT和两个END。没有新增物理模型、没有修改PX4、没有放宽监视或改变策略。

### 7. 原始紧弯首次越线前的连续两秒：正常数据链仍消耗倾角余量

补充原生重算明确使用两个窗：运动切入 `[52.020,54.020]s`、提前N `[54.672,56.672]s`，末端均为第一次>45°。每个窗恰有501条P11记录、250个native策略步；全部active，stale=0、invalid正增量=0、activation=0、250/250步GRU提交，最后有效参考年龄最大20ms。每个电机均501个连续物理步，最大步间隔4ms、应用命令年龄最大4ms；每步applied_sample与神经owner1发布的actuator_timestamp精确对应，没有经典来源混入、缺尾或身份无法对应。

这把“连续参考下也危险”细化为：**首次倾角越线之前，至少已有连续两秒正常神经状态演进、完整有效参考和按时实际命令交付；危险出现在紧弯最后两段的神经闭环响应中，而不是越线前刚发生断流或输出滞留。** 这是T1晚阶段候选的直接支持。两秒连续运行不自动证明GRU已经忘记所有较早初始化差异，也不构成同态分叉；完整单因定论仍需对应排除项。

复核为本轮新增只读脚本 `audit_t1_archived.py` 与 `archived-late-window-audit.json`，同在 `data/handover-t1-margin-20261115-v1/`。旧原始数据未修改。

### 8. 第二对：较干净的共享参考下，神经消耗更多倾角和高度余量

新目录 `data/handover-t1-turn-20261115-v1/`。飞行前固定两次，C后N，复用紧弯整体时间尺度1.15，4m起飞，phase2.875s触发。共享发布器目标250Hz，实测最大发送间隔C8.224ms/N8.461ms，因此称“更高频共享参考”，不冒称每包精确4ms。保留原策略、RINI4准备、准入及45°保护。

35°在本次计划中预先声明为**测试轨迹姿态预算**，不是摄影设备真实要求、不是新的飞行安全标准。45°始终保持原保护与原研究物理安全线。同一轨迹用35/45两个预算观察，不算两次不同飞行。

|项目|经典C|神经N|
|---|---:|---:|
|受测窗最大倾角|25.462627°|43.629021°|
|35°测试预算|未越线|55.288s首次越线，触发后2.772s|
|45°原线|未越线|未越线|
|触发后最大下降|0.071367m|0.267690m|
|最低局部高度|3.938592m|3.742415m|
|正常落地/disarm/进程退出|均确认|均确认|
|执行墙钟|85.0808s|85.0810s|

C/N入口位置差0.015997m、速度向量差0.031610m/s、姿态差0.128576°、角速度差0.006890rad/s。N从[1.34162,0.61481,−0.07259]m/s的运动状态进入。在相近入口和同一参考路径下，神经峰值比经典多18.1664°，相对原45°的最小倾角余量由19.5374°减少到1.3710°；35°测试预算只被N耗尽。这一对是明确的**接管后闭环响应消耗更多余量**的观察，原45°标准下仍是两条已测安全完成的轨迹。

#### 首个实际命令对应哪个参考和历史

- 激活52.552s，entry_mode4、entry_result1；GRU进入前后逐项最大差0。previous_action=[0.481312,0.490565,0.452720,0.492324]，逐项等于记录的classic_action；其身份为sample52.548s，四电机在激活52.552s的物理步正应用该sample。前1s有125/125个teacher-forced native步骤。
- 首条有效新参考在52.556s读取。首个真正发布并被应用的神经动作来自52.560s的native推理，该次stale=0、有效参考年龄0，目标位置/速度六个float32字段精确匹配发送id894（profile=2.925944s，目标位置[2.824386,0.274317,−3.984830]、速度[0.839369,1.046836,0]）。yaw/yawspeed由同一共享发生器保持完整，并通过模块有限性检查。
- 首神经发布52.564s，四电机均52.568s应用sample52.564s，四路身份与4ms应用延迟正常。
- **残余差异仍如实保留：激活52.552s曾有一轮stale=1、零速度捕获的native推理，当时电机仍由经典控制。** 这轮推理虽然没有作为首实际命令直接施加，仍可能改变循环状态。下一条有效参考在4ms后到达。因此本轮满足“首实际神经动作采用及时完整参考”，但不满足“进入后的所有内部计算从第一轮起绝无参考捕获”。不将这一点隐去，也不把本轮包装成严格单因隔离。

#### 超35°之前的晚段过程

在第一次越35°前整两秒 `[53.288,55.288]s`：stale=0，251个native步骤，无再激活，最后有效参考年龄最大8ms；四电机连续4ms物理步、应用年龄最大4ms，每步均匹配owner1发布身份。没有越线前突然断流或迟交付的证据。N在末段出现更大的倾角回摆和短时下降，之后自行恢复；按实际神经目标的原冻结联合恢复进入时间5.396s，2s连续确认完成。

此处最稳妥且有内容的表述：**同一机动从经典交给神经后，即使首实际动作已经采用完整及时参考、历史按实际经典动作准备、下游按时交付，后续姿态响应仍可能明显耗尽更窄的任务余量；现有例子在35°测试预算下显现差异，在45°原安全线内完成。** 严格排除更早一轮参考捕获对GRU的影响，是后续最小隔离工作，不需要通过更猛烈轨迹制造坠毁。

### 9. 交付与实际成本

本轮共4次新增SITL（2条经典对照、2条主体C→N），均正常落地disarm并清理，实际执行墙钟合计320.777s；没有自动补跑、没有真实飞行、没有更改PX4或安全保护。最初2次轻度制动没有产生预定虚拟余量反例，后2次给出更有区分力的实际峰值与任务预算观察。两个旧紧弯原始日志的两秒取证作为独立历史材料，不计新增次数。

最终复核入口：
- `handover-t1-margin-20261115-v1/analysis-v3/`：第一对最终结果、曲线、匹配；v1/v2失败或旧口径保留。
- `handover-t1-turn-20261115-v1/analysis-v1/`：第二对测量、matching、entry-and-late-audit、曲线及对比图。
- 各目录的`runner.py`、`PLAN.zh.md`、`attempts.jsonl`、`C/N/config.json`、`C/N/result.json`、`manifest.sha256`。
- `audit_t1_archived.py`与`archived-late-window-audit.json`：旧两个越45°案例的两秒连续证据。

复核脚本依赖Thor已有Lab/pyulog和原始ULog及四电机bin；远端小型证据可审查数据与图，不声称无Lab的clone可直接重新飞行。大原始数据保留原目录，不纳入提交。报告用于固定现有事实，不增加未实施的修复或已证明安全域。

## T2：控制器历史状态接续错误的历史证据

### 1. 结论与证据范围

按 [2026-11-15 分类基线](https://github.com/JacksonW1025/uav_handover/blob/0a88c03c4775f44b40f9734d3cfcaff13aa7e310/HANDOVER_PROBLEM_TAXONOMY_20261115.md)，T2 的起点是**接入控制器使用的记忆或上一动作，与真实执行经历不相容**。P2、P3、P4 提供两条可以分别解释的历史机制：

1. **进入时用默认状态覆盖真实执行历史。** 悬停期间，GRU 与上一动作一起恢复默认值，接入输出明显偏离原先维持悬停的输出；分别准备这两项只能去掉部分阶跃，同时准备可使阶跃回到基线量级。
2. **停用期间让影子控制器反馈自己未执行的动作。** 神经策略虽然不持权，仍更新 GRU 与上一动作；其软件历史逐渐偏离实际由经典控制维持的飞行。重新启用这份影子历史比 reset 更差；冻结退出时的旧历史反而更好。

这不是“记忆越旧越危险”，也不是“清零一定错”。核心是**软件历史是否与实际执行经历相容**。这些例子出现的是悬停接管电机阶跃、厘米级失高与轻微姿态扰动；并未发生 crash 或 45° 倾角越界。

标签仅使用 X/H/P：X=悬停、约 3 m 高度、低平动速度；H=GRU 与上一动作的初始化/停用演化；P=进入沿、停用时长、实际发布时序及激活时零速度目标捕获。H 是本章独立干预的起点，P 不是新增分类。

本次只读核验，没有飞行、代码修改或 push。P2 两条原始 ULog 下载后核对 SHA，并独立重算输出与高度；P3/P4 读取逐轮 JSON、其中保留的原生电机曲线和记忆曲线，重新计算组均值。P3/P4 的原始 ULog 与 Gazebo motor 二进制未在所读远端树中找到，不能把导出曲线核验称为原始日志复算。

### 2. 版本不能混用：逐实验源码身份

| 批次 | 对应可读源码快照 | 实际二进制 SHA256 | 与 candidate 校验一致的研究补丁 SHA256 |
|---|---|---|---|
| P2 s1a/s1b | `f596cf9839b496b108b405e795313901aaeb37ca` | `4b84cb2b4bac1d6d7080a11c537a7bcf767f157fd7b4726056adc343bd842eb4` | `a01c8c9230f9a46747f22cb87107ab8965fbc26ba7b011e26484016306688b59` |
| P3 batch-01；P4 batch-01a | `abe54c9cedc9484c42276a53922f9ed0f5cacdba` | `1a5b5fd8282fbc42570b4773cfc3585010b0400ba8d5344bdf63037778260ae1` | `c618c593821c1815c0a140a206f7ae067de3b0199320bb759ae1603433f80e6e` |

实际核对：以上快照的 `patches/raptor-final.patch` 哈希等于对应 candidate 的 `lab.raptor.diff_sha256`；`tools/apply_research.py` 与 `research/state/MemoryInit.hpp` 也逐文件符合 candidate。P2 candidate 的 project_head 为较早提交且含工作树改动，不能单独把 project_head 当完整实验源码；这里采用哈希匹配的后续归档快照。P3/P4-01a 使用相同飞行二进制与补丁，P4 增加独立种子/航向及分析而非更换策略。

核验入口：[P2 candidate](https://github.com/JacksonW1025/uav_handover/blob/f596cf9839b496b108b405e795313901aaeb37ca/data/p2-20261015-batch-s1a/candidate.json)、[P3 candidate](https://github.com/JacksonW1025/uav_handover/blob/c186c96d6ffbaf4b04c01b234cb3f9621d616e30/data/p3-20261015-batch-01/candidate.json)、[P4 candidate](https://github.com/JacksonW1025/uav_handover/blob/c186c96d6ffbaf4b04c01b234cb3f9621d616e30/data/p4-20261016-batch-01a/candidate.json)。这些是当时多值 RINI 实验，不可套用 11 月 15 日基线的布尔 RINI。

### 3. 机制一：默认初始化与实际悬停历史不相容

#### 3.1 从代码到首次推理

P2 只干预 16 维 GRU 与 4 维 previous_action，保持激活时当前位置/偏航、零速度捕获逻辑不变：

- N0：原始 reset，GRU/上一动作回到原始初值；在已核验日志中两者均为零。
- N1：GRU reset，仅上一动作换成经典最后发布指令的动作空间表示。
- N2g：经典动作 teacher forcing 得到的影子 GRU，上一动作仍 reset。
- N2：同时准备 GRU 与上一动作。

模式分支及具体数组赋值见 [MemoryInit.hpp L8–34](https://github.com/JacksonW1025/uav_handover/blob/f596cf9839b496b108b405e795313901aaeb37ca/research/state/MemoryInit.hpp#L8-L34)。[apply_research.py L413–460](https://github.com/JacksonW1025/uav_handover/blob/f596cf9839b496b108b405e795313901aaeb37ca/tools/apply_research.py#L413-L460) 显示：从 `research_actuator.owner==2` 读取经典发布指令，反变换到动作空间；非活动期间每轮 observe 前替换 previous_action；进入处理在 RAPTOR 自己线程内完成，并记录写入前后值。这里代码读取的是**实际发布**，不是从物理电机回读的实测动作，解释时应保留这一区别。

证据链为：

```text
进入处理写 GRU/previous_action
 → observe 使用 previous_action
 → rl_tools::control 产生 action
 → 更新 previous_action，(action+1)/2 并重排电机编号
 → active 且发布仲裁允许时发布 actuator_motors
 → research_actuator 记录实际发布值和来源
 → Gazebo 桥转发
 → 机体姿态/高度变化
```

对应当批补丁：[observe/control L988–1035](https://github.com/JacksonW1025/uav_handover/blob/f596cf9839b496b108b405e795313901aaeb37ca/patches/raptor-final.patch#L988-L1035)、[推理后记忆、动作更新及发布 L1044–1087](https://github.com/JacksonW1025/uav_handover/blob/f596cf9839b496b108b405e795313901aaeb37ca/patches/raptor-final.patch#L1044-L1087)。previous_action 是策略的 -1 到 1 尺度，0 不表示关闭电机；映射后为 0.5。

#### 3.2 逐轮 JSON 重新汇总，而非抄报告表

| P2 批次/处理 | n | 首次发布电机最大阶跃均值 | 最大失高均值 m |
|---|---:|---:|---:|
| s1a N0 | 5 | 0.219425 | 0.038843 |
| s1a N1 | 5 | 0.133083 | 0.029839 |
| s1b N2g | 5 | 0.144101 | 0.022466 |
| s1a N2 | 5 | 0.016661 | 0.023413 |
| s1a 神经自身基线 | 3 | 0.024098 | 0.020159 |
| s1b N0 | 5 | 0.227932 | 0.041985 |
| s1b 自由影子 N2s | 5 | 0.376810 | 0.059019 |

这组干预支持两个可写观察：上一动作失配贡献明显的瞬时阶跃；只准备 GRU 或只准备上一动作均不足，同时准备可使悬停接管输出回到原有神经悬停波动量级。N2g 来自 s1b，不能冒充与 s1a 共享同一条飞行前缀。

复核数据目录：[s1a](https://github.com/JacksonW1025/uav_handover/tree/f596cf9839b496b108b405e795313901aaeb37ca/data/p2-20261015-batch-s1a)、[s1b](https://github.com/JacksonW1025/uav_handover/tree/f596cf9839b496b108b405e795313901aaeb37ca/data/p2-20261015-batch-s1b)。各批 results.json 指向逐轮目录及 p2-metrics.json。

#### 3.3 两条原始 ULog 的独立回查

| 项目 | s1a N0-1 | s1a N2-1 |
|---|---|---|
| 进入/首次历史使用时刻，PX4 仿真 μs | 58,040,000 | 58,436,000 |
| 首次神经电机发布 μs | 58,052,000 | 58,448,000 |
| 写入 GRU 范数 | 0 | 1.731209 |
| 首次推理所用 previous_action | `[0,0,0,0]` | `[0.456672,0.458403,0.458026,0.458067]` |
| 最后经典电机发布 | `[.728446,.727798,.728787,.728884]` | `[.728711,.728601,.729356,.728868]` |
| 首次神经电机发布 | `[.490030,.557533,.511979,.529510]` | `[.723742,.723639,.719027,.719251]` |
| 独立重算最大阶跃 | 0.238416 | 0.010329 |
| 独立重算失高 m | 0.0404096 | 0.0227184 |
| 原生姿态流计算全窗口最大倾角 | 1.91765° | 0.61389° |

两条 ULog 的 SHA 与各自 p2-metrics.json 完全一致。失高重算使用 `vehicle_local_position.timestamp_sample`，按触发前最后样本为高度基准，结果与保存指标完全一致；不是以首次发布高度替代原口径。姿态来自 `vehicle_attitude` 四元数，非 Gazebo 世界姿态。入口高度为 3.02179/2.98037 m，水平速度为 0.02381/0.01694 m/s，是相近悬停条件而非同完整快照。

重要时序：两例进入及首次推理均比首次神经发布早 12 ms。上述第一条电机消息不能写成“进入后的第一轮推理输出”，期间已有数轮推理。已核验 `research_timing.action` 与首次发布按动作映射一致，`research_output` 同采样时刻存在桥端输出记录。

原始证据：[N0-1 ULog](https://github.com/JacksonW1025/uav_handover/blob/f596cf9839b496b108b405e795313901aaeb37ca/data/p2-20261015-s1a-S1-c_to_n-N0-1/flight.ulg)、[N2-1 ULog](https://github.com/JacksonW1025/uav_handover/blob/f596cf9839b496b108b405e795313901aaeb37ca/data/p2-20261015-s1a-S1-c_to_n-N2-1/flight.ulg)。

#### 3.4 应用端证据到哪一层

P2 已经有 Gazebo 逐物理步的四电机审计，不应误说“只有发布日志”。[output_chain.py L10–20、L71–119](https://github.com/JacksonW1025/uav_handover/blob/f596cf9839b496b108b405e795313901aaeb37ca/tools/output_chain.py#L71-L119) 读取 `gz-motor/motor-*.bin`，以 applied_sample_us 检查年龄及四电机是否一致。

N0-1 的 [output-chain.json](https://github.com/JacksonW1025/uav_handover/blob/f596cf9839b496b108b405e795313901aaeb37ca/data/p2-20261015-s1a-S1-c_to_n-N0-1/output-chain.json) 保存了神经窗口各电机应用年龄统计，所核对电机0共 2628 步，全部年龄 4 ms，0 保持步。**本次远端树没有对应原始 motor-*.bin，因此不能独立重建该条命令四电机首次应用的确切物理步。** ULog 桥端记录证明转发，不替代电机模型物理步。现有证据支持写为“发布阶跃及闭环物理后果已复核，原应用审计通过”，不要虚构逐命令首次应用时间。

### 4. 机制二：非持权影子计算使用自己未执行的动作

#### 4.1 可定位的独立起点

动作计算与 previous_action 更新位于 active 发布门之前。因此非活动策略照常更新自己的历史，却不把这些动作交给飞机。若不做 teacher forcing，这份历史记住的是“假如我在控制”的动作，而真实飞机由经典控制器驱动。它不是进入时 reset 的同义改写，而是**停用生命周期内的软件历史演化错误**。

P3 增加 N3：退出第一非活动周期在影子推理之前保存 GRU 和 previous_action，此保存副本保持不变，下一次进入写回。[匹配 P3/P4 二进制的退出保存代码 L607–635](https://github.com/JacksonW1025/uav_handover/blob/abe54c9cedc9484c42276a53922f9ed0f5cacdba/tools/apply_research.py#L607-L635)、[MemoryInit.hpp L26–49](https://github.com/JacksonW1025/uav_handover/blob/abe54c9cedc9484c42276a53922f9ed0f5cacdba/research/state/MemoryInit.hpp#L26-L49)。注意：N3 的实时影子仍可漂移；被冻结的是退出副本，重新进入选择该副本。

#### 4.2 逐轮数据支持的后果

以下均从逐轮 p3-metrics.json 重新求均值：

| 批次/停用 | 处理 | n | 发布阶跃 | 失高 m |
|---|---|---:|---:|---:|
| P3 0.3 s | 自由影子 N2s | 3 | 0.054608 | 0.019536 |
| P3 10 s | reset N0 | 3 | 0.217908 | 0.036353 |
| P3 10 s | 自由影子 N2s | 3 | 0.377497 | 0.054643 |
| P3 10 s | 冻结退出副本 N3 | 3 | 0.047310 | 0.023811 |
| P3 10 s | teacher forcing N2 | 3 | 0.021699 | 0.024914 |
| P4 独立种子/航向 10 s | N0 / N2s / N3 / N2 | 各5 | 0.218258 / 0.377009 / 0.031462 / 0.017158 | 0.037508 / 0.057717 / 0.021501 / 0.020385 |

这条现象在 P2 自由影子、P3 停用生命周期和 P4 独立种子/航向中重复出现。不要将“新鲜影子状态”自动等同于“真实飞行历史”。

代表例 P3 D2-N2s-1 的导出记忆轨迹显示：停用 1.388 s 时 GRU 距离退出状态首次超过 0.5，停用结束为 1.441684；这是欧氏距离，**不是 GRU 范数**。67.676 s 再进入保留的上一动作 `[-.281409,-.229234,-.170690,-.215151]`，且第一轮推理确实采用这些值。67.688 s 首次神经发布从经典 `[.727810,.728072,.728143,.728650]` 跳到 `[.354029,.396198,.381348,.372794]`，曲线重算阶跃 0.373780；保存指标失高 0.057205 m，最大倾角 1.537221°。对应 D2-N3-1 的阶跃 0.053799、失高 0.020994 m、倾角 0.662515°。D1-N2s-1 的短停用内距离未超过 0.5，结束距离只有 0.071145，阶跃 0.054606。

复核入口：[D2-N2s-1](https://github.com/JacksonW1025/uav_handover/blob/c186c96d6ffbaf4b04c01b234cb3f9621d616e30/data/p3-20261015-b01-D2-N2s-1/p3-metrics.json)、[D2-N3-1](https://github.com/JacksonW1025/uav_handover/blob/c186c96d6ffbaf4b04c01b234cb3f9621d616e30/data/p3-20261015-b01-D2-N3-1/p3-metrics.json)、[P4 01a](https://github.com/JacksonW1025/uav_handover/tree/c186c96d6ffbaf4b04c01b234cb3f9621d616e30/data/p4-20261016-batch-01a)。P3/P4 姿态峰值与失高这里属于原分析输出，未用其缺失的原始 ULog 独立再算；电机阶跃和 GRU 距离跨越时刻已从保留曲线重算。

### 5. 已支持的发现与不可泛化的结论

**发现 A：控制器启动成功并不意味着内部状态已与接管前行为接上。** 默认初始化会人为改变策略的历史输入，哪怕飞机正在低速悬停、参考目标基本不变，也会产生明显输出阶跃。

**发现 B：后台运行不等于历史准备正确。** 对依赖动作历史的循环策略，只有观察真实执行动作的影子更新才有对应物理含义；使用自身未执行动作可持续积累虚假的历史，再次持权时暴露为瞬态。

**发现 C：历史的新旧不是关键，历史与当前任务/实际执行是否相容才是关键。** P3 平移 3 m、偏航 90° 后重新悬停，N3 仍有效，因为目标相对观测在重新捕获后近似不变；它不是“旧历史在任意状态都安全”的例子。

把这两条机制列为同一 T2 下两个独立案例即可，不需要新增一级分类。P4 运动中的结果还能说明历史问题与参考问题会叠加：P4 报告指出零速度捕获是运动场景大倾角的主要成分；不能把 GRU 后续因参考改变而变化本身再计为新的 T2 起因。

最有价值的补证不是大规模新飞行，而是取回 P3/P4 对应原始 ULog、Gazebo motor 二进制，把“进入写入 → 实际推理采用 → 首个/后续动作发布 → 四电机逐步应用 → 姿态/高度”的时序压成一张图。当前两条历史机制已经具备代码、干预与闭环结果；补齐原始应用链能让读者直接复核整个故事。

## T3：setpoint 信号接续异常

### T3-a：接管时参考空窗，采用默认停车目标（旧 F1，P+X）

经典 OFFBOARD → RAPTOR，x500、三维转弯、seed 20261110。E1 保持经典两次峰 25.229°/25.113°；E2 原等待两次，四电机首次应用到第一条有效外部读取为 156/168 ms，峰 55.276°/55.560°、两次保护中止；E3 缩短等待后为 16/16 ms、峰 31.184°/30.292°、两次正常落地。入口原生位置、速度、姿态、角速度及可比程度见 [F/f1-summary.json](https://github.com/JacksonW1025/uav_handover/blob/cbaf3a53914efe26b2e00444f56f16935b760a27/data/handover-f1-sync-20261112-analysis-v1/f1-summary.json) 的 request_state、entry_state 和 pairwise_states；E2-1 实际入口 NED 约 (2.666,1.790,−4.153) m 和 (0.705,1.642,0.280) m/s。E2-1 发布距请求下界 48 ms，参考有效读 208 ms，桥后实际应用距首读156 ms。不是旧目标滞留：RAPTOR 已经接管但没有有效新参考，按当前位置和零速度生成内部目标。E3 也有首帧零速度，变化是持续周期缩短；同一轨迹时钟在不同时间取样，所以首发 payload 相位不同，不把姿态峰称持续振荡。

实际数据流：[F/f1_runner.py:12–46](https://github.com/JacksonW1025/uav_handover/blob/cbaf3a53914efe26b2e00444f56f16935b760a27/data/handover-f1-sync-20261112-analysis-v1/f1_runner.py#L12-L46)，E2等mode/ACK/nav后恢复，E3监督新active、owner=1、发布后8 ms才恢复，逐电机独立核验，不把8 ms当物理证据；[F/source/project/tools/handover_100/runner.py:90–111](https://github.com/JacksonW1025/uav_handover/blob/cbaf3a53914efe26b2e00444f56f16935b760a27/data/handover-f1-sync-20261112-analysis-v1/source/project/tools/handover_100/runner.py#L90-L111) 在绝对相位生成 ROS TrajectorySetpoint（含位置、速度、偏航）与发送账本，经 XRCE-DDS 到 PX4 同名 uORB。[mc_raptor.cpp:687–719](https://github.com/JacksonW1025/uav_handover/blob/cbaf3a53914efe26b2e00444f56f16935b760a27/data/handover-f1-sync-20261112-analysis-v1/source/px4/resolved/src/modules/mc_raptor/mc_raptor.cpp#L687-L719) 按nav进入、[:145–159](https://github.com/JacksonW1025/uav_handover/blob/cbaf3a53914efe26b2e00444f56f16935b760a27/data/handover-f1-sync-20261112-analysis-v1/source/px4/resolved/src/modules/mc_raptor/mc_raptor.cpp#L145-L159)清有效性/历史，[:829–857](https://github.com/JacksonW1025/uav_handover/blob/cbaf3a53914efe26b2e00444f56f16935b760a27/data/handover-f1-sync-20261112-analysis-v1/source/px4/resolved/src/modules/mc_raptor/mc_raptor.cpp#L829-L857)读取八个必要有限字段并记当前读取时间，[:1051–1089](https://github.com/JacksonW1025/uav_handover/blob/cbaf3a53914efe26b2e00444f56f16935b760a27/data/handover-f1-sync-20261112-analysis-v1/source/px4/resolved/src/modules/mc_raptor/mc_raptor.cpp#L1051-L1089)无有效参考则捕获当前位置/偏航，v=0；[:452–546](https://github.com/JacksonW1025/uav_handover/blob/cbaf3a53914efe26b2e00444f56f16935b760a27/data/handover-f1-sync-20261112-analysis-v1/source/px4/resolved/src/modules/mc_raptor/mc_raptor.cpp#L452-L546)按目标偏航变换并裁剪位置和速度误差，[:1130–1140](https://github.com/JacksonW1025/uav_handover/blob/cbaf3a53914efe26b2e00444f56f16935b760a27/data/handover-f1-sync-20261112-analysis-v1/source/px4/resolved/src/modules/mc_raptor/mc_raptor.cpp#L1130-L1140) RL Tools 推理，[:1239–1290](https://github.com/JacksonW1025/uav_handover/blob/cbaf3a53914efe26b2e00444f56f16935b760a27/data/handover-f1-sync-20261112-analysis-v1/source/px4/resolved/src/modules/mc_raptor/mc_raptor.cpp#L1239-L1290)缩放/重排、发布门、actuator_motors与owner记录。ESC桥[GZMixingInterfaceESC.cpp:66–131](https://github.com/JacksonW1025/uav_handover/blob/cbaf3a53914efe26b2e00444f56f16935b760a27/data/handover-f1-sync-20261112-analysis-v1/source/px4/resolved/src/modules/simulation/gz_bridge/GZMixingInterfaceESC.cpp#L66-L131)传输电机输入，[ResearchMulticopterMotorModel.cc:640–669](https://github.com/JacksonW1025/uav_handover/blob/cbaf3a53914efe26b2e00444f56f16935b760a27/data/handover-f1-sync-20261112-analysis-v1/source/px4/untracked/src/modules/simulation/gz_plugins/research_motor_model/ResearchMulticopterMotorModel.cc#L640-L669)每路物理步记录refMotorInput、appliedSampleUs和stepWallNs。随后用原生ULog姿态/高度和 [F/f1-motor-curves.json](https://github.com/JacksonW1025/uav_handover/blob/cbaf3a53914efe26b2e00444f56f16935b760a27/data/handover-f1-sync-20261112-analysis-v1/f1-motor-curves.json) 复核物理输入与姿态；[F/REPORT.zh.md](https://github.com/JacksonW1025/uav_handover/blob/cbaf3a53914efe26b2e00444f56f16935b760a27/data/handover-f1-sync-20261112-analysis-v1/REPORT.zh.md)有原解释。RINI/RTGT/NCO/RREC/P12一致为0，分组没有额外H干预，不重复算T2。[F/source-identity.json](https://github.com/JacksonW1025/uav_handover/blob/cbaf3a53914efe26b2e00444f56f16935b760a27/data/handover-f1-sync-20261112-analysis-v1/source-identity.json)固定实际版本。

### T3-b：活动参考终止后，超时选择零速度（旧022/023，P+X）

[M/runs/022_active_timeout_rtgt1-a1/mechanism-audit.json](https://github.com/JacksonW1025/uav_handover/blob/46d339713cb3982ef17eace3f6ee30f45b246c48/data/handover-mutation-20261111-analysis-v1/runs/022_active_timeout_rtgt1-a1/mechanism-audit.json) 与[相应023_active_timeout_rtgt2-a1](https://github.com/JacksonW1025/uav_handover/blob/46d339713cb3982ef17eace3f6ee30f45b246c48/data/handover-mutation-20261111-analysis-v1/runs/023_active_timeout_rtgt2-a1/mechanism-audit.json)。M同提交 [tools/handover_mutation/runner.py:9–25](https://github.com/JacksonW1025/uav_handover/blob/46d339713cb3982ef17eace3f6ee30f45b246c48/tools/handover_mutation/runner.py#L9-L25) 先正常交接，看到 active 且目标不 stale 才关闭自己的发布；[tools/handover_100/runner.py:90–111](https://github.com/JacksonW1025/uav_handover/blob/46d339713cb3982ef17eace3f6ee30f45b246c48/tools/handover_100/runner.py#L90-L111) 由 reference_enabled 截断。两例首发布四路都在+4 ms应用，超时捕获均在最后有效读后204 ms。022发布52.044s、应用52.048s，33次有效外部读取，最后52.728s，52.932s出现 activation=0 的 stale 捕获：实际水平(1.9890,0.0473)m/s而目标(0,0)，超时后340ms主体峰49.168°、失高0.121m。023发布51.936s、应用51.940s，52.828s active超时以实际(2.0388,0.0445)m/s捕获，主体峰14.313°、失高0.047m并落地。它们的初始捕获及物理状态不同，是机制对照，不冒充严格同态。实际二进制、补丁、插件和策略身份已同 F1 对齐：用 F 版 [mc_raptor.cpp:829–857](https://github.com/JacksonW1025/uav_handover/blob/cbaf3a53914efe26b2e00444f56f16935b760a27/data/handover-f1-sync-20261112-analysis-v1/source/px4/resolved/src/modules/mc_raptor/mc_raptor.cpp#L829-L857)、[1051–1089](https://github.com/JacksonW1025/uav_handover/blob/cbaf3a53914efe26b2e00444f56f16935b760a27/data/handover-f1-sync-20261112-analysis-v1/source/px4/resolved/src/modules/mc_raptor/mc_raptor.cpp#L1051-L1089)、[1402–1442](https://github.com/JacksonW1025/uav_handover/blob/cbaf3a53914efe26b2e00444f56f16935b760a27/data/handover-f1-sync-20261112-analysis-v1/source/px4/resolved/src/modules/mc_raptor/mc_raptor.cpp#L1402-L1442)（RTGT=1限激活，RTGT=2也覆盖active超时）及上节相同的观察→输出→四电机链。[M/raw-source-index.json](https://github.com/JacksonW1025/uav_handover/blob/46d339713cb3982ef17eace3f6ee30f45b246c48/data/handover-mutation-20261111-analysis-v1/raw-source-index.json) 保存原始入口，[M/FINAL_REPORT.zh.md](https://github.com/JacksonW1025/uav_handover/blob/46d339713cb3982ef17eace3f6ee30f45b246c48/data/handover-mutation-20261111-analysis-v1/FINAL_REPORT.zh.md) 报告主体和清理，未确认落地不单列为T4。

### T3-c：参考恢复瞬间的二次目标跳变（旧P5 E2，P+X）

[P5 docs/THOR_P5_REPORT.md](https://github.com/JacksonW1025/uav_handover/blob/2deb79e2451e191623e86711c5fafed67c428513/docs/THOR_P5_REPORT.md) 的 E0 与 E2、[data/p5-20261018-batch-e2/](https://github.com/JacksonW1025/uav_handover/blob/2deb79e2451e191623e86711c5fafed67c428513/data/p5-20261018-batch-e2/) 可复核。[tools/run_experiment.py](https://github.com/JacksonW1025/uav_handover/blob/2deb79e2451e191623e86711c5fafed67c428513/tools/run_experiment.py) 的 start_stream(...,gaps) 在设定窗口停止发送但原轨迹时钟不停。P5 实验版 mc_raptor.cpp:718/748 接受目标，:913–927 判 200 ms stale 并捕获，:1238–1250更新/结束速度匹配减速剖面；:748、944–951在新外部目标到达时整条替换并退出stale，:444–501转换目标偏航误差并裁剪，再按共用策略/电机链传播。实测同 A0、2 m/s²：0.3s间隙恢复跳变0.138m/0.22m/s、峰13.1°；1.0s为0.768m/1.59m/s、49.3°并中止。A45的1.0s为0.751m/1.60m/s、55.2°。这是发送端主动间隙，非自然DDS丢包统计，首条恢复观测粗于一周期；P5表内“T1”是速度匹配处理名，不是taxonomy T1。

## T4 控制权实际交付异常：两条历史观察与一项隔离组件验证

### 结论与证据级别
按 `HANDOVER_PROBLEM_TAXONOMY_20261115.md`（0a88c03c4775f44b40f9734d3cfcaff13aa7e310），T4从“正确命令产生之后的来源仲裁、消费或应用错误”归类。此次只读核查Thor，并运行一个无飞行的源代码抽取组件测试。没有启动SITL、改控制器、绕过保护或git写入。

1. **发布端实测异常**：10月9日旧重复交接出现C→N→C→N发布者回跳。8次转换对6次请求，局部12ms。尚无该事件四电机物理消费证明。
2. **下游物理步实测时效异常**：10月22日P8开发例在神经持权期间四电机同时保持旧sample至16ms年龄，桥已发布的新消息随后成批到达并被最新值覆盖。违反当时输出链工程限值，飞行却成功；不是已隔离的危险交接反例。
3. **主动注入的组件验证**：真实Gazebo消息类型、逐字抽取的callback/slot消费代码，在显式延后callback的确定性调度中，切换后的第一次消费仍用C标记，正常对照则用N标记。仅证明软件组件语义，不声称原生自动缺陷或Gazebo完整物理复现。

### 观察A：旧发布者回跳（非主动注入）
固定来源：8d0c4166fb8a6f9adb9dbba9f5758f13c6d8446e，`docs/THOR_ENVIRONMENT_FINAL_REPORT.md`第9节，`data/final-repeated_handover/{metrics.json,flight.ulg}`。本次直接重读ULog，0 dropouts；研究发布记录与actuator_motors数值相符：

| 原生时刻s | 发布者 | 四路归一化命令 |
|---|---|---|
|60.120|经典2|.727123,.727226,.726952,.726685|
|60.124|神经1|.508875,.558059,.507617,.540417|
|60.128|经典2|.727107,.727190,.726509,.727022|
|60.132|经典2|.727151,.727115,.726590,.726882|
|60.136|神经1|.497316,.566724,.524950,.533445|

60.124s的vehicle_control_mode仍allocation_enabled=1，60.136s变0。这与报告所述两个发布路径使用独立缓存、不同时看到分配开关的竞争相符。12ms是首次N到重新N，不是已测的执行器故障持续时间。局部最大通道变化约.219/.230。

修复是POSIX共享ActuatorGate：两写者在同一mutex内读取最新vehicle_control_mode，根据neural != flag_control_allocation_enabled决定发布。`research/state/ActuatorGate.hpp:11–18`、`tools/apply_research.py:239–256`给出实现；固定研究基线ddeaddd2213fb8e79d6d008f2c26d7cd82cf52e2可用同路径复核。修后`data/verified-repeated_handover/metrics.json`为6请求/6转换，但它不是同初态锁步成对试验。

旧ULog有actuator_outputs，但该局部只在60.136s记录一行，没有sample身份可证明60.128/132经典命令被四电机执行。无gz-motor目录，无research_output主题。不能把owner记录、稳定窗口PASS或清理成功补成物理应用证据；也不能据此宣称已发生危险姿态后果。

### 观察B：桥成功发布，但物理步仍保持旧命令（非主动注入）
路径：
`data/p8-20261022-dev-b-v1.8-H71.0-W0.0-0.44_0.67-1.13_1.62-2.1_2.39-3.16-T1-1/`
候选HEAD `923ce8a9c814e464154ff10956083513f0f1196c`，身份见`data/p8-20261022-dev-b/candidate.json`。本次直接重读flight.ulg及四份gz-motor/motor-*.bin，ULog 0 dropouts、各bin尾部0残字节。

神经发布者区间47.796–80.472s。四电机均：
| 物理步s | 应用sample s | 本步收到消息数 |
|---|---|---|
|62.288|62.284|1|
|62.292|62.284|0|
|62.296|62.284|0|
|62.300|62.284|0|
|62.304|62.300|3|

research_output在62.296s已记录transport_published=1，分别携带sample62.292和62.296。对应host monotonic为558228016656733/558228016665854ns，早于motor0在62.300s的物理步558228023835185ns，故不是简单把“先物理步后发布”误判为迟滞。四路62.300仍保留62.284，输入分别771.80188/769.94037/769.57861/768.43884。62.304一次收到3条但采用62.300，前两条在最新值槽被覆盖。

这里sample是`actuator_motors.timestamp_sample`经FunctionMotors保留的采样身份，不是唯一发布序号；处理拥塞下多条发布timestamp可相同。必须结合桥sample、内容、物理步及收到计数，不用timestamp相等断言唯一命令。

整神经区间motor0有8169步、322 hold步、Gazebo内覆盖288条，年龄p99=8ms/max=16ms、连续超4ms最大3步。四路违反原p99≤4ms/max≤12ms/连续≤2步约定；这是工程时效失败，不是稳定性定理。该例峰倾角32.2006°、失高.18076m、任务SUCCESS，不能说延迟造成了危险。P8报告记录当时ToDesk负载与RTF约.92，环境是混杂因素，不能从关联直接断言某进程导致这一次延迟。该任务还包含参考gap，且此观察在神经活动中而非进入瞬间，不能当作满足taxonomy全部隔离条件的单因T4飞行。

### 代码链及固定来源
- FunctionMotors::update/value/getLatestSampleTimestamp：实际源码`src/lib/mixer_module/functions/FunctionMotors.hpp:62–82`。新消息替换缓存，value读取已保存值；sample来自timestamp_sample。
- MixingOutput::researchSelectedSampleTimestamp：`src/lib/mixer_module/mixer_module.hpp:166–177`从实际配置输出provider取样本/代数。
- GZMixingInterfaceESC.cpp:90–130将sample编码到Gazebo header，Publish返回仅证明桥选择/传输发布；research_output记录sample/transport_published/累计uORB代数缺口，不证明物理消费。
- ResearchMulticopterMotorModel::OnActuatorMsg在mutex内覆盖可选消息槽；UpdateForcesAndMoments读取并清槽，没新消息保留refMotorInput。物理步将header sample保存为researchAppliedUs，并记录refMotorInput。
- 对观察B的固定候选，`patches/raptor-final.patch`在923ce8a9的1956、1979附近可复核桥标记；同提交`patches/raptor-final-untracked.tar.gz`内`src/modules/simulation/gz_plugins/research_motor_model/ResearchMulticopterMotorModel.cc`的550–558为callback、584附近读取、623/630附近记录应用sample/输入。当前本机版本对应586–594、617–625、651–669，不能混用行号。
- `tools/output_chain.py:12–22,55–66,85–92`解码逐步bin、统计年龄及四路一致性。应用输入并不等于经过电机滤波后的转速/推力。

### 最小组件对照：显式注入，不是第三个默认飞行失败
材料在本分支 `tests/handover_delivery_primitive_20261115/`；原运行与发布副本区别见PORTABILITY.md：
`build_test.py`从当前实际插件逐字提取callback函数体和slot消费段，生成`delivery_primitive.cpp`，使用实际gz-msgs10的Actuators protobuf、std::mutex/optional，以g++和ASAN/UBSAN编译；退出0，无sanitizer报错。来源哈希与抽取文本在provenance.json。

确定性逻辑时间：C sample=1000、参考10；N sample=4000、参考11。正常对照在8000us消费N。显式延后callback的对照在8000/12000仍消费C，到16000才消费N。突发对照在消费前依次callback N4000和N8000，12000只应用后者且received=2。assert全部通过，完整表在result.csv。

此测试没有真实网络、线程调度分布、Gazebo物理步或闭环飞机。墙钟记录函数明确stub，step与marker应用在wrapper中复刻，只有callback和slot消费段逐字复用。预先定义的“handoff后首次消费应为N”在注入延迟时违反，正常对照满足。这是可执行的交付契约示范，不能冒充实际Gazebo integration test，更不能证明默认代码自动延迟8ms。保护、仲裁与真实飞行均未被修改。

### 下一步最小缺口
若需要把T4升格为危险交接的单因闭环例，应在隔离、低速安全SITL中保留ActuatorGate及保护，固定X/H/参考，在明确标记的新输出之后仅对传输callback施加一次有界延迟，保留无注入对照，逐步核对四motor sample/值/实际转速，再判断是否有影响。现阶段不应追求危险来补标题；本章节已诚实给出发布端异常、真实应用时效异常和可执行组件契约三层证据。


### 补充：真实Gazebo插件与物理步的交付对照（2026-11-15）

为补足“抽取组件不是完整Gazebo”的缺口，另运行两臂独立Gazebo台架。没有PX4、没有飞行器、没有修改共享Lab或motor插件。world由固定到世界的base和一个rotor转动关节组成，重力为0，引用原已构建ResearchMulticopterMotorModel.so。输入仅10→11rad/s。两臂独立GZ_PARTITION，Gazebo暂停后逐批单步推进，每步4ms，保持真实transport订阅回调及UpdateForcesAndMoments。与飞行实验错开运行，两臂均正常退出。

源topic /t4/source发布新身份N；独立测试relay转发至实际插件订阅的/t4/command/motor_speed。正常臂立即转发；lag臂明确注入：relay收到N后暂存，等待两个真实物理步后才转发。没有修改插件、仲裁或任何飞控保护；此实验也不模拟完整Commander接管。C/N只是来源身份标签，不是执行了经典/神经推理。

| 真实物理步µs | 正常臂应用marker/输入 | 注入臂应用marker/输入 |
|---|---|---|
|4000|0 / 0|0 / 0|
|8000|C=1000 / 10|C=1000 / 10|
|12000|N=4000 / 11|C=1000 / 10|
|16000|N=4000 / 11|C=1000 / 10|
|20000|N=4000 / 11|N=4000 / 11|

两臂新来源均在8000µs物理步之后发出。预先定义的交付要求是“下一物理步采用新标记”。正常臂满足，注入臂在12000µs首次检查点不满足，直到20000µs才接续。首N应用真实sim时间差为8000µs。每臂32个物理步，motor-0.bin尾部残字节为0，所有断言通过。

**身份与时钟限制：**header中的1000/4000为本试验合成marker，并非源命令生成时间；不能用sim_us减marker计算命令年龄。8ms额外等待来自两臂首N实际物理步的差，而不是marker数值。这里只验证一个真实电机插件的输入消费，不声称四电机共同执行、实际推力测量、危险飞行或默认调度失败。实际Gazebo传输与物理步是真实运行，故比抽取代码测试多了一层直接证据；延迟是预声明注入，必须始终标为注入型T4契约失败。

材料位于本分支 `tests/handover_delivery_gazebo_20261115/`：
- `world.sdf`：最小固定台架；发布副本使用显式插件路径模板。
- `driver.cpp`：真实gz-transport源/relay、显式hold两步及world-control单步。
- `run.py`：两臂分区/进程生命周期；`execution.json`记正常4.598s、注入4.698s，driver与Gazebo均exit0。
- `normal/`、`lag/`：原始driver/Gazebo日志及真实motor-0.bin。
- `analyze.py`、`evidence.json`：逐步原值、断言、插件SHA-256和解释；`manifest.json`：小型材料哈希。

这项结果可作为T4的直接、最小可复现**注入型交接交付观察**，与旧发布者回跳和P8自然时效异常分别计述，不混成三次原生危险飞行。

## 本次发布范围及复核入口

- [T1四次运行的小型材料](tests/handover_t1_20261115/REPRODUCTION.md)：计划、配置、账本、最终曲线/图和实际进入审计；原始ULog/四电机日志不随本次发布。
- [T4源抽取组件材料](tests/handover_delivery_primitive_20261115/PORTABILITY.md)：源抽取器、C++、CSV与来源说明；不含编译程序。
- [T4真实Gazebo固定台架材料](tests/handover_delivery_gazebo_20261115/PORTABILITY.md)：driver源码、world模板、参数化runner、两个32步原始trace、只读核验器。motor-0.bin为小型测量记录，不是可执行文件。

原运行与发布副本的哈希分别保留。整理版仅做Python语法、固定引用/本地链接及已存trace只读复核，没有重跑整理版runner，没有追加飞行或Gazebo。T4原始材料未改，路径参数化副本不冒充原运行脚本。原基线检查通过不代表具备后期Lab依赖；本页代码定位明确区分上游基线与历史修改版。

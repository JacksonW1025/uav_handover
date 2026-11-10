# 一个真实的 Mission → RAPTOR 切换：完整 SITL 单例报告

## 1. 结论与阅读顺序

**已在 Thor 完成一个主体 C→N 切换、18s 神经参考任务、经典控制回收、落地和 disarm。** 只使用 seed **20261109**。主体前有一次工程失败，修复同一 MAVLink socket 的生命周期后在新目录重启；总物理启动 **2次**，真实主体 C→N **1次**，不能写成“一次启动全程无故障”。

三个结论必须并列：

- **工作流 COMPLETE**：注册、准入、Mission、唯一主体切换、参考任务、输出链证据、落地和退出均完成。
- **任务判据 SUCCESS**：最大倾角 **39.302°**，最大高度损失 **0.508m**，未触发“倾角>45°或高度损失>1m”。
- **冻结主判据 FAILURE**：切换后前10s内没有连续2s的联合恢复，最长仅 **0.576s**。不能用后期平稳或较小平均误差将它改为成功。

最有研究价值的发现是：**模式进入后12ms已有神经电机发布，16ms已被四个 Gazebo 电机应用，而首个外部参考到276ms才被控制器读到。** 飞机先在原始 reset/capture 目标下制动，再接收以较早状态为起点的运动参考。最大倾角出现在模式进入后0.300s，最低高度在0.880s。它不是一次理想的速度匹配无扰切换。

这个276ms主要与实验调度中“等 ACK 和模式确认后才发布参考”的等待有关，不能全部归因于 DDS，也不能凭一个单例证明它是倾角峰值的唯一原因。

建议依次查看：

1. [轨迹、倾角、高度及误差总览](../data/cn-single-20261109-final-v1/overview.png)。
2. [切换前后1.2s、电机与参考速度放大图](../data/cn-single-20261109-final-v1/entry-zoom.png)。
3. [主动参考断流与恢复放大图](../data/cn-single-20261109-final-v1/gap-zoom.png)。
4. [完整测量摘要](../data/cn-single-20261109-final-v1/summary.json)及[125Hz主体轨迹CSV](../data/cn-single-20261109-final-v1/subject-trace.csv.gz)。

名称日期沿用请求日2026-11-09；正式完整运行创建于 Thor 当地 **2026-11-10 09:00:44 +08:00**，原始记录保留实际时间。

## 2. 样本身份、失败及修复账本

|阶段|物理启动|真实主体 C→N|结果|
|---|---:|---:|---|
|宿主检查|0|0|CPU min972000/max2601000kHz，既有 host_gate 阻止运行；没有降低守卫|
|首次尝试|1|0|3m起飞、经典悬停10.048s完成，Mission前第二次 MAVLink handshake 失败|
|同方案基础设施修复|1|1|Mission→RAPTOR→经典回收→落地→disarm，完整证据|
|合计|2|1|同一个seed、一个完成的研究单例，没有其他随机种子或第三次飞行|

用户授权设置 Thor 时钟后，既有 host_gate 验证14个CPU的最小/最大频率均2601000kHz，无 ToDesk 会话及其他仿真进程。运行前后均保留宿主证据；没有关闭安全或准入检查。

首次失败路径是 `data/cn-single-20261109-flight`，完整运行路径是 `data/cn-single-20261109-repair-flight`。前者没有被删除、覆盖或当作无成本试运行。首次末尾仍在3.018m、armed/AUTO_LOITER；清理只请求 land 后关闭，所以**首次没有完整落地证据**。这与第二次真实 landed/disarm 必须区分。

高置信度故障原因：通用 preflight 建立并关闭 UDPout socket，场景后来新建临时源端口；PX4 `mavlink_receiver.cpp:3797–3810` 首次绑定回复peer，`mavlink_main.cpp:924–926`继续回复旧端口。第一次没有记录两个源端口，故不冒称抓包证明。修复让本场景显式保留并复用最初已验证的 socket，第二次记录的 preflight/mission local port 均 **46624**，并重新要求新鲜 heartbeat。见[修复说明](THOR_CN_SINGLE_20261109_REPAIR.md)。

修复只涉及 Python 试验接线；seed、参考、Mission、PX4二进制、策略、安全阈值、物理步长不变。`--repair-mavlink`只接受“恰好一个已终止且未进入神经的指定握手失败”，并只允许一次修复启动。账本现在已有两条 START，第三次被拒绝。见[不可覆盖的启动记录](../data/cn-single-20261109/attempts.jsonl)。

**实际完整飞行候选**：`3d9fa486833d6255f4a1e3c1bbc5d403edf79572`。飞行前后源码身份一致。最终报告提交在其后，不把报告版本冒称为飞行时源码。

## 3. 具体实验设计

### 3.1 经典前缀与真实 Mission

- Gazebo x500，初始 yaw0，seed20261109；实例21、系统ID22、ROS domain71、XRCE18888。
- Headless SITL，传感器就绪、双向DDS、Agent重连、策略自检和动态注册通过后正常解锁。
- 飞行前缀为 **AUTO_TAKEOFF到3m → AUTO_LOITER悬停10s → AUTO_MISSION**。没有将 Loiter 称为用户示例中的 Position；未关闭 Position 的手动输入要求。未解锁的预检查含短暂 Offboard 通信探测，它不是研究飞行阶段。
- 通过 MAVLink 正常上传 Mission，利用有效 EKF 全局参考将下表本地 NED 转为 GLOBAL_INT/MSL；不是用外部 setpoint 冒充 Mission。
- 航点半径0.5m、巡航目标1.2m/s。只接收本实例 autopilot component1 发给GCS245/191的正常 Mission，请求缺项、越界、身份错误、拒收和超时均失败。

|航点|N(m)|E(m)|D(m)|
|---|---:|---:|---:|
|0|3|0|-3|
|1|3|3|-3.4|
|2|-2|3|-3|
|3|-2|-2|-3|
|4|0|0|-3|

实际上传经历了重复的 MISSION_REQUEST_INT，正常重发相同项，收到 ACK0且所有0–4项已发送后才开始 Mission。上传约10.823s，未隐藏为瞬时成功。

主体触发条件固定为：当前 Mission 项为1、水平速度≥0.6m/s、距该航点>0.75m，连续0.2s。实际达到条件，但**“当前项1”不保证速度方向已对准第二航段**：触发时仍有明显向负N的速度，属于第一航点附近制动/回摆后的接管。这是实际状态，不将它改写为理想稳定巡航。

### 3.2 唯一主体 C→N 与原始 reset

使用正常 `VEHICLE_CMD_SET_NAV_STATE=100001` 请求日志实际分配的 RAPTOR mode23，等待 Commander ACK及nav_state。没有强写模式、控制所有权或状态。`MC_RAPTOR_RINI=0`、`RTGT=0`、`RREC=0`、`NCO=0`，保持原始 reset，不使用旧研究中的补偿处理，不改权重或物理截止期限。

外部 setpoint **只在 runner 确认模式后开始**，不与经典 Mission 的轨迹生产者提前竞争。首条参考位置、速度和yaw锚定请求前的最新接收状态。因此在控制器实际接管和第一条参考到达之间，存在真实的非零延迟。这个选择已在飞行前固定，是本例要观测的完整链路的一部分。

### 3.3 18s 外部任务及主动断流

50Hz发布有限的 position、velocity、acceleration、yaw及yawspeed。位置/速度用端点加速度为零的 C2 quintic连接。相对触发点的段落为：

|参考时间|终点相对位移N/E/D(m)|终点速度N/E/D(m/s)|
|---|---|---|
|0–2s|水平0.8×初始速度，垂直0.4×初始垂直速度|0/0/0|
|2–5s|-1/+1/-0.3|-0.4/0/0|
|5–8s|-2/0/0|0/-0.3/+0.1|
|8–11s|-1/-1/+0.3|+0.4/0/0|
|11–14s|0/0/0|0/0/0|
|14–18s|保持触发点|0/0/0|

yaw在14s内执行最大30°的平滑 sin²脉冲后返回。**7.00–7.32s只暂停发布一次**，轨迹时间继续；恢复时发布同一时间轨迹，不从中断点重新起算，不再切模式。

触发后完整参考范围检查通过：最大参考半径3.149m，参考高度2.795–3.395m；加1m预留后仍在8m参考边界内。运行安全边界不变：半径10m、高度8m、倾角45°、角速度分量8rad/s。意外退出RAPTOR、失去active或安全事件均会终止并记录失败。

18s参考阶段结束记录875次发布；回收边界期间继续发送以避免额外断流，因此875不是整个发布文件的总行数。随后一次标记 **non-subject** 的 N→C AUTO_LOITER，保持4s后 LAND，确认 landed和disarm。这是回收步骤，不作为第二个主体样本，也没有隐藏。

## 4. 实际时序：注册、准入、所有权与目标不是同一时刻

下表除注明者均是PX4原生启动时间，来源ULog/Gazebo逐步记录。不要把DDS UTC字段直接当作原生时间。

|事件|原生时间(s)|相对RAPTOR进入|
|---|---:|---:|
|注册回复成功，mode23/arming_check_id0|3.400|启动阶段|
|进入AUTO_MISSION|58.360|−8.088s|
|Mission当前项1|66.168|−280ms|
|外部模式命令的日志timestamp|66.420504|−27.496ms|
|Command ACK accepted|66.436|−12ms|
|nav_state23，首个active观测|66.448|0|
|神经电机首次发布/owner证据|66.460|+12ms|
|四个Gazebo电机首次应用该输出|66.464|+16ms|
|首次有效读取设计的外部参考|66.724|+276ms|
|最大倾角39.302°|66.748|+300ms|
|最低高度2.561m|67.328|+880ms|
|回到AUTO_LOITER|84.760|+18.312s|
|进入AUTO_LAND|89.164|回收阶段|
|landed|95.196|回收阶段|
|disarmed|97.204|回收结束|

命令timestamp是消息携带/记录时间，不是精确的 Commander函数到达探针。nav_state与首个active在66.448s已变化，此周期输出仍未交给神经；setpoint configuration已请求直接执行器，而部分经典control flags仍保留到此周期。必须以实际output owner和Gazebo消费再确认后续边界。

主机侧独立分解：

- runner的“发出C→N请求→确认模式”约 **300.795ms**，含粗粒度等待；不是300.795ms的真实模式切换。
- 首个active周期的 `run_wall_ns` → runner记录确认，**273.154482ms**。
- 首次 publish 调用返回 → 控制器读取并记录，**2.458723ms**，包含传输、调度及读取处理，不是纯网络耗时。
- 两者使用同机 `CLOCK_MONOTONIC`，没有DDS UTC换算；276ms则来自原生仿真时钟，不能要求将两个主机差值相加等于它。
- 首次发送的position/velocity转float32后与首次有效读取值逐项相同，关联有内容证据。

## 5. 飞机表现和控制输出

### 5.1 接管状态与初期瞬态

请求前轨迹锚点：p=(3.1484, −0.0501, −3.0945)m，v=(−1.3776, +0.1189, +0.5127)m/s。

实际模式进入：p=(3.0298, −0.0371, −3.0685)m，v=(−1.4304, +0.1391, +0.3750)m/s。

P11证据显示：激活时 `stale=1`、`activation=1`、`last_valid_read_us=0`；先捕获当前位置、目标速度0；GRU16维和previous_action4维清零。当前速度与零速度目标不匹配，首个策略输入分量12触及−1裁剪，首个动作也有+1裁剪。因此即使之后设计了速度连续的外部轨迹，**真正最初的神经控制并没有立即使用它**。

当外部参考终于到达时，位置参考仍从更早的触发状态出发，造成最大约0.517m的目标误差。这个过程可直接从[初期放大图](../data/cn-single-20261109-final-v1/entry-zoom.png)看到：目标北向速度先为0，+276ms才跃迁到约−1.38m/s。图的黑/红/橙/紫竖线分别为模式进入、神经发布、物理应用、首次参考读取。

### 5.2 全神经窗口统计

|量|实测|
|---|---:|
|nav_state神经窗口|18.312s|
|神经motor owner窗口|18.300s|
|最大倾角|39.301895°|
|进入高度 / 最低高度 / 最高高度|3.068464 / 2.560958 / 3.368280m|
|最大高度损失|0.507506m|
|最大水平半径|3.182847m|
|最大水平速度|1.599823m/s|
|最大角速度分量|4.039741rad/s|
|精确consumed-target位置RMSE / 最大误差|0.094786 / 0.517430m|
|归一化电机范围|0–1，全部有限|
|最长连续电机饱和|112ms|
|整个神经窗最大相邻电机步变|0.710914|
|实际owner交接处最大电机步变|0.333152|

跟踪误差以**控制器实际消费的P11目标**为基准，不是发送端轨迹或固定悬停点；小RMSE不能证明目标交接无扰。局部位置来自估计器，不是独立运动捕捉的真值。

后验描述窗口中，初期1s目标误差RMSE0.317m；最后保持段RMSE0.0301m、最大倾角1.669°。最终静止目标首次有效读取为原生80.728s，即进入后14.280s。补充脚本标注14.276s的近似窗口边界，但125Hz采样网格第一点本来就在14.280s，统计不受影响。相位倾角采用125Hz采样，与250Hz全姿态流的39.301895°全局峰值略有不同。

### 5.3 主动断流真正经历了什么

- 计划停止发布320ms；实际最后一次发送到恢复发送间隔 **327.130ms**。
- 控制器最后一次有效读取73.720s，下一次有效读取74.048s，实际有效读取间隔 **328ms**。
- 到73.924s，即上次读取后 **204ms**，严格>200ms超时条件触发，出现内部capture/stale。
- stale持续 **124ms**，74.048s恢复有效外部目标。
- 这与接管初始的276ms无有效外部目标是两个独立时段。

图中橙色表示328ms有效读取间隔，**不是整段都已过期**；红色表示真正124ms stale。后验gap/恢复窗口最大倾角14.829°、最大目标误差0.132m，比初期峰值温和，但它们处于不同运动状态，不是能证明“断流比切换安全”的受控比较。

### 5.4 实际电机消费与计算频率

四个电机记录一致，无不完整二进制尾部。神经窗口的 **4575条已记录发布均找到物理应用**，应用sample age全为4ms，无hold、无Gazebo覆盖；PX4 mixer在神经窗口也无发布覆盖。这里的“全部应用”仅针对本次已记录的发布覆盖范围，不是对latest-value架构作逐条必达承诺。

全流程在神经窗口之外仍有2个hold和2个Gazebo覆盖步，最老8ms，不能把整次运行写成绝对零hold。见[输出链报告](../data/cn-single-20261109-repair-flight/output-chain.json)。

P11 active共有4578行，其中native executor2289步，原生周期固定8000µs，即 **125Hz**；电机发布/物理步为250Hz。不能把通用250Hz control_step称为250Hz神经网络前向。native executor的observe+control时间平均2.607µs、p99 19µs、最大40µs，这不是单独的网络forward基准。

## 6. 准入与健康检查的解释边界

RAPTOR注册成功不等于可运行；单个组件的 `can_arm_and_run=1` 也不等于最终Commander决策。此次证据串联为：

1. request1337注册成功，动态mode23、检查ID0。
2. 进入前最近arming reply在66.436s：`can_arm_and_run=1`。
3. 进入前最近health_report在56.416s：can_arm/run mask16726712含mode23位；health warning/error为0，但arming_check_error_flags为1048704。不是“全系统所有检查都无错误”。
4. 正常Command ACK accepted，实际nav_state23，随后output owner改变且物理端应用。
5. 神经窗口 `vehicle_status.failsafe`全为0，无runner safety abort，ULog dropout0，要求主题无缺失。

**发现并保留了一处原有实现缺陷，不在这次飞行中顺手修改：** `mc_raptor.cpp:576`声明 `arming_check_reply_s arming_check_reply;` 没有零初始化。显式设置了主要要求，但两个relaxed-position字段未设置。ULog中 `mode_req_local_position_relaxed=-1` 为非规范bool表示。

应区分两类字段：`health_component_index=0`使 `externalChecks.cpp:196`跳过可选health flags，`num_events=0`使未用events不被处理，不能把这些未初始化垃圾值解释成真实健康故障。相反，local/global relaxed-position字段会被 `externalChecks.cpp:176–181`无条件消费，并影响后续mode checks，因此不能一律称为无害padding。未初始化bool还涉及C++未定义行为。

实际准入及完成已经得到观测，但这项缺陷限制了跨构建/跨运行复现和健康证据解释的可信度。**没有证据证明它导致首次UDP故障，也没有本例中的因果对照证明它改变了飞行结果。**

## 7. 冻结判据与研究判断

冻结主判据保持原样：安全范围、地面高度、≥0.5s连续电机饱和，以及接管前10s内连续2s同时满足位置误差≤0.2m、速度误差≤0.1m/s、角速度范数≤0.1rad/s；观测间隙>20ms打断连续性。恢复以实际控制器目标为基准。

本次仅恢复项失败，最长联合满足0.576s。移动参考和yaw任务可能使这个偏稳定恢复的条件难以持续满足，但不能因为不适合展示成功就事后更换。并列任务判据“倾角>45°或高度损失>1m”未触发；最终落地也完成。它们回答的是不同问题。

从这个单例可以支持的判断：

- 研究切换不能只有nav_state边沿。至少需要分别度量准入、模式、控制权、执行器消费、有效参考进入和网络状态初始化。
- 本例最大的姿态/高度代价出现在初始接管附近，而不是后来主动断流附近。12/16/276ms三条边界解释了为何“模式已进入”与“新任务已生效”明显不同。
- 最终跟踪较好不意味着初始切换质量好。RMSE、峰值、恢复判据、任务完成和安全事件要并列。
- runner等待和参考生效顺序本身是实验设计变量。值得后续单独设计“等确认后发送”对比预置/原子目标交接，但**本次没有额外运行任何对照**。
- 健康消息初始化缺陷值得后续单独修复并验证，不能用本例一次获准运行就忽略。

不能支持的结论：神经优于经典、对其他种子或机型可靠、某一延迟单独导致39.3°峰值、真实飞机安全，或修改后一定无扰。只做了一个完成的主体样本，且完整Mission未飞完，而是在第二航点任务中按设计中断给RAPTOR。

## 8. 测试、成本与交付证据

### 验证

- 最终离线回归 **119项通过**，pytest报告4.53s，测量wall4.845s/CPU4.733s。见[日志](../data/cn-single-20261109-final-v1/offline-tests.log)及[命令/成本](../data/cn-single-20261109-final-v1/offline-tests-cost.json)。
- 覆盖C2几何、边界、有限值、Mission身份/缺项/拒收、模式失效、数据间隙、不把非有限当成功、清理失败、预算和修复限制；包含真实localhost UDP/MAVLink编码测试，验证固定peer场景下复用socket。
- 正式SITL完整流程、historical analyzer、output-chain analyzer、single-case analyzer均退出0。工作流成功与冻结主判据失败已分开。
- PX4/策略没有修改，因此使用现有已固定binary，未声称本次新编译PX4。宿主后的host_gate通过，无残留仿真。
- 三张图已逐张检查；离线补充不再次启动PX4/Gazebo。健康和时序分析做了独立只读复核。

### 运行成本

|范围|wall(s)|CPU(s)|
|---|---:|---:|
|首次主体前失败的物理流程|56.139|22.516|
|完整单例的物理流程|100.844|43.761|
|两次物理流程合计|156.984|66.277|
|两次标准离线分析合计|5.159|5.113|
|最终119项回归|4.845|4.733|

物理流程包括启动、检查、飞行、关闭，CPU是runner及被等待的子进程使用量，不是飞行原生时长。后验画图/人工阅读/开发前几轮测试和API费用不在上表中；完整费用账单不可得，标为未测，不补0。完整运行板级功耗99个采样，均值29.832W、最大32.658W，只是宿主观测，不是控制器独立功耗或计费。

### 文件与身份

- [完整单例测量](../data/cn-single-20261109-repair-flight/cn-measurement.json)、[事件](../data/cn-single-20261109-repair-flight/events.jsonl)、[metadata](../data/cn-single-20261109-repair-flight/metadata.json)、[运行结果](../data/cn-single-20261109-repair/result.json)。
- [两次原始证据SHA256清单](../data/cn-single-20261109-final-v1/raw-evidence-manifest.json)、[图表/CSV清单](../data/cn-single-20261109-final-v1/manifest.json)。
- 正式ULog：66,959,199bytes，SHA256 `a080ca54c4178950d3f1acc359c91542adbac269db1dd0b31980c6f9a8e913d0`。
- 首次失败ULog：33,885,663bytes，SHA256 `a092efe86c8a612a0d0b347e674cb4a533df4825387c813bbe3871e07f73453e`。
- PX4基础commit `4ae21a5e569d3d89c2f6366688cbacb3e93437c9`；应用补丁的diff/untracked身份见metadata，不能只凭基础commit复现。
- 实际binary SHA256 `784f4fd32a246b0de04c4c074f88bc1833231e71b4b80b7c0f6d7e798a1d41a1`。
- policy SHA256 `5327c83dc57f094ca1977a2533ebce318645be010e16b9354c96c337cd5c278b`。
- 源代码入口：[runner](../tools/cn_single/runner.py)、[轨迹设计](../tools/cn_single/design.py)、[冻结分析](../tools/cn_single/analyze.py)、[后验图表](../tools/cn_single/review.py)、[修复配置](../config/cn_single/repair.json)。

原始ULog、逐步Gazebo二进制、遥测、资源、外部发布记录留在Thor的上述两次运行目录，按仓库策略不推大文件。远端提交可审查的小证据、压缩CSV、图片和报告；GitHub上的CSV不是完整ULog替代品。用户原有未追踪文件和main分支未改动。

已完成的执行入口为 `./tools/cn_single/experiment --execute --repair-mavlink`，**不要再次启动来复现本轮结果**；账本会拒绝。只读重分析应指定新的输出位置，例如 `tools/cn_single/review.py data/cn-single-20261109-repair-flight data/<new-offline-output>`，它拒绝覆盖已存在输出。

最终远端发布身份以交付消息的commit与已核验远端SHA为准；Git push成功不等于CI通过。

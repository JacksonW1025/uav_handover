# 单例经典 Mission → RAPTOR：准备完成，实飞仿真被宿主时钟门阻止

## 结论先行

**本轮没有启动 PX4/Gazebo，也没有完成 SITL 飞行。飞机表现、真实切换延迟、轨迹误差、电机响应和安全事件均为 UNKNOWN，不能用于研究判断。**

已完成独立单例实现、固定实验配置、原生时钟分析入口、离线回归和阻碍证据保存。入口实际停在仓库既有 `host_gate()`：Thor 本次 CPU 最小频率为 972000 kHz、最大 2601000 kHz、governor 为 schedutil，不满足既有的最小/最大均为 2601000 kHz 的要求。执行 `sudo -n jetson_clocks` 返回 `sudo: a password is required`，退出码 1，时钟设置没有执行。没有通过修改守卫、改阈值或替代权限路径继续。

- 物理启动：**0**；C→N 主体切换：**0**；飞行结果：**NOT_RUN**。
- `data/cn-single-20261109/attempts.jsonl` 只有 `BLOCKED_BEFORE_START`，没有 `START_INTENT`。
- 已保留 `preflight-v1.log`、`host-blocked.json`、`sudo-clock-attempt.txt` 和 `status.json`。
- 名称中的日期沿用请求日 UTC 2026-11-09；Thor 本地取证时为 2026-11-10，原始记录保留实际时钟。

## 预先固定的单例设计

只用 Gazebo seed **20261109**、x500 初始 yaw 0°、一个物理启动预算。它不是随机搜索、不同种子比较或旧 P16 结果的复用。

### 经典控制前缀

沿用仓库拥有进程的隔离 SITL 流程：实例21、系统ID22、ROS domain71、XRCE UDP18888；检查真实传感器就绪、双向 DDS、Agent 重连、策略自检、注册成功，再正常解锁。控制器状态只读，不执行通用 `state_contract` 中的注入/恢复诊断。

使用真实 **AUTO_TAKEOFF 到3m → AUTO_LOITER 悬停10s → AUTO_MISSION**。这里没有把 Loiter 或 Offboard 冒称为 Position：用户给出的 Position 示例不是本实现实际采用的模式，真实 Position 所需的手动输入检查也没有被关闭。

通过已核验本实例身份的 MAVLink mission 协议上传并等待完整 ACK，航点为本地 NED 米：

| 序号 | N | E | D |
|---|---:|---:|---:|
|0|3|0|-3|
|1|3|3|-3.4|
|2|-2|3|-3|
|3|-2|-2|-3|
|4|0|0|-3|

利用有效的 EKF 全局参考转换为 GLOBAL_INT/MSL，航点半径0.5m、巡航速度1.2m/s。支持整数和浮点两种 Mission 请求。只处理本实例 autopilot component1 发给 GCS245/191 的正常 mission；拒绝越界请求、拒收 ACK、缺项 ACK 和超时。并不把外部轨迹流伪装成 Mission。

**主体触发**：Mission 当前项为1、水平速度≥0.6m/s、距第二航点>0.75m，连续0.2s。因而是在带水平运动、转向及高度任务的 Mission 中途请求切换，而非悬停时改标签。触发等候最多25s，不满足就保留失败，不改参数重飞。

### 唯一主体 C→N

使用日志实际分配的 RAPTOR mode ID，通过正常 `VEHICLE_CMD_SET_NAV_STATE=100001` 请求。等待正常 ACK 和 `vehicle_status.nav_state`，不强写 nav_state、关闭 Commander 检查或提前假定电机权已移交。

显式采用原始控制语义：`MC_RAPTOR_RINI=0`、`RTGT=0`、`RREC=0`、`NCO=0`，不改网络权重、物理步长或截止期限。RAPTOR 原有 reset 作为被测对象，未换成此前 N2 等补偿处理。

**外部 setpoint 仅在模式确认后开始**，避免与经典 Mission 轨迹生产者竞争。首个 reference 锚定请求前最后已接收位置、速度、yaw；这个状态和第一条发布间存在真实通信/调度间隔，不能称为理想的零误差无缝交接。是否先捕获当前位置、是否先读到残留 Mission 目标、何时读到新外部目标，都由原始 P11/uORB 证据判定，不预设答案。

### 18s 神经任务

50Hz 发布有限的 position、velocity、acceleration、yaw、yawspeed。位置/速度采用端点加速度为零的 C2 quintic 连接：

- 0–2s：从触发时真实速度连续制动到速度0，水平目标移动0.8×初始速度，垂直目标移动0.4×初始垂直速度。
- 2–5s：相对触发点到(-1,+1,-0.3)m，末速度(-0.4,0,0)m/s。
- 5–8s：到(-2,0,0)m，末速度(0,-0.3,+0.1)m/s。
- 8–11s：到(-1,-1,+0.3)m，末速度(+0.4,0,0)m/s。
- 11–14s：回到触发点并停稳；14–18s保持。
- yaw 采用平滑 sin² 脉冲，14s内最大增加30°后回原值。
- **7.00–7.32s 主动中断发布一次**，轨迹时间继续前进，恢复时回到同一时间参数轨迹。它用于暴露200ms有效目标超时、内部捕获及恢复目标跳变，不是第二次模式切换。

触发后先检查完整参考轨迹：加1m预留后半径不超过8m、高度2–5m。原始实时安全边界维持10m半径、8m高度、45°倾角和8rad/s角速度分量。所有运行中的神经阶段还检查 nav_state 与 active 持续存在；意外退模直接记录失败，不把经典控制接管后的轨迹算成神经任务完成。

### 收尾和计数

主体仅一次 C→N。18s任务结束后进行一个明确标记 **non-subject** 的 N→C AUTO_LOITER 恢复，4s后正常 LAND，确认 landed 和 disarmed。这是完整起降所需的回收切换，不被隐藏，也不混称成第二个研究样本。返回前的原生边界读取保持发布，避免人为多造一个末尾超时。

异常仍沿用已有安全清理。清理中仅请求 land 后立即关闭的情况不等于已验证落地，必须报告 abort/清理异常；terminal receipt 尽量保留。单次 START 账本不会因为失败或连接中断自动补跑。

## 为什么不是一个“切模式”的简单测试

观测链为：注册请求/回复及动态ID → external arming/health requirements → Commander实际准入 → nav state/control flags → RAPTOR真实输入及GRU/执行器 → 共用 actuator gate → motor publication → ESC/Gazebo消费。

对应当前源代码：

- `mc_raptor.cpp:362–372,617–627`：注册申请与回复。
- `commander/ModeManagement.cpp:220–330`：注册有效性及模式/检查槽分配。
- `Commander.cpp:1077`、`UserModeIntention.cpp:44–90`：模式请求到 armed canRun 检查。
- `mc_raptor.cpp:569–594`、`checks/externalChecks.cpp:123–217`：神经模式健康/运行要求。
- `mc_raptor.cpp:829–873,1052–1098`：外部输入有限性、有效读取本地时钟以及严格大于200ms的过期逻辑。
- `mc_raptor.cpp:1200–1288`、`research/state/ActuatorGate.hpp`：执行结果到归一化电机命令和实际仲裁。
- 已有 `research_output` 与逐步 Gazebo motor trace：证明实际消费，不能要求 latest-value 链条中的每次神经发布都被物理端逐条执行。

以上为现有代码检查结果，不是这次新飞行的实测结果。

## 数据、分析与判据

新增运行本地 logger topics 包括注册、arming-check、health、failsafe、mission/result、setpoint-config，并启用已有被动 P11 观测。保留配置、二进制/权重/源码 hash、Mission ACK/进度、所有请求/响应、原始ULog、外部发布表、遥测、资源与逐步电机记录。

分析分开报告：

1. 原生 nav 切换、首个 active observation、首个有效目标读取、首个神经 motor publication，绝不直接把 DDS UTC 当 native PX4 时间。
2. 精确 P11 consumed target 下的位置误差、神经窗口最大倾角/高度损失/速度、motor step、饱和、非有限值。
3. 原冻结主判据：安全边界、0.5s连续电机饱和、地面高度、10s内2s联合恢复（任何>20ms观测缺口打断连续性）。移动任务可能刻意不满足“恢复”条件，仍原样报告，不能替换成更宽松的跟踪指标。
4. 并列任务判据：倾角>45°或高度损失>1m。非有限/不足观测为 UNKNOWN，不记成功。
5. 工作流完成与飞行成功分开。COMPLETE 需恰好一个主体请求、一个实际神经模式入口和电机所有权入口、参考任务结束、落地请求、disarm、PX4退出0、证据主题齐全、原输出链检查及源码身份不变。一个完整观测的失败飞行仍是结果，不会被改成成功。

旧通用 analyzer 也保留，但其悬停/恢复 verdict 不能单独当此移动任务的验收。raw ULog/Gazebo/遥测/发布记录按现有策略仅留Thor，远端提交小证据和报告。旧失败运行和用户原有未追踪文件没有覆盖、删除或纳入本次提交。

## 已验证与未验证

离线回归最终日志为 `data/cn-single-20261109/offline-tests-v4.log`：117项通过。覆盖几何/速度/加速度连续性、参考范围、gap边界、配置安全阈值保持、实际 pymavlink 消息API的模拟握手、缺项/拒绝/目标范围、重复START拒绝、模式失效、清理异常以及非有限证据不算成功。它不替代真实 SITL。

没有更改PX4或策略，因此没有声称新编译验证；没有启动飞行，故 **Mission 实际准入、完整ROS/Gazebo联动、首帧切换竞争、320ms缺口的实际消费时长、logger完整性、电机消费与落地均未验证**。现阶段代码是准备版，不是已经运行通过的实验版本。

成本：physical START0；没有新仿真飞行成本。最后一轮离线测试实际 wall/CPU记录见 `offline-tests-v4-cost.json`；开发前几轮日志一并保留。整段开发、阅读、工具/API费用没有可核验完整账单，标为未测，不补0。44GiB量级剩余空间在host记录中保留，没有删除旧数据换空间。

## 继续的最小步骤

在Thor本机终端执行 `sudo jetson_clocks`，密码只在本机输入。完成后确认既有 host_gate 能通过，再继续同一个seed和单个预算；不要降低守卫或另起种子。

准备好的正式入口（仍自行执行守卫）：

```bash
cd /home/car/uav_handover
./tools/cn_single/experiment --execute
```

它需要未存在的 `data/cn-single-20261109-flight`。如果已有 START_INTENT，不得重新调用来“补一次”，须先核对原输出和进程状态。只做离线重分析时，用 `tools/cn_single/analyze.py RUN --output NEW_FILE`，输出文件不得存在。

用户此次要求的完整SITL及飞机表现分析仍未完成；这个报告只交付已完成的准备工作和准确阻碍。

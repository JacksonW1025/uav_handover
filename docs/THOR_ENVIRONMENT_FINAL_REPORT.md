# Thor 软件环境建设与最终验收报告

日期：2026-10-09，Asia/Shanghai。项目：`/home/car/uav_handover`。实验状态：**环境检查完成**。

## 1. 最终结论与适用范围

当前设备已经实际运行经典 PX4、RAPTOR、C→N→C、三次重复交接及状态 Reset / Hold / Restore / Inject 实验，具备开展**冻结配置下短时 SITL 正式对照实验**的基础条件。最终 25 项判断、实际命令、退出状态、日志位置见[验收矩阵](THOR_ACCEPTANCE_MATRIX.md)与[acceptance.json](../data/environment-20261009/acceptance.json)。

验收使用本轮新生成的 ULog；保留建设中的失败尝试。神经控制独立发布执行器命令，经典控制负责起飞和降落。训练机体完整动力学、长期可靠性、真实飞行与全飞控状态恢复不属于已证明的结论。TEST-13 和 TEST-20 的具体范围另在机器结果中声明。

## 2. 实机和系统

重新检查确认 NVIDIA Thor / aarch64、14 个 CPU、约 122 GiB RAM，Ubuntu 24.04.3 LTS、NVIDIA 驱动 580.00、L4T 38.2.1、CUDA 13.0.48、系统 Python 3.12.3、ROS 2 Jazzy。实际 Gazebo 使用 Jazzy vendor 的 Harmonic 8.11.0。没有更换系统、驱动、CUDA 主版本或系统 Python。

完整硬件、磁盘、编译器、版本和动态库输出见 [final-health-classic](../data/environment-20261009/final-health-classic/result.json) 与 [final-health-raptor](../data/environment-20261009/final-health-raptor/result.json)。资源余量随运行变化，以日志采样时刻为准。

## 3. Python 依赖和 ABI

使用 Lab 内 `.local/venv`，基于系统 Python 创建并启用 `--system-site-packages`。保留 ROS 所需 NumPy 1.26.4 和 EmPy 3.3.4，不使用旧依赖清单中的 NumPy 2 覆盖系统 ABI。

关键版本：pyulog 1.2.4、pymavlink 2.4.50、kconfiglib 14.1.0、Jinja2 3.1.2、PyYAML 6.0.1、packaging 24.0、jsonschema 4.10.3、typeguard 4.1.5、pandas 2.1.4、SciPy 1.11.4、matplotlib 3.6.3、pytest 7.4.4、psutil 5.9.8、rclpy 7.1.5、colcon-core 0.20.0、pyros-genmsg 0.5.8、nunavut 2.3.1。补装 cffi 解决现有 PyNaCl 依赖检查缺项。两套环境最终导入和 `pip check` 通过。

新增依赖入口为 [requirements-research.txt](../requirements-research.txt)；完整实际安装版本、路径和系统包见 [environment.lock](../environment.lock) 与健康检查结果。

## 4. ROS 2 工作空间

`workspaces/classic` 构建 px4_msgs；`workspaces/raptor` 构建对应 px4_msgs 和 px4_ros2_cpp。两套 overlay 独立加载。原生 Python type support、真实本地 pubsub、C++ 编译和 pubsub 均通过；接口库 colcon 单元测试已执行。原有接口库的三处修改保留在 [ros2-interface-existing.patch](../patches/ros2-interface-existing.patch)。

实际 PX4 测试验证了 VehicleStatus / Odometry / Attitude / LocalPosition、ROS VehicleCommand→PX4 ACK、OffboardControlMode、TrajectorySetpoint 到 uORB 的双向链路，且停止并重启本轮 Agent 后恢复遥测。RAPTOR 额外导出并实际收到 RaptorStatus 和 RaptorInput。依据见[最终 ROS 命令](../data/environment-20261009/final-commands/final-ros-raptor.json)、[接口测试](../data/environment-20261009/logs/interface-unit-tests.log)、各最终实验 `validation.json` 与 `logs/commands.log`。

## 5. classic 构建与运行

classic 固定提交 `d6f12ad1c4f70ad3230afd7d86e971421e02fef4`，源检出保持干净。实际编译 `px4_sitl_default`，使用编译生成的插件和二进制运行 headless x500。最终连续三轮默认相对高度起飞、经典悬停、降落和进程退出通过，见 [final-classic-relative-03](../data/final-classic-relative-03/validation.json) 及其前两轮。

高度 3 m、经典窗口至少 10 秒；验收位置误差 ≤1 m、倾角 ≤15°。标准在运行前写入 [config/experiment.json](../config/experiment.json)，未为失败结果放宽阈值。

## 6. RAPTOR 构建与运行

RAPTOR 固定提交 `4ae21a5e569d3d89c2f6366688cbacb3e93437c9`，保留原有 RouteObservability 和控制链修改。实际构建 `px4_sitl_raptor`，确认 `CONFIG_MODULES_MC_RAPTOR=y` 和 `CONFIG_LIB_RL_TOOLS=y`；旧 default 预编译文件不能代替此构建。

最终实验使用同一二进制，开启 `MC_RAPTOR_ENABLE=1`、`MC_RAPTOR_OFFB=0`，解析实际注册的动态 mode_id（本机为 23），没有将固定编号写为通用假设。神经窗口至少 5 秒，回经典后至少 10 秒并降落。见 [verified-raptor_hover](../data/verified-raptor_hover/validation.json)。

## 7. 冻结策略

检查点来自固定 blob 子模块，结构为 22 维观测、Dense 16、GRU 16、Dense 4；CPU 推理，无 GPU 后端修改。策略文件在每轮私有 rootfs 的 `raptor/policy.tar` 加载。模块自测、有限输出、实际飞行控制分别验收。

`policy.h`、`policy.tar`、`benchmark.h` 的 SHA-256 全部写入 [environment.lock](../environment.lock)，与原始快照一致；每轮元数据另存策略身份。没有修改权重或训练算法。策略自测和实际 active 诊断见最终轮 `logs/px4.log`、`events.jsonl`。

## 8. 机体、坐标和电机适配

完整源码依据和数值见 [THOR_PLATFORM_MAPPING.md](THOR_PLATFORM_MAPPING.md)。记录 NED/FRD 与 FLU、四元数及角速度转换，动作 `(a+1)/2`，Crazyflie→PX4 排列 `[a0,a2,a3,a1]`，x500 电机编号、旋向、质量、惯量及 Gazebo 速度/推力模型。

保留原有 x500 与 PX4 分配参数，未引入隐蔽控制补偿。策略训练的完整动力学未随资源提供，因此只能证明当前固定机体短时可控，不能证明训练模型一致。原实现在 250 Hz 仿真下 native 同步为 2 步，约 125 Hz，区别于训练 100 Hz；这项差异保留并报告。

## 9. 双向交接与执行器归属

记录请求、ACK、模式确认、RAPTOR active、状态应用和实际 actuator_motors 发布者。新增 ResearchActuator 在两个发布点保存精确 actuator 时间戳和命令；原 RouteObservability 完整保留。

复核早期重复交接发现独立缓存的 allocation flag 可产生一次短暂 C→N→C→N 来源反复切换。新增仅 POSIX 的共享 `ActuatorGate`，两个发布点在同一互斥锁内读取最新 vehicle_control_mode，再决定发布；不修改控制计算与权重。最终要求整个飞行的实际来源转换次数与请求次数一致，而不只检查稳定窗口。最终三轮交接见 [verified-repeated_handover](../data/verified-repeated_handover/metrics.json)；旧失败证据保留。

外部模式确认按约 0.1 秒遥测节奏观测，不能作为精确内部延迟。分析器另以 PX4 nav_state_timestamp 和实际 actuator 时间计算内部切换延迟。交接电机阶跃如实报告，没有将“能稳定接管”等同于“输出无阶跃”。

## 10. 状态研究接口

[StateOps](../research/state/StateOps.hpp) 固定最多 32 float；三类实际暴露状态为 RAPTOR 26 维（GRU 16、previous_action 4、NED 位置参考 3、速度参考 3）、角速度积分器 3 维、速度积分器 3 维。支持 READ / SNAPSHOT / RESET / HOLD / RESTORE / INJECT / RELEASE。

接口仅 POSIX 编译，`MC_RAPTOR_RSH=0` 默认关闭。写入由控制器自身线程在周期边界执行，整包维度、有限值、范围先检查。GRU/previous_action 限绝对值 1，位置 100 m、速度 10 m/s，速度积分器 4，角速度积分器使用实际 PX4 限制。错误码区分关闭、活动拒绝、维度、非有限、范围、无快照和未知操作。

活动控制器允许读取、快照、重置、保持；活动恢复/注入拒绝。HOLD 冻结选定记忆，仍根据新观测计算电机输出。RESET 清记忆并保留 RAPTOR 六个参考。失败不部分写入。快照只有当前进程每模块一个内存槽。

`MC_RAPTOR_RINI=1` 仅研究接口开启时允许进入模式保留记忆，并重建 executor 时序。经典积分器要跨非活动清零周期恢复，须 HOLD→RESTORE→切回 C→RELEASE。最终恢复和注入实验实际核对操作前后数值、ULog 请求/响应与 HOLD 期间值不变；不是仅核对返回码。ASAN/UBSAN [单元测试](../data/environment-20261009/final-commands/state-unit.json)及四类最终 SITL 通过。

未暴露 EKF、FlightTask、姿态/速度滤波器、Lissajous 发生器全部记忆。全状态快照需为各模块定义版本化序列化及一致性边界，不能由当前几个向量安全代替。当前参考实验限定 `MC_RAPTOR_INTREF=0`。

## 11. 日志与时间对齐

ULog 连续采集位置/速度、姿态、角速度、参考、经典 rate_ctrl_status、控制模式、动作/电机命令、推理时序、RouteObservability。GRU、previous_action、速度积分器、内部参考按状态操作和交接边界事件记录，避免高维连续记录影响时序。研究消息均已实际编译并进入新 ULog。

ROS 辅助遥测和外部事件为 JSONL；未生成完整 MCAP，也未把 JSONL 称为完整 rosbag。DDS 将 PX4 时间戳转为 Agent UTC，分析器用 ROS/ULog 完全一致的位置向量建立时间锚点，再把主机 monotonic 事件映射到仿真时间，采样不确定度约 0.1 秒。执行器来源和状态生效时间直接采用内部 PX4 时间。最终 `missing_topics`、dropouts、字段列表、状态请求遗漏均有机器结果。

## 12. 自动化入口与数据

[tools/experiment](../tools/experiment) 提供 health、classic_hover、raptor_hover、handover_c_to_n、handover_n_to_c、handover_c_n_c、repeated_handover 及四类状态实验；方向入口执行完整往返以安全结束。[run_experiment.py](../tools/run_experiment.py) 管理独立 rootfs、instance 21/system_id 22、Domain 71、Agent UDP 18888、私有 Gazebo partition 和串行锁。

运行器验证本轮 PX4 心跳身份和 ROS system_id，设启动/飞行/降落/退出超时与位置、姿态、角速度和遥测保护。每轮记录 argv/PID，只停止自己启动的进程组，先降落和 shutdown，再有界升级信号。保护和失败原因保存；不接管已有飞控。

种子 42 被记录，但未发现可验证的 Gazebo/PX4 通用种子接口，**不声称完全确定性重放**。初始模型位姿和参数明确固定。每次输出必须为新目录。输出结构与分析命令见 [Quickstart](THOR_EXPERIMENT_QUICKSTART.md)。

## 13. 分析与性能

[analyze.py](../tools/analyze.py) 读取真实 pyulog，计算位置/速度、姿态及角速度误差、控制输出阶跃、交接延迟、稳定时间、瞬态、推理时间、周期抖动、观测年龄、执行器归属、状态值和保护次数；生成 overview 与三维轨迹。经典参考在 N 期间可能陈旧，相应姿态/rate 参考误差是诊断量，不应误称神经策略训练目标误差。

最终神经轮 CPU 推理（含 observe 构造与 RL Tools control）的墙钟均值约 6.67 μs、P99 16 μs、最大 109 μs；冻结阈值为 P99 ≤2500 μs。有限输出错误与 executor warning 均为 0。active loop 相邻周期平均约 4.15 ms、P99 8 ms。周期统计排除非活动间隔，未把重新接管的停机时间当成抖动。

同轮主机 CPU 平均约 17.1%，最低可用内存约 108.3 GiB；Gazebo RTF 均值约 0.996，tj 最高约 46.6°C，VIN 平均约 31.4 W、峰值约 39.1 W。其他任务的主机负载可能计入；不是 PX4 单进程独占占用。各进程 RSS/CPU 时间、磁盘余量见 resources.jsonl；CPU 频率、GPU 和电源数据以 tegrastats / nvidia-smi 的可读字段为准。未切换功耗模式，也未开发 GPU 推理。依据为 [verified-raptor_hover/metrics.json](../data/verified-raptor_hover/metrics.json)及其原始资源日志。

以下为最终轮次全部悬停窗口的最大值，包含起飞后的经典稳定窗口；不包含地面与降落阶段。神经单独窗口指标可在对应 metrics.json 查看。

| 最终轮次 | 最大悬停位置误差 m | 最大悬停倾角 ° | 实际/预期来源转换 | 结果 |
|---|---:|---:|---:|---|
| [final-classic-relative-03](../data/final-classic-relative-03/metrics.json) | 0.443 | 0.301 | — | PASS |
| [verified-raptor_hover](../data/verified-raptor_hover/metrics.json) | 0.452 | 1.059 | 2/2 | PASS |
| [verified-repeated_handover](../data/verified-repeated_handover/metrics.json) | 0.449 | 1.666 | 6/6 | PASS |
| [verified-state_reset](../data/verified-state_reset/metrics.json) | 0.433 | 1.336 | 2/2 | PASS |
| [verified-state_hold](../data/verified-state_hold/metrics.json) | 0.461 | 1.251 | 2/2 | PASS |
| [verified-state_restore](../data/verified-state_restore/metrics.json) | 0.445 | 1.858 | 4/4 | PASS |
| [verified-state_injection](../data/verified-state_injection/metrics.json) | 0.449 | 1.504 | 2/2 | PASS |

## 14. Git 和资源边界

整个 `uav_lab/` 保持忽略；原始 sources 快照未修改，89,867 个文件完整校验通过。只有 `.local` 检出/构建、overlay、venv 和 Lab 包装入口发生本机更新。现有 RouteObservability、接口库修改与冻结策略均保留。旧仓库路径仅作为来源历史记录，不用于活动 PATH、模型、策略、库或 ROS overlay。

`.gitignore` 新增忽略每轮 `rootfs/` 和 `cli/`；保留原始 ULog、遥测、日志及指标。主仓库不包含大型 PX4 源码快照、二进制、venv 或编译缓存。检查命令见 [git-boundaries](../data/environment-20261009/final-commands/git-boundaries.json)。

## 15. 全部最终验收

最终结果为 **25 PASS / 0 FAIL / 0 BLOCKED / 0 NOT_RUN**。完整 TEST-01..TEST-25 结果见[矩阵](THOR_ACCEPTANCE_MATRIX.md)。机器文件记录每项命令、退出状态、日志、逐轮证据和声明范围；全部建设过程的成功/失败轮次另列索引。最终验收重新运行实际飞行和分析，不复用建设前轻量检查。进程退出与端口释放另见 [cleanup audit](../data/environment-20261009/final-commands/process-cleanup.json)。最终源码重建后的二进制 SHA 与飞行时一致，适配脚本幂等性见 [idempotence](../data/environment-20261009/research-apply-idempotence.json)。

## 16. 修改的既有文件

主仓库修改 `.gitignore`、`README.md`、`data/README.md`、`Environment Check.md`。本机 Lab 修改 `env.sh`、`scripts/check_lab.py` 包装入口和 README；源码研究修改仅在 RAPTOR `.local` 检出，不改 immutable sources。

RAPTOR 新改动位置：`msg/CMakeLists.txt`、rate_control 与 PositionControl 最小 getter/setter、mc_rate_control / mc_pos_control 自线程状态桥、mc_raptor 状态/时序/模式初始化/参数/发布门、control_allocator 发布门与来源记录、DDS topic 列表。各改动由 [apply_research.py](../tools/apply_research.py) 可审查地应用，完整相对固定 HEAD 差异见 [raptor-final.patch](../patches/raptor-final.patch)。final 补丁含原有修改，勿与 existing 补丁叠加。

## 17. 新增交付物与复现

新增 `Experiment Status.md`、本报告、Quickstart、平台映射、验收矩阵、`environment.lock`、依赖入口、实验配置，`tools/` 环境/健康/构建/运行/分析/证据/导出/验收工具，`research/state/` 固定消息及头文件，`tests/` C++ 状态测试和 ROS probe，以及 `data/` 本轮原始证据。小型未跟踪源码保存在 [raptor-final-untracked.tar.gz](../patches/raptor-final-untracked.tar.gz)；原有修改另存 existing 补丁和 tar。

复现以 [environment.lock](../environment.lock) 的提交、递归子模块、安装版本和 SHA 为准。已有 Lab 使用 `./tools/prepare_lab.sh` 复用资源构建。缺失 Lab 时需先从固定来源准备 `sources/` 快照、Git 检出、Agent runtime 与 workspace 链接；主仓库没有自动重新下载或重迁移原资源。离线完整复现仍需另行归档 Lab 资源和策略，单靠主仓库不等于携带全部依赖。

干净 RAPTOR 固定检出上应用 `raptor-final.patch` 一次，再展开 final-untracked tar；ROS interface 固定检出上应用 ros2-interface-existing.patch。保留快照时不要重复应用 existing 修改。更多布局和命令见 Quickstart。

## 18. 已修复问题

| 问题 | 修复与验证 |
|---|---|
| 缺少构建/解析依赖、Python ABI 风险 | Lab 隔离补装，保留 NumPy 1.x / EmPy 3.x；两环境 pip/import 检查 |
| ROS overlay 未构建、环境继承污染 | 实际构建，清理继承路径并加载对应 overlay；Python/C++ 和实机 DDS 验证 |
| 旧 RAPTOR default binary 没有神经模块 | 构建启用 MC_RAPTOR / RL Tools 的 raptor target 并实际启动 |
| Gazebo 模型可见但缺少传感器插件 | 指定 server.config、编译插件目录和 optical_flow 子目录；新日志验证传感器与悬停 |
| SITL 无 GCS 心跳导致解锁拒绝 | 确认独立实例身份后向本轮 MAVLink 端口发送 GCS heartbeat |
| 显式零经纬度/AMSL 起飞不稳定 | 使用上游默认相对起飞语义，实际设 MIS_TAKEOFF_ALT；连续三轮验证 |
| PX4_INFO_RAW 截断状态 JSON | 分段输出完整固定维度数据，逐响应解析及状态值验证 |
| ULog 多实例订阅配置遗漏 RAPTOR 数据 | 明确 topic instance 0、RouteObservability 多实例；最终缺失检查 |
| DDS UTC 与 ULog 单调时间混用 | 真实位置向量锚定，再插值外部事件 |
| 活动与非活动状态恢复语义不明 | 明确拒绝活动注入/恢复；跨模式 HOLD 保值与 RINI 时序重建；实值核对 |
| 发布缓存引起短暂执行器竞争 | 最新模式共享发布互斥门；整个往返转换次数验收 |
| 重复适配可能重复插入日志代码 | 检查发布点标记后再插入；最终幂等性与重建二进制一致性通过 |
| 外部事件插值窗口可能比要求短约 0.1 s | 运行器额外保持 0.2 s，分析严格检查原要求最短时长 |

失败尝试没有删除；查看各轮 validation 原因、命令日志和 ULog，可区分工程修复与已验证结论。

## 19. 未解决项和研究限制

1. 训练完整动力学元数据缺失；不证明 x500 与训练机体等同，native 频率差异仍存在。
2. 只有短时悬停和有限次数交接；未进行长时、多扰动、大样本统计或真实飞行。
3. 状态接口是指定 GRU/动作/参考/积分器集合，非全飞控快照；内部轨迹发生器和 EKF 等未恢复。
4. 原显式 AMSL 起飞路径的间歇失败根因未完全定位；已切换有实际三轮证据的默认相对起飞入口，保留旧失败。
5. 外部事件定位约 0.1 s，ULog 来源事件与 actuator 日志并非每样本都一一匹配；匹配数量单独报告。全局确定性种子、长时间日志无丢失尚未证明。
6. 交接存在可测电机输出阶跃；本轮证明稳定接管，不证明无冲击控制或最优状态初始化。

这些限制不阻止当前范围的短时研究，但应写入正式实验条件。没有把缺失元数据或未经测试的能力标为已完全验证。

## 20. 开始正式实验

按 [Quickstart](THOR_EXPERIMENT_QUICKSTART.md) 先运行 health，再选择经典、神经、完整交接或状态对照入口。为每个新假设使用独立配置和新输出目录，冻结策略、平台、状态处理和重复次数；保留每轮成功/失败原始数据。先审阅本报告的边界，再比较 Reset / Hold / Restore / Inject 的交接瞬态，不把环境验收样本直接当作正式统计结论。

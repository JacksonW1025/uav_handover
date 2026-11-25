# Autoware 2.0.0：经典与神经规划器交接证据

实验于 2026-11-24 在 Thor 上完成。这里的交接是**参考轨迹的来源交接**：从完整的规则规划器（C）切到 Diffusion Planner v5（N），或者反向切回。执行纵向、横向控制的还是同一个 PID、MPC。PX4/RAPTOR 切的是飞控输出来源，两边不在同一层，但都能对照「新控制路径什么时候真正生效」的问题。

## 1. 怎样观察真实交接

使用原生 Autoware Planning Simulator，同一 Lanelet2 地图和路线 `9540 → 9546 → 9178 → 54 → 112`，不连接实车。默认启动可单独选 C 或 N，但 2.0.0 自带的启动预设没有启动官方 Selector。实验把原版 C、N 并行运行，复用官方 Selector；新增适配只给完整 C 轨迹包装来源标识，不重写轨迹点和原始时标。两个规划器共用里程、任务路线、地图和相关观测，切换时不重启、不暂停、不重新定位。保留 Selector 校验、后置 Planning Validator、MPC/PID、command gate 和原生模型逻辑。

[数据流图](runtime-architecture.svg)。测量链：候选身份 → Selector 实际选中 → Validator 输入/输出 → MPC/PID 有效参考与控制命令 → gate 输出 → 仿真车辆模型输入 → 车辆状态。验证配置：Selector 原有验证在 shadow mode，下游 Planning Validator 默认处理类型 0 会发布某些标为 invalid 的轨迹，不能把“通过该节点”当成“每一项检查都通过”。运行未关闭这些原生检查。

### 基线和在线交接

原生全 C、全 N 两条源码安装基线均到达终点、速度归零，见 [stock-baselines.json](stock-baselines.json)。并行全 C、并行全 N、直道和弯道两向切换均达到同样终态。下面是已有运行的单例时序；以请求时刻为零，未应用模型内部队列延迟修正。

| 原在线运行 | 切点实测速度 m/s | 首次追溯到对应来源的控制周期 ms | 对应命令到模型输入 ms |
| --- | ---: | ---: | ---: |
| 直道 C→N | 4.295 | 96.46 | 122.78 |
| 直道 N→C | 4.249 | 27.27 | 46.86 |
| 弯道 C→N | 2.813 | 95.21 | 119.41 |
| 弯道 N→C | 3.645 | 241.95 | 247.95 |
| 直道 C→N（DDS 额外记录） | 4.294 | 103.24 | 123.13 |

[原在线结果](runtime-summary.json)有新旧轨迹指纹、选择、控制、模型输入和终点状态。旧批次主要通过 SHA-256 与原始轨迹 stamp 确认跟随器运行路径；后续下面这一轮增加了 MPC/PID 各自的有效参考记录，能进一步排除“跟随器收到，但某个控制器沿用旧参考”的情况。不同单次延迟不用于比较方向优劣。

## 2. T1–T4 分别看到什么

在同一路线上完成三对、六趟闭环：弯道 C→N/全 C（36 m）、偏航起步 C→N/全 C（偏航 +0.22 rad，4 m）、弯道 N→C/全 N（36 m）。切换和对照打标都等待实测速率 >1.5 m/s。仅使用固定工况，未重复扫种子；Diffusion 温度=0、batch=1，不把异步调度当成可重复随机种子。六趟均到达并停稳。原在线运行和这轮配对是不同批次，不要混用单例数值。

| 类别 | 观察证据 | 证据形态 |
| --- | --- | --- |
| **T1 物理接管条件** | 初始偏航 +12.61° 在接管前已被全 C 前缀改正。实际请求时相对于道路约 −2.17°，全 C 对照 −2.19°；其后 1 s 峰值实际转角 0.05447/0.04989 rad、侧向加速度代理 绝对值（车速 × 偏航角速度） 0.13555/0.13426 m/s²，两臂 MPC 均 33/33 求解。 | **闭环对照、未触发预期异常**。用起点偏航不能替代实际交接状态。 |
| **T2 历史状态** | 同一弯道帧离线推理 A、A、B，只把 `ego_agent_past` 前 30 行换成直道捕获值，保持最后当前行、另外 14 个张量、模型权重及 latent 相同。重复 A 坐标差为 0；B 的 2 s 位置偏差 **0.405088 m**，80 点最大 **0.422966 m**。 | **离线单变量机制验证**；不作为闭环中历史实际丢失的案例。 |
| **T3 参考接续** | 弯道 C→N 中，旧、新轨迹确实先后进入 MPC/PID 计算。以同一时刻车体位置分别投影到两条轨迹，各向前 3 m，参考速度 **1.93675 → 3.37320 m/s**（+1.43645），两点位置差 **0.20096 m**。跟随器首条新长向加速度指令比最后旧指令高 0.09868 m/s²，gate 后高 0.09473 m/s²。 | **闭环观察到实际采用的参考跨来源跳变**。3 m 数值是对轨迹的几何求值，不是未经记录的 PID 内部目标。前后车辆都遵循自身闭环，未把整段减速归因于这个参考跳变。 |
| **T4 权限传递时序** | 弯道 C→N 中，Selector 改选 N 后 **14.754674 ms** 仍施加改选前算完的最后一条 C 命令，改选后 **39.828054 ms** 首次将 N 命令交给仿真模型输入。两次输入在相邻模型更新周期，实测间隔 **25.073380 ms**。 | **闭环时序观察**，展示改选与生效不是同一个事件。不是断控、不是旧命令晚生成，也不归为原生故障。 |

T2 输入具体是归一化的自车局部 `[x,y,cos(Δyaw),sin(Δyaw)]`，31×4。参数关闭 `use_time_interpolation`，日志显示两组从最早行到当前行均约 3 s；被替换的前 30 行跨度约 2.90 s。直道、弯道的张量来自各自局部坐标系，离线直接替换，不把它当另一段自然连续历史。另有闭环观察：终点附近进入只有 1 点的 N 轨迹时，MPC/PID 分别保留约 300/100 ms 较早的有效参考；固定 N 也会保留约 100 ms 较早的参考。这是下游拒收短轨迹后的状态保留，和神经网络历史输入是两个机制。

T3 后置 gate 确实把第一条 N 指令的速度字段从 3.320846 限到 3.073600 m/s。此模型实际用于积分的是加速度和转向输入，不是这个速度字段。PID 的诊断数组未在本轮采集；源码话题 `/control/trajectory_follower/longitudinal/diagnostic`（`data[2]` 目标速度、`data[3]` 目标加速度）应与 `Control.longitudinal.stamp` 对齐，不用其外层控制消息时间戳替代。

T4 的原生 `DELAY_STEER_ACC_GEARED` 模型以 25 ms 更新，配置加速度/转向输入延迟 0.10/0.24 s，源码向最近步数取整得到 4/10 更新步。此处 `setInput` 是队列**入口**。按源码与实测 tick 推算，首条新命令预期在入队约 99.972/250.161 ms 后才分别进到加速度/转向动力学输入；未记录队头或由此标定车体响应延迟。这里的模型固有延迟不计作交接软件故障。

## 3. 数据和源码定位

- [配对结果](taxonomy-summary.json)：六趟的切点、初态匹配差、1 s 窗、T3 前视数据与 MPC/PID 参考标识；[实验账本](taxonomy-run-ledger.txt)。
- [弯道 C→N 时钟链](curve-cn-timeline.csv)：原始纳秒、相对请求时间、对应原记录行号。队列出口两行标为按模型推定。
- [T2 预测曲线 CSV](t2-replay.csv)：A/B 两条预测的逐点局部 XY；[原生历史时间戳](t2-history-stamps.csv)：从 `HO_DIFFUSION_HISTORY` 直接摘出的两个 31 行序列。
- [原始证据哈希](raw-evidence-sha256.txt)可在 Thor 上对照原 taxonomy 目录的 `logs/`。此处只有小型结果；不存在重新采样或人造的闭环日志。

版本固定为 [Autoware 2.0.0](https://github.com/autowarefoundation/autoware/tree/2.0.0)，umbrella tag SHA `6f91fff359e8af37bd97dcb116f412c7e167ac05`。上游与本地记录源提交如下。本地提交用于对应 Thor 原件，不是上游公开分支。

| 层 | 上游固定提交 | Thor 实验提交 |
| --- | --- | --- |
| Universe | `815d3f1b5c532eaccab33f0479819af8535919d2` | 在线交接 `1f894d9d3944617c78af9410354fcfde0ca5e4b7`；配对观察 `fd45fe0e2851e71107527221f1210d3b68208010` |
| Simulator | `91e68ee268a71e1ed10858fb68d254183b34005a` | `d6caaa27abfacc4a1ad2ec03e8fa5a757cb7f0fb` |
| Launch | `45bd52eb298a9700c51eef556734c6cb0e4af364` | `2e855aaafda909864bbc9d5e960dd727f2027870` |
| Thor 证据归档 | — | 在线 `724d62f2c36d7c731a9f9229cc5b62f5c0a1e828`；配对 `89ce3223185cbe19e9433c2140f65e706b895216` |

按实验提交找源码：`autoware_trajectory_selector/src/trajectory_selector_node.cpp:280–297` 是实际选中发布；`autoware_trajectory_follower_node/src/controller_node.cpp:243–294` 是控制 cycle；`autoware_mpc_lateral_controller/src/mpc_lateral_controller.cpp:354` 和 `autoware_pid_longitudinal_controller/src/pid_longitudinal_controller.cpp:168` 确认有效参考。T2 历史路径是 `autoware_diffusion_planner/src/diffusion_planner_core.cpp:375–400,497–504`，`src/preprocessing/preprocessing_utils.cpp:136–156`，`src/diffusion_planner_node.cpp:639–674`。Simulator 的 `simple_planning_simulator_core.cpp:467–480,637–641` 把输入交给模型并运行更新；`vehicle_model/sim_model_delay_steer_acc_geared.cpp:81–111` 才是内部延迟队列。

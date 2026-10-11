# 2026-10-11 准备阶段候选版本

本轮仅进行本机 headless SITL 工程准备，不开展正式状态策略对照、P1–P4 或实飞。历史 P0 总审计仍为 FAIL，未改写历史运行与指标。

## 范围与版本

修改前的工具、研究源码、文档、配置、补丁和锁清单保存在 `data/preparation-20261011/baseline/project-source.tar.gz`；两套 PX4 差异、未跟踪源码和二进制哈希分别归档。初始候选归档在 `candidate/`；增加诊断并固定本机回环通信后的候选归档在 `candidate-final/`。修复前的冻结身份及计划在 `batch-02/candidate.json`、`batch-02/plan.json`；lockstep 修复后的候选另存为 `batch-03`，不能合并计数。

本轮不修改策略权重、机体动力学、native 频率、原 executor 阈值和原联合恢复标准。4 ms 保持时延目标，没有增加数值硬 FAIL 门槛。

## 已实施

1. 两套 Gazebo 桥的 ESC、wheel、servo 和 gimbal 互斥锁改为对象构造时初始化；删除 `init()` 内的延后初始化，避免回调注册后仍访问未初始化的锁。此修改修复明确的初始化顺序风险，尚不能证明与历史崩溃同根。未新增析构时销毁锁，避免共享 transport 回调尚未退出时销毁；整个对象仍由原桥生命周期管理。
2. 原始 `sensor_baro` 和选中 `vehicle_air_data` 导出到对应 ROS overlay。运行器要求原始/选中气压有限且为正、device ID 匹配、位置估计有效、接收年龄不超过 0.5 s，并持续 2 s；三类消息的发布时间戳也必须推进至少 2 s。就绪失败保留具体原因，不自动重启重试，不关闭解锁健康检查。
3. 新增 `--startup-only`：只启动、等待传感器就绪、保存诊断并退出，完全不进入解锁和飞行流程。Gazebo pressure 原始 transport 输出、原始气压、选中气压和估计值均保存。
4. 推理记录增加位置/姿态采样时间、主机单调计算前后时间、动作发布仿真/主机时间。ESC 输出桥记录 mixer 实际选中的采样时间、输出转速、transport Publish 返回值及累计年龄桶、重复/倒退计数。只增加观测，没有改变排队或输出策略。
5. 子进程允许生成 core；当前系统 core_pattern 指向 apport，不能据此保证每次崩溃都在运行目录产生 core。记录实际配置，未改系统全局 core 设置。

复现入口仍为 `tools/apply_research.py`，它调用 `tools/apply_preparation.py`。补丁已更新；修改前副本在 baseline 内。两套构建通过，源码连续两次适配保持字节幂等；11 项 Python 检查通过，SampleClock 和 StateOps 的 ASAN/UBSAN 测试通过。

## 测量语义

- 角速度、姿态、位置的 timestamp_sample 各有含义。采样偏差不自动等于计算调度迟滞；正的“gyro minus position”表示位置采样更早。
- ESC 桥记录的是输出 provider 选中命令以及 Gazebo transport 发布成功，不是电机物理更新确认。现有 ESC feedback 订阅的也是 command/motor_speed，不能充当独立电机消费证据。
- 重复选中同一采样可以表示命令保持，不等于重复 GRU 提交。
- ULog 分位数和逐行匹配只覆盖记录行；输出年龄桶等累计数仅覆盖至最后记录的计数快照。全程计数末值若没有可靠终态确认，不应称为绝对完整。
- 控制链路的物理步消费确认、训练延迟鲁棒性、硬 deadline 和精确历史观测对齐尚未完成。本轮不以测量成功声明这些能力已通过。

## 冒烟结果

classic 与 RAPTOR 的不解锁冷启动检查均 PASS；一次 RAPTOR 短时 C→N→C 飞行及原严格单轮分析 PASS。该神经发布窗口记录到位置和姿态采样各一次晚于角速度 4 ms，说明先前提出的混合时刻现象确实存在；该测量不能单独证明会导致失稳。

该轮神经持权区间中，ESC 桥记录行的采集至选择年龄 P99=4 ms、最大=4 ms；神经动作发布行的年龄最大=8 ms。两者覆盖不同记录集合，不能据此声称所有旧动作均消费。主机时间匹配的发布至桥时延最大约 5.11 ms，进一步说明仿真时钟年龄与主机耗时不能混为一谈。详见 `data/prep-20261011-smoke-flight-raptor/preparation-trace.json`。

## 预登记批次

批次为 20 次冷启动（classic/RAPTOR 各 10 次）和七类场景各 3 次。所有尝试均进入 results；任一失败即停止该候选进行诊断，未执行项目保持 NOT_RUN。该规模用于工程筛查，不构成可靠性认证，也不构成正式因果对照。

当前冻结批次执行状态以 `data/preparation-20261011/batch-03/results.json` 为准。即使该批次通过，也不能自动关闭历史 P0 未决项或证明电机物理步消费。

## 首批失败与进一步诊断

`batch-01` 在 startup-05（classic，不解锁）停止：此前 4 次通过，该次 PX4 DDS 位置/姿态遥测未就绪，随后 36 项 NOT_RUN。原生检查证明 Gazebo pressure、sensor_baro、vehicle_air_data 正常，但 ULog 完全没有 sensor_gyro、vehicle_imu 和姿态/位置估计数据。这不是一次气压计缺失，也没有进程崩溃。该批次运行期间另修正了飞行失败处理顺序：空中失败立即走原降落/清理流程，跳过新增的阻塞诊断；因此 batch-01 的 candidate_unchanged=false，如实保留，不能作为最终冻结版本批次。

两套 bridge 随后增加 IMU/baro/mag 的原子回调计数，并保存 Gazebo publisher/subscriber 地址。成功诊断轮自动选择的端点为 Docker 网桥 172.17.0.1。多网卡选择是调查线索，尚未证明其导致失败。

注意观测干预：[Gazebo 8.11.0 IMU 实现](https://github.com/gazebosim/gz-sim/blob/gz-sim8_8.11.0/src/systems/imu/Imu.cc)在存在订阅连接时才更新传感器。因此额外 `gz topic -e` 订阅可能改变启动行为；带额外原始传感器订阅的诊断轮，不可代替只有 bridge 消费者的最终验收。Gazebo 官方支持通过 [GZ_IP 指定本机通信地址](https://gazebosim.org/api/transport/13/envvars.html)，后续本机候选将明确冻结这一条件，不以配置更改宣称历史根因已证明。

## 当前冻结条件

`startup-diagnostic` 的 10 次冷启动均通过，但该版本默认额外订阅原始 IMU 和 pressure，作为诊断结果保留。`batch-02` 固定 `GZ_IP=127.0.0.1`，正常启动与飞行不增加原始传感器 transport 订阅；`--capture-raw-sensors` 仅供显式诊断使用。失败时先保存原生消息、bridge 回调计数与端点，再增加短时原始订阅探测，并记录其改变订阅图的事实；该轮始终保持 FAIL，不因探测后恢复而变为 PASS。空中失败跳过阻塞诊断，立即进入原降落与清理流程。

就绪检查接收的 DDS 发布时间戳经过 Agent 的 UTC 转换，只用于验证持续推进与接收新鲜度；它们不用于计算严格恢复窗口或端到端仿真年龄。

## 冻结版本冷启动结果

`batch-02` 的 20 次冷启动全部通过（classic/RAPTOR 各 10 次）。独立检查 20 个 ULog 与启动诊断：没有进入 armed；没有启动额外的 IMU/pressure 数据订阅；IMU 端点均为回环地址；bridge 的 IMU、baro、mag 回调计数均为正；原始与选中气压均有日志。证据为 `batch-02/startup-evidence-audit.json`。这说明当前配置通过了该批启动筛查，不证明历史缺失传感器或崩溃的唯一根因。

历史七组最终分析的 metadata、metrics 与 ULog 哈希均保持不变，见 `historical-integrity.json`；未对旧目录运行新版分析器。

## 正常版本崩溃：现场、可复现竞态与修复

`batch-02` 在 20 次冷启动及首轮前六类飞行通过后，`flight-1-state_injection` 在解锁前 SIGABRT（-6），后续 14 项 NOT_RUN。该轮尚未进入注入，不可称为 Inject 导致的崩溃。候选身份始终保持不变；26 项接受、1 项失败的结果保留于 `batch-02/results.json`。

本次实际获得 apport core，并保存完全匹配运行 SHA256 的 ELF。身份及保存路径见 `crash-core-identity.json`；大文件放在忽略目录 `uav_lab/.local/diagnostics/preparation-20261011/`。原始回溯见 `crash-core-backtrace.log`。AArch64 返回地址带 PAC，普通 unwinder 在 libc 处停止；根据栈中应用返回地址及反汇编，`GZBridge::clockCallback` 调用 `LockstepScheduler::set_absolute_time`，后者在旧源码第 115 行锁定保存的 caller mutex 时进入断言路径，见 `crash-symbols.log`、`crash-lockstep.log`。ESC 回调的另一个线程在正常等待自己的锁，不能据此归咎 ESC mutex。

RAPTOR 本地调度器在收集超时项时先设置 timeout、保存 caller mutex/condition 指针，释放链表锁后才取得 broadcast 锁并唤醒。等待者若被其他信号或虚假唤醒提前唤醒，读到 timeout=true 后会跳过原有 drain，允许 caller 的栈对象在待执行广播之前离开作用域；即使 timeout=false，原有先 drain 链表锁再 drain broadcast 锁，也可能穿过两阶段之间的空隙。这是源码可确认的生命周期竞态，与现场路径一致；尚不能证明所有历史崩溃都只有这一根因。

新增 `tests/lockstep_lifetime_test.cpp`：链接器仅在测试中截获 mutex lock，使真实调度器暂停在已选中 caller mutex 之前，再向等待者发送外部信号。旧实现输出 `returned_before_pending_broadcast=true`，测试 FAIL；修复版为 false，测试 PASS。测试保留锁对象直到双方退出，避免为了复现而主动制造未定义行为。另验证 64 个同时超时等待者全部唤醒，消除旧固定 32 项缓冲区中“已标 timeout 却不广播”的遗漏。修复版 ASAN/UBSAN 通过。该隔离测试使用实际调度器源码，component barrier 和 PX4 日志用测试替身，不据此声称验证了完整 PX4。

修复后的调度器在选择前持有 broadcast 锁，并覆盖完整选择/广播过程；所有返回的等待者先释放 caller mutex、等待 broadcast 完成，再重新取得 caller mutex 返回。链表锁在取得 caller 锁前释放，保持无锁顺序环。源码在 `research/platform/lockstep_scheduler.cpp`，由适配入口复制到 RAPTOR；classic 保留其原有调度器。未修改仿真步长、deadline、executor 阈值或网络权重。该修复没有新增 pthread_cancel 生命周期协议，不能宣称已验证强制取消线程的所有情况。

RAPTOR 重建通过、源码适配两次字节幂等通过、11 项 Python 检查通过。修复后的完整筛查另建 `batch-03`；执行状态以该批次结果为准，未完成之前不宣告准备阶段通过。

## batch-03 结果（lockstep 修复后候选）

`batch-03` 于 2026-10-11 17:58 完成：20 次冷启动（classic/RAPTOR 各 10）及七类场景各 3 次，41 项全部接受，0 失败、0 NOT_RUN，`candidate_unchanged=true`（运行器在每项前和结束时重算候选身份）。结果见 [results.json](../data/preparation-20261011/batch-03/results.json)。

另以 `tools/preparation_audit.py` 从原始证据独立复核，结果写入 [batch-audit.json](../data/preparation-20261011/batch-03/batch-audit.json)，不修改任何运行目录。该脚本先对 batch-02 输出到临时位置做对照：冷启动 20 项与原 `startup-evidence-audit.json` 字段逐项一致；`flight-1-state_injection` 由 PX4 退出码 -6 及 `Fatal glibc error ... assertion failed` 双重识别为失败。batch-03 复核结论：

- 冷启动：全部未进入 armed、PX4 退出码 0、日志无崩溃标记、ULog 哈希与 metadata 一致、`GZ_IP=127.0.0.1`、IMU 端点均为回环且仅 bridge 一个订阅者、IMU/baro/mag 回调计数为正、原始与选中气压均有记录。
- 飞行：21 轮 PX4 退出码均 0、无崩溃标记；18 轮 RAPTOR executor 判定 PASS 且整轮运行时告警 0；联合恢复 75 个阶段全部 SETTLED（未恢复 0、观察不足 0），其中 13 个阶段标记 `true_first_recovery_uncertain`。
- 链路观测：神经动作发布仿真年龄最大 12 ms（flight-2-state_hold），其余 ≤8 ms；ESC 桥运行时年龄桶合计 ≤0 ms 340769、(0,4] 4185、(4,8] 78、(8,12] 1、>12 ms 0；选中采样重复/倒退/负年龄均 0。

范围：这是同一冻结候选的工程筛查。21 轮飞行未再出现 batch-02 的 mutex 断言，是修复后未复现的证据，不证明 P0 报告中所有历史崩溃（包括 -11 段错误）同根，也不证明气压缺失的历史根因。classic 仍使用原调度器，未应用该 lockstep 修复；batch-03 中 classic 13 轮未见崩溃，同样只是未复现。

## 输出链路的实际语义与下一步要证明什么

源码核对（RAPTOR 检出及 Gazebo 8.11.0 `MulticopterMotorModel.cc`）显示，从神经动作到电机的每一层都是“最新值覆盖”，不是队列：

1. `actuator_motors` 没有 `ORB_QUEUE_LENGTH`，uORB 队列长度为 1；`FunctionMotors::update()` 用 `_topic.update(&_data)` 只取最新一条。
2. ESC 输出 WorkItem 由 actuator_motors 回调调度；`IntrusiveQueue::push` 对已在队列中的项直接返回，因此 ESC 运行前的多次发布合并为一次 `Run()`。
3. Gazebo `OnActuatorMsg` 把消息写入单个 `std::optional` 槽并覆盖旧值；每个物理步 `UpdateForcesAndMoments` 读取后 `reset()`，无新消息时保持上一 `refMotorInput`，再经一阶转速滤波（默认上升 1/80 s、下降 1/40 s）。

因此“每个神经动作都被模拟电机执行”不是这条链路的设计语义，不应作为验收要求。同一物理步内到达多个命令时只有最后一个生效属于设计行为。应证明的是：

- **每个物理步实际生效命令的采样年龄**：该步应用的命令对应哪个 `timestamp_sample`，其仿真年龄分布及超出 4 ms 目标的比例与连续段；
- **被覆盖的命令数量及位置**：在 PX4 层（发布但未被 ESC 选中）和 Gazebo 层（发布但未被物理步读取）分别计数，并区分“被更新的命令覆盖”和“丢失”；
- **无新命令的物理步数量**：电机保持上一命令的步数。

batch-03 现有记录的初步量化：18 轮 RAPTOR 飞行中 37270 个已记录神经发布，37080 个的采样 ID 出现在已记录的 ESC 桥行中，190 个（0.51%）未出现。ESC 桥 ULog 同期缺 1408 行（由 `attempts_total` 差值得出），因此 190 只是 PX4 层覆盖数的上界，不能区分覆盖与日志漏行；Gazebo 层目前没有任何逐步消费记录。

建议的最小测量改动（尚未实施，需新候选与新批次）：ESC 桥把选中的 `timestamp_sample` 写入 `gz::msgs::Actuators` 的 `header.stamp`；在 Gazebo 侧以独立 system 插件在每个物理步记录应用的采样 ID 与仿真时间，并累计“覆盖/无新命令”计数；PX4 侧 `research_output` 增加“选中采样与上次之间跳过的已发布动作数”运行时累计，消除 ULog 漏行影响。额外 transport 订阅者会改变订阅图（参见 IMU 订阅干预问题），故优先用插件而非 `gz topic -e`。数值硬门槛仍待测得端到端年龄后由用户确认。

## 2026-10-12：输出链路逐物理步测量（batch-04 候选）

上一节建议的测量已实施，新候选冻结为 `batch-04/candidate.json`：

- **PX4 侧**：ESC 桥把选中的 `timestamp_sample` 写入发往 Gazebo 的 `gz::msgs::Actuators` 消息头（电机模型不读消息头）；`research_output.skipped_publication_total` 以 uORB generation 间隔在运行时累计“actuator_motors 发布后在 ESC 读取前被覆盖”的次数，不受 ULog 漏行影响。
- **Gazebo 侧**：`research/gz/ResearchMulticopterMotorModel.*` 由 gz-sim 8.11.0 `MulticopterMotorModel` 原文件（保存在 `research/gz/upstream-8.11.0/`）生成，差异只有类名和记录语句；记录在力计算之前、`refMotorInput` 更新之后，不改变任何物理输入。每个物理步写一行：仿真时间、本步消费的采样 ID、生效采样 ID、主机单调时钟的到达/消费时刻、上一步以来收到的命令数。`apply_preparation.py` 把它编译为 PX4 gz 插件，并在 `Tools/simulation/gz` 子模块之外生成 x500 研究模型副本，使候选身份能哈希到该改动；classic 变体不变。
- **分析**：`tools/output_chain.py <run>` 生成 `output-chain.json`；批次中每轮 RAPTOR 飞行必须 MEASURED（只要求测量完整，不新增数值门槛）。

冒烟飞行 `prep-20261012-smoke-output-chain` 首次给出每个物理步实际生效命令的年龄。lockstep 下第 k 步采样计算出的命令在第 k+1 步生效，因此年龄的结构下限就是一个物理步 4 ms，原 4 ms 目标恰好等于该下限。

## batch-04：判定标准与重复交接场景不匹配

`batch-04`（20 次冷启动 + 七类场景各 10 次）完成 30 项后，在 `flight-2-repeated_handover` 停止：29 项接受，1 项失败，60 项 NOT_RUN。独立复核见 [batch-04/batch-audit.json](../data/preparation-20261011/batch-04/batch-audit.json)。

- 0 崩溃：20 次冷启动和 10 轮飞行 PX4 均退出 0，日志无崩溃标记。
- 输出链路（8 轮 RAPTOR 飞行，神经持权 18411 个物理步）：生效命令年龄除 9 步为 8 ms 外均为 4 ms，从未连续两步超过 4 ms；PX4 层覆盖 1 次、Gazebo 层覆盖 8 次；4 个电机每步生效采样完全一致。batch-03 中 190 个“未见于 ESC 记录”的动作因此可判定主要是 ULog 漏行，而非覆盖。
- 失败原因：唯一失败项是第三次交回经典控制后的联合恢复 NOT_SETTLED，其余 35 个阶段 SETTLED；执行、executor、持权、状态操作检查全部通过。经典控制器交回后以当时位置作为保持目标，并以 <8 mm 误差跟踪它；但三次交接累计使该目标偏离固定参考 [0,0,-3] 约 0.2 m（高度 −2.842 m），位置误差均值 0.2016 m、最大 0.2176 m，略超 0.20 m 阈值，速度、角速度远在阈值内。也就是说，固定参考在重复交接末段衡量的是目标点累计漂移，而非控制器恢复。87 个历史经典悬停窗口中 6 个相对固定参考的偏移超过 0.15 m，余量很小。

用户确认（2026-10-12）将联合恢复的位置参考改为**控制器当前位置目标**：每个采样向后对齐最近一次 `trajectory_setpoint.position`。setpoint 是保持型指令而非观测，因此不受 20 ms 观测连续性限制；第一次 setpoint 之前的样本无效。RAPTOR 同样跟踪 `trajectory_setpoint`（`mc_raptor.cpp` 以位置减目标作为观测），神经阶段不发布新 setpoint，因而沿用进入神经阶段前的最后一个；状态 reset 保留 RAPTOR 的六个参考字段，inject 场景只改写 GRU 的 16 维，hold 重放保持时的值，所以该参考在所有场景中都等于 RAPTOR 的实际目标。速度、角速度参考和所有阈值不变。固定参考结果作为 `fixed_reference_comparison` 继续报告，不参与判定。

只读复算（结果不写入任何运行目录）：用新实现对 batch-03、batch-04、冒烟和 P0 最终七轮共 143 个阶段重算，固定参考结果与原指标逐阶段完全一致；改用当前目标后只有 batch-04 的上述阶段由 NOT_SETTLED 变为 SETTLED，其余 142 个判定不变。按规则，batch-04 保持 FAIL 原样保留，新标准在新候选 `batch-05` 上重新完整执行。

## batch-05：新标准下的完整冻结批次

`batch-05`（候选同 batch-04 的 PX4/Gazebo 二进制，仅分析器改为当前目标参考）于 2026-10-12 05:47 完成：20 次冷启动 + 七类场景各 10 次，**90 项全部接受**，0 失败、0 NOT_RUN，`candidate_unchanged=true`。独立复核 [batch-05/batch-audit.json](../data/preparation-20261011/batch-05/batch-audit.json)：

- 冷启动 20 次：均未解锁、回环端点、单一 IMU 订阅者、传感器回调与气压记录完整。
- 飞行 70 轮：PX4 全部退出 0，日志无崩溃标记；60 轮 RAPTOR executor 判定 PASS，整轮告警 0；联合恢复 250 个阶段全部 SETTLED，0 个首次恢复不确定。
- 输出链路（60 轮，神经持权 127568 个物理步）：除 1 步为 8 ms 外，生效命令年龄均为 4 ms；被覆盖命令 PX4 层 0、Gazebo 层 1；4 个电机采样不一致的步 5 个。

尾部时延随主机负载变化：三批飞行期间主机 CPU 平均占用分别为 30.9%、22.5%、14.1%，batch-05 的尾部明显更干净。因此时延门槛用 batch-04 与 batch-05 两批合并评估，不只看较安静的一批。

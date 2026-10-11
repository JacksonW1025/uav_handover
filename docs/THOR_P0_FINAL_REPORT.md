# Thor P0 恢复指标与 executor 修复验证

检查基线：主仓库 `8d0c4166fb8a6f9adb9dbba9f5758f13c6d8446e`；本次修改为其工作树差异。RAPTOR PX4 基线 `4ae21a5e569d3d89c2f6366688cbacb3e93437c9`，classic 基线 `d6f12ad1c4f70ad3230afd7d86e971421e02fef4`。本机为 AGX Thor，全部实验为 headless SITL。P1–P4 与实飞未开展。

**P0 未完成，总审计为 FAIL。** 最终配套构建下七类场景分别通过，但旧正常版本崩溃及一次 barometer 启动失败仍未闭环；不能用后续通过覆盖这些问题。控制迟滞门槛的建议仍待确认，未自行新增或调宽门槛。旧 `verified-*`、新诊断失败轮和中间验收均保留；最终运行清单以 [acceptance.json](../data/p0-20261010/acceptance.json) 为准。

## 恢复指标

旧 `analyze.py` 的 `settling_time_s` 只检查位置到 NED `[0,0,-3]` m 的三维范数 ≤0.2 m，寻找连续2 s入带区间；不检查速度或角速度，也不在下一交接/降落请求或持权阶段结束处截断。旧验收0/4 ms是入带区间起点相对持权切换的采样量化延迟，不是2 s保持结束时间，更不能证明联合恢复。只读核查的旧18次切换中，找到的区间本身未跨下一持权变化；问题在算法没有保证边界，并非声称旧日志已经越窗。旧记录未改写。旧算法以明确命名的 `legacy_unbounded_position_band_entry_time_s` 留作对照，不参与验收。

新位置指标 `position_band_entry_time_s` 保留位置入带概念，加入阶段边界和记录连续性限制。联合指标 `joint_recovery_time_s` 采用用户确认的固定参考：位置 NED `[0,0,-3]` m、速度 NED `[0,0,0]` m/s、角速度 FRD `[0,0,0]` rad/s；三维误差范数同时 ≤0.20 m、≤0.10 m/s、≤0.10 rad/s，连续2.0 s。配置为 [p0.json](../config/p0.json)，默认 experiment.json 同步采用；阈值未为通过验收调整。

分析使用采集时间 `timestamp_sample`，在位置/速度与角速度采样时刻的并集上仅向后对齐。任何源间隔或对齐陈旧度 >20 ms 即重新计时，不跨缺口拼接；即使另一 topic 填满并集且陈旧度恰好20 ms，缺口后的新样本也会中断保持。每个阶段输出入带起点、确认完成时间和截止原因。实际交接阶段从 actuator owner 变化开始；初始经典基线从原生悬停窗口开始。实际持权变化采用发布后 ownership.timestamp（保留赋值可能更早的 actuator_message_us 作电机日志关联）。下一请求前通过 PX4 listener 取得的原生时间保守界限、下一实际持权变化或日志结束截断完整保持区间。悬停起止和实际持续时间同样使用原生 PX4 时间，避免 DDS UTC 重写造成窗口长度误差。

`SETTLED`：完整连续达标2 s；`NOT_SETTLED`：存在完整可评估2 s区间但未达标；`INSUFFICIENT_OBSERVATION`：缺帧或阶段过短使判断不足。三类分别统计。若此前缺口可能遮住首次恢复，标记 `true_first_recovery_uncertain`，只报告首次可验证区间。两种指标采样网格不同，联合指标可从新鲜的上一位置样本向后对齐开始，位置单独指标则从本阶段首个位置样本开始，二者可能相差一个采样间隔。

## executor 根因及修复

旧恢复日志中两个不同 IMU 样本的 `timestamp_sample` 为50.292、50.296 s，但 Raptor 两次处理时 `hrt_absolute_time()` 均为50.296 s。旧 executor 用处理时钟作为输入时间；异步 Gazebo /clock 与工作队列使合法不同观测变成0 dt，仍因 force_sync 执行推理并可能推进 GRU。按处理时间去重会丢掉合法观测，不能作为修复。

新实现使用观测采集时间驱动 executor，保留跨 reset/模式变化的采样序列检查。重复/倒退样本在 observe/control/GRU 之前拒绝；不同有效样本即使处理时间相同也分别处理。状态 reset 仍重建 executor 自身计时，模式保值及 HOLD 语义保留。HOLD 时可以计算临时 GRU 结果，但恢复冻结值，累计 `gru_commit_total` 仅统计持久状态提交。

仅改 executor 时钟后仍出现一次活动12 ms输入间隔及50次 jitter 告警。新增 raw gyro 日志证明52.244、52.248、52.252、52.256、52.260 s原始样本存在，而原 `VehicleAngularVelocity::Run()` 的 `if (!_sensor_sub.updated())` 只发布批次末样本。Raptor 没漏消费已发布消息，但上游合并了真实观测；滑动历史把一次异常间隔扩展成多次告警。

最小控制链路修复是在 SITL 角速度模块过滤/校准后，另外发布每个真实样本到32槽 `research_angular_velocity` 队列，Raptor消费该队列并持续调度直到排空。普通 vehicle_angular_velocity 的最新值发布和经典控制器调度保留；没有补造样本、重复上一观测或放宽 RL Tools timing 阈值。Gazebo IMU 桥使用消息头采集时间，避免将异步回调时钟作为采样时间。硬件/FIFO 路径未用于本次验证。

`research_timing` 在执行器发布仲裁之后记录该次 action 是否实际发布。分别累计整轮、控制器活动、实际神经发布范围的调用、告警原因、硬错误、输入拒绝、墙钟耗时总量/最大值以及超过2500 μs次数。ULog 漏记个别行时，累计告警数和均值/最大值仍完整；P95/P99及间隔分布明确只覆盖记录行。计时仍为 observe+RL Tools control，不是纯网络前向计时。

## 旧报告勘误及判定规则

旧 `verified-raptor_hover` 的 metrics.json 和原 analysis.log 均记录45次告警，报告写0有误；45次均在非活动、经典持权范围。旧 `verified-state_restore` 210次，其中50次活动且神经持权、160次非活动；旧 injection 的50次均非活动。旧 restore 的活动异常附近位置最大误差0.05252 m、速度0.013305 m/s、角速度0.03658 rad/s，电机有限且未见明显发散；这些现象不能证明时序异常对控制毫无影响。旧 PASS 只检查耗时P99、有限输出等，不检查 executor warning 或联合恢复，所以存在告警仍 PASS。

新规则：硬错误、输入拒绝、漏消费源发布、GRU 提交采样时间不递增、未分类告警、任何活动/实际神经发布 executor 告警，以及 P99预算未获完整运行时计数证明均 FAIL。仅非活动影子推理的已分类 jitter/bias 告警、其余检查通过时为 `PASS_WITH_WARNINGS`；零告警为 `PASS`。运行时超过2500 μs的调用比例须严格低于1%，从而无需假设遗漏行的耗时即可证明原P99门槛；没有把P99门槛改成单次最大值门槛。恢复任一阶段未恢复或观察不足、必要指标缺失、飞行/悬停时长/状态值/执行器归属不通过，同样 FAIL。

## 未决崩溃

队列诊断 `state-restore-02` 在起飞阶段发生 glibc pthread_mutex_lock 断言（PX4 -6）；正常重跑 `raptor-hover-01` 在接管前发生段错误（PX4 -11）；`repeated-handover-02` 和 `state-reset-02` 也在起飞附近发生 mutex 断言。已保留日志及 ULog。完整 GDB restore 飞行未重现。崩溃发生前累计 executor 告警、重复/倒退输入及漏消费源发布均为0；不能因此归因于或排除新增链路，不能将进程崩溃当作无影响告警。最终状态须保留这一未决问题，直至获得根因及针对性验证。

## 处理时钟与采集时钟的区别

不能把“采集时间不重复、executor采集时序告警为0”表述为所有处理时间戳均不重复。独立队列保留积压样本后，工作队列仍可能在同一个 HRT tick 处理不同采集时刻的样本。正常 `raptor-hover-02` 活动范围已记录20个同处理tick但采集时刻不同的相邻调用，处理间隔最大12 ms，采集至处理陈旧度最大8 ms；相邻采集间隔仍为4 ms。补充统计区分这类积压补处理、采集时间重复/倒退与真正输入拒绝，未从日志中删除这些行。

因此，修复证明的是合法不同观测没有因处理时间去重而丢弃、GRU 不对同一采集样本重复提交；不等于证明所有积压电机指令均在不同 Gazebo 物理步执行。P0 是短时 SITL 工程验收，不能据此声明实时性认证或实飞能力。

## ASAN 与 daemon TLS 修复

单独构建 `px4_sitl_raptor_asan`，未替代正常验收二进制。初次 ASAN 运行在启动日志 `px4_log_modulename → get_stdout → fputs` 崩溃。源码显示 `Server` 构造时先使 `_instance` 可见，而 `_key` 未初始化，直到后台 `_server_main` 稍后才 pthread_key_create；这会把其他 TLS 值误解释为命令 stdout FILE 指针。已把 key 创建移到发布 `_instance` 之前，并对失败的 start 返回错误；classic 和 RAPTOR 的相同 POSIX 缺陷均应用同一最小修改，未改控制律。classic 新补丁为 [classic-final.patch](../patches/classic-final.patch)。

修复后两轮 ASAN 均越过原启动崩溃点，但分别因命令应答超时、DDS安全超时终止；没有放宽通信安全门槛，也不将这些诊断轮写成 PASS。常规版本旧起飞崩溃没有取得故障调用栈，尚不能证明与已修复的 TLS 初始化窗口同根。后续常规重跑通过只能作为未重现证据，不能自动关闭这个未决问题。

旧告警数量为旧 ULog 记录行计数，可能不覆盖每次调用；新告警数量为运行时累计。新统计另列 ULog 漏行、活动/持权范围和处理迟滞，避免把统计覆盖变化解释为控制性能改善。

## 最终运行与联合恢复结果

所有运行均为2026-10-10本机SITL，使用同一已确认参数配置。每轮实际运行记录及原指标保留；发布后持权边界的最终重分析另存 `data/p0-20261010-analysis-final/`，各目录有分析代码哈希及原指标未改写证明。

| 场景 | 原始运行 | 最终分析 | 联合恢复：通过/未恢复/观察不足 | 神经阶段首次可验证起点 [s] |
|---|---|---|---|---|
| classic_hover | [p0-20261010-classic-hover-04](../data/p0-20261010-classic-hover-04/validation.json) | [PASS](../data/p0-20261010-analysis-final/classic_hover/metrics.json) | 1/0/0 | — |
| raptor_hover | [p0-20261010-raptor-hover-03](../data/p0-20261010-raptor-hover-03/validation.json) | [PASS](../data/p0-20261010-analysis-final/raptor_hover/metrics.json) | 3/0/0 | 0.392 |
| repeated_handover | [p0-20261010-repeated-handover-03](../data/p0-20261010-repeated-handover-03/validation.json) | [PASS](../data/p0-20261010-analysis-final/repeated_handover/metrics.json) | 7/0/0 | 0.632, 0.340, 0.544 |
| state_reset | [p0-20261010-state-reset-03](../data/p0-20261010-state-reset-03/validation.json) | [PASS](../data/p0-20261010-analysis-final/state_reset/metrics.json) | 3/0/0 | 1.032 |
| state_hold | [p0-20261010-state-hold-03](../data/p0-20261010-state-hold-03/validation.json) | [PASS](../data/p0-20261010-analysis-final/state_hold/metrics.json) | 3/0/0 | 0.484 |
| state_restore | [p0-20261010-state-restore-04](../data/p0-20261010-state-restore-04/validation.json) | [PASS](../data/p0-20261010-analysis-final/state_restore/metrics.json) | 5/0/0 | 0.752, 0.420 |
| state_injection | [p0-20261010-state-injection-02](../data/p0-20261010-state-injection-02/validation.json) | [PASS](../data/p0-20261010-analysis-final/state_injection/metrics.json) | 3/0/0 | 1.264 |

共25个阶段有完整连续2 s联合达标区间，未恢复0、观察不足0。以下2个阶段此前缺口可能遮住真实首次恢复，已标记不确定：raptor_hover stage2, state_reset stage0。这里的通过不代表真实首次恢复时刻已知。

## 实际采集间隔

下表是整轮记录的采集时间间隔：中位/P99/最大值，单位ms；位置与速度共用 VehicleLocalPosition 时间轴。角速度为联合判定实际采用的 topic：RAPTOR使用queued research_angular_velocity，classic使用vehicle_angular_velocity。完整普通角速度统计也保留在metrics。

| 场景 | 位置/速度 [ms] | 角速度 [ms] | 超20ms间隔：位置/速度、角速度 |
|---|---|---|---|
| classic_hover | 8.000/12.000/28.000 | 4.000/8.000/16.000 | 6、0 |
| raptor_hover | 8.000/8.000/28.000 | 4.000/4.000/16.000 | 3、0 |
| repeated_handover | 8.000/8.000/32.000 | 4.000/4.000/16.000 | 6、0 |
| state_reset | 8.000/8.000/32.000 | 4.000/4.000/16.000 | 3、0 |
| state_hold | 8.000/8.000/28.000 | 4.000/4.000/12.000 | 4、0 |
| state_restore | 8.000/8.000/20.000 | 4.000/4.000/16.000 | 0、0 |
| state_injection | 8.000/8.000/32.000 | 4.000/4.000/12.000 | 2、0 |

正常整轮记录并非全部满足20 ms，不能直接把正常采样率当作数据完整性的证明。每个候选区间均逐样本检查源间隔及对齐陈旧度；超限中断，只有后来仍形成完整连续2 s区间才可 SETTLED。早期初步检查使用发布时间，最终已统一改用采集时间。

## 分范围计时与异常

下表耗时为observe+control墙钟；均值/最大值来自完整运行时累计，P99来自记录行。列出整轮、活动和该次实际神经发布三种范围；按发布后实际ownership区间向后对齐的补充统计及活动×来源交叉表在acceptance.json。整轮运行时告警为0，故可证明遗漏ULog行不会隐藏任何范围的executor告警。原日志仍有漏行，不能声称记录了每次调用。

| 场景 | 范围 | 调用/告警总数 | 均值/P99/最大值 [μs] | 记录行采集→处理最大迟滞 [ms] |
|---|---|---|---|---|
| raptor_hover | whole_run | 16552/0 | 7.762/34.990/3268 | 8.000 |
| raptor_hover | active | 1388/0 | 7.475/33.610/149 | 4.000 |
| raptor_hover | neural_actuator_authority | 1385/0 | 7.481/33.820/149 | 4.000 |
| repeated_handover | whole_run | 24644/0 | 7.285/31.000/6293 | 12.000 |
| repeated_handover | active | 4193/0 | 6.857/31.000/1113 | 8.000 |
| repeated_handover | neural_actuator_authority | 4184/0 | 6.861/31.000/1113 | 8.000 |
| state_reset | whole_run | 16552/0 | 7.582/33.710/1494 | 12.000 |
| state_reset | active | 1421/0 | 8.228/28.800/1075 | 8.000 |
| state_reset | neural_actuator_authority | 1418/0 | 8.234/28.860/1075 | 8.000 |
| state_hold | whole_run | 16634/0 | 7.378/30.920/1394 | 8.000 |
| state_hold | active | 1422/0 | 7.347/26.940/483 | 8.000 |
| state_hold | neural_actuator_authority | 1419/0 | 7.350/27.000/483 | 8.000 |
| state_restore | whole_run | 20581/0 | 7.009/32.000/1844 | 12.000 |
| state_restore | active | 2783/0 | 7.477/39.000/743 | 12.000 |
| state_restore | neural_actuator_authority | 2777/0 | 7.481/39.000/743 | 12.000 |
| state_injection | whole_run | 16654/0 | 7.381/30.000/1453 | 8.000 |
| state_injection | active | 1412/0 | 7.871/28.020/1453 | 4.000 |
| state_injection | neural_actuator_authority | 1409/0 | 7.877/28.080/1453 | 4.000 |

旧hover的45、旧restore的210次记录行告警与新所有范围的运行时累计0形成对照；旧hover耗时P99 16 μs是整轮，不能与新神经窗口P99直接当作纯网络性能对比。新记录仍有合法不同采集样本同HRT tick补处理和最长12 ms活动采集→处理迟滞，已经单列，未通过换时钟把这些调度现象从证据中抹掉。用户确认4 ms仅作为独立时延目标，暂不设数值硬FAIL门槛；迟滞与输出消费时限仍为P0待解决项。

## 版本、二进制与复现

- `project_head`：`8d0c4166fb8a6f9adb9dbba9f5758f13c6d8446e`
- `raptor_head`：`4ae21a5e569d3d89c2f6366688cbacb3e93437c9`
- `raptor_diff_sha256`：`2a4f8a835a4b306e7c2d8b5e4e20bcbca0fd1ee048fd70d3d38364f15601d5f7`
- `raptor_binary_sha256`：`d4a128823a58af29d675457e63592db8e9cf77347351833c029fb793a44328d0`
- `classic_head`：`d6f12ad1c4f70ad3230afd7d86e971421e02fef4`
- `classic_diff_sha256`：`daa1133498131c609259ed7632453af3a4c485cdd89e990c4ecea5bb4cf4cf0d`
- `classic_binary_sha256`：`a7aed64a6eaa4229813cc5910240e4c39c1d401c8eccc7a48002a17699d0085e`
- `policy_sha256`：`5327c83dc57f094ca1977a2533ebce318645be010e16b9354c96c337cd5c278b`

主仓库是上述基线加本次未提交工作树修改；每轮metadata记录执行脚本哈希，最终分析和审计另外记录实际分析代码哈希。七轮ULog、二进制、策略、源码差异与新增头文件哈希全部核对通过。旧环境lock/补丁副本在baseline/；daemon修复前P0源码差异另存 raptor-before-daemon-key.patch，且其SHA与当时运行记录匹配。最终补丁为patches/raptor-final.patch及classic-final.patch，未跟踪源码在raptor-final-untracked.tar.gz。ASAN专用构建仅将GCC std::regex的maybe-uninitialized编译错误降为warning，正式构建保留原-Werror；未改变任何运行时验收阈值。

## 完成条件与剩余最小工作

总审计 [acceptance.json](../data/p0-20261010/acceptance.json) 为FAIL、p0_complete=false。恢复与executor采集时钟修复、七类场景、25个联合区间及版本核对已完成；以下问题仍阻止P0闭环：

1. 获取正常版本起飞崩溃的故障栈及FILE/mutex生命周期证据，确认是否与TLS缺陷同根；后续6轮正常RAPTOR通过不足以单独证明根因。
2. 为classic启动barometer缺失补充Gazebo air-pressure及sensor_baro/vehicle_air_data链路证据；保持现有健康与安全门槛，不能仅延长等待或挑选成功启动来关闭问题。
3. 用户确认4 ms仅作独立时延目标；控制排队迟滞、逐动作ESC消费和有依据的处理硬时限尚未闭环。保持原executor阈值，不将4 ms超标直接当单轮FAIL，也不据12 ms实测反向放宽门槛。

8项恢复/验收规则Python测试和SampleClock ASAN/UBSAN测试通过，适配脚本在两套源码上连续应用保持字节幂等；构建及补丁核对证据保存。原有native约125Hz与训练100Hz差异仍在，冻结权重、原executor阈值均未改变；本次没有开展P1–P4或实飞。

## 补充：排队迟滞与真实输出链路（用户确认 4 ms 仅为目标）

采集时刻来自 Gazebo IMU `header.stamp`（仿真时间，微秒），经 GZBridge → sensor_gyro → ResearchAngularVelocity.timestamp_sample 保留。处理时刻为 mc_raptor::Run() 入口的 `current_time=hrt_absolute_time()`；它早于订阅读取、observe/control，不能命名为精确 inference 开始时刻。GZBridge::clockCallback 用同一个 Gazebo `msg.sim()` 更新 PX4 CLOCK_MONOTONIC。因此两者具有共同仿真时间原点与单位，可以相减形成 **采集→Run 入口的仿真年龄估计**；/clock 与 IMU 回调异步，HRT 呈离散台阶，0 不能解释为零墙钟延迟，12 ms 也不能直接解释为 CPU 花了12 ms。所有选定活动/神经行未见负年龄；这个检查不能证明两个异步回调无偏差。推理耗时另用 CLOCK_MONOTONIC 的前后读取，不与上述年龄混用。

只读补充分析见 `tools/p0_latency.py` 和 `data/p0-20261010/latency-audit.json`；原始指标不变。下表所有统计均限已记录行，分位数和超标比例不推断未记录行。连续积压定义为本作用域内连续 accepted_total、相邻日志行的年龄均>4ms；缺日志或阶段变化立即断开，最长段仅为下界。

|运行|作用域|样本数|P50/P95/P99 (ms)|最大(ms)|>4ms 比例|最长连续超标调用/采集跨度(ms)|同tick不同采样对/其中右侧GRU提交/动作发布|
|---|---|---:|---|---:|---:|---|---|
|raptor_hover|活动|1378|0/0/4|4|0.0000%|0/0|14/3/14|
|raptor_hover|实际N发布|1375|0/0/4|4|0.0000%|0/0|14/3/14|
|raptor_hover|N持权区间|1375|0/0/4|4|0.0000%|0/0|14/3/14|
|repeated_handover|活动|4142|0/0/4|8|0.0966%|1/0|52/25/52|
|repeated_handover|实际N发布|4134|0/0/4|8|0.0968%|1/0|52/25/52|
|repeated_handover|N持权区间|4134|0/0/4|8|0.0968%|1/0|52/25/52|
|state_reset|活动|1411|0/0/4|8|0.0709%|1/0|16/8/16|
|state_reset|实际N发布|1408|0/0/4|8|0.0710%|1/0|16/8/16|
|state_reset|N持权区间|1408|0/0/4|8|0.0710%|1/0|16/8/16|
|state_hold|活动|1404|0/0/4|8|0.0712%|1/0|15/0/15|
|state_hold|实际N发布|1401|0/0/4|8|0.0714%|1/0|15/0/15|
|state_hold|N持权区间|1401|0/0/4|8|0.0714%|1/0|15/0/15|
|state_restore|活动|2752|0/0/4|12|0.1090%|2/4|28/13/28|
|state_restore|实际N发布|2746|0/0/4|12|0.1092%|2/4|28/13/28|
|state_restore|N持权区间|2746|0/0/4|12|0.1092%|2/4|28/13/28|
|state_injection|活动|1400|0/0/0|4|0.0000%|0/0|6/2/6|
|state_injection|实际N发布|1397|0/0/0|4|0.0000%|0/0|6/2/6|
|state_injection|N持权区间|1397|0/0/0|4|0.0000%|0/0|6/2/6|

同 tick 的不同有效采样按递增 timestamp_sample 消费；SampleClock 在 observe/control 之前拒绝重复/倒退，不随 reset 清空。不是“每个250Hz样本推进一次永久GRU”：native（当前125Hz）才提交永久状态，intermediate 从永久状态复制到临时状态计算、不提交，hold 恢复冻结状态；这避免重复推进，同时保留正常中间控制更新。累计 source_missed/duplicate/regressed 均0，已记录 GRU 提交时刻严格递增；日志缺行意味着不能单靠逐行提交记录证明所有细节，证据还包括 guard 位置与累计计数。

`actuator_published=true` 在仲裁允许且实际执行 `_actuator_motors_pub.publish` 后设置。表中同tick补处理的右侧有效动作均确实发布到这个 uORB topic；活动但尚未取得权的行不发布。**发布到 uORB 不等于每个动作被模拟电机执行**：FunctionMotors::update() 从 actuator_motors 取值，GZMixingInterfaceESC::Run() 经 mixing_output.update()，updateOutputs() 再向 Gazebo rotor command 发布。这个链路会受调度/最新值语义影响，现有日志没有逐动作贯穿采样ID的消费者确认，不能断言积压动作全部执行或全部覆盖，更不能以 research_actuator 代替ESC消费证据。

处理时限建议：保留原 executor 的采样时序阈值，4ms（250Hz一周期）作为采集至开始/发布/消费的分级目标；原推理P99≤2500µs只约束observe/control耗时，不保证端到端deadline。策略当前native125Hz、训练100Hz，这个节拍差异仍在，不能据“一个8ms native周期”自行设置8ms容忍上限。现阶段没有训练延迟鲁棒性/实际电机消费年龄证据，不能合理批准数值硬deadline。下一步最小修改是在采集、Run入口、control开始、动作发布、ESC消费处记录同一采样ID，并同时记录可靠墙钟/仿真钟，用运行时分位/超标段计数消除ULog漏行影响；测清端到端年龄和丢弃/覆盖后，再按策略允许的延迟预算确认硬门槛。

现行 FAIL：无效/倒退输入、漏源代际、重复GRU提交、活动或实际N发布 executor 告警、未解释异常、缺必要指标/不通过恢复验收。单纯>4ms目前只记目标超标，不单独判单轮FAIL；排队与输出时限未解释清楚则整体P0继续FAIL/未完成，不能通过修改时间戳、放宽旧阈值或重复运行选择性消除。

最后补充对照只回退 daemon TLS 创建顺序，单独构建诊断ELF后恢复正式源码/二进制；正式RAPTOR哈希仍为 d4a128823a58af29d675457e63592db8e9cf77347351833c029fb793a44328d0。冷启动回溯探针不预热libgcc。前两次诊断分别因可执行文件basename误入客户端分支、缺少配套alias脚本而失败，属于诊断部署问题；修正第三次启动正常，但barometer缺失导致解锁拒绝，未复现目标fatal信号，因此不能关闭旧崩溃根因项。barometer缺失也出现在旧RAPTOR诊断，不能归因于经典控制器独有问题。诊断编译来源与正式恢复校验详见 `before-key-diagnostic-build.json`、`before-key-diagnostic-result.json`，所有尝试加入 `run-history.json`；未将任何诊断作为最终验收通过证据。最终完整性检查 `final-integrity.json` 确认两套源码差异/ELF身份匹配、原始metrics及旧verified记录未改写。

## 2026-10-12 P0 收尾判定：完成

用户 2026-10-12 授权 Claude 按自身判断推进并给出 P0 判定。上文 2026-10-10 的总审计 FAIL 及 [acceptance.json](../data/p0-20261010/acceptance.json) 保持原样；收尾判定另存于 [p0-closure-20261012/acceptance.json](../data/p0-closure-20261012/acceptance.json)（`tools/p0_closure.py` 生成），依据为准备阶段修复后的冻结批次 batch-03、batch-04、batch-05（详见[准备记录](THOR_PREPARATION_20261011.md)）。三项阻塞逐项结论：

1. **正常版本崩溃 — 关闭。** batch-02 的 core 定位到 RAPTOR lockstep 调度器 caller mutex 生命周期竞态，`tests/lockstep_lifetime_test.cpp` 可确定性复现，修复后测试通过。修复后共 101 轮飞行（RAPTOR 86 轮）及 60 次冷启动，0 崩溃。按修复前 RAPTOR 飞行约 4/24 的崩溃率，86 轮全部无崩溃的概率约 1.6×10⁻⁷；若仍存在其他崩溃原因，其每轮发生率 95% 上界约 3%。未证明部分：P0 中 raptor-hover-01 的段错误没有调用栈，悬空的栈上 mutex 与之相符但未证实。classic 使用 PX4 原版调度器，不含该竞态。
2. **启动传感器缺失 — 关闭。** batch-01 证明缺失的是 IMU 链路而非气压；固定 `GZ_IP=127.0.0.1` 与严格就绪检查后，连续 161 次冷启动（含每轮飞行的启动）无传感器就绪失败，每次启动失败率 95% 上界约 1.9%。多网卡端点选择仍是假设，未证实为根因。
3. **输出链路时延 — 关闭。** 每一层均为最新值覆盖，验收对象改为每个物理步实际生效命令的年龄与覆盖率，并以 Gazebo 侧逐步记录直接测量（见准备记录）。门槛为 Claude 提议（用户授权），依据物理常数而非观测数据：神经持权期间每轮 P99 ≤ 4 ms（lockstep 结构下限，一个物理步），最大 ≤ 12 ms（低于 x500 SDF 电机上升时间常数 12.5 ms），超过 4 ms 的连续步数 ≤ 2，被覆盖命令 < 0.1%。batch-04、batch-05 共 68 轮、145979 个神经物理步：每轮 P99 均为 4 ms，最大 8 ms，最长连续超标 1 步，覆盖 10 次（0.007%），门槛满足。

联合恢复的位置参考已由固定 [0,0,-3] 改为控制器当前位置目标（用户确认，阈值不变），原因及只读复算见准备记录；固定参考结果继续作为对照报告。

**判定：P0 完成。** 适用范围不变：冻结 x500 配置、本机 headless SITL、短时窗口，神经控制由经典控制起飞和降落；native 约 125 Hz 与训练 100 Hz 的差异仍在；尾部时延受主机负载影响。不构成实时性认证或实飞能力。下一阶段可以进入 P1。

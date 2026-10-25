# P11 字段、时钟及机制接口

本文件与 `tools/apply_p11.py`、`research/state/ResearchP11.msg` 配套。P11 仅 SITL，新增 topic 没有控制器订阅。`MC_RAPTOR_P11=0` 默认关闭，且要求 `MC_RAPTOR_RSH=1` 才记录。原策略、权重、保护、目标和 GRU 更新方程不变。完整分叉没有实现：Gazebo/EKF/时钟状态没有完整快照，因此同种子暖机配对只能称近似配对，必须检验预事件差异。

```mermaid
sequenceDiagram
    participant R as runner CLOCK_MONOTONIC
    participant D as DDS/uORB latest value
    participant C as RAPTOR Run
    participant E as executor
    participant G as Gazebo physics 4ms
    R->>D: send_id, publish-call bracket, profile p/v/yaw
    C->>C: hrt now + host monotonic pair; mode/entry reset
    C->>D: updated+update once; finite-field validation
    D-->>C: gyro, LP, attitude, external target
    C->>C: last_valid_read=now only on valid external read
    C->>C: strict age>200ms => capture same observed p/yaw; T0 v=0
    C->>C: RTGT profile; RREC transition (before duplicate rejection)
    C->>C: SampleClock duplicate/regression rejection; state operations
    C->>C: observe RAII swaps virtual target; P11 pre-GRU and exact read states
    C->>E: clipped target-yaw FLU errors, relative rotation, omega, previous action
    E->>E: action-history mean; Dense22→16 ReLU→GRU16→Dense4
    E->>E: native ~8ms commits; intermediate ~4ms uses temporary hidden
    E-->>C: output clip[-1,1]; observation target restored
    C->>D: (action+1)/2; remap [0,2,3,1]; actuator gate
    C->>D: P11 post-GRU/action; timing and actuator evidence
    D->>G: coalesced latest motor-speed command, timestamp_sample
    G-->>D: existing truth pose; finite-difference velocity/acceleration
```

| 字段/来源 | 坐标、单位 | 写入/使用时间及限制 |
|---|---|---|
| runner `p11-sends.jsonl` | send_id 整数；host monotonic ns；profile s；p NED m、v NED m/s、yaw rad | 每次实际 `trajpub.publish` 前后包围；不改消息、不伪称 send_id 经 DDS 传入 native。发送 ID 与读取通过时间区间和值匹配；静止重复值可能不可唯一匹配。 |
| `ResearchP11.timestamp/run_wall_ns/read_wall_ns` | native us / host CLOCK_MONOTONIC ns | 每个 Run 的 native 取时、随后 host 取时、订阅读取后 host 取时。当前 native 查询因同一线程串行，被上一 Run 的 read_wall 与当前 run_wall 因果夹住；宽度逐行保存，不假定恒为4ms。首行没有前括号则未知。不能把一个 profile bound 当全程精确仿射对齐。 |
| `timestamp_sample/local_position_sample/attitude_sample` | native us | 实际被读取 gyro/LP/attitude 的采集标识。LP 保持和姿态保持分别建模，不能用最近的新日志值替代。 |
| `subscription_updated/external_valid/external_timestamp/last_valid_read_us/invalid_total` | bool/us/count | 使用原订阅结果，不调用第二次 update。消息字段全 finite 才刷新读取时钟；外部 header 经过 DDS 时间转换，不能单独当 runner ID。重复/拒绝由 `research_timing` 与 `raptor_status` 复用。 |
| `external_position/velocity/yaw` | NED m、m/s、rad | valid read 的原消息值；无 valid read 则 NaN，不能当0。保持状态由最近有效读取重建。 |
| active/stale/activation；`research_target` / `research_recovery` | bool / native us | guard、捕获、RTGT/START/resume 与 sample rejection 的顺序见图；状态跳变可能先于重复样本拒绝。末段停止发送也会产生捕获，不能删除。 |
| `position/velocity/attitude/angular_velocity` | NED m、m/s；FRD→NED quaternion wxyz；FRD rad/s | `observe()` 实际读取的缓存值。estimator 和命名控制输入保留两条路径，禁止混称真值。 |
| `network_target_position/velocity/target_yaw` | NED m、m/s、rad | 在 P7 RAII recovery view 生效期间记录；observe 后恢复原 trajectory，外部目标与网络目标须区分。 |
| `policy_input[22]` | p误差3、旋转矩阵9、v误差3、角速度3、action history4 | 实际 executor 输入；p 每轴 clip±0.5m、v 每轴 clip±1m/s，目标 yaw FLU 系。没有额外尺度归一化。未裁剪误差由实际 p/v/target/yaw 计算，并独立核裁剪后输入。 |
| GRU before/after16；previous action before/after4 | 无量纲 | before 在 observe 内，state ops/entry reset 后；after 在输出写入后。native 提交、intermediate 临时状态不提交。previous action 是每个控制调用的输出，history 为 native 间隔内平均，不是一个简单 FIFO。 |
| executor_action4 | [-1,1] | 已经 executor clip，尚未 (a+1)/2 和 remap。不是未限幅网络输出。未限幅 Dense 输出由完整输入/前状态/权重离线重算，核其 clip 与实测输出一致；该量标记 RECONSTRUCTED，不冒称直接 native 采集。 |
| `research_actuator/actuator_motors/research_output` | motor [0,1] / speed command rad/s | 复用所有权、分配/映射、桥接选择、跳代及 applied sample。最新值链允许合并，不能要求每条输出都执行。 |
| `gz-motor/motor-*.bin` | physics/native us、host ns、refMotorInput rad/s | 现有每物理步 command consumption trace；refMotorInput 是电机命令，不是实际转速。真实转子速度/推力未直接记录，本轮不为可选项重写仿真器。 |
| `vehicle_local_position_groundtruth` | Gazebo 世界 ENU→NED；m、m/s、m/s² | p由pose转换，v=(p-p_prev)/dt，a=(v-v_prev)/dt；dt由pose回调的native hrt差确定并被源实现限制在1–100ms。truth.timestamp_sample是回调时钟，不是已证实的原物理采集时刻。a 为数值运动学加速度（静止≈0），不再减 g；与 IMU proper acceleration 不同。估计器原点差须单独对齐；同步保持并报告约20ms发布与0–16ms记录年龄，未覆盖的回调运输差不填0。 |
| `vehicle_attitude_groundtruth` | FRD→NED wxyz | 源 pose 四元数变换；用 SO(3) 测地角比较，不能直接相减欧拉角。 |
| `vehicle_angular_velocity_groundtruth` | 源实现为 Euler 差/dt | 名称不等于机体系 omega。仅原样保留，若从真值四元数差求角速度，必须标为数值派生并注明帧、时间窗口。 |
| 姿态几何代理 q | `-g*R_body_z,xy/R_body_z,z` m/s² | 仅几何量；不等于净水平加速度。推力、竖直加速度、气动和估计器遗漏不能填0。Rzz≤0.1 时不定义，不外推。 |

日志覆盖验收比较 P11 与 timing 的所有 active control sample 集合、唯一性、连续边及 native commit，任何缺口单列。单步重放容差 h/action 1e-5，连续递推 1e-4，几何输入 1e-4；依据 binary32 运算及累积误差制定。单步允许真实前状态；连续仅首次初始化，递推 h/previous action/history，不逐步注入。两者均为已知外生输入的重放，不能作为闭环预测结果。

观测等价开发对照使用同任务/种子/暖机，预注册沿用 P9 的峰值倾角差≤2.5°，控制4ms/native8ms节拍保持、source miss/duplicate/regression不增加、p99 observe+control<2500us。P11 hook 在既有 timed span 外的部分需由 Run/read/pub host 时钟和整条节拍一并检查，不能仅用原 inference duration 声称无开销。

最终观测版本另在 `research_timing` 记录 `p11_cycle_wall_start/end_ns`（从参数/观测setup开始到P11完整uORB发布结束，包含普通控制工作）、setup、pre-GRU拷贝、post拷贝、完整publication时长。关闭/开启对照使用同一最终二进制；分项不是相互独立的因果成本估计，完整跨度涵盖未单列的读取拷贝。runner每条sidecar记前次 publish+JSON+flush 的完整跨度，正常stop事件补最后一次；中止时缺失的最后可选开销值明确未知，不影响原始发送/控制状态数据的逐次覆盖。全部控制行和发送/读取匹配用于检验异步logger吞吐，未降采样。

M1/M2的初始机体状态取pre-stream实际读取状态，因此仍含估计/保持年龄不确定性；不冒称真实机体快照。M2四个电机滤波状态从初始末命令的稳态值近似初始化，是真值缺失下的模型初态假设。源码滤波后速度设定不等于实际JointVelocity；真实RPM未记录，剩余执行误差仍需独立界。已停止的RTGT profile可在网络目标预测中压缩成当前r/v=0的持有态；新fresh结束旧profile、下一capture重建profile，输出与之后reset关系不变。RREC非零初态不被当前正式预测入口接纳，开发RREC重放单独验证。

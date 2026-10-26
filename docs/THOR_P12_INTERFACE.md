# P12 唯一状态机与双时钟接口

本规范区分真实源码映射、实验交付门及模型近似。P11规范保留，P12状态/模式如下；网络权重不变。普通输出调用不能合并成恒4ms流动。

## 状态与坐标

`z=(p_world,v_world,q_FRD_to_NED,omega_FRD,estimator_state, cache_gyro,cache_LP,cache_att, t_cache, target_external,last_valid_read,stale,target_capture,p0,v0,yaw0,target_profile,recovery,h,previous,mean,count,executor_call_index,last_commit_sample,filter4,joint4,pending_motor_command,applied_command,sample_clock,native_hrt,host_monotonic,delivery_queue)`。

真实仿真器和估计器完整状态并未导出/快照，不能称可精确分叉的全状态。world高度是Gazebo世界ENU的z；控制器NED z和估计器原点须另存，不能用内部目标差替代绝对高度。P12沿用P11的真值topic和held回调年龄限制，不宣称真值topic是同一物理时刻的无延迟采样。

控制器实际读取p/v是LP缓存，q是姿态缓存，omega是gyro缓存。策略输入前18维为yaw目标帧FLU坐标的逐轴位置clip±.5、相对旋转矩阵9、速度clip±1、角速度3；后4维为executor动态均值。GRU hidden16、previous4、mean4、count和调用计数均为状态。目标捕获复制同一缓存p/v/q，不能独立选择p0/v0。RTGT2垂向目标速度仍为0。

执行分成：executor action[-1,1]；映射/重排后的motor command；桥接latest-value选择；物理步消费的rad/s命令；期望转速内部滤波；求解器实际关节rad/s；乘slowdown后的仿真转子rad/s；由关节状态计算的推力/世界力矩。任何一层都不统称“真实RPM”。

## 源码顺序与模式

1. Run取得native current_time，记录host时钟；模式/首次激活处理、teacher forcing先于读取。gyro队列逐次消费，LP/姿态各读取最新或保持；cache sample不等于native now。
2. P12交付门读真实executor `intermediate_step` 和 `force_sync_native`。在初始化且active时，PH1只允许`index%force_sync==0`，PH2只允许非零余数。拒绝消费时保留uORB latest pending，不更新last_valid_read，不写伪造时钟。inactive/PH0原样。
3. 实际一次trajectory update通过全finite检查才刷新native读取时间并替换外部目标。read-before/read-after host区间与P11更宽的Run/read区间同时保留。守卫评估发生在真实读取后：`not set || internal_reference || now-last_read>200000`。恢复消息先读可阻止当次捕获。
4. stale跃迁或首次激活才capture：p/yaw来自当前缓存，v目标原为0；P12 override仅在启用且非activation/active/已见外部消息时可选择RTGT2。activation所有臂T0。RTGT profile按sample elapsed闭式积分，fresh结束profile，resume可跳回原绝对任务目标。h/previous/mean/count保持。
5. target/recovery跳变先于SampleClock拒绝；重复/回退样本不会执行网络，但前面的真实读取/目标跳变不能被模型抹掉。P12观察topic覆盖成功调用；拒绝调用须联用research_timing及research_target，不能用P12缺行宣布没有跳变。
6. state操作之后observe（P7虚拟target的RAII view有效）；先记录GRU、previous、mean/count，再更新均值：`mu'=(n*mu+previous)/(n+1)`（n0直接previous）。Dense/ReLU/GRU求临时h*，Dense/clip生成action。native调用提交h*；intermediate用临时副本，保留h。每次输出均写previous；history count在native置0，否则加1。reset/hold是额外离散模式，本轮不施加其干预，不能假设通用接口没有这些模式。
7. 原actuator gate和remap后发布；桥接及Gazebo队列可覆盖中间命令。命令消费与capture的顺序通过跨线程host区间比较，重叠即UNKNOWN，不用相同sample ID推断跨线程先后。
8. physics PreUpdate消费命令，先用本步读取的JointVelocity计算推力/力矩，再更新filter，写JointVelocityCmd；动力学求解器后续执行。故filter-after不是本步推力的转速。

```mermaid
sequenceDiagram
    participant R as runner/host
    participant U as uORB latest target
    participant C as RAPTOR/native hrt
    participant E as executor/sample+call index
    participant G as Gazebo physics
    R->>U: original absolute task + event mask
    C->>E: inspect real call index (P12 experiment gate)
    C->>U: permitted phase: actual update once
    U-->>C: valid target or held cache
    C->>C: strict native age >200ms => correlated capture
    C->>E: observation+mean; output every accepted call
    E->>E: native commits h; intermediate temporary h
    E-->>C: clipped action; previous written every output
    C->>G: latest command queue via existing bridge
    G->>G: consume => joint-based forces => filter update => joint command
    Note over C,E: sample advances 4ms while native may jump 8ms then plateau
    Note over C,G: host brackets order threads; overlapping brackets remain unknown
```

## 新日志

`research_p12`：native/sample、read_begin/end CLOCK_MONOTONIC ns、last_gru_sample_before、真实call_index before/after、history mean/count before/after、请求phase、预测及实际commit、pending/permit、LP/att更新、external_seen/repair_requested。与P11同一sample联接，不能按native timestamp唯一联接（平台允许重复native值）。预测commit字段只是装置验收，需要与actual_commit逐行核对。

`gz-motor/execution-p12-{0..3}.bin`：小端、每行152B，5个uint64为simUs/sampleUs/consumeWallNs/filterWallNs/endWallNs；14个float64为dt秒、command、filterBefore/After rad/s、jointVelocity rad/s、scaledJointVelocity rad/s、thrust N、torqueWorld xyz N·m、tauUp/Down秒、slowdown、motorConstant。仅当HANDOVER_P12_TRACE存在时记录，不参与控制。旧motor-*.bin仍为56B。filterBefore直接读FirstOrderFilter::previousState；其构造初值是当时refMotorInput（本配置0），由首行和连续前后状态核验，不能以末命令稳态代替。实际关节转速符号与turningDirection一致，不能直接与非负滤波值相减；应先取相应符号/幅值。

full-cycle统计在P12发布后更新原timing的cycle-end字段，含P12参数读取和发布；before/after拷贝等旧分项不能单独代表新完整开销。新增P12 topic在init advertise，未启用不发布。buffer每25步flush，正常关闭保留尾部；缺行/截断需直接报告，不能补零。

## 时间跳进、平台和追赶

接受非递减native而不是严格递增；sample由SampleClock检查，host为实时间隔。第70条合法词为sample 80336/80340/80344/80348ms，native 80336/80344/80344/80348ms；host间隔约7.886/.205/3.866ms。守卫在跳进调用已看见较大读取年龄，平台调用不再增加年龄，executor依实际sample与计数推进。`host_delta/native_delta`在平台不定义，输出null并保存原delta；这不是把平台换成0比率。native回退另列异常，不能悄悄与平台合并。

盲预测的调度必须事前给定或作为不确定集传播，真实未来native/更新/消费词只允许用于已知输入重放与评分。日志词可验证映射一致性，不证明该词可被事前预测。完整状态/真实调度硬界缺失时，有限情景包络不是已证覆盖。

执行力矩字段的作用域：torqueWorld是每个motor plugin显式施加到parent link的旋翼反扭矩及rolling moment，thrust是旋翼局部轴标量。臂长×推力的力矩、air drag及其他插件/求解器作用未合成总机体wrench；不能将该字段称整机总力矩。M3仍以控制器NED状态作为经验机体代理，未建立估计器原点到绝对世界高度的完整动态误差；真实world高度以独立held groundtruth路径报告，不悄悄等同NED z。

开发v2任务epoch：runner通过真实listener回执确认native_step=True，以该已发生Run的CLOCK_MONOTONIC记录定义随后实际任务表时间零点；query前后和回执年龄保留。原sample/native和消息header不修改。共同world参考是新配置中的NED[0,0,-3]、yaw96°；它是声明的实验任务变更，不是生产控制器语义，也不是对旧数据事后对齐。最后两次已实际执行；提交/count同步改善不能替代LP/姿态缓存和完整初值相同。

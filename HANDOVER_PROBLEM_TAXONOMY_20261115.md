# PX4 RAPTOR 切换问题四类基线

日期：2026 年 11 月 15 日

所属分支：`research/handover-baseline-20261115`

适用范围：经典控制与 PX4 RAPTOR 的运行时交接，以及 RAPTOR 活动期间的 setpoint 回退和恢复。

本文固定四种分类名称、判定边界及对应的飞行例子。每个例子都展开到代码变量、消息和实际执行链，用来说明问题从哪里开始、怎样传播，以及怎样与另外三类区分。第一类和第四类采用待验证的构造场景；第二类和第三类有历史 SITL 中的相近机制证据。文中的示例数值不构成本分支的新实验结果。

## 1 分类名称与边界

| 编号 | 分类名称 | 起始问题 | 单因例子的隔离条件 |
| --- | --- | --- | --- |
| T1 | 接管后神经控制器安全裕度不足 | 接收控制器在当前运动状态下的恢复过程，会耗尽剩余安全裕度 | 历史状态、setpoint 接续和命令交付均正确 |
| T2 | 控制器历史状态接续错误 | 首次及后续计算使用的记忆或上一动作，与真实执行经历不相容 | 物理入口可安全接管，setpoint 和命令交付均正确 |
| T3 | setpoint信号接续异常 | 控制器实际采用的目标发生中断、错误保留、语义改变或不连续恢复 | 历史状态和命令交付正确，连续参考下入口可安全接管 |
| T4 | 控制权实际交付异常 | 预期控制来源、已发布命令和执行器实际应用之间发生交付错误 | 入口可安全接管，历史状态和 setpoint 均正确 |

分类单位是一个独立的起始问题。飞机倾斜、失高、制动或追赶属于后果，同一种后果可以由不同类别产生。按独立起因归类，可以避免同一条因果链被重复计数。

例如，T3 的参考跳变会改变观测，随后改变 GRU；GRU 的变化属于该参考事件的传播过程。若同一次飞行还存在一个独立的错误初始化，则记录两个起因及其交互。只有证据支持单一起因时，才将整条案例归为一个单因类型；归因不清的记录保留待定状态。

X、H、P 继续作为案例描述字段：X 记录物理状态，H 记录保留下来的软件信息，P 记录交接规则与实际时序。四类问题分别围绕安全裕度、历史状态、参考信号和实际交付组织，具体案例可以同时涉及 X、H、P。

## 2 固定源码与共用数据流

### 2.1 源码身份

本分支的环境基线锚点为 `ddeaddd2213fb8e79d6d008f2c26d7cd82cf52e2`。其 [environment.lock](environment.lock) 记录 PX4 RAPTOR 上游提交 `4ae21a5e569d3d89c2f6366688cbacb3e93437c9`、RLtools 子模块提交 `15940da2a8334d7532c4a5650ee4e09526206414`，并配套本仓库的研究补丁。下文上游代码链接固定到这两个提交；基线研究接口另行引用本仓库文件。

基线通过 [tools/apply_research.py](https://github.com/JacksonW1025/uav_handover/blob/ddeaddd2213fb8e79d6d008f2c26d7cd82cf52e2/tools/apply_research.py) 和 [patches/raptor-final.patch](https://github.com/JacksonW1025/uav_handover/blob/ddeaddd2213fb8e79d6d008f2c26d7cd82cf52e2/patches/raptor-final.patch) 增加状态操作、进入时保留状态、发布者仲裁和记录。下文涉及正常 `reset()` 的场景采用原始重置路径；需要隔离历史影响时，明确准备并核验相应状态。

本分支 `MC_RAPTOR_RINI` 是是否保留状态的布尔研究开关，不能直接套用后期实验中同名参数的多值编号。基线也未携带后期的高频四电机物理步审计链，相关能力范围见 [README](README.md) 和 [基线核验说明](docs/BASELINE_VERIFICATION.md)。

### 2.2 从切换请求到电机应用

```text
模式请求
  → UserModeIntention::change() 查询 canRun()
  → Commander 仲裁并发布 vehicle_status.nav_state
  → RAPTOR 判断 nav_state 与 ext_component_mode_id
  → 进入沿发布 setpoint_config 并初始化本轮状态
  → 读取状态估计与 trajectory_setpoint
  → observe(observation)
  → rl_tools::control(device, executor, ..., policy, observation, action, rng)
  → action.action[] 映射及电机编号重排
  → actuator_motors 发布
  → 输出功能订阅、输出限制、驱动或仿真桥
  → 电机与机体运动
```

上游进入沿采用 `!previous_active && next_active`。`next_active` 根据最近读取的 `vehicle_status.nav_state` 与 `ext_component_mode_id` 判断；基线补丁进一步检查注册完成状态。进入时发布的配置包含 `source_id`、`TYPE_DIRECT_ACTUATORS` 和 `should_apply=true`，随后执行重置。[进入处理源码](https://github.com/PX4/PX4-Autopilot/blob/4ae21a5e569d3d89c2f6366688cbacb3e93437c9/src/modules/mc_raptor/mc_raptor.cpp#L514-L534)

`observe()` 把位置、速度、姿态、角速度及上一动作构造成策略观测；位置和速度误差进行坐标变换与裁剪。得到动作后，代码按 `(action + 1) / 2` 映射电机命令，按构建配置重排编号，并在 `status.active` 时发布。具体坐标、编号及仿真映射见 [平台映射](docs/THOR_PLATFORM_MAPPING.md)。归一化命令与物理推力之间还经过电机模型，二者的数值关系需要单独核对。

下文代码块以变量赋值和逻辑摘写为主，省略日志、统计及无关分支；场景赋值仅用于说明状态，不是可直接应用到飞控的补丁。

## 3 T1 接管后神经控制器安全裕度不足

### 3.1 飞行场景

飞机在下降过程中，经典控制器已经开始制动。此时距离平地约 0.8 m，下沉速度为 1.5 m/s，操作者请求交给 RAPTOR。使用地面为局部原点的 NED 坐标，可将入口写成：

```cpp
// 构造场景中的值，单位分别为 m 和 m/s。
_vehicle_local_position.z  = -0.8f;
_vehicle_local_position.vz = +1.5f;

// 此位置保持目标在切换前已存在，切换后持续正确送达。
_trajectory_setpoint.position[2] = -0.8f;
_trajectory_setpoint.velocity[2] = 0.0f;
```

其余位置、速度及姿态字段保持完整有效。历史状态已正确准备，参考在进入重置后重新被本轮接受，输出交付正常。这样可以独立观察神经控制器在该物理状态下的恢复能力。

假设后续成对验证得到：经典控制继续制动还会下降约 0.4 m；RAPTOR 在相同入口和相同目标下需要下降约 1.1 m 才能停止下沉。0.8 m 的剩余高度能够容纳经典控制的恢复，RAPTOR 的恢复过程则会先接触地面。这些距离是构造例子的假定结果，尚待真实闭环对照取得。

### 3.2 代码变量与传播过程

`Run()` 从局部位置消息更新 `position[]` 和 `linear_velocity[]`。在目标 yaw 为零的简化条件下，竖直速度误差进入观测的关系为：

```cpp
v[2] = -(linear_velocity[2] - _trajectory_setpoint.velocity[2]);
// 经目标坐标系旋转后：
observation.linear_velocity[2] = clip(vt[2], max_velocity_error, -max_velocity_error);
```

本例输入下，未裁剪的竖直误差为 -1.5 m/s；默认 `max_velocity_error=1.0`，该分量进入策略时为 -1.0。此时位置恰好位于目标位置，位置误差接近零。策略仍能看到姿态、角速度及历史动作，但这组位置误差本身不表达剩余离地高度。[观测构造](https://github.com/PX4/PX4-Autopilot/blob/4ae21a5e569d3d89c2f6366688cbacb3e93437c9/src/modules/mc_raptor/mc_raptor.cpp#L344-L412)

后续数据流为：

```text
position[] / linear_velocity[] / q / xyz
  → observation
  → executor 和 policy
  → action.action[]
  → actuator_motors.control[]
  → 剩余下降距离与最低高度
```

`UserModeIntention::change()` 中的 `canRun()` 查询，以及 RAPTOR 对状态更新窗口的检查，属于已有准入与运行条件。上述调用位置没有计算本例的预计最低高度或剩余制动距离。接管能否留在安全范围，需要结合当前策略、机体、入口状态、参考和环境评价。[模式请求准入](https://github.com/PX4/PX4-Autopilot/blob/4ae21a5e569d3d89c2f6366688cbacb3e93437c9/src/modules/commander/UserModeIntention.cpp#L43-L89)

### 3.3 分类判定与区分性对照

本例的起始问题是：接管后的神经闭环需要更多恢复空间，当前安全裕度无法容纳该过程。参考信号、历史初始化与输出链均按预期工作。

判定需要同时保留三个对照：同一入口继续经典控制；在相同目标及正确交接下进入 RAPTOR；在更大安全余量下执行相同 RAPTOR 接管。只有后两类对照共同说明恢复需求及余量关系，才能支持该归因。

若改变参考接续即可消除失败，或者发现错误历史或输出延迟，应按相应起因记录。高速、低空、大倾角只是触发条件，不能单独充当 T1 的证据。

应观察入口 `z/vz`、姿态、角速度、真实参考及其接受时刻、历史准备状态、命令应用时刻和最低世界高度。地面起伏或局部原点变化时，安全余量需要额外的地面与坐标依据。

## 4 T2 控制器历史状态接续错误

### 4.1 飞行场景

飞机在空中稳定悬停，经典控制器持续维持固定位置。参考在交接前后保持一致，所有必填字段有效。假设四路实际归一化电机命令均约为 0.6，对应 RAPTOR 动作尺度中的约 0.2。这里的 0.6 只用于说明动作尺度，实际悬停值随机体与模型变化。

切入 RAPTOR 后，默认进入路径把上一动作恢复为固定初值，并重置策略执行状态。若这些初值与刚刚真实执行的悬停历史不相容，首轮及随后若干轮推理可能偏离所需输出，造成电机阶跃、短暂失高或姿态扰动。

### 4.2 从 reset 到策略输入

RAPTOR 的 `reset()` 执行以下操作：

```text
previous_action[] ← RESET_PREVIOUS_ACTION_VALUE
rlt::reset(device, executor, policy, rng)
```

`RESET_PREVIOUS_ACTION_VALUE` 在该版本中为 0，采用策略的 -1 到 1 动作尺度。该赋值更新软件历史，电机输出在后续动作映射和发布阶段产生。[模块重置](https://github.com/PX4/PX4-Autopilot/blob/4ae21a5e569d3d89c2f6366688cbacb3e93437c9/src/modules/mc_raptor/mc_raptor.cpp#L40-L54) [常量定义](https://github.com/PX4/PX4-Autopilot/blob/4ae21a5e569d3d89c2f6366688cbacb3e93437c9/src/modules/mc_raptor/mc_raptor.hpp#L108-L116)

RLtools 的重置继续向下传递：L2F 层初始化 `executor.action_history`；执行器层重置 `policy_state`、时钟有效标志和步数；GRU 层把 `state.state` 恢复为模型的 `initial_hidden_state.parameters`。模型保存的初值需按具体权重解释。[L2F 重置](https://github.com/rl-tools/rl-tools/blob/15940da2a8334d7532c4a5650ee4e09526206414/include/rl_tools/inference/applications/l2f/operations_generic.h#L23-L34) [执行器重置](https://github.com/rl-tools/rl-tools/blob/15940da2a8334d7532c4a5650ee4e09526206414/include/rl_tools/inference/executor/operations_generic.h#L24-L38) [GRU 重置](https://github.com/rl-tools/rl-tools/blob/15940da2a8334d7532c4a5650ee4e09526206414/include/rl_tools/nn/layers/gru/operations_generic.h#L88-L106)

当前观测中的 `observation.previous_action[]` 由模块 `previous_action[]` 填充，再进入 L2F 动作历史和策略计算。完整传播为：

```text
真实执行过的电机动作约为 0.6
  → 对应策略动作约为 0.2
  → 进入时 previous_action 被设为 0，GRU 恢复模型初值
  → observation.previous_action[] 与循环状态共同影响推理
  → action.action[] 发生偏移
  → 映射后的电机命令产生阶跃
  → 飞机出现瞬态扰动
```

从代码只能确定重置及输入路径；具体输出偏移方向和幅度由策略及入口状态决定，需要闭环观测。[历史动作输入](https://github.com/PX4/PX4-Autopilot/blob/4ae21a5e569d3d89c2f6366688cbacb3e93437c9/src/modules/mc_raptor/mc_raptor.cpp#L403-L412)

### 4.3 基线中可定位的历史状态

本基线研究接口访问冻结网络 GRU 的实际路径为：

```cpp
executor.executor.policy_state.content_state.next_content_state.state.state
executor.executor.policy_state_temp.content_state.next_content_state.state.state
```

`research_get(float *v)` 读取 16 维 GRU、4 维上一动作、3 维目标位置和 3 维目标速度；`research_set()` 写回相应值，并同步正式与临时 GRU 状态。该路径及 16 维约束适用于本基线冻结网络。[状态接口实现](https://github.com/JacksonW1025/uav_handover/blob/ddeaddd2213fb8e79d6d008f2c26d7cd82cf52e2/tools/apply_research.py#L50-L82)

这个接口同时包含历史和参考。只干预历史时，需要保持 `v[20..25]` 中的参考值一致，并额外核验 yaw、yawspeed、参考有效标志和接受时刻。26 维接口没有完整包含这些信息，也不等于完整仿真快照。

### 4.4 分类判定与区分性对照

单因例子要求飞机处于可接管范围，首次有效参考与切换前目标一致，控制器输出及时应用。对照只改变 GRU 和上一动作的准备方式，观察首次推理输入、输出阶跃及后续恢复。

历史 P2 在悬停条件下记录过相近机制：同时用真实执行历史准备 GRU 并对齐上一动作，电机阶跃从约 0.22 降至 0.017；这些数值属于当时的研究改动及实验条件。[P2 固定报告](https://github.com/JacksonW1025/uav_handover/blob/f596cf9839b496b108b405e795313901aaeb37ca/docs/THOR_P2_REPORT.md)

保留旧记忆、清零或后台推理的效果，需要由其与真实执行经历的相容性解释。后台策略产生过但未实际执行的动作，也可能使保留下来的历史偏离真实飞行。

## 5 T3 setpoint信号接续异常

### 5.1 飞行场景

飞机沿北向以 2 m/s 飞行，参考发生器持续生成时间参数化轨迹。切换时，飞机与当时参考都位于北向约 10 m。GRU 与上一动作已通过对照方式正确准备，控制输出链保持正常。

```cpp
// 构造场景的切换前状态。
position[0] = 10.0f;
linear_velocity[0] = 2.0f;
_trajectory_setpoint.position[0] = 10.0f;
_trajectory_setpoint.velocity[0] = 2.0f;
```

切入 RAPTOR 时，参考流短暂中断。RAPTOR 先捕获当前位置并要求速度归零，飞机开始制动。参考发生器的任务时间仍在推进；0.5 s 后流恢复，送来的轨迹目标已到北向约 11 m，目标速度重新为 2 m/s。此时飞机因制动落后于该目标，随后又开始加速追赶。

这里 Setpoint 的异常接续先制造停车目标，再接回继续前进的任务目标。先制动、后追赶的幅度和是否越过安全限制，取决于入口、断流长度及恢复轨迹。

### 5.2 进入时有效性重置与缺参考捕获

上游 `reset()` 会清除 `timestamp_last_trajectory_setpoint_set`。同一次 `Run()` 后续仍有机会读取新参考；若本轮读取到新的完整有效消息，可以立即重新置为有效。若新消息没有到达或字段不完整，就可能进入缺有效参考的分支。

```text
进入重置：timestamp_last_trajectory_setpoint_set ← false
  → 本轮没有接受新完整参考
  → status.trajectory_setpoint_stale ← true
  → 捕获 position[] 和当前 yaw
  → _trajectory_setpoint.velocity[] ← 0
  → _trajectory_setpoint.yawspeed ← 0
```

缺有效参考的条件可以在进入时立即成立。持续活动期间，最后一次有效参考接受后超过 `TRAJECTORY_SETPOINT_TIMEOUT=200000` 微秒，也会进入该处理。该版本用 `current_time` 更新最后有效参考接受时刻。[参考有效性检查](https://github.com/PX4/PX4-Autopilot/blob/4ae21a5e569d3d89c2f6366688cbacb3e93437c9/src/modules/mc_raptor/mc_raptor.cpp#L572-L613) [捕获与恢复](https://github.com/PX4/PX4-Autopilot/blob/4ae21a5e569d3d89c2f6366688cbacb3e93437c9/src/modules/mc_raptor/mc_raptor.cpp#L768-L803)

参考完整性要求 `position[0..2]`、`velocity[0..2]`、`yaw`、`yawspeed` 全部有限。因此，发布者持续发消息也可能没有形成被 RAPTOR 接受的有效参考。定位时需要同时检查收到消息、接受消息及实际采用目标。

### 5.3 从停车参考到追赶参考

刚捕获时，位置误差接近零，北向速度误差约为 2 m/s。该误差经过目标坐标变换与裁剪后进入 `observation.linear_velocity[]`，使策略面对制动任务。飞机继续运动时，捕获位置留在后方，位置误差随之出现。

流恢复后，完整新消息进入 `temp_trajectory_setpoint`，通过有限性检查后覆盖 `_trajectory_setpoint`，并更新有效标志和接受时间。随后 stale 状态解除，后续推理直接使用恢复后的参考。

```text
trajectory_setpoint 发布中断或未被接受
  → 缺有效参考
  → 捕获当前位置、速度目标归零
  → 制动，物理进度落后于任务时间
  → 新完整参考恢复并覆盖 _trajectory_setpoint
  → 位置及速度目标重新向前
  → observation 变化
  → 策略加速追赶
```

### 5.4 分类判定与区分性对照

本例的起因是控制器采用的 setpoint 在交接中发生了不符合任务接续要求的变化。物理入口在连续参考下可安全运行，历史状态准备正确，电机按时接收策略命令。

区分性对照保持入口、历史处理和输出链一致，只保证有效参考连续采用，或者改变恢复接回方式。观察任务发生器参考、uORB 消息、模块接受记录和 `_trajectory_setpoint`，才能定位异常发生在发布、传输、接受还是选择环节。

已有 P4 与 P5 分别记录零速度捕获及超时恢复相关问题；这些结果对应各自的参考处理配置。本文的 10 m、11 m 和 0.5 s 是构造场景。[P4 固定报告](https://github.com/JacksonW1025/uav_handover/blob/c186c96d6ffbaf4b04c01b234cb3f9621d616e30/docs/THOR_P4_REPORT.md) [P5 固定报告](https://github.com/JacksonW1025/uav_handover/blob/2deb79e2451e191623e86711c5fafed67c428513/docs/THOR_P5_REPORT.md)

## 6 T4 控制权实际交付异常

### 6.1 飞行场景

飞机正在转弯，经典控制的最后一组电机命令包含维持转弯的差动输出。请求交给 RAPTOR 后，参考连续，历史状态已正确准备，RAPTOR 正常算出应当减小转弯的电机命令并持续发布。

构造一个下游故障：执行器输出任务延迟 40 ms 才消费新命令，期间实际电机继续执行先前的命令。飞机仍受旧差动输出驱动，可能继续转动；新命令应用后才开始相应纠正。40 ms 是待验证的故障注入值，其物理后果取决于机体和当时运动。

该场景要求核对驱动或仿真桥在延迟期间的保持与超时行为。如果实际进入其他保护输出，分析应以实际应用的值为准。

### 6.2 上游控制权与命令发布

RAPTOR 通过 `vehicle_status.nav_state` 识别激活，发布 `TYPE_DIRECT_ACTUATORS` 配置；Commander 经配置生成 `vehicle_control_mode`。经典控制分配器根据 `flag_control_allocation_enabled` 更新 `_publish_controls`。这些步骤改变软件控制路径。

RAPTOR 的策略动作写入 `actuator_motors.control[]`，更新 `previous_action[]`，经过编号重排后在 active 条件下发布。[动作映射与发布](https://github.com/PX4/PX4-Autopilot/blob/4ae21a5e569d3d89c2f6366688cbacb3e93437c9/src/modules/mc_raptor/mc_raptor.cpp#L864-L894)

本基线另外在经典与神经发布路径使用 [ActuatorGate](research/state/ActuatorGate.hpp)，在共享锁内读取最新 `vehicle_control_mode`，根据分配标志允许对应一侧发布。因此，构造本例时保留已有仲裁，选择发布之后的消费或应用环节引入延迟。

### 6.3 命令发布之后的数据流

`FunctionMotors` 的关键逻辑为：

```cpp
// 逻辑摘写。
if (_topic.update(&_data)) {
    updateValues(..., _data.control, ...);
}
// value() 从已保存的 _data.control 中返回通道值。
```

`MixingOutput::update()` 调用输出功能的 `update()`，再读取 `value()`，经过安全状态和输出限制后调用 `_interface.updateOutputs(...)`。本例把延迟放在这条命令消费与实际应用链上。[电机功能订阅](https://github.com/PX4/PX4-Autopilot/blob/4ae21a5e569d3d89c2f6366688cbacb3e93437c9/src/lib/mixer_module/functions/FunctionMotors.hpp#L62-L79) [输出更新](https://github.com/PX4/PX4-Autopilot/blob/4ae21a5e569d3d89c2f6366688cbacb3e93437c9/src/lib/mixer_module/mixer_module.cpp#L421-L446)

```text
正确的 observation 和历史状态
  → 正确生成 action.action[]
  → 正常发布 actuator_motors
  → 下游消费或应用延迟
  → 输出链继续保持旧命令
  → 电机实际输出落后于上游控制权切换
  → 姿态继续偏移
```

可把构造时序表示为：

| 事件 | 构造时刻 | 证明的内容 |
| --- | --- | --- |
| RAPTOR 成为实际模式 | t0 | 模式身份改变 |
| Direct Actuators 配置完成应用 | t0 附近 | 软件控制链切换 |
| RAPTOR 发布有效新电机命令 | t1 | 神经命令已到发布端 |
| 电机首次应用相应新命令 | t1 加 40 ms | 实际交付完成 |

这张表只固定下游延迟；t0 到 t1 的具体间隔需要测量。

### 6.4 发布者记录与实际应用证据

基线在实际调用电机消息发布后记录 `research_actuator`。其 `owner=1` 表示 RAPTOR，`owner=2` 表示经典控制分配器，`actuator_timestamp` 对应发布的 `actuator_motors.timestamp`。[消息定义](research/state/ResearchActuator.msg) [发布记录补丁](https://github.com/JacksonW1025/uav_handover/blob/ddeaddd2213fb8e79d6d008f2c26d7cd82cf52e2/patches/raptor-final.patch#L609-L619)

因此，`nav_state`、`raptor_status.active` 和 `research_actuator.owner` 分别提供模式、活动计算路径和发布者证据。实际应用还需要输出功能读取、驱动或仿真桥消费、物理步等证据。本基线现有的 owner 记录不足以单独证明四个电机已在同一物理步应用新命令。

若延迟使 RAPTOR 的 `previous_action[]` 随后偏离实际执行动作，这属于交付故障引起的下游状态偏离。归类仍从独立引入的交付延迟开始。

### 6.5 分类判定与区分性对照

本例的直接起因位于命令产生之后：正确命令没有在要求的时间内作用于执行器。对照只消除消费或应用延迟，保持策略、参考、历史准备和入口不变，比较实际应用时间及物理响应。

单看发布主题里存在消息，无法完成这个判定。必须关联消息身份、内容和下游应用。若故障来自多个发布来源争用，则记录每一条被实际采用的命令及其来源，再归入本类的来源交付问题。

## 7 四类单因原型的互斥判定

| 原型 | 连续参考和正确交接下神经接管具有足够安全裕度 | 历史状态接续正确 | setpoint 接续正确 | 实际交付正确 |
| --- | --- | --- | --- | --- |
| T1 | 否 | 是 | 是 | 是 |
| T2 | 是 | 否 | 是 | 是 |
| T3 | 是 | 是 | 否 | 是 |
| T4 | 是 | 是 | 是 | 否 |

表中第一列指正确参考、相容历史和及时应用下的接管能力。T2、T3、T4 发生后，飞机也可能失去安全裕度；这种后续结果不使它们自动变为 T1。

归因时，先记录错误开始的位置，再检查传播链及针对性对照。只观察到电机阶跃，无法区分历史错误、参考跳变和消息来源变化；只观察到失高，也无法完成 T1 的判定。涉及多个独立起因的记录分别标注各起因；缺少区分证据的记录保留待定。

单因原型的逻辑边界已在此明确。四类对所有实际案例的覆盖程度，仍需通过完整流程审查与案例核验建立。

## 8 代码证据与案例记录要求

### 8.1 每个案例的最小记录

每个案例记录平台与版本、前后控制来源、任务目标、触发事件和初始状态，随后串起以下证据：

| 环节 | 关键内容 | 对应用途 |
| --- | --- | --- |
| 物理入口及环境 | p、v、q、角速度、离地或边界余量、机体与执行器状态 | 判断入口条件和恢复裕度 |
| 参考 | 发生器目标、传输消息、接受时刻、有效标志、实际采用的目标 | 定位 T3 |
| 历史 | GRU、previous_action、动作历史及初始化规则 | 定位 T2 |
| 软件控制权 | 请求、nav_state、setpoint_config、控制标志、active | 对齐软件交接过程 |
| 实际命令 | 发布者、消息时间、命令内容、消费与应用时刻 | 定位 T4 |
| 物理后果 | 倾角、最低高度、跟踪偏差、恢复时间及任务结果 | 保留后果及严重程度 |

这些是取证要求，部分需要新增观测点。现有状态接口、owner 日志和消息时间戳各有范围；数据未覆盖的环节不能由相邻环节代替。

对照需说明初态匹配程度。基线的部分控制器状态读写接口没有覆盖完整估计器、执行器、仿真器和消息队列状态，因此通过接口恢复部分状态不能直接宣称完整同快照分叉。

### 8.2 流程覆盖与问题计数

按首次进入、持续运行中的参考回退与恢复、退出交回、再次进入及连续事件检查四类问题。触发环节作为标签，不因同一机制出现在多个环节就增加一级类别。

例如，首次进入缺参考与活动期间超时可能进入相同零速捕获逻辑，可在 T3 下记录两个触发环节。短间隔再次进入和累计失高需要追查各自的起因；间隔属于条件，失高属于后果。只有发现现有分类无法表达的独立机制，才重新讨论一级分类。

历史报告用于提供机制线索和已有观测，具体结果继续附各自的源码、补丁、模型与实验条件。该基线文档固定的是四类问题及其代码级解释，不把构造场景计为新增已确认缺陷，也不预设搜索方法、效率优势或修复保证。

# P14 运动地图补充：源码语义与接口

本页是独立补充，不修改原 P14 结论。基线 `eed2f84daca23f7a36fce8c4ab0ea8b1fba1512c`；全部计算离线。源码位置是本仓库及固定 Lab 副本，不是推测的通用 PX4 行为。

## 实现、近似和可恢复性

|环节|真实实现和定位|原 M14|本补充及仍缺内容|
|---|---|---|---|
|物理姿态/平移|`tools/p13/physical_model.py:source_step`；P13 逐物理步取证及 FreeJoint 离散更新|水平/角继承 M4 经验推力差/阻尼；源垂向|运动源核含转子相位惯量、旋翼轴投影阻力、spin、力矩与 COM/body 离散连接；未把实际未来姿态注入|
|物理与估计姿态|Gazebo ENU/FLU→NED/FRD；`mc_raptor.cpp:observe` 读 `vehicle_attitude`|从 LP 姿态开始经验物理传播，同时作观测姿态；`att=oldq`|物理 q 与估计 q 分开；初始左旋转 `qhat*qphys^-1`，后续观测近似 `align*qphys_old`。常量 align 没有代替真实融合校正|
|`att=oldq`|真实姿态 topic 异步更新、保持，sample/native 独立|仅一个 4ms 模型步延迟；不是读旧真实四元数|默认仍为声明的 4ms 近似，并有取消延迟对照；真实未来延迟集合未认证|
|gyro|`src/modules/sensors/vehicle_angular_velocity/VehicleAngularVelocity.cpp:887–954`；`LowPassFilter2p.hpp`|经验 plant 的 omega 直接入网（FRD→FLU 符号转换），没有源码 gyro 滤波过程|250Hz/40Hz DFII，两组 3D delay、前缀确定的输出偏差；原始传感器/校准/估计 bias 可离线核对。未来 bias、噪声、reset/device 切换仍不是已知|
|LP|`EKF/output_predictor/output_predictor.cpp:178–365`：IMU 传播、延迟 buffer、融合姿态校正、位置/速度误差积分、局部参考变动|只新增垂向互补近似；水平仍 M4；.25s 来自源参数，不是完整 EKF|三轴互补输出状态、独立 origin、前次 body v；这是最小条件替代，不是源码 OutputPredictor 全重建|
|LP 更新相位|`mc_raptor.cpp` gyro callback 内分别更新 LP/att 缓存；每条缓存有自己的 sample|`(sample-lp_phase)%8000==0` 的名义保持；不使用未来更新词|仍明确条件化该词；保存 LP 值、相位，姿态/gyro 单独保存；不能从预测贴近反推实际相位已知|
|导航轴与航向|`GZBridge.cpp:671–743 navSatCallback` 直接传 north/east/down GPS 速度；姿态由独立估计链产生|LP 与物理 q 混合的范围见原 STATE；不能从 q 差得到 LP 导航轴差|Nav=NED 恒等，估计姿态 align 独立；最初补充把约 5.3–5.8° 姿态航向差用于旋转 LP 的假说已否定并保留旧输出|
|native/sample|`mc_raptor.cpp` 读消息/严格超时/重复拒绝；`rl_tools/.../executor/operations_generic.h:93–200`|4ms sample/native、8ms LP、实际初始 index、每两调用提交|同样是前瞻可用的名义条件词，不是实际调度重放；F2 另有平台/追赶和多一调用消费的两个固定点情景|
|capture/resume|`research/state/TargetProfile.hpp` 及接入源码；捕获前消息先读，native age>200ms，capture 在重复 sample 拒绝前|P12 状态机：相关捕获，实际 mean→临时 GRU→native h 提交→previous 更新|同源 LP/yaw 复制生成元；resume 回到原绝对计划，保留物理、神经、执行、D。未强制 capture 或伪造时间|

Lab 前缀：`uav_lab/.local/checkouts/px4-raptor/`。统一坐标见原 `THOR_P14_STATE.md`。真实物理 q、估计 q、局部导航 origin、缓存读取时间各自有状态；LP 不等于 named origin。COM→body 杆臂 FRD z=.001869131m，named 为 .241869131m，速度含 ω×r 和独立关节残差。滤波设定值不改名真实 RPM。

## 最小可实现观测状态

现有日志能把 gyro 的 6 个 DFII 延迟量从过去 raw sensor 递推出来，配合 device/calibration 和 bias 选择；完整 EKF 并不是实现这个滤波器的必要条件。实际接入输出可先表示为独立 `qhat,pLP,vLP,gyro,bias,delay1,delay2`，加缓存年龄/发布阶段和更新门。观测创新/校正可以作为带来源的输入集合，而不必把整个 EKF 协方差直接塞入地图。

但若要让这个集合覆盖真实未来，必须取得或认证：OutputPredictor 的 `_delta_angle_corr`、`_vel_err_integ/_pos_err_integ`、输出/垂向 ring buffer 及索引、延迟融合的 q/v/p、bias、`_global_ref`、平均 dt 和 reset 状态。`estimator_states` 加输出 topic 不唯一确定这些内部变量；现有原始 IMU/GPS/baro/mag 允许给定融合输入的重建，不唯一识别完整 EKF 初态。任意小的姿态偏差盒不能代替这项覆盖义务。

## 地图边类型

机器实例：`data/p14-motion-20261027/delivery-v6-edge/map-edge.json`，数值/区域数组沿用v5，本机保存并入 hash 清单。v6补齐queue/last-send/sample/native/下一提交位，四个checkpoint与原live-loop的index/count/last-read/stale逐项相等，并作JSON往返核验。输入/输出均包含：

`owner, pCOM/vCOM/qphys/omega, qhat/LP/gyro/filter-delays/bias/origin, caches+ages,
h/previous/mean/count/index, filter/rotor-phase/pending-command,
reference/captured-reference, sample/native/read-age/phase, H0/L/D/W`。

局部姿态初态为 3D 误差；传播以共享四元数生成元和单位群不变量承载，中心随源角动力学运动。并非每步全量重建的 Lie-algebra 管束。在 checkpoint 输出关于运动中心的局部 log 外包：若相对四元数正图内，`log(deltaq)=2 vec(deltaq)+r`，`||r||<=2(asin(a)-a)`，a 是 vec 范数上界。新增 chart 余项单列；不将单位群误写为冻结姿态。

```mermaid
flowchart LR
 S[联合状态区域 + H0/D] --> A[停止交付 A]
 A --> G[真实读取/超时规则的条件模型]
 G --> C[同源 capture 复制]
 C --> H[保持: 运动物理+观测+NN+执行]
 H --> R[绝对计划接回]
 R --> V[恢复 + 全前缀 L/D/W]
 V --> N[B前同一联合区域]
 N --> B[第二事件算子]
 B --> T[继续有界 或 TOP+首个义务]
```

任意三、四或有限事件词沿同一类型迭代。`TOP` 不重置，历史 D 不撤销，不能以每条边重新独立采样初态来制造可组合性。D本轮用单调标量区间及`D>=当前L`关系约束，尚未保留整个过去max与所有状态的生成元相关性；其他内部状态保留共同列。这是保守投影而非历史清零，后续可将max写成共享ReLU算子进一步保留关系。时间守卫不确定时需要分支/区间；当前数值实例只有一个明确条件词，分支数=1。

## 可复用的真实控制权交接

本轮没有交接新实验，只核对源码。

* C→N：`tools/apply_research.py:193–224` 先原 executor reset，再应用 `MemoryInit.hpp`。RINI=4 保留 teacher-forced shadow h、previous 写 classic 已施加 action；不是保留所有历史。executor reset 重置时间/index/均值计数，激活 reference 按 TargetProfile 单独捕获。原模式0/1/6各自语义不变。
* N→C：`ActuatorGate.hpp` 在同一锁下读 commander allocation flag 仲裁两发布者；执行滤波、实际关节、机体状态不会因 owner 切换物理重置。`tools/apply_research.py:540–612` 的 NCO=1 只在首个 classic 位置循环、有效最近 neural actuator 年龄≤50ms、姿态可读时协调 velocity integrator；否则原路径。经典位置/速度/姿态/rate 的控制状态和 reference 更新需要新模式，不能由神经 h 代替。
* 可复用：连续物理/执行/观测管束、latest 队列选择、同源捕获、线性 copy/select/reset/affine-jump 算子、时钟门及全前缀 D。需新增：经典各层积分器/限幅及 inactive shadow teacher 的联合演化、owner/reference 的分支守卫、异步协调跳变。不能把纯断流的完整状态清单直接称已经覆盖交接。

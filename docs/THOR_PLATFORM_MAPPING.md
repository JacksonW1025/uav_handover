# RAPTOR ↔ PX4 ↔ Gazebo 映射与边界

依据本机固定提交源码、SDF 和本轮新 ULog。未更改策略权重、推力补偿或机体动力学参数。

## 观测与参考

PX4 位置/速度为 NED，机体姿态/角速度为 FRD。`mc_raptor.cpp::observe()` 对位置误差和速度误差进行 `(x,-y,-z)` 转换，并旋转到目标 yaw 参考系；位置误差截断 ±0.5 m，速度误差截断 ±1 m/s。四元数按 `(w,x,-y,-z)` 转换，计算相对目标姿态。角速度 `(p,-q,-r)` 为 FLU。网络实际输入 22 维：位置 3、旋转矩阵 9、速度 3、角速度 3、上一动作 4。冻结网络为 Dense 16 → GRU 16 → Dense 4。

状态接口的六个参考值直接来自 `_trajectory_setpoint`，采用 **NED**。原 `RaptorStatus.msg` 内部参考字段的 FLU 注释与实际赋值不一致，本轮不据该注释转换数据；使用状态操作事件和实际源码语义。`MC_RAPTOR_INTREF=0` 时原状态消息也不持续填充内部参考字段。Lissajous 全部发生器状态尚未纳入快照。

## 动作与电机

神经原始动作先由 `(a+1)/2` 映射为 PX4 电机归一化指令。现有 Crazyflie 编号重排保留为 `[a0,a2,a3,a1]`。这只说明编号约定，不证明策略训练机体是 Crazyflie 动力学。

| 策略动作索引（0 起） | PX4/Gazebo 电机索引 | Gazebo FLU 位置 x/y，m | 转向 |
|---|---|---|---|
| 0 | 0 | +0.174 / −0.174 | ccw |
| 2 | 1 | −0.174 / +0.174 | ccw |
| 3 | 2 | +0.174 / +0.174 | cw |
| 1 | 3 | −0.174 / −0.174 | cw |

`actuator_motors` 经 `gz_bridge` 的输出功能 101–104 到 `command/motor_speed`，由四个 `MulticopterMotorModel` 驱动。SDF `maxRotVelocity=1000 rad/s`、`motorConstant=8.54858e-6`，力与转速平方相关；PX4 仿真输出范围 150–1000，不能把归一化电机指令直接当作线性推力。

机体 base mass=2.0 kg，各旋翼 0.016076923 kg；base 惯量约 `(0.021667,0.021667,0.04) kg·m²`。经典 allocator 原参数力臂约 x=±0.13、y=±0.20/0.22 m，与 SDF 几何并非逐值相同；本轮保留原配置并通过悬停实测。完整训练质量、惯量、推力曲线和随机化范围没有可验证的训练配置，未假定相同。

## 时序及实际验证

Gazebo 物理步长 4 ms，IMU 250 Hz。原 RAPTOR 通过 `IMU_GYRO_RATEMAX/100` 的整数值设置 native 同步：250/100=2，因此 GRU 推进约 125 Hz；中间输出约 250 Hz，训练 native=100 Hz。训练/部署频率差异是已有实现行为，不能将本轮结果外推为时序完全一致。测量由 `research_timing` 给出墙钟推理耗时与 PX4 控制时间戳，原始数据保存在新 ULog。

`research_actuator` 在实际发布 `actuator_motors` 后记录发布者及同一执行器时间戳；神经悬停窗口验证 owner=1，经典窗口验证 owner=2，避免仅凭模式应答推断接管。自带策略样例校验与实际神经悬停分别验收，结果见 `data/final-*/metrics.json` 与 [验收矩阵](../data/environment-20261009/acceptance.json)。

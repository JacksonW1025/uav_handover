# P13 直接物理状态与时间接口

## 旧文件盘点

远端/本地基线73d467b一致，盘点时无飞行进程。P12c十条ULog没有vehicle_visual_odometry/vehicle_odometry记录。全data命名盘点仅有旧20261011的10个gz-imu和18个gz-pressure日志，没有P12原始pose/odometry日志；runner的可选原始采集也只订阅IMU和气压。旧motor每步sim_us/dt可恢复，P12b重型World记录另有物理步及积分前后time。旧groundtruth的poseInfoCallback丢弃物理header，写native回调时间，位置/欧拉角差分分母裁剪[.001,.1]秒；这些速度不能修名成为COM物理速度。

旧执行文件直接保存消费命令、filter前后、joint、scalar thrust和parent torque。旋翼链接WorldLinearVelocity、axis/wind/drag在施力源码中存在但未保存，不能无损补造。旧A/b/lambda/free/post/约束模式保留并优先复用，不因本轮接口重新大批采矩阵。

## 新采样位置

`research/gz/P13PhysicsTrace.hh`在现有motor插件中被动调用，只有HANDOVER_P13_PHYSICS_TRACE声明时启用。actuator0单独保存body；每个actuator保存自己的rotor。PreUpdate读取物理输入状态，ApplyMotorForce中的实际局部变量记录当前施力与本步filter写入结果，PostUpdate读取积分后状态。三者共用Gazebo iterations/simTime/dt，phase0/1明确标记。simTime是更新标签，其与World前后时间的对应要实测，不把PreUpdate标签直接称为积分前时刻。

直接记录：world ENU位置/速度，link FLU姿态，world角速度；五个链接的WorldInertialPose及偏置点WorldLinearVelocity、质量及加权COM；named model origin和base frame；每个rotor链接p/q/v/world omega、实际axis/wind、thrust/drag/parent torque、消费sample、joint及filter。母体COM是五链接惯心加权，旋翼轴上质心不因自转移位。原点至COM r=.241869131m，base至COM r=.001869131m；速度保留omega×r，不从callback差分生成。

`EnableVelocityChecks`只请求物理结果组件，不设置速度/力/约束。缺少组件的早期初始化行valid显式保留；任务期必须完整。物理真值、LP任务判据、运输后callback和controller缓存各有独立来源/时间。

## 缓冲与终态

body544字节/行×131072，rotor288字节/行×65536×4，总预分配约146.8MB（十进制）。非暂停250Hz时body每步两行，均约262秒容量。首次PreUpdate分配、创建64字节不完整文件头；此后回调不做新流磁盘写入。析构时写完整记录及count/drop/error/complete。完整头不足以单独验收：同时检查物理步连续、阶段唯一、字段valid及全部文件长度/hash。进程异常死亡只剩未完成头，按缺失处理，不补零。原有ULog/执行流未改为无IO，不能宣称整个平台零同步写入。

默认完整求解器矩阵观察关闭。新增body物理状态不等同连续域不变性证明；离散成员核查、条件关系、未来硬界和后验残差分别输出。

## 首轮实际验证与检测边界

开发12/12完成。独立核查Post→下一Pre的COM/base/origin位置、速度、姿态、角速度和各链接惯心状态全部逐字一致，步号+1，标签simTime增加下一步dt。故Pre的状态物理时刻是`sim_ns-dt_ns`，Post是`sim_ns`；rotor施力行以将要推进到的destination-step标签连接，不能把Pre标签直接当其状态时刻。积分按真实4ms dt，不按回调时间差。

首条理想刚性固定偏置检查2.9494081e-8m超过原1e-8m，原FAIL及阈值保留。v3完整几何式加入实际关节位移/速度残差（由记录的惯心状态独立重算），位置/速度核对约4.1e-15m/1.1e-15m/s。这是字段/代数一致性，不是动力学或未来关节残差界。未来理论不能把残差设零。

缓冲头errors计数覆盖最初及主体若干写入；运行版最后header重写和fclose返回值未检查，**errors=0不等于全部IO错误可检测**。独立完整读取同时检查文件精确长度、完整头、序列/阶段/valid、跨文件对应及SHA，证明当前文件可完整读回；不声明fsync或断电持久性保证。未为此离线可核查事项重飞或改当前观测二进制。原序列化错误的v1不完整分析输出和独立v2/v3分析结果均保留。

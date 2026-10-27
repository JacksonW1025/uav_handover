# P14 状态、测量点与时间规范

P14全程离线。以下区分源码关系、直接记录、条件近似和未知量。

## 点与坐标

Gazebo为世界ENU、链接FLU；控制接口为NED、FRD。使用
`S=[[0,1,0],[1,0,0],[0,0,-1]]`、`B=diag(1,-1,-1)`，`R_NED_FRD=S R_ENU_FLU B`。p/v乘S，世界角速度先乘S再由R转入FRD；四元数wxyz、角速度rad/s，距离m、时间s。高度H向上，NED点的H=−z、W=v_z；LP的−z仍是其局部高度，不自动成为绝对世界高度。

五链接COM由惯心质量加权，named-model origin、base/body、IMU是不同点。理想COM→body杆臂在FRD为`r_CB=(0,0,.00186913101803548)m`，COM→named为`.241869131m`。通式是

`p_B=p_C+R r_CB+δp_joint`，
`v_B=v_C+R(ω×r_CB)+δv_joint`。

δ由直接链接/COM记录独立核对，不补零，也不由这次小值给未来界。P14在78条task0之后窗口核对几何，旧启动早期2.95e−8m刚性FAIL的窗口不同，原FAIL保留。IMU杆臂由`EKF2_IMU_POS_*`决定，本78条均0；EKF输出发布body原点，不能因此把它等同Gazebo命名模型点。

LP另含导航局部原点、估计与融合校正；姿态还含航向估计/标定差。与物理姿态的SO(3)差不是同物理时刻的纯估计误差；最近过去物理Post、运输与cache年龄均保留。特别是水平/航向参考差不能用一个固定z偏置修复。M14只使用初始信息确定垂向局部原点，动态状态仍是近似；未宣称恢复完整EKF。

## 时间和更新

物理Pre(k)是`simTime−dt`状态，Post(k)是`simTime`状态，Post(k)=Pre(k+1)及全部p/v/q/ω独立核对；rotor施力采用将推进到的目的步编号。原callback真值戳是native回调戳，差分v不能改名直接物理速度。IMU保留原sample；LP/姿态cache各自保持，不用日志中较新状态替代控制器真实读取。

sample、native hrt、host单调时钟分别保留。native可跳进、平台、追赶；严格超时`native−last_valid_read>200ms`，消息先读，capture先于重复sample拒绝。初始化门使用同调用pre-read initialized/force-sync/index，不能由last-GRU或事后提交推断。旧第27项缺这些字段，仍只能给有限推断。

accepted调用先更新mean/count，再计算临时GRU；native才提交h，每个输出更新previous。capture复制同源缓存p/v/yaw，h/history/filter不清零；resume返回原绝对任务。latest发布/桥接选择/物理消费不同；力使用本步当前joint，之后filter更新并写joint command，solver随后推进。没有“每个action必执行”的假设。

## M14的完整因果近似

M14保留M5源垂向推力/轴投影阻力和M4经验水平/角动态。正确body点进入垂向反馈。用`ρ=exp(−dt/.25)`，预测body速度b、前次body速度b_old、观测器速度v，有

`v_next=b+ρ(v−b_old)`，
`z_next=b_z+origin+ρ[z+dt(v+v_next)/2−b_z−origin]`。

它保留独立的局部origin、速度误差和位置误差动态，未将所有时变误差塞进同一常量；但这不是PX4 OutputPredictor的完整实现。实际源码有延迟输出缓冲、融合位置/速度误差积分和姿态校正，未来融合状态并非物理body真值。`.25`取全部记录相同的源参数，无新拟合；把它用于简化互补式是明确的建模近似。水平/姿态/gyro/cache仍沿用M4闭合，相关性和模型不足不隐去。

自主计算采用事前声明的名义4ms sample/native、8ms LP相位和初始真实index；不读取未来native/消息/cache词，因此也不声称覆盖所有合法时序。完整时序集合传播、EKF状态及实际SERVO数值/模式预算仍是独立义务。

# P14R：运动闭环地图接口

基线 `69ca54ff3029df671de740cf0a4ab4495b03b44a`。本轮独立目录 `tools/p14r/`、`config/p14r/`、`data/p14r-20261027/`；旧冻结、失败、模型成绩与未启动清单不回写。

## 状态与来源

|状态|实现/时间|必须区分|
|---|---|---|
|COM p/v、机体q/w、旋翼相位|P13直接Pre/Post物理步；ENU/FLU转换NED/FRD|COM/body/named origin不相同；body杆臂及实际关节残差保留|
|OP q/v/p、global_ref、环缓冲、积分与校正|真实OutputPredictor传播/融合前后；独立native/sample/host|OP p相对global_ref；LP是MapProjection局部原点，不能用姿态yaw差旋转导航速度|
|融合目标q/v/globalposition、gyro/accel bias|correctOutputStates实际输入|已知输入诊断可读未来；自主只持有过去初始残差模板，尚非完整EKF|
|LP/姿态缓存及样本年龄|实际控制读取时刻；source OP生产者可先/后于读取|物理姿态、估计姿态、缓存姿态独立；d06初始OP落后8ms，其余有效记录4ms|
|gyro|原始物理角速、积分输入、DFII延迟及bias分别记录|40Hz/250Hz源滤波，非原始w直接喂控制器|
|h、previous、mean/count、临时h|源GRU提交/普通输出顺序|普通调用产生动作；只有提交更新live h，临时h输出关系不能在非提交时套到live h|
|filter、pending、consumed|源切换滤波及每物理步消费|最近已消费命令不能代替最新已生成NN命令；条件模型下一步消费后者|
|publisher/transport/readslot、clock/guard|保留last emit、gap退出、next poll、最新消息槽、native/sample、index/force_sync|允许读取前消息不能清空；capture在重复sample拒绝之前|
|H0/L/D/W|COM与LP各自task0基准；D_next=max(D,L_next)|D及失败历史不在capture/resume/拼接时清零；W为直接物理速度，非回调差分|
|经典控制状态|velocity/rate积分、姿态参考模型、yaw torque滤波、allocator/缓存|NCO0下velocity积分在禁用MPC回调归零；rate及姿态参考状态不能在N→C任意冷重置|

## 记录平台

`P14RBuffer.hpp` 使用既有格式验证的有界mmap；core744、fusion5096字节。实际v2使用进程寿命映射，避免退出时静态对象先析构、后台线程仍写的风险。`complete=0` 是其明确契约，必须另核进程已退出、文件长度、committed count/sequence、丢样/错误及整个活动窗覆盖。它不宣称断电事务持久性。

容量core524288/fusion262144/gyro131072；宿主300秒、1000/500/250记录每秒验收针对新增OP记录。既有P13物理缓冲在本次约100秒任务全覆盖，不能据此宣称整个所有接口300秒均获验证。实际二进制/插件/权重普通副本在 `runtime-v1/`、`runtime-v2/`，原二进制在 `pre-change-runtime/`；CLI链接不作为快照。观测不参与控制计算；被动源码块剥离后控制token相同，但不宣称相对无观测控制器动态零扰动。

## 因果预测、诊断与时序条件

`model.forecast` 只读初态与事前计划。实际OutputPredictor源C++经独立ABI接入；合成IMU采用源码形状的梯形积分/圆锥项。未来融合目标由延迟的自身物理轨迹加初始融合误差模板产生，这部分为近似，不是EKF源闭合。世界坐标、LP原点与姿态heading偏差独立。

8个持久代表词为poll相位0/2ms × 联合运输0/4ms × producer PRE/POST。联合运输同时影响目标和观测交付，不能单独归因缓存。代表词不是全部合法时序；producer阶段可变、native平台/追赶、host服务时间超过条件界必须进入不同分支/UNKNOWN。`clock_reach` 的10ms服务、4ms运输、8ms读取等待是显式条件，spin_once的timeout不是调度硬保证。历史112个闭合事件落入条件括号只是回顾性覆盖。

已知未来IMU、融合目标、物理状态、实际读取/缓存词仅在 `source-replay-*`、`A-input-contrasts-*`、`closed-diagnostics-*` 使用。它们不能进入自主成绩，也不能给出可相加归因百分比。

## 联合集合与后继

旧66条前缀的8方向外包具有显式成员见证，保留旋翼相位、最新生成/已消费命令及离散类别；内部环缓冲旧日志不可恢复，不补造。实际传播限预登记每族12个支撑，共24点。点集不是连续域或全部未来可达集合。

新增d02/d03有真实完整OP初态。连续曲线保留物理、估计、历史、执行与OP缓冲的同源生成关系；其内部点未证明可达。两条记录publisher年龄分别15.577/10.386ms，目标读取年龄虽均8ms，不能抹掉这个时序差。最终采用两个本源时序fiber的保守并集，各四段；只有并集包含两条完整实测端点，单fiber不能冒称完整联合初态覆盖。

`D`、`DLP`及各自H0作为联合状态，经max传播；v5及更早联合曲线只用一条D0的结果保留但不再支持两条完整初态的高度声明。严格守卫/提交/消费关系仍分离，不能压成恒定4ms系统的一般定理。

后继NPZ保留同一中心/全部生成列，JSON保留模式、时钟、计数、publisher/待消费槽、OP ring、传感器积分状态和D。点地图4事件分段恢复与不中断结果一致。无压缩集合从真实resume checkpoint恢复8调用，动作宽逐位一致；旧列来源标签丢失只影响后续分项归因，数值G和共同来源未重新独立化。

## 源关系约束与储能

压缩后可与源图关系相交：`action=clip(W2*h_temp+b)`，`pending=speed(action)`，提交时`h=h_temp`；非提交时不能将action接到live h。恢复这些关系不是缩小真实初态；它去除外包制造的伪独立辅助状态。旧pending、h/action约束丢失与捕获独立取整尝试均留档。

源T0捕获复制缓存同源值；理想实数copy对照与未认证的binary32/cache缺陷分开。删除旧互补模型专用align/origin/bpold/bias只在源OP的N模式成立；gyro/bias、OP历史、临时h、物理/动作历史、D及队列不能因经验相关而删去。

16调用的源解析一阶链得到时变因子 `P_k=C_k^T C_k+A_k^T P_(k+1) A_k`，保留p/h交叉项。非线性残差r需要另满足相应界：

`V_next <= (1+alpha)(V_k-||C_k e||²)+(1+1/alpha)||L_next r||²`。

必须逐前缀检查绝对倾角/高度余量；线性恒等式不等于完整事件恢复证明。IEEE/libm/降阶数值、真实未来EKF创新、SERVO/模式和采样间预算仍是独立义务。A4仍为NOT_PROVEN_EXCLUDED。

## 交接覆盖

实际C→N RINI4：仲裁切换，重置执行器时序/mean，再复制shadow h与classic previous，初始化读取例外，首个动作与连续filter共同进入同一地图。随后N段断流—捕获—接回真实记录已审计。

N→C同接口跳变与真实Position/Attitude/Rate控制核已离线实现检查。缺失姿态参考模型初态/消费字、yaw torque滤波和分配器边界时，输出 `TOP_FOR_ACTIVE_CLASSIC_FLOW`，不能发明reset或保持机体不动来跨过C段。当前不是完整运动N→C→N闭环证书。

## 最终限定与条件后继

初始信息使用“observe缓存＋同次调用post神经历史＋截至Run开始的生产者历史”表示。`initial-stage-v1`独立核对五条调用结束均早于首次预测调用；这是合法的过去信息集合，但不是同一瞬间完整OP/EKF快照，初始调用内生产者推进仍由名义模型处理。d02/d03曲线端点覆盖只对应此声明的分阶段状态。

最终双时序fiber×四分段见 `C-joint-v6`。无压缩单quarter从resume检查点续算至197调用失域；141调用已经失精度，B/0.5s/2s恢复未达。恢复仅实现并验证单联合根、无压缩、固定因果时序词；不支持的通用多根/任意时钟恢复直接拒绝。已保存G不重新独立化；旧列来源标签不可恢复只用于归因限制。恢复8调用逐位一致不推出其后的认证。

源码参数导出的条件COM高度后继是：

`L_j <= L0+j dt W0+A_down dt² j(j+1)/2+j eta`，
`D_j <= max(D0,max_(i<=j)L_upper_i)`。

`height_constraint.py`将推力方向、阻力、惯量/旋翼角动量、杆臂和离散几何误差显式接入；例子的A_down约15.38m/s²。需要工作域保持、无接触/额外力、理想执行及数值缺陷预算，不能据此发LP/倾角/整任务证书。第140调用区域的条件高度时域276ms不是实际必要损高或神经闭环可达性结论。

经典首输出协调另提供非空条件 `I_req=raw_target-Kp(rate_ref-omega)+Kd omega_dot-Kff rate_ref` 且 `|I_req|<=I_limit`。目标独立给定，真实源码核验证误差9.3e-10；yaw滤波、分配器、首个物理消费与完整参考模型状态仍须连接。

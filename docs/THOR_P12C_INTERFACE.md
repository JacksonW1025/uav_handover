# P12c 最小观测接口与非干扰范围

本接口对应本轮10次准备的实际平台`minimal-direct-only-1`。正式0次，整体工程NOT_RELEASED。原P12b两个ULog发布的失败、旧源码/实际二进制和45个未启动身份保持不变。

## 版本与三层记录

修改只涉及声明的被动观测和离线工具：`tools/apply_p12b.py`按精确旧字节迁移至一次direct写入、零`research_p12b` ULog发布，并移除冗余publisher成员。反向置回观测差异后，与归档的旧实际cpp/hpp逐字相同。没有改读取门、超时、capture、history、GRU、filter/执行或保护逻辑。源码一致不等于时序或闭环轨迹一致。

基础P11/P12、目标、执行、LP/truth和保护日志始终存在；新增轻量开关`MC_RAPTOR_P12B`仅切换pre-read原生文件。重型求解观察库独立关闭，10次没有加载或产生完整矩阵/冲量文件。正式草案选用经过准备的light-on/heavy-off配置，但没有通过动态放行，因而没有冻结。这里没有无观测原始控制器对照，不声称整个canonical系统零扰动。

每种量只有一个分析canonical来源：

| 状态 | 来源/阶段 |
|---|---|
| executor initialized、force-sync flag/value、index、gate、实际updated/finite-valid、last-valid-read、activation/sample修复门 | light-on单个`read-p12b.bin`，同一次调用pre-read快照与读取后结果；off明确UNOBSERVED |
| p/v、R/omega、观测缓存/年龄、hidden/previous/action、实际目标 | P11 ULog；before/after标签与真实源码顺序一致 |
| mean/count、输出调用/GRU提交、sample/native/host区间 | P12 ULog；不压成恒定4ms控制映射 |
| capture/resume | research_target与实际fresh valid read见证；主机发送计划不能替代达成 |
| filter-before/after、实际joint、有符号推力/力矩、已消费命令 | 原motor execution-p12物理步文件；消费、force-before-filter、filter和end阶段分别保留 |
| 最新桥命令/排队 | research_output与motor消费标识；不能把最新发布等同已执行，完整transport/进行中快照仍不全可得 |
| LP/姿态与原保护 | 原ULog及runner事件，原主判据/任务判据不变 |
| 世界H/姿态 | Gazebo Pose_V的groundtruth ULog，**回调native hrt标记，非保留的物理pose header时间** |

原生流magic/version/sequence/失败计数覆盖所有写入，包括inactive shadow和后续SampleClock拒绝调用；active行必须同sample且pre-read wall落在对应调用区间内，不能用last-GRU或后状态猜ready。五条on均通过，`research_p12b` ULog均为零。五条off仅验共同基础状态，新增初始化字段不补造，旧通用完整native验证的适用限制与输出保留；不把off当作完整pre-read初始化证明。

## 三门验收及停止

首飞前封存516项，三类任务×两个预定seed块×off/on原定12次；同PX4/插件/权重，轻量开关为唯一观测处理。原协议和尺度在`preparation/noninterference-spec.json`，不按结果修改。

- 硬语义：10次已完成记录的适用字段、连续神经/history/target/filter重放、名义sample4ms完整性、原8ms消费年龄和2500μs cycle p99、版本/保护检查通过。不是对完全未观测物理状态的证明。
- 动态：全部互相有效task0至结束前缀，没有峰值/capture对齐或择短窗。SAFE_EVENT块1倾角差6.469902°超过5°；BOUNDARY块1的世界损高差.244987m、LP损高差.223158m、向下速度差.515613m/s超过.2尺度，故未建立事前等价。任务标签相同不替代时程验收。
- 充分性：SAFE_EVENT块2预事件SO3按封存计算1.001894°略超1°；没有舍入为1或事后放宽。cache和连续差异原样保留，没有拟合校正。边界块2未启动，完整矩阵未完成；既不能从不显著认等价，也不能把原始差异直接认作观测因果影响。

原验收工具只比较双方都有的capture/resume，可能空集合误过。保持原sealed工具/规范，独立v2/v3复核要求完整覆盖事件同时有capture及实际fresh-valid resume；截断/NOT_REACHED不能冒充缺失或达成。已完成的6条事件飞行共12个事件均有两类见证，时序差也在原.024s尺度内，没有新增或替代启动。原full12验收工具没有被用来生成虚假完整PASS。

发现不可逆的动态门失败时，第10项已经启动，因此让它正常完成；在既有attempts.lock上于案例间取得锁，下一项在登记START前被拒绝。服务退出中的BlockingIOError是这个受控停队列，不是新SITL或观测协议失败。最终10 START/10 FINISH、零STOP_CRITICAL，剩余2准备/24正式未启动。

10次运行期间516项无漂移。全部进程结束后仅增加防误续跑的driver guard；实际使用的旧driver、原seal、新旧SHA与补丁单独保存在`preparation/post-stop-driver-guard/`。当前driver因此不能自动继续旧队列；这个未执行的止启工具改动不是新观测/运行版本，二进制和原结果未变。

## 高度与速度不能混称真值

`GZBridge::imuCallback`用IMU消息物理header时间；`poseInfoCallback`却用回调时`hrt_absolute_time()`，并以两次回调时间差裁剪到[.001,.1]s后差分p/v。原始pose物理header没有写入groundtruth。因而groundtruth的vz是**回调差分速度**，不是直接物理twist；其年龄也是回调戳年龄，不等于已认证物理测量延迟。

事件表附`event-COM-geometry-and-W-provenance.json`，保留前后回调native区间、差分分母、H/R各自年龄、控制读区间及UNKNOWN物理测量时刻。不能由这些值构造零误差物理W初态。

源码merge后的named model origin至COM距离r=.241869131m。以世界向上e_z、相容姿态/角速度约定：

`H_model = H_COM − e_z R r`；`W_model = W_COM + e_z R(omega × r)`。

不只保留高度偏置，也保留速度项。用controller R/gyro与callback差分W组合的COM速度仅是异步混合估计；不称直接真值或认证区间。旋转几何和累计D均不在capture/resume重置。LP原任务判据、world诊断及COM物理推导分别标注。

## 运行快照与旧数据

实际PX4 SHA：`b6ea5a948b2ab0ed35f715ffa42fc9b09ec5dac33106691d7c573e02c98778d9`。

policy.tar SHA仍为`5327c83dc57f094ca1977a2533ebce318645be010e16b9354c96c337cd5c278b`。10个PX4/插件/权重/构建普通副本在`data/p12c-20261026-runtime-local/`，清单`preparation/runtime-snapshot.json`。旧P12b实际副本不变，旧CLI symlink不是历史二进制。DART/GZ实际库与Ubuntu headers来源身份分开，未声称发行二进制已从阅读源码重建认证。

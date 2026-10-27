# P15 信息、公平与后继接口 v1

## 研究对象与输入

沿用 P14H 普通 PX4/插件/权重文件，未增加物理或EKF hook。实际动力学/保护不改。仅 runner 在合法发送窗口之前选择未来 B，并保持同一6秒巡航参考；所有分支共同绝对任务坐标。每次启动的源码身份前后核验。新的控制语义是事前冻结的自适应事件计划，事件仍走真实停流、严格200ms守卫、捕获/接回和latest-value消费。

在线输入为一次 `listener research_p11` 返回的**完成行**，同 timestamp/sample 的 direct pre-read identity，以及已落盘执行记录。P11 浮点输出5位小数；后验逐字段核验与ULog误差<=5.2e-6。mean/count来自真实policy input和commit，不清零history。输入在查询返回时才可用，LP/att copy仍只知道发生于run/read区间。执行日志每25步刷新，约100ms年龄须保留；待消费运输身份 UNKNOWN。不同量各自时间不被压成同一瞬时物理状态。

P13 COM/速度/角速/模型原点是有界内存缓冲，退出后落盘，**本轮在线排序不可读取**。这些字段用于后继误差和独立核验。LP导航速度不按估计yaw差旋转。fullP保留于原始记录，未声明恢复完整EKF。

## L15 轻量闭环及后继

A保留P14H源物理+OP队列模型作为有成本的离线参照；B=L15以真实LP/姿态/gyro/h/previous/mean/count及有年龄的filter初始化，复用P11 M2经验输出动力学，4ms运动姿态、8ms LP更新、1步姿态缓存、真实NN/history更新和源码目标守卫。LP动力学是输出近似，不等同真实COM。未来融合/运输采用声明名义规则，分支越界/模型偏差均需实际核验。没有新拟合完整EKF。

评分是后继轨迹的全前缀倾角/损高归一化最大值；它与后继状态分开保存。有限rollout到B接回后1秒用于排序，不宣称完整任务预测或安全。后继保存h/previous/mean/count、reference、filter/命令槽、clock/read状态、D和失败锁存；未观测运输pending仍UNKNOWN。后验直接物理后继保存在独立事件表。

在线工作进程与ROS目标发送分离。任何计算超过预定deadline导致的协议未完成单独保留；不能延迟B或把模型失败当物理失败。每次决策保存完整候选/评分/输入及其available_by、运行耗时、选中原因。真实consume/action/任务结果在另一路评分。

## 两条可检查关系

1. 源guard cell：call index mod2、允许读取侧、当前last-valid-read和严格native timeout共同定义cell。cell内响应差分只在未改变producer/read/commit/consume词时使用；跨cell须比较两侧，不用连续导数越过轮询边界。L15复用源码copy/commit映射，不声明未来真实词唯一。
2. 对给定有向垂向加速度预算，`W_next=W+a*dt`、`L_next=L+W*dt+0.5*a*dt²`，`D_next=max(D,max_prefix L)`。若保证向上制动至少b且持续至W<=0，则充分下降储备为`W_+²/(2b)`；示例条件不能称真实必要损高。事件前后保存D与已失败锁存。恢复误差用于限制复用区间及选择，不让单次归一化范数代替真实安全指标。

局部更新将由开发冻结：只修正可定位的恢复加速度/消费阶段关系，保留前后版本、适用时间和成本，不以任意任务标签偏置吸收全部误差。正式不按结果改规则。

## 评分与样本

原P11 task规范保持：共同计划首事件时刻至post_stream结束，LP损高>1m或倾角>45°。原flight frozen结果并列。失败见证可在截断前成立；无失败但未完整覆盖为UNKNOWN。controller-read前缀和直接COM为另列诊断，不能替换原LP/姿态判据。未到达B不能记组合成功。独立block、共享对照、模型和窗口分别计数。

M0全局均匀，M1分前缀均匀，M2分前缀无方向廉价基线，M3分前缀方向闭环；各方法同级可用输入、相同启动额度，额外建模/在线/前缀费用单列。物理同seed不等于同状态，不做免费物理快照复用主张。

## 最终接口资格与分析版本

启动42=开发6/搜索32/地图4，全部唯一终态。冻结控制/模型/配置仍为b303；分析修正版独立放在data路径，未改变运行模型。`tools/p15/report.py`是冻结原汇总，只有物理成本且把非PASS的有效前缀遗漏，保留原版本。最终读`delivery-v4/machine.json`的资格与结论、`delivery-v2/method-total-costs.json`及最终成本补充；不要把旧汇总当全费用结果。

资格类型分开：完整平台；`PASS_SCORED_TASK_PREFIX_AUX_TAIL_UNKNOWN`（OP尾部未知）；`PARTIAL_CONTROLLER_TASK_PHYSICS_MISSING`（NN/LP任务可用、COM/物理不可用）。后一项没有恢复物理数据，也没有取消其原START/错误。所有组按实际资格使用，未把未执行候选赋标签。

`evaluation/*/event-states.json`分别给COM/model-origin、直接物理W和LP/cache、h/action/history、执行、native/sample/commit/read。LP判据的H0、控制器缓存比较H0及物理COM H0分开，不能直接拼减。首次Bpre原字段为首次模型call>=B；`extra-metrics`和`delivery-v4`另用双方严格<B的行，保留各自时刻、不事后对齐。v3曾把独立ULog任务H0与控制器模型H0混用比较，原结果保留，地图误差仅使用v4。

地图输出同时含：名义时间轨迹、全部前缀L/D/W/倾角、完整声明模型后继、守卫/时钟原点、适用条件、误差未知项、真实锚点及费用。当前后继是条件点；未闭合真实联合域不能用任意小盒冒充。运行时标量局部更新没有改变4次选择，不能声称认证边界扩展。新seed采用已经FINISH且payload hash核对的前条更新，未来本条数据只评分。

模型拼接必须保存原始profile/sample算术原点，不能仅保留数值相等的局部t。`model-clock-reuse-v2`将该项加入离线模型实现，保留完整h/mean/previous/count、LP/姿态缓存、plant、reference、pending、filter、D与失败；不改变冻结独立选择与预测成绩。真实未观测pending和未来时序条件仍UNKNOWN。模式C→N→C的真实控制接口沿用历史源码，但本轮地图不新增经典闭环交接效果主张。

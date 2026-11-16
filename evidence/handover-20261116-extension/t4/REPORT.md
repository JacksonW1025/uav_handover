# T4 新配对：按新 active 通知释放，缩短实际交付等待

## 直接结果

两次全流程 x500 SITL 悬停均正常起飞、经典→RAPTOR、回到经典并落地。两臂设置相同的60 ms relay暂存预算，仅第二臂允许收到新鲜的RAPTOR active通知后提前释放。四电机首次实际应用神经命令的等待由24 ms降为4 ms；首条神经命令由四路均未应用，变为四路均实际应用。

|测量|按60 ms截止释放|新active通知提前释放|
|---|---:|---:|
|首次N发布（原生s）|51.328|51.348|
|首次四路N应用（原生s）|51.352|51.352|
|发布→首次实际应用|24 ms|4 ms|
|relay实际暂存跨度（clock快照）|60 ms|32 ms|
|release快照相对首次N发布|+20 ms|−12 ms|
|首次N应用前已发布的N样本数|6|1|
|其中留在relay后被新样本替代|4|0|
|已转发但四电机都没采用|1|0|
|首次N sample四路是否实际采用|否|是|
|subject窗口最大倾角|1.291°|1.726°|
|subject窗口失高|0.04093 m|0.04150 m|
|落地、disarm、PX4/relay/Gazebo退出|全部确认|全部确认|

这里改善的是交付等待与首样本接续，飞机一直处于正常悬停。初态在请求时相差位置0.04774 m、速度0.01398 m/s、姿态0.1932°。策略、机型、RINI0/RTGT0、连续50Hz参考、60 ms预算及所有保护相同，两次candidate-before/after均未变化。不是靠增大倾角取得正结果。

## 发生的全过程

1. runner对relay预先请求一次60 ms暂存窗口，然后按原方式发模式命令并等待ACK/nav；宿主最大暂存仍为100 ms。
2. 截止臂在51.288 s开始暂存。神经于51.328 s发布第一个样本，但四电机直到51.348 s这个物理步都还在用经典sample51.288 s。
3. 新神经样本51.328、51.332、51.336、51.340在relay的latest slot先后被替代，未转发。
4. 51.348 s时释放sample51.344；随后sample51.348立即正常转发。51.352 s物理步四路均received=2，采用更新的51.348，前一条虽已转发也未成为电机输入。
5. 提前释放臂在51.304 s开始暂存。runner收到新鲜active后写release文件，relay在clock快照51.336 s解除暂存，此时释放的仍是经典样本。第一条N在51.348 s才发布，此时路径已经恢复透传，四路在51.352 s正常应用它。

这个结果把T4细分成两种丢弃位置：中间relay覆盖、实际电机latest slot覆盖。模式已激活与首条神经输出已经真正到达电机之间，存在可以由交付规则改变的时间段。提前释放由已有active状态驱动，不猜电机幅值，也不把DDS通知当原生首N时刻。

## 时钟口径

事件排序分别使用原生PX4/Gazebo模拟时间及宿主monotonic，绝不把DDS UTC时间和native相减。上表release原生值是relay订阅的clock快照。host同域测量：截止臂从active通知被runner接收到实际release记录为31.681483 ms；提前臂为0.218630 ms。relay完整日志中记录source/held/forward/release_latest与monotonic时刻，样本详情在sample-accounting.json。

## 代码与复核入口

- runner.py:17–26：保留super.receive后，用fresh_active检查新active、exit_reason0和比请求前更新的timestamp；一旦满足，第二臂写.release，第一臂只记录观测。
- runner.py的switch：仅在正常模式请求前准备检查，原mode/ACK/nav等待、连续发布和安全检查不变。
- relay.cpp:19：同一mutex里先检查.release，再检查原sim/host期限；释放已有latest后永久透传。callback与latest槽语义未变。
- 精确差异：runner-change.patch、relay-change.patch。二者是隔离/tmp副本，无共享Lab源码修改。
- audit.py从原始flight.ulg和四路bin重建research_actuator的owner/control→actuator_motors sample→research_output桥值→电机实际input。窗口每条可匹配值误差0，两个ULog均0 dropout，八个bin尾部完整。
- sample_accounting.py进一步从原始relay.csv及native日志区分“未转发”和“转发未采用”，而非把所有未应用样本一概算成网络丢包。
- plot.py产生delivery-comparison.pdf/png。匹配初态保存在matching.json。
- 原始证据：/home/car/uav_handover/data/handover-t4-active-release-20261116/。大日志留Thor。

## 执行成本与范围

两次启动、两次完成，无失败、无重试。wall总146.131045 s，CPU总69.579528 s。完整attempts.jsonl、两个result和validation保存；图和分析在Thor产生。原45°倾角、8 rad/s角速度、10 m水平半径、8 m高度上限以及正常landing流程均沿用。没有关闭或更改安全机制。本文的新配对为主动受控交付扰动/恢复实验；旧发布者回跳与其门控修复仍是另一个历史实例。

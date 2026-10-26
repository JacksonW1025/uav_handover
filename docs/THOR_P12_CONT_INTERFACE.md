# P12续轮状态、时钟与初始化模式

本规范对应正式冻结68dfb73b。原P12状态机和双时钟字段保留；这里补充准备续轮及停批暴露的范围边界，不修改该冻结的代码或有效性。

扩展状态除机体/观测缓存/目标/GRU/previous/mean/count、执行filter/joint与命令队列外，还必须区分executor的`last_control_timestamp_original_set`、两个control timestamp、`force_sync_native`和`intermediate_step`。它们是调度初始化状态，不能由“GRU已存在历史”或“本调用最终提交了GRU”替代。N2可保留inactive shadow的h及last-GRU时间，同时在首次active输出重新初始化executor时序。

| 模式 | 实际源码关系 | 本轮接口/模型范围 |
|---|---|---|
| inactive/未初始化/force-sync未就绪 | P12交付门保留原读取路径，允许消费任意当前消息 | first-call pre-read readiness未直接记录；源码可审计，冻结全active相位审计遗漏豁免 |
| 已初始化普通输出 | 实际index决定是否允许uORB update；每个接受sample更新mean及previous，intermediate不提交h | P12 before/after/history/count/actual_commit直接核验 |
| GRU提交输出 | 临时h提交，count置0；不同于每个4ms输出 | 稳态force-sync2约125Hz提交，250Hz输出；训练100Hz差异未改 |
| fresh/hold | 实际finite消息读取刷新native last-read；保持LP/att缓存及其样本年龄 | 不用主机发送意图代替实际读取 |
| stale/capture | 先真实读取，再严格native age>200ms；target复制同源p/v/q | target跳变在SampleClock重复拒绝之前，memory不随capture重置 |
| 实验修复门 | 所有臂先设MS0抑制，随后由实际提交sample+原首事件绝对计划设正门限；到门限后才允许mode2 | MS门只选择参考，不伪造时间、不强制capture；所有已达到的正式修复捕获另核查确为mode2 |
| resume/恢复 | 返回原绝对任务目标；h、history、执行状态继续，世界高度不重置 | 完整poststream5秒与恢复2秒dwell保留；恢复time是持续满足区间的起点，不是单点已达成 |
| 选择/消费/动力学 | latest-value层可覆盖命令；physics读取joint算力，再更新filter并写joint command，随后solver执行 | 直接filter与JointVelocity分开；不能声称每个action都执行 |

```mermaid
sequenceDiagram
 participant R as runner/common epoch
 participant C as native Run/read gate
 participant E as executor timing/history
 participant G as physics/solver
 R->>C: same all-arm MS0 before arming
 C->>E: activation may retain shadow h but reset timing readiness
 C->>C: uninitialized: original actual read permitted
 E->>E: first output initializes timing and may commit h
 Note over C,E: post-call actual_commit cannot define pre-read eligibility
 R->>C: confirmed actual commit epoch; set same planned sample gate
 C->>C: initialized gate1 or2; finite read; strict native timeout
 C->>E: correlated capture, MS selects T0 or RTGT2, then mean/network
 E->>G: published latest action
 G->>G: consume/current joint forces/filter/joint cmd/solver
 Note over C,G: sample/native/host brackets retained; overlap means unknown order
```

第27项的唯一相位审计例外在active第0行：index0→1、gate_permit=1、actual_commit=1、有效读取，last-GRU仍为inactive阶段48340000us。任务期1198次有效读取全部intermediate。源码明确允许未初始化/force-sync未就绪路径，但冻结audit对所有active读取要求PH2不提交，因此FAIL。没有据诊断删除首行、改门或回写有效性；第28–48项停为未启动。下一工程版本必须显式记录pre-read initialized/force-sync模式，并在冻结前验证fresh-message-at-activation路径，而不是根据事后提交标志猜测。

`truth_pv`是GZBridge已转换的NED字段，世界高度H=−z；位置直接来自世界pose。其v/a由native回调时间差分生成，angular groundtruth也是Euler差分，不等同直接物理twist。独立分析v2修正未执行汇总器的符号/混合单位错误；原观测、冻结LP任务判据、scorev2及原FAIL均未改。

M4初值来自任务前记录及最后完成的执行状态，异步年龄保留。pending-command使用最后消费值近似，另审计桥接已发布命令；完整运输/slot状态没有精确快照。M4预测从暖机后已初始化域开始，采用名义调度；合法native平台可被状态机与已知输入重放容纳，但真实未来host/native/消息消费词没有已证明覆盖。P11第70条旧无效性、停批和两pending保持原样。

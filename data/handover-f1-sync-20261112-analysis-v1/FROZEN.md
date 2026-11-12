# F1 固定版本：参考接续时序

2026-11-13（UTC+08:00）固定本轮结果。本次仅归档、复核与发布，新增飞行 **0**。后续分析从本版本继续；不要覆盖这里的轨迹、配置与结果，变化应另建目录。

## 从哪里看

1. [完整报告](REPORT.zh.md)：六次 E1/E2/E3 的飞行过程、初态、目标、电机与姿态响应。
2. [发现经过与代码链](CODE_AND_DISCOVERY.md)：区分早期发现和本次对照。
3. [全部测量摘要](f1-summary.json)、[逐步目标/输入/动作与初态](f1-comparison.json)、[参数核查](parameter-audit.json)。
4. [启动账本](../handover-f1-sync-20261112/attempts.jsonl)、[配置计划](../handover-f1-sync-20261112/round-01-plan.json)、[成本与收尾](execution-summary.json)。
5. 四张图：[目标/动作/姿态](f1-target-action-attitude.png)、[有符号响应](f1-signed-response.png)、[四路命令](f1-four-motor-commands.png)、[物理步输入](f1-four-motor-physics-input.png)。

固定结论：模式确认等待延长了接管后内部零速度捕获目标的驻留。四电机应用神经输出后，参考空窗由原路径的156/168ms缩至16/16ms，峰倾角由55.276/55.560°降至31.184/30.292°；经典对照为25.229/25.113°。原路径两次越线、修正路径与经典各两次未越线。修正只改变首发等待，不消除首帧零速捕获；本轮经典是OFFBOARD，旧Mission为发现背景。

## 本次固定的代码是什么

`f1_runner.py` 与同目录分析、执行脚本按实验原件逐字保留。`source/project/` 保存39个本地Python依赖文件，逐个与启动时candidate哈希一致。`source/px4/working-tree.patch` 保存实际PX4工作树差异；`untracked/` 保存启动身份内的全部未跟踪研究源文件，`resolved/` 提供关键控制器与桥接源码直接阅读。

PX4基线为 `4ae21a5e569d3d89c2f6366688cbacb3e93437c9`，但**基线commit不是全部运行代码**：必须结合patch及untracked。差异哈希与六例记录的运行身份相符，见[source-identity.json](source-identity.json)及逐例candidate-before/after。全部修改仍保留在原实验工作树，未替换其文件或更换分支。该源码快照包含运行所需的既有研究基础，不表示本轮新做了这些修改。

## 远端可以直接复核

在仓库根目录运行（仅Python标准库，不启动仿真）：

```bash
python3 data/handover-f1-sync-20261112-analysis-v1/recheck_published.py
```

核对归档SHA-256，重新读取六条原生派生态度/高度CSV算峰值，并用源时间字段重新计算四条电机到参考间隔及实际发送先后。`artifact-manifest.json` 是原实验清单；`freeze-manifest.json` 是本次发布清单。复核脚本核对派生证据，不冒充从ULog重新解析。

## 留在Thor而未上传的内容

大体积 `flight.ulg`、完整Gazebo四电机bin、telemetry/resources、setpoint发送全日志、进程日志、rootfs、二进制、模型权重和构建目录均留在Thor，未删除。原始ULog哈希保留在逐例score/metadata；策略、二进制和插件哈希见source-identity及candidate记录。远端提供关键时间链源记录与原生派生曲线，不提供独立重建整个Lab所需的全部资源。

原脚本的绝对路径保持原样，完整重算需要Thor原始日志和既有ROS/PX4/Gazebo/pyulog/numpy/scipy/matplotlib环境；不得把这个归档当成任意机器上一键起飞包。本次不重新构建、不重飞，原有六次结果保持完整。

6次原启动、0重试；wall404.391s、CPU176.136s。4例落地/disarm确认，2例保护中止且恢复未确认；冻结联合恢复与任务安全结果仍分开保存，失败窗口不补齐。

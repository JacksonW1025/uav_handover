# 2026-11-16 发布核验

## 文件与来源

- 基于远端 `research/handover-baseline-20261115` 的 `8503fa197e6fbfc3c633c51df7b7e7d1156924c1` 整理。只增加本轮小型证据、四类工作文档、独立 Autoware 技术记录与 README 导航。
- 分类定义、既有固定报告、environment.lock、共享 Lab 和已有原始实验文件均保持不变。
- `evidence/handover-20261116/manifest.json` 是本次发布文件的 SHA-256 清单。各分析结果内另存原始 ULog/电机记录与模型哈希；两者作用分别为“本次整理是否完整”和“观测来自哪个原件”。
- 不提交策略模型、可执行程序、原始 ULog 或原始四电机 bin。CSV 是分析导出的局部轨迹/网络输入摘要，不替代原始证据。
- 各脚本保持本轮实际执行副本。脚本内的历史路径和工具依赖用于指认运行来源，复算需在具备对应原件与匹配工具的隔离目录中进行；本次提交不将早期环境基线改装成后期实验系统。

## 检查

- 基线 `tests/check_baseline.py`：Python/JSON、原源码包路径和既有文档本地链接检查。
- 本轮全部 JSON 解析、全部 Python AST 解析、全部工作文档的相对链接存在性检查。
- T2：8 个原始产物 hash 与 as-run manifest 一致；四种处理的均值由逐帧数值重新算得一致。
- T4：直接编译所附实际 `ActuatorGate.hpp` 与显式 uORB 替身；16 种组合通过，缓存不一致例子的旧规则允许双发布、新规则只允许神经。
- `git -c core.whitespace=blank-at-eol,space-before-tab,cr-at-eol,-blank-at-eof diff --cached --check` 通过。原样 CSV 使用 CRLF，两份原样脚本末尾保留空行；为保持 as-run hash 不改写这些格式。另做大文件/原始日志排除检查，提交范围只含本轮材料。

## 五次启动

[执行账本](../../evidence/handover-20261116/execution-ledger.json)保存每次开始的结果、运行成本、构建与策略身份及进程退出。T1 三次、T3 两次均正常落地与 disarm，PX4/Gazebo 退出码均为 0。辅助监控/通信进程中的 -2 是清理阶段发出的中断，单独记录，不与飞行进程异常混为一谈。

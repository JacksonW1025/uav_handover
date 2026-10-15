# 实验数据

## 数据保存策略

自 2026-10-15 起（含对此前全部历史的重写），远程仓库不再保存大体积原始飞行数据，以便协作者快速克隆并了解全部研究工作：

- **只在实验机本地保存**（`.gitignore`）：每轮 `flight.ulg`、`gz-motor/` 逐物理步电机轨迹、`telemetry.jsonl`、`resources.jsonl`、Gazebo 原始传感器抓取日志（`logs/gz-imu.log`、`logs/gz-pressure.log`、`logs/probe-*.log`）。合计约 25 GB。
- **远程保留**：每轮的 `config.json`、`metadata.json`（源码/二进制/策略身份和 `ulog_sha256`）、`events.jsonl`、`validation.json`、`metrics.json`、`p1-metrics.json`/`p2-metrics.json`、`output-chain.json`、`preparation-trace.json`、文本日志、图；每批的 `plan.json`、`candidate.json`、`results.json`、`batch-audit.json`、`diagnosis.json`；报告与图。全部结论都能从这些文件追溯和复核。
- **完整示例 ULog**（可直接用 pyulog/PlotJuggler 打开）：
  - `p1-20261013-b02-S1-c_to_n-1/flight.ulg`（P1 悬停 C→N，原始复位）
  - `p2-20261015-s1a-S1-c_to_n-N0-1/flight.ulg`（P2 S1 N0，含 `research_memory`）
  - `p2-20261015-s1a-S1-c_to_n-N2-1/flight.ulg`（P2 S1 N2）
- 需要重新分析（`tools/analyze.py`、`tools/p2_audit.py` 等）时在实验机本地运行；原始文件可用 `metadata.json` 中的哈希核对。实验机本地还保留重写前的完整历史分支 `archive/full-raw-history`。

2026-10-09 环境建设期间产生的实际新 SITL 数据。没有导入旧仓库实验记录。最终验收结果和全部成功、失败尝试索引见 [acceptance.json](environment-20261009/acceptance.json)。

| 目录 | 用途 |
|---|---|
| `environment-20261009/` | 依赖、构建、健康检查、通信和单元测试的命令输出与退出状态 |
| `final-classic-relative-01` 至 `03` | 默认相对高度起飞的三次连续经典悬停验证 |
| `verified-raptor_hover/` | 最终发布仲裁后的神经悬停及 C→N→C |
| `verified-repeated_handover/` | 最终三次双向交接 |
| `verified-state_reset/`、`verified-state_hold/` | 最终状态重置、保持实验 |
| `verified-state_restore/`、`verified-state_injection/` | 最终快照恢复、受控注入实验 |
| `acceptance-*`、其余 `final-*` | 建设过程的原始尝试与诊断；不能替代最终冻结配置验收 |

每轮在实验机本地保留原始 `flight.ulg`、配置、源码/策略身份、事件、遥测、日志、指标、判断和图像（远程仓库只含其中的小文件，见上）。`rootfs/` 与 `cli/` 是重复的本机运行副本，被 Git 忽略。`telemetry.jsonl` 记录辅助 ROS 遥测；没有将其冒充完整 ROS bag。

```bash
cat data/verified-raptor_hover/validation.json
./tools/experiment analyze data/verified-raptor_hover
```

分析器随本轮工程修复增强；旧目录的历史判断反映当时版本，最终矩阵仅使用明确列出的最终证据。再次分析旧数据可能发现之前未检查的时长或发布竞争问题，原始日志始终保留。

## 2026-10-10 P0 收尾

`p0-20261010/` 保存构建/测试/实验命令证据、旧 lock/补丁副本、版本身份和收尾验收清单；`p0-20261010-*` 保存各次独立原始运行。诊断失败与中间分析版本也保留，不应选择性忽略失败；最终运行选择及未决问题见 [P0 报告](../docs/THOR_P0_FINAL_REPORT.md)。`verified-*` 为原验收，未改写，其 PASS 不包含新版联合恢复与 executor 规则。

## 2026-10-11 准备阶段

`preparation-20261011/` 保存修改前与候选源码归档、构建/测试结果、预登记批次计划、候选身份和运行清单。`prep-20261011-*` 为各轮独立原始运行；冒烟、诊断、失败和冻结批次全部保留。`batch-03`（lockstep 修复后，41/41）、`batch-04`（加入输出链路测量，30 项后因固定参考恢复标准停止）、`batch-05`（当前目标参考，90/90）各有 `batch-audit.json` 独立复核；`batch-01`、`batch-02` 的失败与诊断保留。`prep-20261012-*` 为 batch-04/05 及输出链路冒烟运行，RAPTOR 运行含 `gz-motor/` 逐物理步记录和 `output-chain.json`。其结果不替换历史 P0 FAIL。[范围与测量限制](../docs/THOR_PREPARATION_20261011.md)。

## 2026-10-12 P0 收尾

`p0-closure-20261012/acceptance.json` 由 `tools/p0_closure.py` 从 batch-03/04/05 复核结果生成，为 P0 完成判定的机器可读依据。

## 2026-10-13 P1

`p1-20261013-batch-02/` 为冻结批次（48/48），`batch-01/` 为保留的停批记录，`p1-20261013-b0{1,2}-*` 为各轮运行，`p1-20261013-p0-reverify/` 为分析口径扩展后的 P0 复核。见 [P1 报告](../docs/THOR_P1_REPORT.md)。

## 2026-10-14/15 P2

接受批次：`p2-20261015-batch-{s1a,s1b,s3-03,nc-03,explore-02}` 与 `p2-20261015-equivalence-02`；停批批次（`p2-20261014-equivalence`、`batch-s3`、`batch-s3-02`、`batch-nc`、`batch-nc-02`、`batch-explore`）和开发运行（`dev-0*`、`crash-probe-01`）原样保留并附 `diagnosis.json`。`p2-20261014-action-map/` 为动作映射拟合，`p2-20261015-nstar/` 为 N★ 记忆提取。每批 `p2-table.md` 为逐轮结果表。见 [P2 报告](../docs/THOR_P2_REPORT.md)。

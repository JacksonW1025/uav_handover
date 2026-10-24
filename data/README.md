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

## 2026-10-15 P3

接受批次：`p3-20261015-batch-01`（39/39，运行目录 `p3-20261015-b01-*`）、候选等价性 `p3-20261015-equivalence`（运行 `p3-20261015-eq-*`）、冻结前尾延迟检查 `p3-20261015-dev-10b`（运行 `p3-20261015-dev10b-*`）。未达到 8 ms 余量的 `p3-20261015-dev-10`（运行 `p3-20261015-dev10-*`）原样保留并附 `diagnosis.json`。开发运行 `p3-20261015-dev0{1..6}-*` 保留。每轮新增 `p3-metrics.json`（三个事件与记忆证据）和 `p3-memory.json`（策略精确回放与记忆长度）；批次目录有 `p3-table.md`。见 [P3 报告](../docs/THOR_P3_REPORT.md)。

## 2026-10-23 P8-B2 收尾与 T1 探索

`p8-20261022-batch-b2/` 保存完成结果、预算身份修订、旧停止诊断/失败现场以及 `export-revalidation-20261023/` 最终900次复验。当前汇总为 `final-summary.json`，旧 `b1-b2-summary.json` 的导出失败状态属于历史。`p8-20261023-t1-boundary/` 是独立24次探索（18域内、6域外），不计入原900次。小型配置、指标、文本日志与结果随仓库保存；新24次原始ULog只在Thor原工作目录，见该目录 `LOCAL_RAW_DATA.md`。全部解释见 [P8报告](../docs/THOR_P8_REPORT.md)。

## 2026-10-24 P9 冻结验证与执行中断

`p9-20261024-preparation/` 保存新模型、26条普通辨识的可移植trace/输入哈希、草案版本、误差、种子/预算/成本、开发账本与检查点；`p9-20261024-dev-01`至`-10`为十次新开发/等价性尝试。
`p9-20261024-freeze/` 为正式前提交的27项冻结输入、预测、搜索/修复规则及回执。P8遗失模型没有补造，旧900与24次不进P9分母。

`p9-20261024-formal/`有102次启动，其中101条完成（B48、C搜索53）。第102次首参考样本因父进程/会话失联中断，无有效测量。
原aggregate最后RUNNING及等待状态是保留的中断现场；当前状态见`p9-20261024-interruption-v1/interruption-assessment.json`。
`p9-20261024-audit-interrupted-v1/`保存101条逐条原始重测PASS及全批102/101完整性FAIL，`p9-20261024-report-interrupted-v1/`保存明确分离的部分结果、CSV、搜索史、图与输入输出manifest。
参考有效0/36、D0/36；71条静态任务NOT_RUN、7个未用搜索槽不挪用，没有自动补跑。

全部原始数据只在Thor本地，尤其未完成样本的ULog来源、保全副本与哈希见[LOCAL_RAW_DATA](p9-20261024-interruption-v1/LOCAL_RAW_DATA.md)。远端不含完整原始遥测。详见[P9报告](../docs/THOR_P9_REPORT.md)。

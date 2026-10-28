# P16 复现与恢复

工作目录`/home/car/uav_handover`，Python为`uav_lab/.local/venv/bin/python`，`PYTHONPATH=tools OPENBLAS_NUM_THREADS=1`。冻结提交`dbd5aeaf2613add201cd7411cf81648d6b8bfad6`已推送、远端回读一致。运行层和分析层分开；不能为重算评分重新启动飞行。

材料固定为`research/p16-mac-materials-20261028/`，来源提交`5caca9a3509552408442fde74a9ec249067fd78d`，完整保留相对目录。`HANDOFF.txt`、`MODEL_CARD.json`、`DOT_P16_PROMPT.txt`为输入。`check_materials.py --help`显示完整离线验收入口；已存结果`data/p16-20261028/material-acceptance-v1/{integrity,full}.json`，656文件、18轨迹重辨识、两个预测及12查询均通过。`material-integration-v3`保留接线修复/失败和测试，旧记录未覆盖。

## 安全的离线复现

```bash
PYTHONPATH=tools OPENBLAS_NUM_THREADS=1 uav_lab/.local/venv/bin/python -m pytest -q tests/test_p16.py tests/test_p16_workflow.py tests/test_p16_material.py
PYTHONPATH=tools OPENBLAS_NUM_THREADS=1 uav_lab/.local/venv/bin/python data/p16-20261028/analysis-source-v2/benchmark.py /tmp/p16-frozen-prediction-check-new
PYTHONPATH=tools OPENBLAS_NUM_THREADS=1 uav_lab/.local/venv/bin/python -m pytest -q data/p16-20261028/analysis-source-v2/test_analysis.py
```

所有输出路径必须未存在。冻结初始预测24条的重复计算逐项差0，记录`frozen-forecast-reproduce-v1/result.json`；25.790CPU秒、26.773墙秒为重复计算成本估计，原始初始预测只有CPU测量，二者不混称同一次实际费用。

全真值齐全后：

```bash
PYTHONPATH=tools OPENBLAS_NUM_THREADS=1 uav_lab/.local/venv/bin/python data/p16-20261028/analysis-source-v2/report.py /tmp/p16-analysis-new
```

该入口只评分既有原始结果、盲回放A_grid/A_cheap、核对G/R冻结地图和自身history、离线消融及绘图。它不调用启动器、不回写原结果、不更新G/R、不能提升旧预测独立性。若分析修版，使用独立版本及未存在的输出目录，保留失败回执。合成全流程测试在`/tmp/pytest-*`隔离，绝不当作真实32次记录。

## 数据与状态

- 全部实际启动：`data/p16-20261028/attempts.jsonl`，同一ID只能一个START_INTENT。
- `runs/<id>/run/`：本机ULog、direct-read、execution、P13物理和telemetry，原始大文件按原规则留Thor。
- 每run的小证据：`row.json`、`before-start.json`、`candidate-before.json`、`execution.json`、`review-cost.json`、`manager-cost.json`、`analysis-v*/result.json`和host前后快照。
- `frozen/`：24候选、30正式物理身份、固定第二seed六点、参数、G/R规则、成本合同、shuffle。
- `policies/G|R/`：隔离的输入seal、q00–q08地图、每查询decision/return/reveal-cost和terminal-seal。
- 两terminal hash在任何fill之前核验；`replication-forecast.json`在fill和第二seed结果之前生成。fill与seed2不返回G/R。
- `preflight-formal/`普通文件副本保存实际PX4、插件、权重，gate保存源码/config/runtime hash及网络数组零差证明。真实源码和运行二进制身份分别记录，不以symlink冒快照。

恢复必须先检查实际宿主PX4/Gazebo/Agent/runner、ledger与输出，不重复已START项。ToDesk连接时原host_gate禁止启动；不能替用户断开。原守卫自行通过后，持久`wait-host-before-main.py`才调用冻结orchestrate；若它已运行，不另起第二队列。服务断连后也遵循上述核账。代码/参数/配置不得在正式运行中编辑或commit。

## 成本和解释

策略查询数与唯一物理START分开。共享结果在各自选中之后揭示，各自反事实费用仍支付完整启动、前缀、任务、关闭、审查；实际项目只记一次。开发共同费用半摊和各自全担两种固定视图并报。补真值、第二seed、历史采集和建模分别列。历史CPU/墙时缺测为UNKNOWN，不能补0。重复测量选择/预测的成本是估计，不伪造原执行测量。

有限主seed24网格、第二seed六点的经验结论不外推连续域或所有种子。R的0.3m/5度为旧数据经验预算；容差门通过不等于未来硬界。实际受体后续揭示的状态仅用于条件核验与反例，不能回流选择。前缀已失败和D历史不重置。

分析v2独立保留v1源码/测试/原错误。它修复R转移日志before别名的分类变化统计，重建同一冻结history下的base与after；原地图和选择语义不变。实际受体核验包含`branch_compatible`和记录可用性，未通过时撤回条件解释，冻结预测照计。第二seed六点不计算完整网格转换精度。费用范围详见`analysis-source-v2/cost-scope.json`，原始流程外管理CPU只有合计，不能称逐策略全部费用已独立实测。

## 完成后的全量结果与补充分析

本轮32/32已关闭：开发2、主池24、第二seed6；不要再运行任何启动器。`execution-complete.json`及`final-audit-v1/audit.json`记录全终态，`process-evidence-v1.json`独立核对实际每行仅一个PX4/Gazebo及Gazebo seed参数。

主要评分在`analysis-v2-results/`。原Grid13/RBF8/G6/R6均为首次持续满足任务OR四门；独立分项和UNKNOWN另列。原实验源码仍为冻结dbd5aeaf2，包含已知复用before别名日志缺陷；该缺陷不影响预测/选择。v2纠正主要转移日志，v3纠正所有受影响消融日志，不回写原文件。其他纯分析入口均不读取未来信息来改变模型或选点。

在现有结果之后，以下命令必须使用新的输出目录（示例`/tmp`），不会启动SITL：

```bash
PYTHONPATH=tools OPENBLAS_NUM_THREADS=1 uav_lab/.local/venv/bin/python data/p16-20261028/analysis-supplements-v1.py /tmp/p16-supplement-new data/p16-20261028/analysis-v2-results
PYTHONPATH=tools OPENBLAS_NUM_THREADS=1 uav_lab/.local/venv/bin/python data/p16-20261028/actual-pair-diagnostic-v1.py data/p16-20261028/analysis-v2-results /tmp/p16-actualpairs-new
PYTHONPATH=tools OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/p16-mpl-cache uav_lab/.local/venv/bin/python data/p16-20261028/plot-classification-v1.py data/p16-20261028/analysis-v2-results /tmp/p16-figures-new
PYTHONPATH=tools OPENBLAS_NUM_THREADS=1 uav_lab/.local/venv/bin/python data/p16-20261028/repair-ablation-logs-v3.py /tmp/p16-logrepair-new
PYTHONPATH=tools OPENBLAS_NUM_THREADS=1 uav_lab/.local/venv/bin/python data/p16-20261028/cost-inventory-v4.py data/p16-20261028/analysis-v2-results /tmp/p16-cost-new
PYTHONPATH=tools OPENBLAS_NUM_THREADS=1 uav_lab/.local/venv/bin/python data/p16-20261028/task-only-grid-sensitivity-v1.py /tmp/p16-taskgrid-new
```

actual-pair、task-only-grid为暴露后的回顾性机制/设计诊断，不能替换封存政策。`pre-reveal-score-results-v2`来自各自揭示前的选择文件；R缓存结果的预测只是在它自身揭示前，不能称另一条新独立飞行前预测。main-score独立评分与最终主分数一致，第二seed不参与调参。

最终本地回归包含`tests/test_p16_final.py`及版本化分析测试，日志`final-regression-152.log`；它核对物理/虚拟启动、成本缓存收费、分项漏判、冻结与回顾性结果区分、全部消融元数据修订。旧151/145测试日志保留。GitHub CI必须另查发布SHA的actions/check-runs/status，空列表是未报告，不能当绿灯。

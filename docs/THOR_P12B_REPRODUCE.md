# P12b 离线复现与证据路径

以下命令不启动SITL，所有output必须是新目录。准备预算已8/8、正式0/45且工程NOT_PASSED；不要调用campaign进行额外启动。

```bash
# 单条canonical准备记录全离线重算，输出选一个从未存在的新目录。
uav_lab/.local/venv/bin/python tools/p12b/workflow.py \
  --run data/p12b-20261026-development-v2/prep05-F4-ph1-AB-on-direct-v2/run \
  --models data/p12-cont-20261026-freeze/models \
  --output /tmp/p12b-offline-new

# 条件事件映射/精确反例，不拟合数据。
uav_lab/.local/venv/bin/python data/p12b-20261026-analysis-source/margin_map.py \
  /tmp/p12b-margin-new.json

# 按任意新目录输出实际事件级状态表。
uav_lab/.local/venv/bin/python data/p12b-20261026-analysis-source/event_tables.py \
  data/p12b-20261026-development-v2/prep05-F4-ph1-AB-on-direct-v2/run \
  data/p12b-20261026-development-v2/prep05-F4-ph1-AB-on-direct-v2/analysis \
  /tmp/p12b-event-table-new

uav_lab/.local/venv/bin/python -m pytest -q \
  tests/test_p12b.py tests/test_p12.py tests/test_p12c.py tests/test_p12_score.py
```

已完成复现输出`data/p12b-20261026-reproduction/reproduction.json`：七个NPZ模型数组完全一致，scorev2除compute_s一致；不覆盖原analysis。最初命令的models路径以该次运行supervisor和prediction.json绑定hash为准；不得替换权重或再训练。用真实未来流的old-miss诊断只能定位误差，不能重命名自主预测。

主要入口：

| 证据 | 路径 |
|---|---|
| 原v1开始/停止及完整协议 | `data/p12b-20261026-preparation/attempts.jsonl`, `protocol.json` |
| direct-v2开始/终态及聚合预算 | `data/p12b-20261026-preparation-v2/attempts.jsonl`, `revision-release.json` |
| 原FAIL/修订范围/正式停止 | `preparation-v2/acceptance.json`, `acceptance-scope-review.json`, `formal-stop.json`, `freeze-status.json` |
| canonical同次调用/神经目标执行重放 | 每个`development-v2/<id>/analysis/` |
| 全8启动/全45未启动和事件表 | `delivery/reviewed/startup-ledger.json`, `delivery/event-table-manifest.json` |
| 初态、修复共同窗与全任务代价 | `delivery/prefix-and-costs/costs-and-covariates.json` |
| 全前缀数组/首越界区间/事件分类 | `delivery/prefix-and-costs/prefixes.json`及本地完整NPZ |
| 旧AB对B单独的历史比较 | `delivery/historical-B-before/comparison.json` |
| 旧漏判修正诊断与原错误保留 | `delivery/old-miss-diagnostic-v2/`, `delivery/old-miss-diagnostic/phase-erratum.json` |
| 求解重查与时序连接 | `preparation-v2/solver-recheck/`, `prep03-execution-connection/`, `prep07-execution-connection/` |
| 实际runtime普通副本hash | `preparation/runtime-snapshot.json`, `preparation-v2/runtime-snapshot.json` |
| 全部剥离源码及旧失败 | `preparation-v2/controller-source-closure-reviewed/`, `controller-source-closure/` |
| 实际v1 Lab源码补充归档 | `preparation/revision-1-actual-lab-reconstructed/` |
| 未应用清理候选 | `preparation-v2/cleanup-candidate-NOT_VALIDATED/` |
| 当前可复建独立patch导出 | `patches/p12b-20261026-tested-direct-v2/` |

表中短路径均在`data/p12b-20261026-...`下；具体绝对路径及SHA见机器清单。原始大文件留在Thor，Git只提交小证据与工具。ULog在run/flight.ulg与rootfs/log下为硬链接；不能重复计算其释放容量，未删除任何历史文件。大solver/bin与完整NPZ没有降采样或抽行后替代原件。补充前缀NPZ在总清单里，初始raw清单保持版本不回写。

实际v2 PX4 SHA为`cc314acb408cfa7ab92e8910f9ce6cba873cdad378c73d169009172ed587ec60`，policy.tar SHA为`5327c83dc57f094ca1977a2533ebce318645be010e16b9354c96c337cd5c278b`。真实DART/GZ依赖版本/hash与headers来源分别存档；复建结果应另存与实际快照比较，不能把源码阅读称发行二进制认证。

测试输出保留在`preparation*/`：最终focused、project-wide、根目录误收集、错误测试文件名、source apply幂等、anchor/build失败与成功、直接packed writer、真实World/seed单元。任何再分析写新目录，旧P11/P12有效性与评分不回写。

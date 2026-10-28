## 最新状态更新：2026-10-28 16:03UTC

原宿主门已于15:56:42通过，现有同一进程正在执行正式orchestrate；16:08仅原等待截止，已不再适用。不要另建等待/物理队列。当前4主池有效终态，第5条运行，累计7START=2开发+5主池；以attempts实时账本为准。G/R各q4已返回，源码/HEAD保持原冻结。

# P16 可恢复检查点（15:55UTC，未完成）

本轮仅P16：总START32，上限开发2/主池24/第二seed6，不转预算、不重跑。当前实际2开发、主池0、第二seed0；两开发有效，d02科学FAIL且B前已失败，原analysis-v1错误保留、analysis-v2修复。全旧P15/P14及失败保持。

主冻结HEAD/远端均`dbd5aeaf2613add201cd7411cf81648d6b8bfad6`；材料`5caca9a3509552408442fde74a9ec249067fd78d`，656完整hash、18重辨识/两预测/12查询复现PASS。139正式源/历史回归PASS，独立分析v2另6PASS。原48JSONseal和1573源码/配置/runtime字段检查无漂移。`.gitignore`原授权新增raw规则；AGENTS及旧publication回执是他人/历史未跟踪文件，不要加入提交。

唯一物理等待进程PID44017（父shell44007、exec session6574），`wait-host-before-main.py`，每30秒原`p9_run.host_gate`检查。ToDesk视频PID4092546持续存在，不能代替用户停止。约16:08UTC等待到期；到期先核实该PID已结束、账本和PX4/GZ/Agent没有未决，才恢复等待或未START项。不得因为服务/会话重连重复开发或主池案例。

门通过后已有脚本自动运行冻结`p16.orchestrate`，输出`orchestration-v2.log`。不另起并行orchestrator。G/R各8自身查询，联合共享物理但只在自身选中后揭示，双终态seal→固定六点预测→补齐24主池→seed2六点。全部budget/prediction/row/model hash门已接通。实际源/配置/HEAD不能在飞行队列进行中编辑或commit。

依赖后处理PID214960（父214950、exec session41580），`postprocess-after-complete.py`：只等待`execution-complete.json`+32唯一且均已reviewed后，运行离线report、145相关回归、只读finalaudit；绝不调用飞行启动器。最大等待约18:42UTC，失败时保留日志，不自动重启物理。后处理输出`analysis-v2-results/`、`final-audit-v1/`、`postprocessing-complete.json`及`postprocess-after-complete.log`，然后仍需模型复核、完善报告、正常发布。

分析v1完整保留；v2修复冻结reuse日志before别名统计，原策略/地图不变。对实际受体同时查signature+branch_compatible/available，前提不符撤回条件解释，冻结漏判照计。第二seed六点仅描述性分类/初态，不能据NO_TRANSITION称主池精度达标。成本含R校准53.061CPU秒、开发半摊/全担并报；流程外G/R管理CPU仅合计，原逐策略费用缺测，只能下界/后验重算估计，不能宣称完整总收益。v2源封存`analysis-source-v2/source-seal-before-main.json`，不静改，后续实现错误新版本全量重算。

现有raw复用probe验证新增capture字段提取路径PASS：d02实际capture比名义晚7.996ms，冻结4ms门拒绝复用，未放宽；`return-field-probe-v1`未写回原目录、未新增START。开发D反例`developer-ledger-counterexample.json`：B前D1.039m、后段新增仅.049m，丢L/D或前缀倾角会错误撤销失败。

后处理完成后，另执行不接触选择器的预登记补充：

```
PYTHONPATH=tools OPENBLAS_NUM_THREADS=1 uav_lab/.local/venv/bin/python data/p16-20261028/analysis-supplements-v1.py data/p16-20261028/analysis-supplement-results-v1 data/p16-20261028/analysis-v2-results
```

用同一最终未查询集合比较q0/q8，去掉已查询标签覆盖的表面改善；复用接受记录去重为候选/类，不能把9张地图重复记录当样本。OE24预测已在首main标签前生成，仅固定敏感性、不改变EE主策略。

最终读delivery/成本/所有例外后改`docs/THOR_P16_REPORT.md`（当前只是执行中草稿），完善接口/复现、边界/质量-成本图、两目标分别结论。只有双方首次且持续四门达标才量化SITL节省；未达标不外推。实际项目32唯一START含真值补齐，策略反事实查询费另栏。旧获取/人力/部分管理费用UNKNOWN，不补0。最后回归/旧tracked历史不变/新rawhash和实际宿主无simulators回执，正常commit/push回读远端SHA。真实CI用GitHub actions/runs?head_sha、commits/SHA/check-runs和status三项；冻结commit目前0/0/0，是NO_CI_REPORTED，非绿灯。不要P17或新增预算。

# P13复现与证据索引

所有命令从`/home/car/uav_handover`运行。使用`uav_lab/.local/venv/bin/python`，系统Python没有NumPy。原始文件在Thor，完整NPZ、ULog、gz-motor和普通运行二进制按原规则留本地；仓库交付hash、分析源、小型结果及独立PNG/PDF。不要删除或降采样旧日志，不把CLI符号链接当作历史二进制。

## 版本与权限边界

基线`73d467beb70acf2c7413468f74be76e3b73c723a`；正式冻结发布`4c122aaa9710b93699c52cbfc059653681ef4b31`，回执`data/p13-20261026-freeze/receipt.json`，完整冻结文件表`manifest.json`。正式结果后的提交是分析/交付版本，不能把其新HEAD回填成运行HEAD。

运行实际PX4、研究motor插件、Gazebo/DART插件/库、policy及构建输入普通副本在`data/p13-20261026-runtime-local-v1/`，索引`data/p13-20261026-preparation/runtime-snapshot-v1.json`。PX4 SHA为`b6ea5a948b2ab0ed35f715ffa42fc9b09ec5dac33106691d7c573e02c98778d9`，motor插件`21211d96e9d929b3d3f5a6dea32ba4d319dca82b353617105cefde4cc6fb58ea`，原policy tar `5327c83dc57f094ca1977a2533ebce318645be010e16b9354c96c337cd5c278b`。

以下都是**离线复现**，不启动SITL。每个输出目录必须全新；不要向旧目录运行新分析，不修改既有账本或冻结文件。完整84次上限不代表可自行补跑；本轮额外6条在正式前已明定UNUSED。

## 主要数据

- 唯一启动账本：`data/p13-20261026-preparation/attempts.jsonl`，START_INTENT计数，PHYSICAL_END与分析FINISH分别记录。
- 开发：`data/p13-20261026-development/<dev-id>/run`及`analysis-v1`；首条序列化和理想刚性FAIL在`physics-v2`保留，实际完整几何另为`physics-v3`。
- 正式：`data/p13-20261026-formal/<id>/run`；计划及种子顺序在`config/p13-formal.json`。每项独立普通运行身份、配置hash、metadata、wrapper和终态。
- 封存自主输入、预测与v2评分：默认每项`analysis-v1/{packed-physical,prediction,score}`；第53项按`analysis-pointer-v2.json`选择新`analysis-v2`，原partial目录和FAIL保留。所有当前分析通过`analysis_paths_v1.analysis_dir`解析，不覆写旧目录。其中`prediction/isolation.json`记录bwrap隐藏全部data/export、网络/PID隔离；只复制过去初态、事前计划、权重与封存模型。实际未来只进评分端。
- 同步物理事件表：`data/p13-20261026-formal-analysis-v3/<id>/events/event-states.json`；其原有`entire_capture_hold`和`mechanical_proxies`字段是保留的legacy计算。**完整XYZ保持段采用最终`results-v3/holds/<id>/hold-axes.json` schema2（capture调用包含）；代价采用contrasts中的`common_window_costs_v3/own_covered_costs_v3`（真实joint与10倍空气动力转速平方分别报告）。**
- 最终分块结果：`data/p13-20261026-results-v3/{cases,blocks,contrasts,nonadditivity}.json`。
- 全前缀与分项分母：`data/p13-20261026-synthesis-v3/`；A前/初始差异`data/p13-20261026-covariates-v3/`；时钟/消费`data/p13-20261026-clocks-v3/`；第一越界括号`crossing-v3`；仅定位误差的事后lag诊断`phase-v3`。
- 终态审核及原始/派生/二进制完整hash：`data/p13-20261026-delivery-audit-v2/`。最终报告和机器结论以该审核及最终结果为依据，不用中途preview替代。
- 科学图：`docs/figures/p13/`，PNG用于报告，PDF可单独导出。所有种子都画出，不事后择“最一致”一对。

## 全量离线重算

运行中的正式队列不得修改tools/research/config或commit；下列复现应在正式队列已结束后进行。把示例输出路径换成自己的全新路径。

```bash
uav_lab/.local/venv/bin/python data/p13-20261026-analysis-source/aggregate_v5.py data/p13-reproduction-results-new
uav_lab/.local/venv/bin/python data/p13-20261026-analysis-source/synthesis_v2.py data/p13-reproduction-results-new data/p13-reproduction-synthesis-new
uav_lab/.local/venv/bin/python data/p13-20261026-analysis-source/covariates_v2.py data/p13-reproduction-results-new data/p13-reproduction-covariates-new
uav_lab/.local/venv/bin/python data/p13-20261026-analysis-source/clock_execution_v2.py data/p13-reproduction-results-new data/p13-reproduction-clocks-new
MPLCONFIGDIR=/tmp/p13-reproduction-mpl uav_lab/.local/venv/bin/python data/p13-20261026-analysis-source/plot_results_v3.py data/p13-reproduction-results-new data/p13-reproduction-synthesis-new data/p13-reproduction-figures-new
```

`aggregate_v5`从所有已完成身份和既有直接物理事件表重算；完整raw/NPZ必须在本机。分析只生成新目录，不会调用campaign。逐记录也可调用`record_review_v3.py <absolute-formal-case-dir> <absolute-new-output>`、`phase_diagnostics_v2.py <absolute-case> <absolute-new-output>`、`crossing_v2.py <absolute-case> <absolute-new-output>`；不能把新的输出替换旧正式评分。

第53项须先按analysis-pointer选择analysis-v2，其余默认analysis-v1。对封存预测的独立重算可调用`tools/p13/isolated.py --packed <case>/analysis-v1/packed-physical --models data/p13-20261026-freeze/models --output <new-output>`。bwrap需要宿主支持；失败保留child.log，不改模型或放开未来输入来求成功。这是同一模型重算，绝不是新SITL或独立飞行样本。

## 源物理诊断与条件关系

```bash
uav_lab/.local/venv/bin/python data/p13-20261026-analysis-source/source_discrete_kernel_v1.py data/p13-reproduction-source-kernel-new
uav_lab/.local/venv/bin/python data/p13-20261026-analysis-source/controlled_kernel_replays_v1.py data/p13-reproduction-controlled-kernel-new
uav_lab/.local/venv/bin/python data/p13-20261026-analysis-source/height_constraints_v5.py data/p13-reproduction-height-new
uav_lab/.local/venv/bin/python data/p13-20261026-analysis-source/recovery_discrete_v1.py data/p13-reproduction-recovery-new
uav_lab/.local/venv/bin/python data/p13-20261026-analysis-source/repair_parameter_conditions_v4.py data/p13-reproduction-repair-new
```

前两个会使用实际未来命令/执行/状态作误差定位，其结果不能混入自主预测成绩。高度必要储备、充分恢复、全保持修复条件和SERVO数值预算是不同方向/不同前提的关系；参见`THOR_P13_THEORY_RESULTS.md`。源参数包络不是正式数据经验最大值，也不是完整闭环可达性证书。

原独立测试记录：`preparation/targeted-tests-v1.log`为41项Python通过；幂等、实际构建与buffer ASAN/UBSAN宿主验证另有日志。`height-constraints-v4/tests.json`为8项源必要储备/延迟/历史D/窗口边界回归；`recovery-discrete-v1/map.json`含30项精确有理数递推核对。测试脚本有固定旧输出的不得直接覆盖旧证据，应复制修改为新输出路径再运行。

## 保留错误及解释边界

`analysis-revisions/`逐项记录JSON scalar修正、真实joint单位/阶段修正、修复位置初始速度项、离散窗口floor、COM/原点与全保持cache假设、capture调用包含等；旧文件和中途preview全部保留。原正式实验与源hash不因这些确定分析修复改变。

数据完整性依赖完整读回、精确长度、header/valid/步序列、Post→下一Pre连续与SHA；当前析构的最后header重写/fclose返回值未完全计错，不能只由errors=0宣称全部IO错误可检测或断电持久性。理论的未来数值/模式/估计器/cache/历史传播仍有未闭合项。三种模型、重叠窗口、三间隔和两读取策略都不得虚增独立种子块数。

第53项的全run空中近似误用于经典降落触地，原2.689mm FAIL保留。独立`physics-scope-v4`以不变1mm检查完整研究任务（含全部poststream和handover），并保留全run字段/头/步序/连续性；回查全部53项后只离线恢复53分析，确认旧进程结束后同一冻结实验层继续未启动13项。`revision-8-physics-phase-scope.json`记录完整证据，不把地面contact当作空中SERVO认证，也不把分析版本当成新的实验版本。

最终机器结论为`data/p13-20261026-final-analysis-v4/machine-conclusion-final-v2.json`。最终报告在生成稿后增加了LP软件body点与named-model点的源码复核、实际参数和M5错误说明；生成前稿及SHA在delivery-review-v2保留。候选M5代码/参数及66条分项评分未变。高度v5仅修正COM→LP测量点说明，COM必要储备数学/示例与v4一致；修复条件v4改用源body小杆臂，旧named-point版本保留。

实际宿主终态快照位于delivery-review-v2/host-process-terminal.json；首个只读ps查询因宽屏选项拼写失败，无进程操作，随后实际host的正确查询确认312个所属PID均不在进程表。source-seed-final-v2独立核验66项GZ命令种子、metadata/project HEAD与源函数确定展开的运行配置。

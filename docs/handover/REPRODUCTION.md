# 复核与复现

## 已发布数据

在仓库根目录运行 `python3 tests/check_evidence.py`。脚本读取版本库中的 CSV、压缩轨迹和 JSON，核对 T1 三臂峰值与接管时序、T2 电机和高度响应及紧弯回放、T3 两组参考空窗和六条转弯轨迹、T4 样本的转发及应用。它只读取数据。Python、JSON 和源码归档的静态核对使用 `python3 tests/check_baseline.py`。

## 从原始记录重新分析

| 案例 | 入口 | 输入 |
| --- | --- | --- |
| T1 紧弯 | [analyze.py](../../evidence/t1/turn/analyze.py) 与[刹停分析](../../evidence/t1/braking/analyze.py) | C2/N/PRE 的 ULog、事件日志、四路电机记录；ULog 哈希见 [results.json](../../evidence/t1/turn/results.json)。 |
| T2 直线 | [analyze.py](../../evidence/t2/straight/analyze.py) | N2/N4 的 ULog、事件日志、四路电机记录与冻结策略；见 [summary.json](../../evidence/t2/straight/summary.json)。 |
| T2 紧弯 | [replay_policy.py](../../evidence/t2/turn/replay_policy.py) | [发布的原生帧](../../evidence/t2/turn/replay.json)与相同冻结策略。运行 `python3 evidence/t2/turn/replay_policy.py /path/to/policy.tar`。 |
| T3 直线 | [analyze_fixedphase.py](../../evidence/t3/straight/analyze_fixedphase.py) | 固定相位两臂 ULog 和电机样本；见 [summary.json](../../evidence/t3/straight/flight-analysis/summary.json)。 |
| T3 转弯 | [analyze_f1.py](../../evidence/t3/turn/analyze_f1.py) 与 [analyze_t3.py](../../evidence/t3/turn/analyze_t3.py) | 六次飞行的 ULog、事件与四路电机记录；见 [source-identity.json](../../evidence/t3/turn/source-identity.json) 和[重算结果](../../evidence/t3/turn/analysis/t3-recomputed.json)。 |
| T4 悬停 | [audit.py](../../evidence/t4/hover/audit.py) 与 [sample_accounting.py](../../evidence/t4/hover/sample_accounting.py) | 两次悬停的 ULog、relay CSV 与四路电机记录；见 [raw-audit.json](../../evidence/t4/hover/raw-audit.json)。 |

执行脚本保留原实验的绝对路径与依赖，用于定位实际运行的工作区。原始记录由 Thor 实验端保存。离线复算时，按文件哈希取得对应原件，在独立的分析目录中映射脚本的输入输出路径。分析依赖见 [requirements-research.txt](../../requirements-research.txt)。

## 在 Thor 重跑 SITL

共享底座为 Jetson AGX Thor、Ubuntu 24.04、ROS 2 Jazzy、Gazebo Harmonic。仓库的[环境锁](../../environment.lock)、[补丁](../../patches/)和[工具](../../tools/)对应早期平台基线。各实验使用后续冻结的候选构建，须按对应证据的策略、二进制哈希与工具快照准备独立 Lab。准备平台需要匹配的 PX4 及子模块、策略文件、ROS 接口、XRCE Agent 和系统依赖。早期平台启动与接口说明见[固定基线文档](https://github.com/JacksonW1025/uav_handover/blob/141a2b31becee1a909e0d76f552b0724eb315f99/docs/THOR_EXPERIMENT_QUICKSTART.md)。

| 重跑对象 | 实际执行入口 | 配置或来源 |
| --- | --- | --- |
| T1 紧弯三臂 | [runner.py](../../evidence/t1/turn/runner.py) | 按 C2、N、PRE 运行；[构建身份与补丁](../../evidence/t1/build/)记录参考准备改动。 |
| T2 直线两臂 | [experiment.sh](../../evidence/t2/straight/experiment.sh) | [N4](../../evidence/t2/straight/N4/config.json) 与 [N2](../../evidence/t2/straight/N2/config.json)。 |
| T2 紧弯 | [原实验回放脚本](https://github.com/JacksonW1025/uav_handover/blob/141a2b31becee1a909e0d76f552b0724eb315f99/evidence/handover-20261116-extension/t2/moving/replay.py) | 从 T1 N 臂飞行记录及冻结策略提取 `tight_turn_moving`。发布帧的重算使用上一节的独立脚本。 |
| T3 直线两臂 | [experiment.sh](../../evidence/t3/straight/experiment.sh) | [flight-plan.json](../../evidence/t3/straight/flight-plan.json) 与 [runner](../../evidence/t3/straight/fixed_phase_runner.py)。 |
| T3 转弯六次 | [experiment.sh](../../evidence/t3/turn/experiment.sh) | [原试验冻结方案与工具快照](https://github.com/JacksonW1025/uav_handover/tree/cbaf3a53914efe26b2e00444f56f16935b760a27/data/handover-f1-sync-20261112-analysis-v1)。 |
| T4 悬停两臂 | [experiment.sh](../../evidence/t4/hover/experiment.sh) | [plan.json](../../evidence/t4/hover/plan.json) 和 [relay/runner 版本](../../evidence/t4/hover/source-identity.json)。 |

每次启动使用独立的输出目录。保留配置、执行账本、退出记录和原始日志，以便用同一事件口径核验新结果。

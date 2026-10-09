# Environment Check

检查日期：2026-10-09（Asia/Shanghai）。状态：**环境检查完成**。

本轮已实际安装 Lab 内隔离依赖、构建 classic / RAPTOR PX4 与两套 ROS overlay，并运行新的 headless SITL 悬停、双向交接、重复交接及状态干预实验。原始 ULog、失败尝试、命令退出状态和分析结果均保留在 `data/`。

| 项目 | 最终状态 |
|---|---|
| Thor / aarch64 / 14 核 / 122 GiB | 实机重新检查通过 |
| Ubuntu 24.04.3 / L4T 38.2.1 / 驱动 580.00 / CUDA 13.0 | 保持现有版本 |
| Python 3.12.3 / Jazzy / Gazebo Harmonic 8.11.0 | 依赖与原生消息支持检查通过 |
| classic 与 RAPTOR 构建 | 均已实际构建并运行 |
| ROS 双向通信 / Agent 重连 | 实际 PX4 实例验证通过 |
| 经典悬停 / 神经独立执行器窗口 / C→N→C | 新日志端到端验证通过 |
| 三次重复交接 / 状态 Reset、Hold、Restore、Inject | 实际状态值和输出归属核对通过 |
| Lab 资源完整性 / Git 边界 | 89,867 个文件校验通过；Lab 整体忽略 |

完整结论及限制见[最终报告](docs/THOR_ENVIRONMENT_FINAL_REPORT.md)；逐项命令、退出码、日志见[机器可读验收](data/environment-20261009/acceptance.json)和[25 项矩阵](docs/THOR_ACCEPTANCE_MATRIX.md)。启动方式见[Quickstart](docs/THOR_EXPERIMENT_QUICKSTART.md)。

当前具备固定配置下开展正式短时 SITL 交接和状态对照实验的条件。训练动力学一致性、约 125 Hz native 与训练 100 Hz 的差异、长时统计及完整飞控状态恢复仍需按报告范围处理。

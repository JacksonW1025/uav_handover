# 无人机仿真工具

本仓库提供基于 PX4/Gazebo 与 Crazyflie 固件闭环的仿真配置、运行脚本和日志分析工具。

## 交接实验

- [PX4/RAPTOR 与 Crazyflie 2.1 交接汇总](docs/handover/README.md)
- [PX4/RAPTOR T1–T4](docs/handover/T1.md)（[T1](docs/handover/T1.md) · [T2](docs/handover/T2.md) · [T3](docs/handover/T3.md) · [T4](docs/handover/T4.md)）
- [Crazyflie 2.1 T1–T4](docs/handover/CRAZYFLIE_CASES.md)
- [PX4 / MCNN Control T1–T4](docs/handover/PX4_MCNN_CASES.md)（官方前馈网络，x500 SITL）
- [交接证据索引](docs/handover/CROSS_PLATFORM_EVIDENCE.md)

## 本地检查

使用 Python 3.10 或更新版本，在仓库根目录运行：

```bash
python3 tests/check_baseline.py
python3 tests/check_evidence.py
```

## 仿真环境

[环境锁](environment.lock)记录实验环境与依赖版本。[仿真配置](config/experiment.json)定义运行参数，[工具目录](tools/)包含环境准备、仿真启动和日志分析脚本。

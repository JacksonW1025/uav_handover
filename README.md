# 无人机仿真工具

本仓库提供基于 PX4 和 Gazebo 的软件在环（SITL）实验配置、运行脚本和日志分析工具。

## 本地检查

使用 Python 3.10 或更新版本，在仓库根目录运行：

```bash
python3 tests/check_baseline.py
```

该命令检查 Python 与 JSON 文件、源码归档路径和本地文档链接。

## 仿真环境

[环境锁](environment.lock)记录实验环境与依赖版本。[仿真配置](config/experiment.json)定义运行参数，[工具目录](tools/)包含环境准备、仿真启动和日志分析脚本。

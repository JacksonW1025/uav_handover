# PX4 / RAPTOR Handover

NVIDIA Jetson AGX Thor 上的 PX4 经典控制、RAPTOR 神经控制、C → N → C 双向交接及控制器状态干预研究。2026-10-09 已完成本机环境建设和真实 headless SITL 验证。

- [环境检查](Environment%20Check.md)
- [实验状态](Experiment%20Status.md)
- [实验 Quickstart](docs/THOR_EXPERIMENT_QUICKSTART.md)
- [最终验收报告](docs/THOR_ENVIRONMENT_FINAL_REPORT.md)与[验收矩阵](docs/THOR_ACCEPTANCE_MATRIX.md)
- [机体和电机映射](docs/THOR_PLATFORM_MAPPING.md)
- [环境锁定](environment.lock)、[实验配置](config/experiment.json)、[数据索引](data/README.md)

```bash
./tools/experiment health
./tools/experiment classic_hover
./tools/experiment raptor_hover
./tools/experiment handover_c_n_c
./tools/experiment state_restore
```

整个 `uav_lab/` 属于本机环境并被 Git 忽略。仓库保存研究源码、补丁、配置、原始实验日志和文档；克隆后需按锁清单准备 Lab。运行资源来自当前 Lab，系统 ROS 2、Gazebo、CUDA 继续使用本机安装。重建步骤见 Quickstart。

当前验收范围为冻结 x500 配置的短时 SITL，神经控制窗口由经典控制起飞和降落。完整训练动力学元数据、长时间统计验证及完整 EKF/FlightTask 状态快照仍超出当前验证范围，详见最终报告。

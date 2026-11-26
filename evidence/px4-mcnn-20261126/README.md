# PX4 MCNN / Gazebo x500 native closed-loop evidence

[实验报告](../../docs/handover/PX4_MCNN_CASES.md) · [对比图 PDF](paired-windows.pdf) · [数值](metrics.json) · [溯源](provenance.json) · [八条运行的记录](runs.json)

在仓库根目录运行：

```bash
python3 evidence/px4-mcnn-20261126/verify.py
python3 tests/check_baseline.py
python3 tests/check_evidence.py
```

离线验算只用 Python 标准库。原始 ULog 和 Gazebo 电机追踪二进制保存在 Thor，没有复制进 Git。归档的 gzip 是原生窗口的独立导出，无插值，含原生时间。查某个字段的含义时可对照 [提取器](extract.py) 与 [复算器](verify.py)。

- `vehicle_*`、`trajectory_setpoint`、`actuator_motors`、`neural_control`：PX4 ULog 原生主题。记录的 `neural_control.network_output` 已映射归一化，不能当作未映射的 MLP 输出。
- `mcnn_native`：只读模块侧记录。A 是激活，R 是实际采纳有效参考，N 是发出归一化 motor 命令。
- `gazebo_motor_apply`：Gazebo 每步记录，四个 motor 索引各自采纳的命令标识和转速参考。对照器用 PX4 发布戳和数值交叉匹配，不把 ESC 回声代替物理步证据。
- `relay`：真实 Gazebo relay 收到、暂存和发送的事件。源自隔离的仿真进程。
- `mcnn_prior_entry`：T3 前次进入时的原生参考接受记录，供验证二次进入首拍确实保留 A 的标识。

[构建与运行说明](setup/BUILD.md)包括实验用补丁、Gazebo 记录器来源和重跑命令。保持现有 RAPTOR 与 Crazyflie 目录不变。

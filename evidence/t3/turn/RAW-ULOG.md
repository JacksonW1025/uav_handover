# T3 紧弯对照：原始 PX4 ULog

这里保存 [T3 紧弯实验](../../../docs/handover/T3.md)第一轮的三臂。每个 `.ulg.gz` 是相应原始 `flight.ulg` 的无损 gzip 压缩，不是 CSV、重采样或重新生成的日志。解压后逐字节与实验目录中的原件一致，SHA-256 与该次运行的 `metadata.json` 一致。三份 ULog 均为 Gazebo/PX4 SITL，ULog 标识 `PX4_SITL`，GPS 为默认仿真场景数据，非实飞位置；没有记录到 ULog dropout。

| 运行 | 条件与结果 | 原件字节数 | 原件 SHA-256 |
|---|---|---:|---|
| [001 E1](001_E1_repeat1-a1/original.ulg.gz) | 经典持续控制，不切换；峰值倾角 25.23°，正常落地 | 47,444,687 | `6223a324504680e66337458bd23cfac7542b9e5db71a21bd8b31ed1012080210` |
| [002 E2](002_E2_repeat1-a1/original.ulg.gz) | 原等待；四电机首次使用神经命令后 156 ms 有效读入外部参考；峰值倾角 55.28°，保护中止 | 34,479,973 | `397742468b0d3af6856019fea8887fbe464c1391c8d96be008c76b61ecb0046f` |
| [003 E3](003_E3_repeat1-a1/original.ulg.gz) | 提前恢复参考；对应间隔 16 ms；峰值倾角 31.18°，正常落地 | 47,298,753 | `8362177358517355b9e5996dccfaa9302b57704495525eee960ae1543f145204` |

在本目录运行 `gzip -dc 002_E2_repeat1-a1/original.ulg.gz > E2-repeat1.ulg`，再用 `sha256sum E2-repeat1.ulg` 核对，或用 ULog 工具打开解压文件。日志时间戳使用 PX4 启动后的微秒，不是墙钟或任务相位；任务计划约在 2.750 s 请求交接。`research_p11` 和 `research_target` 记录实际读入/采用的参考，`research_actuator`、`actuator_motors`、`research_output` 记录所有者、命令和输出桥时序，`vehicle_attitude`/`vehicle_local_position` 记录响应。四电机应用时间引用同批原生 Gazebo 电机证据和 [复算结果](f1-summary.json)，不能仅凭 PX4 发布记录推断。与原分析一致，等待长短也改变了首次恢复参考的任务相位；这里不是固定首条参考数值的直线实验。

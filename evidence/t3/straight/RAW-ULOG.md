# T3 直线固定首条参考：原始 PX4 ULog

这是 [T3 直线固定首条参考实验](../../../docs/handover/T3.md)的完整两臂。压缩包里的 `.ulg` 解压后逐字节与对应原始 `flight.ulg` 一致；下列 SHA-256 与运行 `metadata.json` 及[归档分析](flight-analysis/summary.json)一致。两份日志均来自 Gazebo/PX4 SITL (`PX4_SITL`)，使用默认仿真 GPS 场景坐标，均无 ULog dropout。

| 运行 | 激活至有效读入 | 四电机首次应用至有效读入 | 峰值倾角 / 最大失高 | 原件大小（字节） | 原件 SHA-256 |
|---|---:|---:|---:|---:|---|
| [001 短空窗](001_fixedphase_early-a1.ulg.gz) | 32 ms | 16 ms | 2.89° / 3.49 cm | 49,533,334 | `ca35f54cda64d98064b776fc191cd7787a947d112f97452f7ee0bdc6b3b38bc6` |
| [002 长空窗](002_fixedphase_delay60-a1.ulg.gz) | 96 ms | 80 ms | 7.28° / 4.89 cm | 49,417,072 | `5dbeed44d5f30d075ee15ae3792cc1d7333f014711317f7925e4cb6df6b866a3` |

两臂均在任务相位 3.000 s 请求交接，首条移动参考的相位与有效载荷相同；两者都正常落地。日志时间戳是 PX4 启动后的微秒，不是墙钟或任务相位。`research_p11` / `research_target` 用于核实参考读入和目标，`research_actuator` / `actuator_motors` / `research_output` 记录电机命令及桥接，`vehicle_attitude` / `vehicle_local_position` 记录实际响应。四电机应用时刻还依赖 [Gazebo 逐电机交叉核对](flight-analysis/summary.json)，不能只靠 ULog 证明。

在本目录运行 `gzip -dc 001_fixedphase_early-a1.ulg.gz > T3-straight-short.ulg`，再用 `sha256sum T3-straight-short.ulg` 核对原件，或用 ULog 工具直接读解压文件。

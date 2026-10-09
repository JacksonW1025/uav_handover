# 实验数据

2026-10-09 环境建设期间产生的实际新 SITL 数据。没有导入旧仓库实验记录。最终验收结果和全部成功、失败尝试索引见 [acceptance.json](environment-20261009/acceptance.json)。

| 目录 | 用途 |
|---|---|
| `environment-20261009/` | 依赖、构建、健康检查、通信和单元测试的命令输出与退出状态 |
| `final-classic-relative-01` 至 `03` | 默认相对高度起飞的三次连续经典悬停验证 |
| `verified-raptor_hover/` | 最终发布仲裁后的神经悬停及 C→N→C |
| `verified-repeated_handover/` | 最终三次双向交接 |
| `verified-state_reset/`、`verified-state_hold/` | 最终状态重置、保持实验 |
| `verified-state_restore/`、`verified-state_injection/` | 最终快照恢复、受控注入实验 |
| `acceptance-*`、其余 `final-*` | 建设过程的原始尝试与诊断；不能替代最终冻结配置验收 |

每轮保留原始 `flight.ulg`、配置、源码/策略身份、事件、遥测、日志、指标、判断和图像。`rootfs/` 与 `cli/` 是重复的本机运行副本，被 Git 忽略。`telemetry.jsonl` 记录辅助 ROS 遥测；没有将其冒充完整 ROS bag。

```bash
cat data/verified-raptor_hover/validation.json
./tools/experiment analyze data/verified-raptor_hover
```

分析器随本轮工程修复增强；旧目录的历史判断反映当时版本，最终矩阵仅使用明确列出的最终证据。再次分析旧数据可能发现之前未检查的时长或发布竞争问题，原始日志始终保留。

# PX4 / RAPTOR 控制器交接实验

在 PX4 x500 与 Gazebo 的软件在环仿真（SITL）中，经典 Offboard 控制器先飞行，再让 RAPTOR 接手。仓库收录四类已验证的交接问题，包含实验配置、当时执行的脚本、发布版轨迹与报表，以及从切换请求到四电机实际应用的时序证据。

| 分类 | 已验证的场景 | 关键观察 |
| --- | --- | --- |
| [T1 接管后安全余量不足](docs/handover/T1.md) | 紧弯后刹停，经典持续控制、运动中接管、提前接管三臂 SITL | 峰值倾角分别为 25.9°、42.90°、43.01°。两条神经轨迹都在刹停阶段超过本实验 35° 倾角预算。 |
| [T2 控制器历史状态接续错误](docs/handover/T2.md) | 低速直线闭环对照和紧弯原生首帧回放 | 直线清零 GRU 后，首次发布的最大单电机命令阶跃从 0.02168 增至 0.12972，首秒失高从 1.33 cm 增至 2.63 cm。紧弯固定同一帧及上一动作，回放首步的变化从 0.0873 增至 0.1588。 |
| [T3 Setpoint 参考接续异常](docs/handover/T3.md) | 直线固定首条参考、转弯按原任务时钟恢复参考，两组 SITL | 直线中，四电机接管到参考读入的空窗从 16 ms 增至 80 ms，峰值倾角从 2.89° 增至 7.28°。转弯原等待组的空窗为 156/168 ms，两次均超过 55° 并触发保护。 |
| [T4 控制权实际交付异常](docs/handover/T4.md) | 悬停中的命令暂存对照，四路 Gazebo 电机物理步审计 | 首条神经命令发布到四电机首次应用的等待为 24/4 ms。按截止时刻释放的一组从第六条神经样本开始应用，按 active 通知提前释放的一组应用了首条。 |

## 在本地复核结果

用 Python 3.10 或更新版本运行以下命令。复核直接读取已发布的样本和时序，重算表中指标。

```bash
git clone --depth 1 --single-branch --branch main https://github.com/JacksonW1025/uav_handover.git
cd uav_handover
python3 tests/check_evidence.py
python3 tests/check_baseline.py
```

| 路径 | 内容 |
| --- | --- |
| [docs/handover/](docs/handover/README.md) | 分类定义、对照设计、逐步响应与指标口径 |
| [evidence/](evidence/) | 按 T1–T4 归档的数据、图、脚本和构建身份 |
| [环境配置](config/experiment.json)、[环境锁](environment.lock)、[工具](tools/) | Thor 上 PX4/RAPTOR 与 Gazebo 的共享实验底座 |
| [复现指南](docs/handover/REPRODUCTION.md) | 发布数据、原始日志与 SITL 重跑各自的入口及所需文件 |

全部飞行结果来自 headless SITL。重跑使用实验记录对应的 PX4 构建、策略、Gazebo/ROS 环境与脚本依赖。原始 ULog、四路电机二进制和私有构建保存在实验端，仓库中的摘要和导出数据附有来源与时间口径。

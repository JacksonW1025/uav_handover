# Crazyflie 交接实验（单种子）

[结果报告](REPORT.zh.md) · [数值摘要](metrics.json) · [数据索引与哈希](manifest.json)

Crazyflie 2.x 标准模型、同一种子、七次独立的 CrazySim/MuJoCo SITL 启动。宿主在经典和学习型外环间切换，CrazySim 所用的 Crazyflie 固件一直以同一套 PID 执行速度目标。这与 [PX4/RAPTOR](../../docs/handover/README.md) 在飞控内部切换模式和命令来源不同。该对照展示同类交接机制可以在两种集成方式下出现。T2–T4 是有意构造的单因素条件，T4 验证的是外环命令交付到固件接口，不涉及底层电机控制来源切换。

## T3 与 T4 如何区分

依次记录任务参考、外环实际读取的参考、学习型外环算出的命令、宿主发送的命令，以及固件控制循环的当前目标。T3 在第二项偏离，T4 在第四项偏离。两者都可能让固件持续收到正速度指令并晚刹。

- 固件把这类 CRTP 指令按相同优先级交给 Commander，并在接受时记下当前 tick。这个时间说明指令何时被接收，无法说明它基于多新的目标或出自哪个外环。[CRTP 指令优先级](https://github.com/llanesc/crazyflie-firmware/blob/aa6571dc465f06f7d1f9aaf7b0b861fbcd1b3d67/src/modules/src/crtp_commander.c#L111-L123) · [Commander 时间戳](https://github.com/llanesc/crazyflie-firmware/blob/aa6571dc465f06f7d1f9aaf7b0b861fbcd1b3d67/src/modules/src/commander.c#L74-L89)
- `ctrltarget.vx` 是固件控制循环的速度目标。表中时间是 20 ms 周期日志里首次观测到负目标的时刻，相对宿主首条切换拍命令，以宿主回调时钟对齐，不是 UDP 到达或电机执行的精确时间。[控制循环](https://github.com/llanesc/crazyflie-firmware/blob/aa6571dc465f06f7d1f9aaf7b0b861fbcd1b3d67/src/modules/src/stabilizer.c#L323-L357) · [日志字段](https://github.com/llanesc/crazyflie-firmware/blob/aa6571dc465f06f7d1f9aaf7b0b861fbcd1b3d67/src/modules/src/stabilizer.c#L426-L439)

## 复核

从仓库根目录运行 `python3 evidence/crazyflie-20261123/analyze.py`，不需要仿真环境。CSV 仅保存切换附近窗口和各通道末端样本；时间戳和值原样保留。各臂的 `summary.json` 来自完整记录；`metrics.json` 全部数值与完整记录复算一致。完整日志、容器、固件二进制、模型和 Python 环境都不在 Git 中。

[runner.py](runner.py) 是实验当时的脚本，保留原样。运行时，将它放到已配置 [CrazySim](https://github.com/gtfactslab/CrazySim/tree/3ec8b55da4bff887da542a9f314da825460e65be) 的本机忽略目录 `uav_lab/.local/crazyflie-sim/handover-pilot/`。脚本会从上一层寻找 CrazySim 源码和 Ubuntu 22.04 ARM64 容器版 `jammy/cf2`。发布的数据目录只用于离线复核。依赖版本见 [manifest.json](manifest.json)。

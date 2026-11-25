# Crazyflie：四个交接案例

四例均来自 CrazySim/MuJoCo 单种子闭环仿真，Crazyflie 固件 PID 内环保持不变，切换发生在经典与学习外环之间。T1 是正常交接；T2、T3、T4 是分别改变一个入口条件的对照。T4 的证据到固件速度目标接口，未涉及底层电机控制权替换。

| 类别 | 发生了什么 | 对照结果 |
|---|---|---|
| [T1：转弯中刹车](../../evidence/crazyflie-turn-brake-20261124/README.md) | 新参考准时、暖历史和正常交付，但接手方给出的反向速度命令较弱。 | +300 ms 时两组都以约 0.31 m/s 侧飞，沿原方向却还剩 0.030 / 0.126 m/s（全经典 / 交接）。 |
| [T2：历史清零](../../evidence/crazyflie-20261123/results-v1/H_clear/host.csv) | 暖历史对比入口清零，目标和交付路径保持一致。 | 首条命令 −0.018 → −0.081 m/s，倾角峰值 5.80° → 7.17°，后向速度超调更明显。 |
| [T3：接手时读取旧目标](../../evidence/crazyflie-20261123/results-v1/R_stale/host.csv) | 学习外环已接手，却读到 +0.22 m/s 而非 −0.05 m/s，并据此算出向前命令。 | 固件日志首次观测到负目标：正常 15 ms，旧目标 324 ms；前 1 秒净前移 2.8 → 9.9 cm。 |
| [T4：下游仍发送旧输出](../../evidence/crazyflie-20261123/results-v1/D_hold/host.csv) | 学习外环读对参考并算出 −0.018 m/s，下游却继续发缓存的经典 +0.224 m/s。 | 固件日志首次观测到负目标 331 ms；前 1 秒净前移 9.0 cm（正常组 2.8 cm）。 |

T2–T4 共用已冻结的 [正常对照 N_slow](../../evidence/crazyflie-20261123/results-v1/N_slow/host.csv)。详见[前轮结果及复核说明](../../evidence/crazyflie-20261123/README.md)与[数值摘要](../../evidence/crazyflie-20261123/metrics.json)。T3 与 T4 的飞机都晚刹；区分它们，要对照学习器读到了什么、算出了什么、最终发出的是什么。

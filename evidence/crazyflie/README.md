# Crazyflie 2.1 原生固件闭环证据（T1–T4）

[完整案例报告](../../docs/handover/CRAZYFLIE_CASES.md) · [69 组数值摘要](summary.json) · [版本与校验清单](manifest.json)

本目录归档第二飞行平台 **Crazyflie 2.1**（Bitcraze 官方固件 + RLtools 16 维循环 GRU 控制器，与 PX4 RAPTOR 策略同源）的 1000 Hz 锁步闭环实验数据、图谱与可移植复现测试台（`harness/`）。

## 固定上游源码基线

| 组件 | 仓库 | 固定提交 |
| --- | --- | --- |
| 神经飞控外树模块 | `rl-tools/crazyflie-controller` | `3e00e932eb74cceb92a859a4390a5742a7be27af`（历史参照 `deca3ab1`） |
| 16 维 GRU 策略权重 | `rl-tools/crazyflie-controller-blob` | `f546fa32ab57bc5fa37228e22a0a1fd53cc2fb08` |
| 经典飞控固件 | `rl-tools/crazyflie-firmware` | `d92f2b080fbcdd177d46b173cb826d2d3a879078` |
| 官方 l2f 动力学 | `rl-tools/rl-tools` | `6bb2fda96b765e5f1dce915da750022824b9eec5` |

## 目录说明

- `summary.json`：全部 69 组闭环对照与参数扫掠指标（覆盖 T1、T2、T3、T4 及 5 步反事实归因 `cf_attribution`）。
- `figures/`：5 张高分辨率图谱（总览与四步归因 + T1–T4 分项图）。
- `traces/`：64 份压缩后的 500 Hz 闭环轨迹日志（`.csv.gz`）。
- `harness/`：C/C++17 锁步固件闭环测试台源码（`cf_plant.hpp`、`sim_hal.*`、`sim_executor.cpp`、`run_crazyflie_campaign.cpp`、`verify_baseline.cpp`、`stubs/`）及绘图脚本（`plot_crazyflie_evidence.py`）。
- `verify.py`：离线核验脚本，校验所有文件 SHA-256、69 组摘要数值及轨迹一致性。

## 离线核验与本地重跑

在仓库根目录执行离线核验（无需 C++ 编译）：

```bash
python3 evidence/crazyflie/verify.py
```

如需从归档轨迹重绘全部 5 张图谱：

```bash
python3 evidence/crazyflie/harness/plot_crazyflie_evidence.py
```

如需重新编译并跑完 69 组固件锁步闭环，将上述四个上游仓库检出至同一目录后指定 `CF_DEPS_DIR`：

```bash
CF_DEPS_DIR=/path/to/deps bash evidence/crazyflie/harness/build.sh
./evidence/crazyflie/harness/build/run_crazyflie_campaign /tmp/cf_out
```

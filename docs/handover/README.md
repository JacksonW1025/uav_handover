# 双飞控交接证据汇总（T1–T4）

本仓库 `main` 分支保留当前最干净、可离线复核的双飞行平台 **T1–T4** 交接证据：**第一平台 PX4/RAPTOR（X500 SITL，微内核异步 uORB）** 与 **第二平台 Crazyflie 2.1（原生固件 + RLtools 16 维 GRU，1000 Hz 锁步闭环，69 组对照）**。历史探索分支与早期多平台记录归档于独立分支 `archive/pre-cleanup-20261126`。

## 1. 双平台 T1–T4 有效内容总览

| 类别 | 交接闭环位置 | 第一平台：PX4 / RAPTOR（X500 SITL） | 第二平台：Crazyflie 2.1（69 组原生锁步） |
| --- | --- | --- | --- |
| **[T1](T1.md)** 接管后安全余量不足 | 机体动力学与环境余量 | 紧弯三臂（`C2` / `N` / `PRE`）＋ 刹停误差裁剪审计：`C2` `25.895°`（失高 `5.30 cm`）vs `N` `42.900°`（`24.25 cm`）/`PRE` `43.010°`（`22.56 cm`）；[机制图](../../evidence/px4-figures/t1-x500-photo-v12.png) | 紧弯刹停 ＋ 顺风扫掠（`0..1.8 m/s`）：经典 `18.4°–26.2°`（掉高 `1.2–3.3 cm`）vs 理想神经 `46.4°–48.4°`（突破 `47.0°` 推重比上限），掉高 `40.4–55.6 cm`；[图谱](../../evidence/crazyflie/figures/cf_t1_margin_depletion.png) |
| **[T2](T2.md)** 控制器历史状态接续错误 | 策略内部 GRU 记忆 | 直线闭环 `N4/N2`（首拍阶跃 `0.02168 → 0.12972`，首秒失高 `1.33 → 2.63 cm`）＋ 紧弯同帧回放（`0.0873 → 0.1588`，误差 `2.1×10⁻⁷`）；[直线图](../../evidence/px4-figures/t2-closed-loop-straight.png) · [转弯图](../../evidence/px4-figures/t2-tight-turn-v7.png) | 上游 `l2f_reset()` 清零与 `rlt.orig=-0.8` 毒化：逆风偏心直线掉高 `15.9 → 54.3 / 67.6 cm`；右急弯预热存活（`26.6°`）vs 毒化冲至 `2.58 m/s`、`33.1°` 坠毁；[图谱](../../evidence/crazyflie/figures/cf_t2_history_mismatch.png) |
| **[T3](T3.md)** Setpoint 参考接续异常 | 上游参考轨迹接口 | 直线固定载荷（`16/80 ms` 空窗，`2.89° / 7.28°`，含原始 ULog）＋ 三维紧弯六次（`E1` `25.23°/25.11°`，`E2` `156/168 ms` 空窗 `55.28°/55.56°` 中止，`E3` `16 ms` `31.18°/30.29°`，含原始 ULog）；[直线图](../../evidence/px4-figures/t3-reference-mechanism-v6.png) · [转弯图](../../evidence/px4-figures/t3-reference-mechanism-v14.png) | 直线 `0..260 ms`（`4.8° → 31.0°`，掉高 `5.7 → 28.2 cm`）＋ 等高掉头急弯 `0..220 ms`（对齐 `168 ms` 达 `40.8° / 42.4 cm`，`220 ms` 达 `43.2° / 55.6 cm`）＋ 历史 `deca3ab` 丢前馈（偏差 `0.89 m`）；[图谱](../../evidence/crazyflie/figures/cf_t3_setpoint_gap.png) |
| **[T4](T4.md)** 控制权实际交付异常 | 下游电机执行通道 | 悬停双臂（`deadline60` vs `active_release60`）：发布到四电机采用 `24 ms`（第 6 条样本，前 5 条被覆盖）vs `4 ms`（首条样本），含逐条样本审计与 SHA-256 清单；[出弯机制图](../../evidence/px4-figures/t4-turn-exit-mechanism-v8.png) | **T4-A**：上游默认 `motor_warmup=1` 强制 `500 ms` 25% 油门真空（下坠 `-2.62 m/s`，掉高 `173.2 cm`）；**T4-B**：出弯旧差动延续 `0..60 ms` 倾角 `28.7° → 39.1°(24ms) → 50.8°`；[图谱](../../evidence/crazyflie/figures/cf_t4_authority_delivery.png) |
| **反事实归因** | 复合失效逐层剥离 | 各单因严格独立对照（T1–T4 分别隔离构建与验证） | 同初态 5 步归因链（`cf_attribution`）：`85.2°` 翻转 → `41.7°` 坠地 → `32.9°` 坠地 → `25.4°` 存活 → `25.5°` 经典 Oracle；[总览图](../../evidence/crazyflie/figures/cf_overview_px4_alignment.png) |

## 2. 证据目录与校验入口

- **PX4 / RAPTOR 分项文档**：[T1](T1.md) · [T2](T2.md) · [T3](T3.md) · [T4](T4.md) · 机制图目录 [evidence/px4-figures/](../../evidence/px4-figures/)
- **Crazyflie 2.1 分项文档**：[Crazyflie 2.1 案例详情](CRAZYFLIE_CASES.md) · 数据与测试台 [evidence/crazyflie/](../../evidence/crazyflie/README.md)
- **复核与复现指南**：[REPRODUCTION.md](REPRODUCTION.md)（离线校验运行 `python3 tests/check_evidence.py`）
- **历史快照**：早期 PX4 完整定义快照固定在 [141a2b31](https://github.com/JacksonW1025/uav_handover/tree/141a2b31becee1a909e0d76f552b0724eb315f99)。

# Autoware 离线接口对照

记录日期：2026-11-16。本文件独立记录外部系统的公开接口与源码；本仓库当前实证仍聚焦 PX4。

## 三种不同的交接接口

本对照区分参考来源选择、控制器计算切换及最终命令交付。不同接口的观测点不同。

| 接口 | 交接的东西 | 关键证据 |
|---|---|---|
| PX4 RAPTOR 与经典控制 | 直接电机命令的发布权；同时切换了控制器内部计算 | 模式、参考和历史、发布者、四路应用样本、机体响应 |
| Autoware Generator–Selector | 下游跟踪器所用的轨迹来源；跟踪器和与车的接口可以不变 | 候选生成者 ID、选择时刻、轨迹时间原点、跟踪器实际采用数据 |
| VisionPilot–Safety Island | 正常驾驶命令与锁定刹停之间的最终动作决策 | 输入周期、SI 决策/输出序号、CARLA 车体首帧实际应用 |

如果同一条旧目标在下游继续被正常权限的控制器使用，按 T3 诊断；如果已期望换到新的执行权限，实际沿用旧执行样本，按 T4 诊断。同一次运行可以有两处互相独立的异常，分别取证。

## T1–T4 的地面版本

- **T1 恢复余量。** 同一初态下，确认新刹车命令已经应用，再比不同策略的剩余制动距离或转向余量；或在规划层确认可行轨迹被及时采用，再查跟踪器从当前速度与曲率能否跟上。刹车命令送迟所损失的距离归 T4，如果参考切到跳变目标归 T3。未找到官方同入口恢复余量的因果配对；这是具备明确可测量量的对应假设。
- **T2 历史。** 历史不限于 GRU，也可以是上一预测轨迹、已执行转向或优化器热启动。Autoware 排序器有“前次最佳轨迹”和“以前的转向”一致性度量，质量项默认关闭。测试可以固定同一车身状态与同批候选，仅分别保留实际采用的历史、来源自己的预测历史，查首选轨迹及控制输出。此处为机制入口和迁移假设。 Diffusion Planner 的 [固定版本源码：上一轨迹投影](https://github.com/autowarefoundation/autoware_universe/blob/0.53.1/planning/autoware_diffusion_planner/src/diffusion_planner_core.cpp#L291-L353) 会在启用时检查偏移和朝向再采用投影；[模型输入构造](https://github.com/autowarefoundation/autoware_universe/blob/0.53.1/planning/autoware_diffusion_planner/src/diffusion_planner_core.cpp#L435-L466) 使用上一轮预测构造轨迹前缀。[默认配置](https://github.com/autowarefoundation/autoware_universe/blob/0.53.1/planning/autoware_diffusion_planner/config/diffusion_planner.param.yaml) 关闭投影，且 delay_step 为 0，不能把开启选项的假设当默认表现。
- **T3 参考。** 选出的新轨迹需被跟踪者接受并保持当前时钟与任务进度；在 VP/SI 中还要验证路径和速度属于同一相机周期，且能配到同一时刻的车辆状态。官方已查过周期身份和重复样本不刷新有效性，但不是 PX4 式参考捕获的独立复现。建议同时记下候选轨迹、实际接续轨迹、跟踪器采用的第一段。[固定版本 selector](https://github.com/autowarefoundation/autoware_universe/blob/0.53.1/planning/autoware_trajectory_selector/src/trajectory_selector_node.cpp#L231-L273) 的顺序是汇总、校验、排名、适配、发布；无候选、上下文不足或无法适配时，该次处理不发布新轨迹。不能只从该函数断言下游一定继续采用旧轨迹，还要测跟踪器。
- **T4 交付。** SI 的正常/停机决策须沿单一出口走到 CARLA actor；批准输出序号与物理帧上的油门/刹车要能对上。官方原 Ackermann 探针显示，停车请求后约 1.15 s 才出现首个明显刹车帧；单一执行出口的另一组集成验证，从 SI 已经检测到故障到首帧应用刹车约 6–14 ms。两者起点不同。第一例观察到车辆接口的命令语义不符；第二例验证从已检测到实际应用的可追踪响应。两者都是 CARLA actor 控制字段，不能说是实车制动力矩。

## 发布架构与运行配置的区别

Autoware 2.0.0 的发布配置在启动时选择 rule_based 或 diffusion_planner；运行时选择器有源码，但该发布配置未启动它。AutoE2E v1.0 公开结果为开环，实车闭环仍在开发。这两项分别记录，不将其合并描述成默认系统已部署经典与神经的运行时交接。

来源：[Architecture 2.0](https://docs.autoware.org/main/design/autoware-architecture-v2/) · [Generator–Selector 详细接口](https://docs.autoware.org/main/design/autoware-architecture-v2/roadmap/detailed-architectural-interface/) · [Autoware Universe 0.53.1](https://github.com/autowarefoundation/autoware_universe/releases/tag/0.53.1) · [Trajectory Ranker](https://autowarefoundation.github.io/autoware_universe/main/planning/autoware_trajectory_ranker/) · [Safety Island CARLA 控制契约和测试数据](https://autowarefoundation.github.io/autoware-safety-island/design/vp_si_control_contract.html) · [AutoE2E 发布](https://autoware.org/autoware-foundation-and-tier-iv-join-forces-to-releases-autoe2e-an-open-source-ai-model-for-end-to-end-autonomy/)
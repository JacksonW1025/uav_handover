# PX4 / RAPTOR Handover

> 2026-10-24最终更新：**P9授权执行与交付已收尾，原批完整性FAIL保留**。开发10，正式173启动、169条主测量（B48/搜索53/参考35/D33）；102/162/164/169分别披露，7搜索槽未用，不补跑。D有7个完整四臂簇；v3异常后未经另一次显式决定建立v4的流程偏离单列披露。高度仍拒判，跳过分母0，边界搜索有负结果。见[P9最终报告](docs/THOR_P9_FINAL_REPORT.md)。


> 2026-10-24 v2更新：**P9仍未完成**。用户批准后新适配器24项无飞行测试和160条字节兼容通过，冻结0050ecee后启动2/11条。D07-C通过；D07-R首接回前安全中止，新测量成功但原P7缺恢复数据门失败，按规则停批。累计164启动、161条主测量；余9条未启动，102/162/164分别保留。见[P9 v2报告](docs/THOR_P9_CONTINUATION_V2_REPORT.md)。


> 2026-10-24续接更新：**P9再次按测量异常停批，尚未全部完成**。开发10；正式162启动、160条完成冻结测量；原102缺失，第162次已飞行失败但冻结P9首开口中断分析异常。参考35/36，D24条完成＋1条异常、11条未启动。原101/续接59逐条原始重测通过，两批整体完整性仍FAIL；无重跑。见[P9续接报告](docs/THOR_P9_CONTINUATION_REPORT.md)。


NVIDIA Jetson AGX Thor 上的 PX4 经典控制、RAPTOR 神经控制、C → N → C 双向交接及控制器状态干预研究。2026-10-09 已完成本机环境建设和真实 headless SITL 验证。

> 2026-10-24：**P9阶段证据已保存，执行中断，任务未全部完成**。新模型与冻结设计、B48及C搜索53已完成；第102次启动因执行会话失联而中断，参考有效0/36、D0/36。101条完成记录原始重测逐条通过，全批完整性审计仍FAIL。见[P9报告](docs/THOR_P9_REPORT.md)与[冻结计划](docs/THOR_P9_PLAN.md)。没有自动重跑、放宽判据或改写旧P8结果。

> 2026-10-15：**P2 完成**（RAPTOR 接管时的内部状态干预），见 [P2 报告](docs/THOR_P2_REPORT.md)；P1（原始双向交接性能）见 [P1 报告](docs/THOR_P1_REPORT.md)。
>
> 2026-10-12：**P0 完成**，判定依据见 [P0 报告收尾节](docs/THOR_P0_FINAL_REPORT.md#2026-10-12-p0-收尾判定完成)。2026-10-10 的历史 FAIL 记录保留；旧环境验收 PASS 本身不代表 P0 完成。

- [环境检查](Environment%20Check.md)
- [实验状态](Experiment%20Status.md)
- [实验 Quickstart](docs/THOR_EXPERIMENT_QUICKSTART.md)
- [最终验收报告](docs/THOR_ENVIRONMENT_FINAL_REPORT.md)与[验收矩阵](docs/THOR_ACCEPTANCE_MATRIX.md)
- [机体和电机映射](docs/THOR_PLATFORM_MAPPING.md)
- [环境锁定](environment.lock)、[实验配置](config/experiment.json)、[数据索引](data/README.md)

```bash
./tools/experiment health
./tools/experiment classic_hover
./tools/experiment raptor_hover
./tools/experiment handover_c_n_c
./tools/experiment state_restore
```

整个 `uav_lab/` 属于本机环境并被 Git 忽略。仓库保存研究源码、补丁、配置、每轮实验的配置/身份/事件/日志/指标/判定/图、批次复核和报告；大体积原始飞行数据（ULog、逐物理步电机轨迹、逐帧遥测）只保存在实验机本地，仓库保留三个完整示例 ULog，见 [数据保存策略](data/README.md#数据保存策略)。克隆后需按锁清单准备 Lab。运行资源来自当前 Lab，系统 ROS 2、Gazebo、CUDA 继续使用本机安装。重建步骤见 Quickstart。

当前验收范围为冻结 x500 配置的短时 SITL，神经控制窗口由经典控制起飞和降落。完整训练动力学元数据、长时间统计验证及完整 EKF/FlightTask 状态快照仍超出当前验证范围，详见最终报告。

2026-10-11 准备阶段：候选版本与启动/链路观测改动见 [准备记录](docs/THOR_PREPARATION_20261011.md)。历史 P0 FAIL 保持；批次结果另存，不替换旧验收。

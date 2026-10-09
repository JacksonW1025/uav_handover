# 最终验收矩阵

机器可读命令、退出码和逐轮证据见 [acceptance.json](../data/environment-20261009/acceptance.json)。PASS 限于测试声明范围。

| 测试 | 内容 | 结果 | 证据 |
|---|---|---|---|
| TEST-01 | Lab 环境加载与路径隔离 | PASS | [final-health-classic.log](../data/environment-20261009/final-commands/final-health-classic.log) |
| TEST-02 | Python 关键依赖、ABI 与 pip check | PASS | [final-health-classic.log](../data/environment-20261009/final-commands/final-health-classic.log) |
| TEST-03 | classic ROS overlay / Python / C++ pubsub | PASS | [final-ros-classic.log](../data/environment-20261009/final-commands/final-ros-classic.log) |
| TEST-04 | raptor ROS overlay / Python / C++ 接口 | PASS | [final-ros-raptor.log](../data/environment-20261009/final-commands/final-ros-raptor.log) |
| TEST-05 | 经典 PX4 SITL 正常启动 | PASS | [validation.json](../data/final-classic-relative-03/validation.json) |
| TEST-06 | Gazebo x500、传感器和电机插件实际工作 | PASS | [validation.json](../data/final-classic-relative-03/validation.json) |
| TEST-07 | 经典控制短时悬停 | PASS | [validation.json](../data/final-classic-relative-03/validation.json) |
| TEST-08 | 实际 PX4↔ROS 双向通信、Agent 重连 | PASS | [validation.json](../data/final-classic-relative-03/validation.json) |
| TEST-09 | 生成并解析本轮新 ULog | PASS | [validation.json](../data/final-classic-relative-03/validation.json) |
| TEST-10 | 真正启用 MC_RAPTOR / RL Tools 的构建 | PASS | [final-build-raptor.log](../data/environment-20261009/final-commands/final-build-raptor.log) |
| TEST-11 | RAPTOR 模块启动与动态模式注册 | PASS | [validation.json](../data/verified-raptor_hover/validation.json) |
| TEST-12 | 冻结策略加载、自测、有限推理与时序 | PASS | [validation.json](../data/verified-raptor_hover/validation.json) |
| TEST-13 | 机体/电机映射在当前冻结平台验证 | PASS | [validation.json](../data/verified-raptor_hover/validation.json) |
| TEST-14 | 神经独立控制窗口稳定悬停 | PASS | [validation.json](../data/verified-raptor_hover/validation.json) |
| TEST-15 | C→N 模式、实际执行器归属和悬停 | PASS | [validation.json](../data/verified-raptor_hover/validation.json) |
| TEST-16 | N→C 实际恢复经典执行器输出 | PASS | [validation.json](../data/verified-raptor_hover/validation.json) |
| TEST-17 | 完整 C→N→C | PASS | [validation.json](../data/verified-raptor_hover/validation.json) |
| TEST-18 | 三类状态 READ / RESET / SNAPSHOT / HOLD / RESTORE | PASS | [validation.json](../data/verified-state_reset/validation.json) |
| TEST-19 | 受控注入与非法输入/活动写入拒绝 | PASS | [validation.json](../data/verified-state_injection/validation.json) |
| TEST-20 | 执行器归属、交接与状态事件日志完整 | PASS | [validation.json](../data/verified-raptor_hover/validation.json) |
| TEST-21 | 自动运行、降落、结束与数据保存 | PASS | [validation.json](../data/final-classic-relative-03/validation.json) |
| TEST-22 | 日志解析、指标和可视化 | PASS | [validation.json](../data/final-classic-relative-03/validation.json) |
| TEST-23 | 连续三轮基础实验与三次交接稳定性 | PASS | [validation.json](../data/final-classic-relative-01/validation.json) |
| TEST-24 | 活动路径不依赖旧仓库 | PASS | [final-health-classic.log](../data/environment-20261009/final-commands/final-health-classic.log) |
| TEST-25 | Git 忽略整个 Lab，保留实验源码和原始证据 | PASS | [git-boundaries.log](../data/environment-20261009/final-commands/git-boundaries.log) |

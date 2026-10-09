# Thor 实验 Quickstart

全部飞行操作限本机 headless SITL。项目目录 `/home/car/uav_handover`，本机 Lab 为 `uav_lab/`，每轮新数据存入 `data/`。完整验收见 [最终报告](THOR_ENVIRONMENT_FINAL_REPORT.md)。

## 日常入口

```bash
cd /home/car/uav_handover
./tools/experiment health
./tools/experiment classic_hover
./tools/experiment raptor_hover
./tools/experiment handover_c_n_c
./tools/experiment repeated_handover
./tools/experiment state_reset
./tools/experiment state_hold
./tools/experiment state_restore
./tools/experiment state_injection
```

各命令实际启动组件、检查 DDS 双向通信和 Agent 重连、执行飞行、降落、保存并解析新的 ULog；成功退出 0，失败退出非 0。失败数据同样保留，不自动删除或覆盖。`handover_c_to_n`、`handover_n_to_c` 也执行包含指定方向的完整 C→N→C，便于安全返回。

`raptor_hover` 使用经典控制起飞，在约 3 m 高度由 RAPTOR **独立控制执行器**至少 5 秒，再回经典控制降落。它不代表神经控制起飞或着陆已验证。经典悬停窗口至少 10 秒，重复交接默认 3 次。当前冻结阈值：位置误差 ≤1 m、倾角 ≤15°、推理 P99 ≤2500 μs；仿真保护范围及其余参数见 [配置](../config/experiment.json)。

可明确指定新的输出目录和实验配置：

```bash
./tools/experiment handover_c_n_c --output data/my-new-handover --config config/experiment.json
./tools/experiment classic_hover --hover-s 15
```

输出目录必须不存在。同一设备的本项目实验通过锁串行运行；默认 PX4 instance=21、system_id=22、DDS Domain=71、Agent UDP=18888。更改配置时同时检查端口和实例占用；运行器只控制本轮创建的进程，不接管已有 PX4。

## 查看结果

每轮目录包含：

| 文件 | 内容 |
|---|---|
| `config.json`、`metadata.json` | 冻结配置、源码提交、差异摘要、二进制/策略哈希、模式 ID、环境、实际启动命令 |
| `events.jsonl` | 请求、应答、模式确认、状态操作及实际生效时间、启动/退出事件 |
| `flight.ulg` | 本轮原始 PX4 日志 |
| `telemetry.jsonl`、`resources.jsonl` | ROS 遥测与本机资源采样 |
| `metrics.json`、`validation.json` | 指标、逐窗口判断、失败原因 |
| `overview.png`、`trajectory.png` | 状态/电机/模式时间线与空间轨迹 |
| `logs/` | PX4、Gazebo、Agent、命令、统计、温度功耗、分析输出 |
| `rootfs/`、`cli/` | 本机运行副本，Git 忽略 |

```bash
cat data/my-new-handover/validation.json
cat data/my-new-handover/metrics.json
./tools/experiment analyze data/my-new-handover
```

DDS 时间戳会被 Agent 转换至 UTC。分析器用 ROS 与 ULog 中完全一致的位置向量建立对应，再按仿真时间对齐；外部事件定位约有 0.1 秒采样不确定度。实际执行器归属另用 PX4 内部时间戳判断。不要把外部模式确认延迟当成精确的内部输出切换延迟。

## 状态实验语义

接口仅编入 POSIX/SITL，`MC_RAPTOR_RSH=0` 默认关闭；运行器在自检后启用。

| 对象 | 数值布局 | 支持范围 |
|---|---|---|
| `raptor` | 16 维 GRU + 4 维 previous_action + 3 维 NED 参考位置 + 3 维 NED 参考速度 | 26 维，固定检查点布局 |
| `rate` | x/y/z 角速度积分器 | 3 维，使用 PX4 实际积分限制 |
| `velocity` | x/y/z 速度积分器 | 3 维，研究写入限绝对值 4 |

`READ` 读取；`SNAPSHOT` 保存本模块一个内存槽；`RESET` 清记忆（RAPTOR 保留参考）；`HOLD` 冻结上述数值，仍用当前观测计算控制；`RELEASE` 恢复更新；`RESTORE` 恢复槽；`INJECT` 要求精确维度、有限值和范围。

活动控制器允许读、快照、重置、保持；拒绝恢复/注入。非活动控制器允许受控恢复/注入。失败返回明确错误码，整包检查后才写入。所有写入由控制器自己的线程在周期边界执行，响应和 ULog 记录生效时间。

非活动经典位置控制器仍有 PX4 原有积分清零行为；要跨模式保留恢复值，先 HOLD，再 RESTORE，进入经典模式后 RELEASE。神经控制器默认进入模式时重置；恢复/注入对照显式使用 `MC_RAPTOR_RINI=1`，重建执行器时序后保留指定记忆。此开关只在研究接口启用时生效。两类策略均记录到参数和事件。

`state_reset` 对激活的 RAPTOR 及待机经典积分器重置；`state_hold` 保持神经记忆一个控制窗口；`state_restore` 在两次神经窗口间恢复快照，并恢复经典积分器；`state_injection` 在经典控制期间注入 GRU=0.02，然后保持至神经接管并释放。各类实验都先执行受控状态接口自检。

快照不包含 EKF、FlightTask、滤波器、Lissajous 轨迹发生器的全部状态，也不跨 PX4 进程持久化。当前参考实验限定 `MC_RAPTOR_INTREF=0`。高维隐藏状态按事件记录，未持续高频记录。

## 重新构建与故障定位

```bash
source uav_lab/env.sh classic
source uav_lab/env.sh raptor
./tools/prepare_lab.sh
```

`prepare_lab.sh` 复用已有 Lab、安装隔离依赖、构建两套 overlay 和 PX4；不重新下载、迁移或清空资源。依赖和版本见 [environment.lock](../environment.lock)。Lab 缺失时先按锁清单准备固定资源；主仓库克隆本身不携带 Lab。

重新准备缺失的 Lab 时，使用归档资源或锁中固定提交和递归子模块，建立以下布局：

```text
uav_lab/sources/{px4-classic,px4-raptor,px4-msgs-classic,px4-msgs-raptor,px4-ros2-interface,xrce-agent}
uav_lab/.local/checkouts/{px4-classic,px4-raptor,xrce-agent}  # 独立 Git 元数据
uav_lab/manifests/{sources.json,snapshot-files.json}        # 原归档清单
uav_lab/workspaces/{classic,raptor}/src/
```

ROS 两套 `src/px4_msgs` 分别相对链接到 `../../../sources/px4-msgs-classic`、`../../../sources/px4-msgs-raptor`；raptor 的 `src/px4_ros2_cpp` 链接到 `../../../sources/px4-ros2-interface/px4_ros2_cpp`。必须保留固定 blob 和 RL Tools 子模块。

在干净 RAPTOR 固定检出中，应用一次 `patches/raptor-final.patch`，展开 `patches/raptor-final-untracked.tar.gz`；该补丁已经包含原有 RouteObservability，不能再叠加 `raptor-existing.patch`。干净 ROS interface 固定检出应用 `ros2-interface-existing.patch`。若资源本来就是带原有修改的快照，则使用 `tools/apply_research.py`，不要重复应用 existing 补丁。

Agent 可用已有 runtime；需要重建时在准备好的固定 checkout 上执行：

```bash
cmake -S uav_lab/.local/checkouts/xrce-agent -B uav_lab/.local/agent-build \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="$PWD/uav_lab/.local/runtime/xrce-agent"
cmake --build uav_lab/.local/agent-build -j8
cmake --install uav_lab/.local/agent-build
```

保留 Lab 的 `scripts/MicroXRCEAgent` 包装入口，使其设置 runtime/lib 并执行 runtime/bin/MicroXRCEAgent。然后运行 `./tools/prepare_lab.sh`、两套 health 和实际实验入口。上述缺失 Lab 重建说明没有在当前设备重复下载或重迁移资源；本轮实际执行的是已有资源的本地编译与验证。

健康检查不会重新执行飞行。重新验收时，每类实验必须使用新输出目录，并保存实际退出状态；`tools/acceptance.py` 汇总的是本报告约定的最终目录，新增验收轮次应同时更新其目录清单，不能直接将旧 PASS 当作新环境结论。

先看本轮 `validation.json` 的原因，再看 `logs/px4.log`、`logs/gazebo.log`、`logs/agent*.log` 和 `logs/commands.log`。模型存在而无传感器时检查 `GZ_SIM_SERVER_CONFIG_PATH`；消息存在而收不到时检查对应版本后缀、overlay、QoS 和 Domain；状态写入拒绝时检查活动状态和边界。`health` 只负责健康检查，飞行能力须由具体实验入口验证。

没有修改系统、驱动、CUDA 主版本或策略权重。策略训练的完整动力学参数未随检查点提供；250 Hz Gazebo 下原实现将 native 同步设为 2 步，约 125 Hz，区别于训练 100 Hz。正式对照须固定并报告该条件，当前结果只支持此配置的短时实验。

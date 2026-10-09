# Environment Check

> Git 管理规则更新（2026-10-09）：整个 `uav_lab/` 是本机环境，全部忽略；远端只保留 Lab 外的项目实验源码、实验数据和文档。本次仅更新管理规则，未重新验证运行环境。

更新时间：2026-10-08 21:37:53（Asia/Shanghai，UTC+8）；初始检查：2026-10-08 20:52–20:56；资源整合与完整校验：2026-10-08 21:33。设备为 NVIDIA Jetson AGX Thor Developer Kit，aarch64、14 核 CPU、Ubuntu 24.04.3 LTS。

总体判断：项目资源已统一到 `/home/car/uav_handover/uav_lab`，基础 PX4 SITL 的源码、运行文件和仿真资源齐备，具备开始复核的资源条件；新 Lab 的 Python 依赖及 ROS overlay 尚不完整，不能认定完整实验链路已可运行。RAPTOR 当前运行文件未启用该模块，双向交接尚待构建和验证；状态干预仍需开发。

本报告以整合后的目录和环境入口为准，替代旧报告中以其他仓库为实验资源入口的描述。本轮复核只读取资源、版本、进程和依赖，并更新本文及 `.gitignore`；没有安装、修复、编译、启动仿真或停止已有进程。此前已按要求复制项目资源并创建 Lab 入口，不再沿用“仓库未写入”的旧检查边界。

## 当前资源布局

统一根目录 L=`/home/car/uav_handover/uav_lab`。下表路径均相对 L，除非标出绝对路径；A 指经典版本，B 指含 RAPTOR 的版本。

| 资源 | 当前目录与用途 |
|---|---|
| 本机上游源码/资源 | `sources/px4-classic`、`sources/px4-raptor`、`sources/xrce-agent`、两套 `sources/px4-msgs-*`、`sources/px4-ros2-interface`；位于整体忽略的 Lab 内，无嵌套 Git 元数据 |
| 本机独立 Git 检出 | `.local/checkouts/{px4-classic,px4-raptor,xrce-agent}`；用于后续构建，保留各自提交及递归子模块；被 Git 忽略 |
| 已有运行文件 | `.local/runtime/{px4-classic,px4-raptor,xrce-agent}`；仅复制二进制、PX4 启动资源和插件，没有旧构建缓存/运行参数/日志 |
| ROS 消息/接口工作空间 | `workspaces/{classic,raptor}/src`；通过相对链接引用本 Lab 源码；尚无本 Lab 的 install overlay |
| 环境入口/辅助源码 | `env.sh`；`scripts/MicroXRCEAgent`、`check_lab.py`、`mavlink_probe.py`、`px4_mission.py`、`px4_gz_flight.py` |
| 清单与新实验数据 | `manifests/` 记录来源、提交、已有修改、复制校验；`requirements/` 保留依赖清单；新数据目录为 `/home/car/uav_handover/data` |

源码/资源约 2.4 GiB，本机 Git 检出与运行文件约 6.4 GiB。未导入旧实验 runs/results/logs、uav3d、旧虚拟环境或系统 Python/ROS 安装。原目录保留，当前环境入口及运行库解析不读取它们；来源记录中的旧位置仅用于溯源。

## 直接依赖与准备状态

“已验证可用”仅覆盖表中具体通过的查询/轻量检查，不等于完整飞行链路通过；资源存在、构建产物存在和运行验证分别判断。

| 所需环境 | 当前发现与版本或路径 | 准备状态 | 缺口或下一步 |
|---|---|---|---|
| 系统与容量 | Ubuntu 24.04.3，aarch64，14 核；内存 122 GiB、当前可用约 110 GiB，无 Swap；根分区 937 GiB、剩余约 243 GiB（/home 同分区） | 已验证可用 | 资源余量为本次查询值；未做实时性能测试 |
| JetPack/L4T | R38.2.1；nvidia-l4t-core 38.2.1-20250910123945；初检 dpkg 未查到 JetPack/runtime/dev 元包记录 | 已发现，待运行验证 | 不根据 L4T 推断完整 JetPack 元包版本或组件覆盖；未找到元包不等于组件未安装 |
| ROS 2 Jazzy | 系统 `/opt/ros/jazzy`；ros2cli 0.32.6；本次通过新 Lab 入口加载后 `ros2 --help` 成功；Fast DDS/Cyclone DDS 包初检已发现 | 已验证可用 | 只验证安装与 CLI；本 Lab 消息解码和节点通信未运行验证 |
| 环境加载 | `source uav_lab/env.sh classic` 或 `raptor`；清除继承的 overlay/Conda 路径后加载系统 Jazzy；Python 选 `/usr/bin/python3` 3.12.3 | 已验证可用 | 两套入口路径检查均通过；未修改用户 .bashrc；普通终端原有环境不等于 Lab 入口环境 |
| ROS 工作空间构建 | `workspaces/{classic,raptor}/src` 的消息/接口链接均位于 L 内；未复制旧 install/build/log，当前未发现本 Lab 的 install 目录 | 缺失 | 当前缺少本 Lab 已构建的 overlay；初检旧仓库 px4_msgs CLI 成功不能算新工作空间已可用 |
| PX4 经典源码 A | `sources/px4-classic` 及 `.local/checkouts/px4-classic`；v1.17.0，detached HEAD，提交 `d6f12ad1c4f70ad3230afd7d86e971421e02fef4`；本机检出 status 干净 | 已发现，待运行验证 | 未重新编译或飞行；A 未发现 RAPTOR 模块，适合作为经典基线候选 |
| PX4 RAPTOR 源码 B | `sources/px4-raptor` 及 `.local/checkouts/px4-raptor`；detached HEAD，提交 `4ae21a5e569d3d89c2f6366688cbacb3e93437c9` | 已发现，待运行验证 | 保留原有控制链修改及未跟踪 RouteObservability 文件，来源状态/补丁在 manifests；不能视为未改动的原始基线 |
| 子模块与复制完整性 | 六套源码共 89,867 个条目校验一致；独立 Git 检出的提交和递归子模块固定提交检查通过；B RL Tools `15940da2...`、blob `bc6683a9...` | 已验证可用 | 验证范围为文件/链接完整性、固定提交；不证明全部子模块内部无修改或可编译 |
| 已有 SITL 运行产物 | `.local/runtime/px4-{classic,raptor}/bin/px4`：复制的 aarch64 ELF；相应 etc/ 和 plugins/ 已在 L 内；两套二进制及插件 ldd 通过且不解析到旧仓库 | 已发现，待运行验证 | 本机有既有构建产物，未重新构建或启动；运行目录不是增量构建目录，未带旧参数/rootfs |
| 已启用 RAPTOR 的运行产物 | B 的现有运行副本来自未启用 MC_RAPTOR/RL_TOOLS 的 default 构建；原配置与符号检查已确认 | 缺失 | 在 L/.local/runtime 与本次复制范围内未发现启用 RAPTOR 的产物；消息生成文件存在不代表模块已编入 |
| Gazebo 与匹配线索 | 系统 standalone Harmonic/libgz-sim8 8.14.0；Lab 加载后 vendored `gz sim --versions`=8.11.0；PX4 动态依赖使用 transport13、msgs10 | 已发现，待运行验证 | 同属 Harmonic 代际；库解析通过，当前版本组合的模型/插件加载与仿真运行仍未验证 |
| 机体/世界资源 | 两套 `sources/px4-*/Tools/simulation/gz/{models,worlds}`；有 x500、x500_base、传感器变体及 default.sdf 等，PX4 airframe 含 gz_x500/SIH quadx | 已发现，待运行验证 | 入口只指向 L 内模型/世界/插件；未验证模型加载或 RAPTOR 对该机体的适配 |
| RAPTOR 模块与构建支持 | `sources/px4-raptor/src/modules/mc_raptor`；CMake 依赖 RL Tools/blob、C++17；`boards/px4/sitl/raptor.px4board` 启用模块 | 已发现，待运行验证 | 配置和完整子模块资源已有，目标编译未验证 |
| 策略检查点 | `sources/px4-raptor/src/modules/mc_raptor/blob/{policy.h,policy.tar,benchmark.h}`，policy.tar 约 133 KiB；blob 提交 `bc6683a9a2cff29bede2add18c0d7e3ac0cc9c27` | 已发现，待运行验证 | 策略已复制且校验一致；新运行目录尚未准备 `PX4_STORAGEDIR/raptor/policy.tar`，未执行加载/自测 |
| 策略与机体适配 | B 源码配置 FLU 观测、四动作、Crazyflie→PX4 Quad-X 电机重排、10 ms 训练时间步和 SITL 时序阈值 | 受限未验证 | 质量、推力曲线、动作范围、转子顺序、时序和推理延迟均需实测 |
| RAPTOR 激活/退出 | `mc_raptor start/status`；rc.mc_apps 按 MC_RAPTOR_ENABLE 启动；MC_RAPTOR_OFFB 支持替代 Offboard 或独立外部模式，nav_state 对动态 mode_id 激活 | 已发现，待运行验证 | 当前运行副本不能执行该模块；注册、独立悬停、C→N→C 和返回经典控制未验证 |
| ROS 2↔PX4 链路 | uXRCE-DDS Client 源码在两套 PX4 内；Agent 源码/运行文件/包装入口都在 L 内；MAVLink/MAVROS 是另一个请求与反馈入口 | 已发现，待运行验证 | 本次 ps 曾短暂发现 Agent/PX4/ROS 进程，后续查询已退出或不可读；未确认所属实验、节点或话题，不作为通信成功证据 |
| Agent/Client 匹配 | Agent v2.4.3 @ `73622810d984...`；两套环境下 `scripts/MicroXRCEAgent udp4 --help` 返回成功，未启动服务；A Client 2.4.0；B 另有 3.0.1 源码，但复制产物原配置未启用 v3 | 已发现，待运行验证 | 需验证 UDP 传输、DDS 类型与消息后缀；v3 源码存在不代表产物使用 v3 |
| px4_msgs/ROS 接口 | `sources/px4-msgs-classic` 2.0.1 @ `86d8239e...`；`sources/px4-msgs-raptor` @ `18ecff03...`；interface @ `c3e410f0...`；已有匹配各自关键模式/状态消息字段的检查线索 | 已发现，待运行验证 | 字段比较非完整类型验证；接口库保留已有修改，详见 sources.json；新 overlay 尚未构建 |
| 基础开发工具 | 初检 Git 2.43.0、GCC 13.3.0、CMake 3.28.3、Ninja 1.11.1；本次 Lab 入口选系统 Python 3.12.3 | 已验证可用 | 命令/版本证据；没有编译验证，不再依赖原 Conda 或 PX4 venv |
| 当前系统 Python 的已发现依赖 | 分发元数据：empy 3.3.4、Jinja2 3.1.2、NumPy 1.26.4、PyYAML 6.0.1、packaging 24.0、jsonschema 4.10.3、typeguard 4.1.5；requirements 清单已在 L 内 | 已发现，待运行验证 | 未穷尽 requirements 或执行实际生成/编译；旧虚拟环境依赖版本不再代表新 Lab |
| 当前 Python 的关键缺项 | `/usr/bin/python3` 的分发元数据和 find_spec 均未发现 `pyulog`、`pymavlink`、`kconfiglib`；本 Lab 未创建专用虚拟环境 | 缺失 | 仅指当前选定 Python；不等于全机未安装。分别影响日志分析、MAVLink 辅助脚本及源码配置/构建，后续在本 Lab 准备依赖 |
| 模式请求/状态反馈 | PX4 DDS 配置有 vehicle_command、vehicle_command_ack、vehicle_status、trajectory_setpoint/offboard_control_mode；系统 MAVROS 2.14.0；MAVLink 辅助源码已复制 | 已发现，待运行验证 | 命令响应、控制源互斥、恢复经典控制未验证；辅助脚本还缺当前 Python 的 pymavlink |
| ULog 与分析 | 日志源码支持 actuator_motors、参考及 rate_ctrl_status；系统 rosbag2 MCAP 0.26.11；新数据目录 `/home/car/uav_handover/data`；不导入旧 ULog | 已发现，待运行验证 | 新日志落盘、完整字段、时间同步未验证；当前 Python 缺 pyulog，旧环境成功解析日志不代表新 Lab 已可分析 |
| RAPTOR 诊断/电机记录 | B 发布 raptor_input（观测/previous_action）、raptor_status（active/exit_reason/参考/时序），active 时发布 actuator_motors；logger 含既有 route_observability 插桩 | 后续实验开发项 | 已查默认 logger/DDS 配置未见 RAPTOR 两类诊断的显式项，需明确采集/导出；没有新实验日志 |

## GPU/CUDA 辅助条件

| 所需环境 | 当前发现与版本或路径 | 准备状态 | 缺口或下一步 |
|---|---|---|---|
| GPU/驱动查询 | 本次 nvidia-smi 查询成功：NVIDIA Thor，驱动 580.00 | 已验证可用 | 仅验证识别/查询，未做 GPU 计算或仿真渲染测试 |
| CUDA 工具 | `/usr/local/cuda-13.0/bin/nvcc` 13.0.48，本次版本查询成功 | 已验证可用 | 未编译 CUDA 项目；不是此次先导实验的直接门槛 |
| RAPTOR 后端 | B 源码 POSIX 路径使用 RL Tools DefaultCPU，非 POSIX 为 ARM 后端 | 已发现，待运行验证 | 不要求默认安装 PyTorch，也不默认 GPU 推理；实际推理可用性和延迟未验证 |

## 状态干预能力

| 所需环境 | 当前发现与版本或路径 | 准备状态 | 缺口或下一步 |
|---|---|---|---|
| GRU/递归状态 | B executor 为私有成员；reset() 调用 RL Tools reset，进入神经模式时重置 | 后续实验开发项 | 尚无已发现的外部读写/快照恢复/指定初始化 API，需设计重置、保留与映射语义 |
| 上一动作 | raptor_input 含 previous_action，reset 默认置 0（动作域 [-1,1]） | 后续实验开发项 | 字段可诊断但采集待准备；指定注入与经典电机动作归一化映射需开发 |
| 参考 | raptor_status 有 internal_reference_position/linear_velocity；MC_RAPTOR_INTREF 和 intref lissajous 命令已有 | 已发现，待运行验证 | 轨迹参数入口不等于全部参考状态精确读写；需对齐 C/N 参考与坐标系 |
| 经典积分器 | rate_ctrl_status 有三轴速率积分项；PositionControl 私有 _vel_int 与 resetIntegral()/XY，RateControl 有 resetIntegral() | 后续实验开发项 | 内部 C++ 方法不是外部实验 API；补速度积分器诊断及两类积分器注入/保留/恢复 |
| 反复交接与因果记录 | B 有既存 RouteObservability 修改和 active 边沿逻辑，已随源码复制 | 后续实验开发项 | 审核既有插桩；补交接事件、发布源、快照、时戳和初始化策略，之后验证重复交接 |

## Git 与证据管理

| 所需环境 | 当前发现与版本或路径 | 准备状态 | 缺口或下一步 |
|---|---|---|---|
| Git 忽略边界 | 整个 `uav_lab/`（含 sources、策略、模型、manifests、检出和运行文件）忽略；Lab 外的项目源码、data、docs 保留 | 已验证可用 | 已移除 Lab sources 的提交例外；本机文件保留，不删除 |
| 校验清单 | `manifests/sources.json`、snapshot-files.json、copy-verification.json、runtime-verification.json；本次 check_lab.py 再次通过轻量路径/依赖验证 | 已验证可用 | 完整 SHA-256 校验记录为整合轮；本次未再次复制或重建资源 |
| 远端可复现性 | Lab 源码快照、Git 元数据与运行产物均不上传；需版本管理的实验源码放到 Lab 外 | 受限未验证 | 新机器克隆后需单独准备整个 Lab；克隆仓库不会带入本机实验环境 |

资源查找/验证范围为 L、系统 `/opt/ros/jazzy`、系统 Python、dpkg、GPU 查询及进程列表。旧仓库仅是整合来源，不作为本次依赖查询入口；没有全盘或容器镜像扫描。“缺失”限定到当前 Lab 或选定 Python；未找到不推断为全机未安装。RAPTOR 判断依据本 Lab 同版本源码与子模块，没有套用其他版本在线文档。

## 三项结论

1. **基础 PX4 SITL：具备开始复核的资源条件。** 本 Lab 的经典源码、ARM 运行产物、Harmonic 资源和动态库解析检查通过；完整脚本/日志实验尚需本 Lab Python 依赖和 ROS overlay，当前悬停、模式切换及日志采集未验证。
2. **RAPTOR 原始双向交接：尚不具备直接运行的完整条件。** 模块、策略、RL Tools 和构建配置已整合，但启用 RAPTOR 的产物缺失，策略运行路径/机体适配未验证，源码已有修改需确定基线；独立悬停与 C→N→C 均未运行验证。
3. **状态干预：仍需开发。** 增加 GRU、上一动作、参考及经典积分器的受控诊断/注入/初始化接口，补齐 RAPTOR 采集和交接事件记录，再验证反复交接。

## 下一步（仅建议，本轮不执行）

1. 在本 Lab 准备所需 Python 依赖与匹配的 ROS overlay，不再加载旧仓库环境。
2. 用经典版本复核 SITL 独立悬停、模式反馈和新 ULog 落盘；本轮未实际启动。
3. 审核 RAPTOR 源码已有修改，确定基线后准备启用模块的构建与策略运行路径；本轮未编译或加载策略。
4. 验证 RAPTOR 独立悬停、机体/电机/时序适配，再验证一次 C→N→C 和完整日志；本轮均未运行。
5. 基础交接通过后开发状态干预与重复交接插桩，保持源码/数据/文档和本机环境的 Git 边界。

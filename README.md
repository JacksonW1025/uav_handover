# PX4 / RAPTOR 交接研究环境基线

此分支保留Thor上的经典/神经控制交接基础环境、源代码注入、配置、启动、日志和基础测试，不携带历次实验批次与搜索方法。

2026-11-16 的独立小型证据与工作记录见 [T1–T4 当前工作](docs/handover/README.md)。这些新增材料与固定环境基线分开保存，不改变 `environment.lock`，也不将后期运行能力归给早期环境锚点。

## 版本与范围

- 新分支：`research/handover-baseline-20261115`。来源为平台验收提交 `8d0c4166fb8a6f9adb9dbba9f5758f13c6d8446e`，保留历史祖先，不改旧分支、不合并main。
- 采用这份早期、完整匹配的环境锚点，而不是把后期搜索工具和不同版本补丁拼在一起。[environment.lock](environment.lock)仍为原始环境锁，不代表当前Thor运行目录的实时状态。
- 平台：Jetson AGX Thor / aarch64、Ubuntu 24.04、ROS 2 Jazzy、Gazebo Harmonic；仅headless SITL，不支持真实飞行。
- 保留经典/神经悬停、C→N→C、重复交接及状态read/reset/hold/restore/inject基础接口。后期高频四电机物理步审计、P11/P12、H/P搜索和F1 runner没有移入此基线，不能用本版本宣称已具备这些测量能力。

## 目录

|目录或文件|内容|
|---|---|
|`environment.lock`、`requirements-research.txt`|固定源码/子模块身份、环境记录与Python依赖；部分依赖是范围约束，不是完整离线包锁|
|`config/experiment.json`|实例、端口、控制窗口、保护范围与日志配置|
|`research/state/`|POSIX/SITL状态操作、uORB消息、执行器归属与周期测量源码|
|`patches/`|匹配上述环境锚点的PX4与ROS接口补丁和小型源码归档|
|`tools/`|环境准备、自检、启动、日志分析和基础审计|
|`tests/`|状态操作C++单元测试、ROS探针、无Lab静态检查|
|`docs/`|操作、平台映射及本次整理核验说明|
|`uav_lab/`|本地独立Lab，Git忽略，仓库不携带|

## 获取干净工作副本

```bash
git clone --single-branch --depth 1 --branch research/handover-baseline-20261115 \
  https://github.com/JacksonW1025/uav_handover.git uav_handover_baseline
cd uav_handover_baseline
python3 tests/check_baseline.py
```

当前树不含历史批次，但Git祖先仍保留历史数据。干净树不等于完整仓库体积变小；只需要基线时使用上述浅克隆。旧源码、旧数据与远端引用均未删除。

## 环境准备与运行

**仅clone不能从零直接起飞。** 还需要锁中匹配的PX4及递归子模块、策略blob、px4_msgs/ROS接口源码、ROS overlays、XRCE Agent、venv和系统依赖，以及Lab manifests。它们不随本分支发布。已有Thor Lab持续演进，不能把它直接当作本锚点的同版本资源，也不要将这里的旧prepare/apply脚本作用到共享Lab。

在独立、版本匹配且资源齐全的Lab中，按[Quickstart](docs/THOR_EXPERIMENT_QUICKSTART.md)准备、构建和检查；[平台映射](docs/THOR_PLATFORM_MAPPING.md)说明坐标、动作和接口语义。准备脚本会修改该Lab并构建，不是只读检查；本次没有执行它，没有安装依赖或启动飞行。

```bash
# 以下仅适用于已经单独准备好的匹配Lab
./tools/experiment health --output data/my-new-health
./tools/experiment handover_c_n_c --output data/my-new-handover
./tools/experiment analyze data/my-new-handover
```

每次用新输出目录，保留成功与失败证据。默认PX4 instance=21、system_id=22、DDS domain=71、Agent UDP=18888；运行器只管理自身进程。原始ULog、遥测、运行副本与日志留在本地，不默认提交。

## 本次验证与历史结果

本次仅整理环境基线，检查Python/JSON语法、Shell语法、补丁归档路径、文档链接及状态操作单元测试；不将历史验收等同于新分支已重新构建或飞行通过。完整范围见[基线核验说明](docs/BASELINE_VERIFICATION.md)。

F1结果只保留[固定归档报告链接](https://github.com/JacksonW1025/uav_handover/blob/cbaf3a53914efe26b2e00444f56f16935b760a27/data/handover-f1-sync-20261112-analysis-v1/REPORT.zh.md)。该档案的实验脚本、数据与后期测量链不属于本基线；大型原始日志及未发布运行环境仍在Thor本地。

# PX4 / RAPTOR Handover

研究 PX4 经典控制与 RAPTOR 的双向交接；先开展独立悬停和 C → N → C，再研究状态初始化与反复交接。

实验项目资源统一放在本仓库的 [uav_lab/](uav_lab/README.md)。不依赖 `/home/car/uav_sf` 或原 `/home/car/uav-lab` 的源码、模型、策略或通信组件；Python、ROS 2、Gazebo、CUDA 等系统软件继续使用本机安装。

- [Lab 资源与使用说明](uav_lab/README.md)
- [当前环境检查报告](Environment%20Check.md)：整合后的资源位置、最新轻量验证结果及待验证项。
- [资源来源与版本](uav_lab/manifests/sources.json)
- [复制完整性校验](uav_lab/manifests/copy-verification.json)

本次只整理资源，没有安装依赖、编译项目或启动实验；不导入旧实验记录，新实验从空的数据目录开始。

Git 管理原则：整个 `uav_lab/` 仅保留在本机并忽略；远端保留 Lab 外的项目实验源码、数据和文档，克隆后需另行准备 Lab。

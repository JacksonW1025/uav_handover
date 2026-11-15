# 基线整理与核验（2026-11-15）

来源：`8d0c4166fb8a6f9adb9dbba9f5758f13c6d8446e`。本分支直接以该提交为祖先，使用独立工作树，未修改旧研究工作区、分支或Lab。当前树移除历史批次、历史状态汇总及硬编码历史验收脚本 `tools/acceptance.py`；相关文件仍完整保存在祖先和旧分支中。保留匹配的源代码、补丁、配置、依赖、环境锁及通用工具；未移植不同版本的后期研究测量链。

变更：重写根README，修正两份操作文档的历史证据链接；data默认仅保留说明，原始输出本地保存；边界检查相应改为检查data说明的可跟踪性；增加无Lab静态检查。历史Quickstart中的验收语义仅属于来源版本，不是当前Thor最新系统或本次新增验证。

核验命令：

```bash
python3 tests/check_baseline.py
bash -n tools/experiment tools/lab-env.sh tools/prepare_lab.sh
g++ -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined tests/state_ops_test.cpp -o /tmp/handover-baseline-state-test
/tmp/handover-baseline-state-test
git diff --check
```

以上检查通过。另核对当前树没有ULog、批量数据、凭据模式或失效本地Markdown链接。未运行Lab health、PX4/ROS构建、补丁实际应用、DDS集成、Gazebo或任何飞行；未触碰共享Lab。编译状态操作单元测试不等于完整SITL验收。仓库没有本次新基线的CI配置，远端推送不代表CI通过。

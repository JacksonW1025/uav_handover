# 首推理参考准备配对材料

新实验身份、原源码/binary及私有binary哈希见provenance.json；reference-readiness.patch是唯一飞控源码干预。原始数据与private-build不随此发布。C为未arm即失败的启动，C2/N为实际两次飞行，成本全部保留。

发布脚本将研究根改为HANDOVER_RESEARCH_ROOT环境变量；记录/构建命令以${HANDOVER_RESEARCH_ROOT}代替本地路径，CSV只规范换行。as-run-sha256记录原文件，published-sha256记录发布副本。原记录没有覆盖。build-commands-clean.json还依赖原Thor编译环境，不是独立零依赖构建器。

整理版仅做语法/链接/哈希检查，未重新构建或运行。runner会启动SITL；analyze/audit依赖后期研究工具及完整原ULog/motor记录，不应在原输出目录覆写结果。复制到独立研究与数据目录后才复核。该参考准备改动只用于隔离实验，不是已部署的通用修复。

发布的失败启动日志仅移除行尾空格；错误内容不变，原字节哈希仍保留。

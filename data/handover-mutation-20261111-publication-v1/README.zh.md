# 069 变异研究 Git 发布记录

## 阅读入口

- [最终报告](../handover-mutation-20261111-analysis-v1/FINAL_REPORT.zh.md)
- [逐例完整表](../handover-mutation-20261111-analysis-v1/逐例完整表.zh.md)
- [完整派生汇总](../handover-mutation-20261111-analysis-v1/summary.json)
- [原始日志本机位置与 SHA-256](../handover-mutation-20261111-analysis-v1/raw-source-index.json)
- [23 次启动与结束账本](../handover-mutation-20261111/attempts.jsonl)
- [发布来源与逐文件 SHA-256](source-manifest.json)

## 范围和版本

本分支从已发布的 c129dd11efaf9c6230839835538888bedb523957 建立，仅加入本轮三轮变异研究、必需的 runner/分析依赖及离线测试。原实验 HEAD 为 003cd249a0b1baa3ad78a25c18473657af39aa70；原分支、其八个未发布 quickcheck 提交及其他未提交研究保持不变。实验候选包含整个原工作区的文件哈希；发布分支只收录本任务依赖，不能将新的发布 HEAD 当作原实验身份。

保留 23 次唯一启动、22 次实际主体交接、001 中断及独立恢复、全部失败与场景未实现记录。10 个执行 PASS 不等于安全：已实现轨迹 15 失败、7 通过；证据限定汇总仍为 15 失败、5 通过、3 UNKNOWN。没有追加实验或修改控制器、策略、保护阈值。

原始 ULog、events、telemetry、resources、publisher records、电机二进制及日志继续保存在 car。发布前重新读取并核验索引中的 183 个文件，共 1,424,096,495 字节，全部 SHA-256 和字节数匹配。候选版本、逐例配置/metadata/validation/result、原计划、账本、派生窗口和图均保留。001 没有原 runner result/validation，缺失不补造。ZIP 是已有内容的重复封装，没有放进 Git；package-validation.json 仅是先前本地 ZIP 的历史校验记录。

## 复核方法

在克隆工作区运行 Python 离线测试不启动仿真；发布校验测试读取已提交报告、账本与原始日志索引，不要求原始日志或 ROS。具体命令与结果见 validation.json。运行依赖 mock 测试时，使用 car 上现有 Lab Python 和 ROS 环境。

分析工具保留生成本轮结果时的原文件字节和本机绝对路径，不在发布过程中改写结果或重新运行旧分析。完整原始日志重分析需 car 上原始数据与 Lab；应先将分析工具复制到一个新的输出目录并核对其中 ROOT/BATCH 路径，不能直接在归档输出目录重跑。历史 069/070 派生摘要已包含；完整旧 100-case 数据未随本次发布。

原报告“没有 commit/push”描述的是实验结束时的状态；本发布记录对应之后的独立 Git 发布，不修改冻结报告。

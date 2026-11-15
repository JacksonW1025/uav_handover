# 完整SITL受控relay注入材料

保留runner、relay C++、计划/协议、窗口CSV、完整小型链审计与图。原始ULog/四路完整bin和编译relay不提交。runner/analyze根路径改为HANDOVER_RESEARCH_ROOT；记录中${ARTIFACT_DIR}代表此材料目录。原文件哈希见as-run-sha256.json，原记录未修改；published-sha256记录发布副本。现存manifest是原运行清单，不是整理版哈希。

复现需要后期完整研究树、Thor Lab、Gazebo transport13/msgs10、原插件和原数据；此干净基线不包含这些全部依赖。编译relay.cpp得到同目录relay后experiment.sh会启动完整SITL，禁止与其他批次并发。默认case为plan.json中的normal/delay40；准确名字由其cases读取。analyze.py→supplement.py→finalize.py读取原始日志并写新小证据，请只对独立复制的材料与数据目录操作，勿覆盖原件。

本次整理版只做Python/Shell语法与已有证据一致性检查，没有追加构建、SITL或Gazebo。注入40ms为整个relay窗口；实际首次神经来源应用比正常晚4ms，第一条N sample被后续N覆盖。两臂安全正常收尾，没有观察到性能恶化。

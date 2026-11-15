# T1本次四次SITL的小型证据

margin采用analysis-v3，turn采用analysis-v1。失败/旧分析版本、原始ULog、四电机bin与完整Lab仍保留原Thor目录，不复制到此。原运行材料SHA保存在各as-run-sha256.json，published-sha256.json记录发布副本。

脚本仅将硬编码研究根改为环境变量HANDOVER_RESEARCH_ROOT，并增加import os；已做语法检查，没有用整理版重跑飞行或分析。需要后期完整研究工具、Lab、原始日志，干净基线本身不具备这些依赖。不要在原数据目录运行分析脚本覆盖结果；复核应使用独立数据副本。runner是会启动SITL的历史流程，不是只读检查；本次文档发布没有追加启动。

图表和JSON是原结果副本，不把历史哈希当作修改后脚本的哈希。记录里的路径以原研究仓库为根，用于查找来源。

发布账本仅将output绝对路径改为研究根相对路径；原账本哈希保留，事件与时间不变。

发布CSV仅将CRLF换行为LF，数值文本不变；原字节哈希仍列在as-run-sha256.json。

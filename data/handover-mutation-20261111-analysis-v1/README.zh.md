# 交付包阅读顺序

1. FINAL_REPORT.zh.md：最终结论与限制。
2. 逐例完整表.csv / .zh.md：23次启动完整记录。cases.csv提供更细的窗口/入口字段。
3. summary.json：完整聚合分析，保留原证据限定判据并另列已实现物理结果。
4. mechanism、capture-stage、direction及subject-vs-cleanup审计：目标/记忆/采样/尾段证据。
5. raw-source-index.json：只存本机原始路径、字节数和SHA-256；不含原始ULog、telemetry或电机二进制。
6. candidate-versions.json及delivery-evidence：两版候选、预注册计划、账本与最终执行核验。

本包只含研究交付内容，不含上传工具或凭据。原始数据仍在car，不会随ZIP外传。分析重跑命令：OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 taskset -c 0-3 uav_lab/.local/venv/bin/python data/handover-mutation-20261111-analysis-v1/tools/analyze_mutations.py --plots。

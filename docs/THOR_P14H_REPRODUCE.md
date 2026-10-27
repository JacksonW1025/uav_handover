# P14H 复现

仓库基线0a387decb7809b9005b308aa03499283410fe61b；独立目录data/p14h-20261027。所有旧冻结/失败保留。环境environment.lock，Python为uav_lab/.local/venv/bin/python，PYTHONPATH=tools，OPENBLAS_NUM_THREADS=1。原始大文件和普通运行版本副本保留Thor本地，按交付hash校验；旧CLI symlink不作旧二进制。

先读PLAN、INTERFACE、REPORT和机器摘要。离线命令的输出必须用新目录，不能原地重算：

```bash
PYTHONPATH=tools OPENBLAS_NUM_THREADS=1 uav_lab/.local/venv/bin/python -m pytest -q tests/test_p14h.py tests/test_p14g.py tests/test_p14r.py
PYTHONPATH=tools OPENBLAS_NUM_THREADS=1 uav_lab/.local/venv/bin/python tools/p14h/analyze_offline.py /tmp/p14h-new-response-audit
PYTHONPATH=tools OPENBLAS_NUM_THREADS=1 uav_lab/.local/venv/bin/python tools/p14h/map_edge.py /tmp/p14h-new-map
```

map_edge及其他计费程序的common台账目标为本轮独立目录；仅在核实资源余量和新输出身份后复算，完整复现不自动包含飞行。selection prepare→calculate→select为可执行的未来数据隔离选测流程，池与规则在rules.json、初始包hash在input-hashes.json。v1路径失败、v2 namespace计费缺测及v3复用/重计记录均保留。不得将已暴露样本重命名为前瞻验证。

工具链：apply_p14h.py仅注入EKF2被动post-update快照，先apply_research原幂等工具再独立补丁，源码独立导出source-export-v1，不改旧patches。构建须CCACHE_DIR=/tmp/p14h-ccache。实际PX4/ResearchMulticopterMotorModel/policy.tar/policy.npz副本和hash在preflight最终版本；源版本与真实二进制身份分别核验。

独立物理执行必须使用已发布independent-plan-v2身份与固定实验层。pipeline逐项campaign→review→evaluate，不重复任何START_INTENT，断连先核账本和宿主所属进程。原始sample/native/host/physics身份全保留。这里不提供自动追加飞行命令；新实验需要独立授权。

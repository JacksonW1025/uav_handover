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

收尾分析使用独立命令，均必须新输出目录：

```bash
PYTHONPATH=tools OPENBLAS_NUM_THREADS=1 uav_lab/.local/venv/bin/python tools/p14h/timing_window_audit.py /tmp/p14h-new-time-audit
PYTHONPATH=tools OPENBLAS_NUM_THREADS=1 uav_lab/.local/venv/bin/python tools/p14h/risk_scope.py /tmp/p14h-new-risk-scope
PYTHONPATH=tools OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/p14h-mpl uav_lab/.local/venv/bin/python tools/p14h/plots.py data/p14h-20261027/delivery-v2 /tmp/p14h-new-figures
```

report.py全量生成事件表、错误、成本、机器摘要和原始hash，单次约45–60 CPU秒；使用资源驱动task.py并登记新身份。AB-storage-extension-v2.py源保留在data目录，C范围已用约2907/3000 CPU秒，复现应另计预算，不能自动借本轮余量续算。其forward-J/C矩阵与metric.npz留在本机，已提交J/C前缀可供后向重算；该扩展未实现或验证完整中断续算驱动，不能把原P14R恢复测试推广到它，未完成尾部不得补零。

独立执行有v1暂停、v2仅继续未启动e12，所有已启动身份不重跑。terminal_e11_repair.py保存当次分析修订的原命令和拒绝测试；不要重跑main覆盖旧analysis-v2，可只调用verify对源端点只读核验，或先为新的分析输出参数化。冻结原audit FAIL、原v1路径/计费错误及新scope回执均保留。

初态来源严格区分：原包cutoff字段为Runstart，h_after/cache信息的可用上界为Timing cycleend；真实输入在A前可用，但不构成Runstart瞬时全快照。旧producer替换是下界完成词诊断，不是唯一真实cache读取词。全量更正见timing-window-audit-v2；旧分数不改写。

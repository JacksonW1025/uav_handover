# P15 复现与版本

使用Thor工作目录与`uav_lab/.local/venv/bin/python`，设`PYTHONPATH=tools OPENBLAS_NUM_THREADS=1`。大原始数据、模型完整逐调用输出和实际二进制普通副本保留本地；小证据及hash提交Git。不要在旧输出路径重算。

1. 输入P14H `82ac9fa476a73a61b5dd31619921ec5e6de68856`，`baseline.json`本地保存旧跟踪文件hash和dirty。继承/限制见PLAN和INTERFACE。
2. `python tools/p15/benchmark.py`、`prepare.py`、开发各分期plan是历史执行步骤；已启动身份不能再次执行。`attempts.jsonl`为唯一START账本。
3. `python tools/p15/theory_check.py <new-output>`：源码名义点后继拼接和有条件高度关系，第一版失败及第二版修复保留。`freeze_design.py`和`prestart.py`仅生成一次，不覆盖已冻结配置。
4. `python tools/p15/preflight.py <new-output>`生成普通运行版本、源码配置快照及逐文件gate。完整gate不可覆盖；preflight-current仅为显式当前引用。
5. 开发后冻结`search-freeze-v2/plan.json`、`map-freeze-v2/plan.json`、模型参数、P15源码和全部配置，commit/push/远端回读后保存`experiment-freeze-v1.json`，才允许search/map启动。
6. `python tools/p15/pipeline.py <frozen-plan> <new-queue-output>`按唯一START跳过已启动项，未审查终态会暂停等待范围审查。仅授权范围内的headless SITL。启动预算不因分析错误恢复。
7. `python tools/p15/analyze.py <target>`用于**新分析版本**，不能覆盖旧结果。源重放、直接pre-read、执行滤波、物理接口、fullP、在线输入精度均核验。d01未启用OP的限制和原错误保留。
8. `python tools/p15/evaluate.py <target> <new-output>`从实际决策时封存的输入完整预测，原始未来状态只在独立评分端使用。全前缀、0.5/2秒、事件窗及B前history误差分别保存；COM数据只作退出后诊断。
9. `python tools/p15/report.py <new-output>`全账本汇总、所有方法成本与三值分母；未执行候选没有实测标签。离线随机序列波动只重排实际已执行标签，不为未执行池补标签。
10. `python -m pytest -q tests/test_p15.py tests/test_p14h.py tests/test_p14g.py`；最终再跑所影响的旧运动/接口回归，记录精确数量和命令。真实GitHub CI状态与本地测试分开。

源码/模型变更影响物理身份，正式队列不能静改。纯路径/评分/图表错误在独立分析版本中保留旧错并回查，不能借此改变阈值、候选、参数、顺序或独立成绩。原P14H及更早FAIL/UNKNOWN不回写。新问题需要新授权时只交付方案，不挪用历史名额。

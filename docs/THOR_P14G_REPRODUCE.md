# P14G复现

仅离线。**禁止调用任何飞行启动器、使用P14R剩余名额或启动P15。** 基线5d035fc10b80fc171a24fe33d728db8af4a43d31，最终源SHA见发布回执。输入/参数和预算封存在config/p14g/protocol-v1.json，开工状态在data/p14g-20261027/start-state.json。所有输出目录必须新建，不原地重跑旧结果。

## 快速验证与整合入口

```bash
export PYTHONPATH=tools
export OPENBLAS_NUM_THREADS=1
uav_lab/.local/venv/bin/python -m pytest -q tests/test_p14g.py tests/test_p14r.py tests/test_p14_motion.py tests/test_p14.py tests/test_p13.py tests/test_p12.py tests/test_p12_score.py tests/test_p12b.py tests/test_p12c_platform.py
uav_lab/.local/venv/bin/python tools/p14g/pipeline.py /tmp/p14g-pipeline-new
```

pipeline使用已保存的源分区、同域计算、模型选择、前提核验，输出map-edge/workflow及撤回账本。实际安全UNKNOWN，条件前缀与完整事件不可混同。主机器入口delivery-v5/machine-conclusion.json，逐项分析analysis-v2，图在docs/figures/p14g。

## 依赖与原始文件

沿用P14R source-inputs-v3/d02–04和v4/d05–06；实际源OP库offline-build-v2/libop.bin、P13封存policy.npz。本轮未改Lab、构建、权重/保护。完整原始文件在P14R六个runs目录；d01仍隔离，d05删失保留。旧ledger/原始hash与输入在delivery-v5/historical-preservation.json核验。

P14G全部NPZ/数值检查点本机保存并由local-array-hashes.json列hash，不加入Git、不删除降采样。缺原始文件必须报告缺失，不能用摘要代替。OP/gyro/cache/COM几何语义见INTERFACE；LP导航速度不因yaw差旋转。

## 分项计算

- `prepare.py NEWDIR`：从截止Run开始的过去两次融合误差构造候选率，源OP时间常数只是代理假设。inputs-v1保留原包与hash。
- `audit_timing.py NEWDIR`、`timing_evaluate.py NEWDIR`、`consume_audit.py NEWDIR`：源状态机、连续P/D区域及实际评分。初始化用同次pre-read；运输有序与组件模式明确区分。
- `weights.py NEWDIR [d02|d03]`：192调用解析伴随8行sketch，只排序，不是全域证明。
- `batch_sets.py B NEWDIR [PREVIOUS]`：四法、zero/small64ms和完整8cell联合域0.8s。资源90CPU/110wall/24GiB；PREVIOUS只引用身份相同的已完成结果，旧失败保留。
- `run_c.py NEWDIR`：未来data/export隐藏的bwrap自主点计算与24项创新集合对照；需要宿主允许namespace。首次NETLINK失败在C-v1，宿主完成在C-v2，未重飞。
- `run_d.py NEWDIR`：未来隐藏的35候选选择；正常输入7别名不计独立测试。D-v2修metadata，D-baseline-v3/v4修暴露后uniform/LP基线与canonical id；旧结果不覆盖。
- `op_transfer.py NEWDIR`：源缓冲/积分42维关系及C++小扰动数值核查；Jury说明另见C-PI-proof.json，不是完整飞行保证。

以上是方法复现接口，不是要求重新消耗本轮全部CPU。长批次必须重新登记独立离线资源预算，不能绕过原5400/7200上限恢复未启动项。

## LP指标修版与资源记录

rich-v3是对固定B40＋C24的被动LP/COM全量标注回查。rich_sets只读NumPy中心/G并断言Context.n不变；analysis-v2逐项验证共同前缀原核心指标差0。预算失败保存数值64ms检查点及完整指标前缀，最后未确认域检查行排除。没有用资源停止当真实不稳定。

rich-v3/execution.json给精确waited-child CPU与管理CPU；早期C/D/weights已退出、CPU缺测，不由墙时冒充。resource-reservation与resource-accounting-note-v2给cap/四核墙时保守扣账、200未实测allowance及90采样竞态裕量，所以不能写“全轮CPU硬帽已独立认证”。旧aggregate RSS缺测；各成功任务peakRSS及地址空间帽单列。后续报告/测试/发布在预留100CPU内，所有重算和旧锚点计成本。

## 评分与版本

C-score-v1保留原三值评分v2；用LP缓存列评分、首次域外行排除、已有失败见证有效，不完整安全为UNKNOWN。全部五记录×9比较、0.5/2秒/事件窗/全前缀误差在C-errors-v1。主词漏判1/1/1、误报0、预测UNKNOWN0；实际高度UNKNOWN1。全部8词逐对比P14R分类不变，不挑有利词。

innovation_audit是未来实测仅评分侧的前提反证，不是自主输入。small预算离开后所有依赖真实安全覆盖在withdrawal-ledger标UNKNOWN；不抹去主要漏判。D只有5个实际锚点，模型/重复窗不增加独立单位，其余候选只设计价值。所有改进/修正版均回顾性，不恢复独立前瞻。

GitHub Actions/check-runs/combined statuses在推送后查询，空pending不是绿灯；CI与本地测试分开，发布后本地回执保存SHA/远端回读及原API响应。

## 最终正确性修订

`weighted-v4`保留两条正确post-state伴随及10项同域重算；旧pre/post错位结果原样保留，分析入口analysis-v2按result_source引用正确数据。`weighted_fix.py`和`weighted_analysis.py`记录该有限修复，183.56 CPU秒计入成本。该版本仍是8行全前缀符号sketch，不能推广为所有输出导向方法的否定。最终资源数值扣账5316.28含100验证及200未实测allowance，硬帽认证仍UNKNOWN。

最终账本/源输入hash索引：`final-index-v1`，由`tools/p14g/index.py NEWDIR`生成；最终106项回归在tests-final-v3.log。历史receipt不纳入本次提交。图示仅保留已确认域前缀，LP历史D不夸大舍入差异。

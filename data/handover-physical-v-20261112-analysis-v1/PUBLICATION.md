# 本轮远端证据包

本目录发布完整中文报告、两图、六例派生高频CSV、score/audit摘要、物理状态与时序、前瞻选点、成本及原始执行/分析脚本。相邻 `../handover-physical-v-20261112/` 保存协议、六份计划/prelaunch、六例配置/结果及18行启动账本。源文件按原样复制，SHA256见 `publication-source-manifest.json`。

不含 flight.ulg、Gazebo逐物理步原始bin、全量遥测/进程日志、Lab、策略权重或其他批次数据。每例score保留原始ULog SHA，可在Thor核对。派生数据的一致性不代替从原始ULog独立复算。

## 任何设备可运行的只读检查

从仓库根运行（Python 3标准库，无需PX4或第三方包）：

```bash
python3 data/handover-physical-v-20261112-analysis-v1/recheck_published.py
```

它验证源文件hash、六例V及三窗G、原生派生倾角/失高、两分支选父、选择早于子例启动及账本。不写文件，不启动飞行。

## 原实验脚本的依赖限制

`physical_search.py`、`execute.py`、`score.py`、`audit.py`、`final_evidence.py`、`analyze_physical.py` 是当次实际脚本快照，未为发布改写。它们含Thor绝对路径，依赖本地 `uav_lab`、`tools/handover_lyapunov`、`tools/handover_100`、`tools/handover_explore`、`data/handover-advanced-20261112-offline-v1/directional_analysis.py` 等已有环境，不能声称远端clone后即可启动或从ULog复算。原始运行目录已存在，勿直接重跑会启动飞行的入口。此次未把其他批次依赖或整个Lab夹带提交。

两图已经查看；失败曲线止于保护截断，父例002完整观察17.156秒。报告的5越线/1未越线、只有002确认落地，以及无新增经典对照限制保持不变。

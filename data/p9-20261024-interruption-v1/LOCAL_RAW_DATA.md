# P9 中断样本与原始数据位置

原始ULog、完整telemetry/resources与逐物理步电机轨迹只保存在Thor本地，不提交远端。
原101条完成运行在`data/p9-20261024-formal/<id>/run/`，每条`flight.ulg`哈希可从独立审计及各run metadata核对。

第102次`C-CZ15-g0.1-reference-P9-Z`因runner/campaign父进程消失而未完成。
其原始日志仍保留于`data/p9-20261024-formal/C-CZ15-g0.1-reference-P9-Z/run/rootfs/log/2026-10-24/00_36_47.ulg`，
正常SIGINT清理后另复制到本目录`raw/flight.ulg`以保全；两个位置均未删除。

- 字节数：241618208。
- SHA-256：`ce68fe27a0e7cb471b70793f81142890e9d2a52b0d7ee9d03988ddb8ab51482c`。
- 原始结构可解析、dropout记录0，不代表计划实验完成；控制流中断后的孤儿尾段不能当作参考验证。
- 该次保留为已启动的基础设施中断，飞行结果未知，不进入101条正式测量分母，不重跑或补造FINISH。

本目录的raw清单、进程归属/清理记录、结构检查与中断评估为小型可发布证据；原始二进制只在本机。
远端并非完整原始数据，重新执行原始重测需要Thor本地原始文件。

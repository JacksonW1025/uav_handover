# P9 execution-v4：仅显式续接本次已授权的D09四臂

本次用户已批准执行原剩余9条。v3已启动5条，169因真实额外恢复暴露被原P7拒绝；v3单元按规则退出，169永不改判、不重跑。还有D09-Z/C/R/CR四条独立可做且未启动项仍在同一批准范围内。本版本是显式提交、推送后才启动的执行续接，不是接管/重启旧单元，不新增接纳例外、研究条件或预算。169的拒绝不阻止保存后继续原清单其余独立项；绝不为了完成清单将其放行。

## 冻结不变与预算

测量器为原v2冻结measurement_v2；机会/接纳仍为v3冻结opportunity_v3。原P7源码、字段、FAIL和169的REACHED_UNVERIFIED不改。host_gate、measure_row、decide_row、execute_one与v3在仅归一化epoch标签后AST完全一致，另存证明；161条原始回放、62项联动测试继续作为原规则证据。本执行器只改新freeze路径、历史链、初始计数169、四条白名单及新输出路径。

四行均从原冻结plan排除所有START_INTENT取得，顺序Z/C/R/CR，D09原种子389965395、方向80°、速度1.8m/s、窗口[[0,.3],[.7,1.1],[1.34,1.66],[2.32,2.6]]、11.79m路径、固定16s及所有参数/阈值/误差/模型/修复选择保持原样。每行重新检查生成域和runner预算、与原预测完全一致。正式169→最多173，开发仍10，新开发飞行0，不动7搜索槽。102/162/164/169均拒绝重试；174拒绝，目录/ID重复拒绝。

若四条全部接纳，主测量最多169条（已有165＋4），D33条：Z8、C9、R8、CR8；7个完整四臂主簇。旧102永久缺失、162事后诊断、164原证据FAIL及169额外恢复证据FAIL分别保留，不拼总体PASS。数值已测不等于协议接纳。v3停止时的报告/成本/ledger快照绑定本次提交时169版本，后续共享账本追加保留冻结前缀；不得改写旧记录。

## 前置核验与运行

冻结57项原执行测试和追加169不可重试测试，共58项，无SITL；包括真实四臂原分析链及新runner、四个实际白名单槽、完整四行campaign与遇UNKNOWN即停、预算、持久化顺序等。无飞行测试不计为开发飞行。临时夹具失败日志保留，不覆盖原run。新manifest保存原115项及新执行代码、四行清单、前缀、原模型副本、测试/等价性、身份/预测/主机门控。

独立唯一单元p9-continuation-v4.service，沿用已验证Type=exec、Restart=no、RuntimeMaxSec=2h、KillMode=control-group、SIGINT、SendSIGKILL=no。启动意向及新目录避免重复。启动前/每次核全局进程、无ToDesk会话、无其他仿真竞争、时钟/存储/身份；不关闭ToDesk或停止他人任务，不改安全和网络权限，仅无风headless SITL。五层历史冻结哈希与对应提交blob核验后，先commit/non-force push/远端回读/receipt，再只调用一次launch_v4.py。

执行仍逐条按原v3逻辑：真实飞行失败但证据有效可以继续；只有精确的未到恢复机会例外可单独接纳，缺证据/不合格额外START等均拒绝并停止本批。没有新增豁免169或类似情况。所有失败启动均计数，不补跑。审计每批及合并分母、原始数据哈希、预测、代价和删失；原批所有FAIL保持。最后审阅报告、图/CSV/清单/成本/负结果后正常发布，远端原始数据仍不齐全（ULog/telemetry/resources/电机步数据仅Thor）。

```bash
# 完成receipt和全部门控后只执行一次，不重复启动
uav_lab/.local/venv/bin/python data/p9-20261024-continuation-v4-preparation/launch_v4.py
systemctl --user show p9-continuation-v4.service -p MainPID -p InvocationID -p ActiveState -p ExecMainStatus
```

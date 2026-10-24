# P9 continuation-v2：获批的11条及独立首开口中断测量

用户2026-10-24明确回复“继续”，批准已提出的新测量/执行版本及剩余11条。此版本不重启v1单元、不补跑102/162，不更改原冻结代码、原run文件、模型、参数、种子、阈值、修复选择或搜索封存。原两批完整性FAIL永久保留。所有新源码位于独立data目录；无新的开发/等价性飞行，开发保持10。

## 只执行原清单剩余项

冻结清单为原静态plan按原顺序排除所有START_INTENT后恰11行：D07-C/R/CR，D08-Z/C/R/CR，D09-Z/C/R/CR。速度1.8m/s、11.79m目标路径、首末段、事件时间、16s窗及每簇原种子均不变。生成域和runner预算分别用原validate_row核查，11条重新预测均须与原冻结预测完全相同。高度null、整体拒判与空跳过规则不变。

正式账本继续使用原文件并核验本次冻结前缀，启动编号163…173；所有启动/失败都计数，不再使用原180上限的额外7槽。开发10≤12，本批新开发0。新错误停止本批，不自动重试、不自动第四批、不转移搜索7个未用槽。只有11个白名单ID可被claim，已启动ID及第174次均拒绝。

## 独立measurement-v2

原tools/p9_metrics.py、P5/P6/P7及run_experiment均不编辑。优先运行原P9分析器，保留完全相同的字典与p9-metrics.json序列化，标记ORIGINAL_COMPATIBLE。原160条逐字节回归必须通过后才冻结启动。

只有原分析器报告“no observed first interruption”时，才尝试新增首开口分支；其他缺证据/异常返回结构化UNMEASURABLE并使执行停止，不猜成功。该分支要求：

- 原始P7记录安全中止、无闭合间隔、存在index0计划gap_started，配置为显式windows；事件计划与首窗口一致。
- 首skip位于计划起点后0–40ms，末emit在起点±40ms内且不晚于+20ms；原生末接收距profile_start＋计划起点≤50ms。50ms为20ms发布周期＋原30ms时钟散布容差；不由验证结果拟合。
- 原始research_target只有一个在飞行超时捕获，模式/decel与处理相同；末接收→捕获处于原200–216ms范围，捕获在RAPTOR拥有控制的日志段内，之后没有外部接回。
- 局部状态至少3行、有限，样本间隙≤20ms；原数值核心还须满足至少3条巡航目标和原30ms时钟散布门。缺topic、非有限值、错时序/多捕获等均NA。

原数值核心从绑定原SHA的源码读取，只把缺失first锚点替换为已验证native末接收；其余16s、轨迹、倾角/高度/代价计算不变。输出单独p9-v2-assessment.json及p9-v2-metrics.json，标记OPEN_GAP_CENSORED，不冒充原冻结兼容。观测极值为完整窗下界；已观察>45°或>1m可判失败，未越高度阈值的删失结局为未知。未发生接回没有恢复记录，末接回代价UNOBSERVED_FINAL_RESUME；null绝不填窗口端点。计量版本及原分析器异常随每条结果保留。

162仅作为事后开发诊断回归：新分支输出不写回162、不补旧FINISH、不加入主171条分母。102没有计划内中断/可信流尾，仍不可测。允许的新分支是本批事前冻结规则，不根据本批正式数据再调整。

## 无飞行测试与身份

冻结前完成：保守证据谓词、闭合/后续开口兼容、102拒判、162删失且恢复为空、缺topic/错超时/双捕获/缺样本、任务边界及不伪造追回、已启动ID和174上限拒绝、11行原顺序原数据一致；另对160条有效原始日志调用适配器，原兼容输出与已保存p9-metrics.json逐字节一致。所有这些均无SITL启动。测试日志、兼容160清单/耗时、host/candidate/storage/11预测检查连同源码/计划/模型副本登记SHA-256。

原27项和续接v1的59项冻结文件及原Git blob继续核验；新候选只允许project_head不同，tools/research/config、Lab/二进制/策略/plugin相同。新清单提交、非force推送并回读成功后，写新receipt才允许启动。

## 托管、门控及分析边界

复用已验证user-systemd托管方式，但独立单元p9-continuation-v2.service及新输出目录。Type=exec、Restart=no、RuntimeMaxSec=2h、KillMode=control-group、SIGINT、SendSIGKILL=no；一次launch-intent和目录拒绝重启。只管理本单元自己创建的进程。每条前检查全局namespace、ToDesk无连接、无其他PX4/Agent/Gazebo、时钟及存储、候选哈希；有ToDesk等待而不关闭它，竞用/异常停止而不停止其他任务。仅无风headless SITL，无实机。

unit依次执行11→独立原始审计→三执行版本描述性报告→图和成本。没有自动Git，人工审阅后发布。原101/续接v1的59分别重算通过但全批仍FAIL；本新批独立11可有自己的完整性PASS，绝不拼成整体验收PASS。

全局最多173次启动，最多171条原兼容测量；如有新OPEN_GAP_CENSORED则其计量版本另列、兼容数下降。102永久缺失，162永久事后诊断；D35条主测量对应Z8、C/R/CR各9，只有8个完整四臂主测量簇，D07-Z另列，不宣称9个完整原冻结配对簇。可以补充呈现D07的事后诊断对照，但不得混入主分母或改变原失败。

B48、C53及参考35结果不变，搜索不再运行、参考和D不反馈模型/修复。保留CZ60参考误差0.50s等负结果。任务代价仍最大落后≤4.5m、末接回6s绝对落后≤0.5m、10s内位置≤0.2m/速度≤0.1m/s连续0.5s。连续值配对仅双臂完整窗，n=1退化bootstrap不能作总体CI。后续风险、观测删失/NA、原主/倾角/高度/任务分母均单列。

成本区分原批、新批、102的421.028s、162的74.193s、模型适配/历史识别、无飞行开发和离线计量。人工工时未知仍NA。原始ULog/telemetry/resources/Gazebo电机数据只在Thor本地，远端不称全原始齐全。

```bash
# 仅在receipt核验后执行一次；不得重复执行
uav_lab/.local/venv/bin/python data/p9-20261024-continuation-v2-preparation/launch_v2.py
systemctl --user show p9-continuation-v2.service -p MainPID -p InvocationID -p ActiveState -p ExecMainStatus
tail -n 8 data/p9-20261024-continuation-v2-session.log
```

# P9 continuation-v3：恢复机会证据封装及最后9条

用户2026-10-24 09:50:43 UTC明确批准“可以，继续”，范围为独立机会封装、端到端无飞行回归、新冻结及原剩余9条。保留全部旧P7/P9字段、FAIL、原始数据与审计；不重跑102/162/164，不把164事后新分类加入前瞻分母，不修改模型/飞行参数/种子/阈值/搜索/修复选择。本版本只在data独立脚本中定义证据接纳；原tools/research/config/Lab不改。

## 唯一运行清单与预算

原冻结plan排除全部START_INTENT后，按原顺序恰为D07-CR，D08-Z/C/R/CR，D09-Z/C/R/CR。种子依次为D07 1789132554、D08 310789402、D09 389965395；每簇同种子、事件表和处理均来自原plan。每条仍独立核查生成域、runner路径预算及原预测完全一致。速度1.8m/s、11.79m路径、首末段和固定16s窗不变；RREC/RTGT/RINI等均原值。

启动前正式164，编号165…173，共最多9新启动；开发仍10，新开发/辨识飞行0。已启动ID、旧输出目录及174次拒绝。7个搜索未用槽不挪用，不因失败补跑。新错误停止本批，不自动重试或再建版本。剩余原9项执行后，若都可接纳，主测量最多170条；D34条：Z8、C9、R8、CR9，8个完整四臂簇。102永久缺失、162事后诊断、164原P7证据FAIL均另列。全局不宣称验收PASS。

## 四种机会状态

原P7仍由原脚本计算和保存：不覆盖status/problems/checks或旧结果。另存opportunity-v3和admission-v3：

- NOT_REACHED：RREC=0时表示该恢复功能禁用；RREC>0时只能在完整原生证据证明观察期内没有达到源码规定恢复机会时使用，绝不等于恢复成功。
- REACHED_VERIFIED：已有符合条件接回，原P7 START时序、状态、恢复律及其原允许例外均通过。
- REACHED_UNVERIFIED：已知接回机会且尾段足够，却缺应有数据或验证失败。
- UNKNOWN：短尾、缺日志/捕获/状态、参数/轨迹不符或时序矛盾；不接纳。

原P7正常MEASURED路径保留原数值，不因新封装改阈值。新状态为UNKNOWN/REACHED_UNVERIFIED时不能借旧布尔值放行。RREC=0出现恢复行仍为异常。虚拟目标END CONVERGED与机体追回分别判断；START无END、END_STALE/INACTIVE均不当作机体追回。

## 唯一新增接纳例外

必须同时满足：原P7 status INCOMPLETE，且problems列表仅有“no research_recovery rows with MC_RAPTOR_RREC > 0”；原主结局为飞行失败；原P9数值分支已在v2事前定义的OPEN_GAP_CENSORED中测得；以下原生证据全部充分：

1. 计划内首gap已开始、有唯一非activation超时捕获、没有闭合接回；延迟/模式/decel和phase通过原v2证据规则。
2. 捕获后到最后拥有控制的观测段，状态active且stale，至少3行、末行覆盖末端8ms内、间隙不超过原20ms连续性界限；research_memory同段覆盖且连续，ULog无dropout。activation捕获已观察，参数RSH/RINI/RTGT/RREC在捕获时匹配且尾段无不符改动。
3. 没有后续外部接收；存在接回或早先闭合事件就不能用“无恢复机会”豁免。已接回但尾段不足12ms或采样不完整为UNKNOWN；足够却缺数据为REACHED_UNVERIFIED。
4. T0捕获位置/零目标速度匹配且无T1 profile；T1/CR捕获目标速度为实测水平速度，截断到中止前的全部T1 profile符合原闭式模型（1e-4），并验证mode/decel/位置，而非只查参数。
5. 原生测量、策略输入重建、输出链路、进程/崩溃/trace、主机/身份等其余门控全部通过。缺任何必需检查不接纳。

例外只产生`evidence_admissible=true`，原p7_measured仍false、P7仍INCOMPLETE、legacy_infrastructure_ok原样保留。独立`observed_flight_failure`始终由实际主结局确定，不与证据失败相互掩盖；无恢复机会标NOT_EXPOSED，追回null，末接回代价UNOBSERVED。既有及新增飞行失败均保留，不因此变成功。

## 事前无飞行证明

先完成62项测试，包括真实四臂ULog经真实P7 CLI→v2测量/导出→生产runner判定；原161条ULog的P7重算相同、原P9序列化逐字节相同且无需例外接纳。102/162/164负例只事后检查，不改旧分母。

矩阵覆盖全部9个原槽、首开口、后来开口、已有接回缺topic/短尾、START无END和CONVERGED/STALE/INACTIVE、缺捕获/状态/日志、参数/CR截断目标轨迹错误、UNKNOWN、其他P7问题/物理门失败、重复ID/目录、174、域界、预测持久化→START→模拟执行→结果→FINISH、异常计数与停批、ToDesk/并发/namespace/时钟拒绝。测试禁止调用SITL；临时复制小文件，ULog只读链接，原文件不改。初期测试夹具错误日志保留，不能称所有开发尝试都一次成功。

164依本规则的结果只标posthoc，不成为前瞻验证；D07-CR虽是新未运行臂，与已见D07其他臂共享种子/事件，因此不能称整个D07为新独立事件族。没有依据其结果调模型或修复。

## 冻结、托管、审计与发布

原27/v1 59/v2 81项继续核验，新增源码、规则、测试、161回放、清单、原模型副本、账本前缀、身份/主机/预测/预算检查登记SHA-256；新提交先非force push并核远端，再写receipt启动。候选相对原飞行实现仅project_head不同。运行中不改冻结源、不commit。

独立唯一单元p9-continuation-v3.service，复用已测托管机制：Type=exec、Restart=no、RuntimeMaxSec=2h、KillMode=control-group、SIGINT、SendSIGKILL=no。一次launch-intent和新目录拒绝重复；只清理本单元自己创建的后代。每次全局门控检查ToDesk无活动、无其他PX4/Agent/Gazebo、CPU时钟/资源/身份；不停止他人任务、不关闭ToDesk、不修改安全/网络权限；仅无风headless SITL。

单元执行9→本批独立原始审计→四执行版本分母报告→图与成本，后续人工审阅再正常commit/push。原批全局FAIL保留，v2 C PASS/R FAIL保留；新批可独立PASS但不能拼为总体PASS。记录新机会例外数量与原兼容/新增删失数量，原164事后新分类另列。所有旧输入哈希检查不覆盖旧run分析。

B48预测误差、危险低估与空跳过NA，C53封存搜索及35参考（CZ60 .50s误差）、D配对/非配对、任务代价、未追回/删失、后续风险及全部负结果完整报告。高度仍无模型，整体拒判；不把账本称Lyapunov或安全集外必败。完整窗连续值与已知二元分母分开，小样本不作总体保证。成本区分新飞行、无飞行封装/回放、旧失败与未知人工成本；原始ULog/telemetry/resources/电机步数据仅Thor本地，远端不称全原始齐全。

```bash
# receipt及全局门控核验后，只调用一次
uav_lab/.local/venv/bin/python data/p9-20261024-continuation-v3-preparation/launch_v3.py
systemctl --user show p9-continuation-v3.service -p MainPID -p InvocationID -p ActiveState -p ExecMainStatus
tail -n 8 data/p9-20261024-continuation-v3-session.log
```

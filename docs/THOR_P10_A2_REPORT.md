# P10-A第二轮：源码事件闭合与完整序列的离散误差管

2026-10-24。**新增SITL、开发和正式飞行均0，B/C/D均未启动。** 第一轮及其澄清文件、NOT_PASSED、所有历史证据原样保留。本轮独立版本化，不改Lab/PX4/策略/安全保护，不扩大P9接纳或修补旧异常。

本轮得到一个**声明代理/时钟/误差类内的完整序列正结果，待父线程复核**：1.8 m/s单次停流，非零初始不确定性，真实源码的严格超时捕获和接回，连同末段停流再捕获，覆盖完整−5…16 s。它不是无条件SITL安全保证，不能自动授权B；原A的历史NOT_PASSED不改写。

## 基线与先行覆盖判定

开工本地和GitHub main实际回读为 `64acacd1fc56361e7b83d8509d8f77a67586f502`。已核原报告、P/证书、验证器、P9模型/预测实现、runner和源码注入及当前Lab模块的只读源码。`.agents/`仍为空。原未跟踪AGENTS.md、P9锁文件保留；本轮只增加A2文件。

原域 `Vraw≤49` 必须满足每轴 `|e|≤sqrt(.0245)≈.1565 m, |d|≤sqrt(.1029)≈.3208 m/s`。原138/156旧冻结预测越必要域的事实保留，全部仅作已见开发核查。

先做可覆盖性检查，而非先补映射：在本轮完整预滚动加速段 `t=−1.8 s`，独立集合审计得到整个声明初始集合 `|d|>0.3401 m/s`，已超过旧必要域；这发生在gap之前，且没有饱和。4 ms读取/观测模式还需要22槽延迟，原8 ms/11槽矩阵不能原样应用。**路线A“沿用原raw证书”失败，不是只缺事件图，也不能靠缩放P解决。**

18个有限候选名义检查（速度1.5/1.8/2.0，RTGT0/2，gap .3/.5/.65）的原始记录在 [coverage-candidates](../data/p10-20261024-a2/construction-reviewed/coverage-candidates.json)，逐类判定另见 [coverage-table](../data/p10-20261024-a2/coverage-table.json)。它们是反例/候选搜索，不是连续参数域证明；其中的成功名义回放不等于通过集合证书。原生成器的`nominal_saturated_samples`实际累计截断分量命中数、同拍可能两项，解释表明确更名，不把它当独立样本分母。

| 类别 | 具体证据/拒判原因 |
|---|---|
| 原raw域保守 | 本轮主类整个集合在−1.8 s即越d必要界，但完整新管证得 `|e|<.326,|d|<.493`，实际截断未激活。 |
| 真正饱和 | RTGT0候选捕获后d常超过1 m/s，部分还越位置.5 m；本轮验证器明确UNKNOWN，未用未饱和矩阵冒充覆盖。 |
| 遗漏状态 | 第一轮缺capture参数、read-age、armed和虚拟目标依赖；本轮映射补齐，主类通过RREC0/初始化条件证明虚拟分支不可达。RREC>0仍UNKNOWN。 |
| 时钟模式 | 发布−2 ms mod20 ms，读取/gyro为4 ms。用pub时刻当read时刻会把主捕获提前一拍；其他步长、丢样或改变guard的相位/抖动均不自动接纳。 |
| 误差假设 | 当前状态每步w的P范数≤1e−7是明确条件，未从经验残差推出；机器算术包络也是声明条件，无真实系统全域证明。 |

## 路线B：截断研究及新证明对象

逐轴clip满足 `clip(z+δ)−clip(z)=σδ, σ∈[0,1]`。在不跨阈值的模式上σ为0或1；跨阈值的集合须覆盖所有模式或另给余项。若要求位置/速度σ均0时也严格共同耗散，该模式保留位置单位特征值，不能由一个严格正定差分不等式直接得到全模式严格收缩。**这说明候选严格共同证书有障碍，不等于饱和系统不稳定。**

本轮改用轨迹中心误差管：新4 ms离散化保留P9原kp/kv/τ/88 ms延迟，但不是原8 ms预测器或连续DDE的精确积分。没有重拟合模型，没有缩放原P。先写clip模式及其拒证条件，再证明一个原研究速度子类的整个集合不进入截断。

主类固定NED-x直线、target-yaw=0；横向状态/目标/扰动恒0，姿态输出取纯俯仰、`Rzz>0`的几何lift。它是源代码允许的输入子类，不代表所有heading/yaw。RSH1、RINI4、RTGT2、RTDEC2、RREC0；分析区间内RAPTOR保持active，要求有效、唯一、递增的传感器/gyro样本，无早退/丢包。实际神经/GRU、电机、估计器、竖直动力学不由该代理精确解析，其影响若要外推须符合严格w条件。

## 完整事件图与时钟

[事件映射](../config/p10_a2_events.json)枚举完整事件状态：机体/代理、按样本身份排序的延迟队列、发布/剖面时钟、最近消息与实际read-age、stale/previous-stale/armed、capture参数和时钟、虚拟目标/速率/积分时钟、active与早退状态。**47维只是物理状态/队列误差的度量部分，不是整个混合系统的全部Markov状态**；capture辅助变量的关联和误差另行保留。

| 事件 | guard、reset和历史规则 |
|---|---|
| 发布/保持 | runner按monotonic profile推进，gap内不发，接回仍在原时间参数轨迹；UTC消息stamp不作超时原点。 |
| 实际读取 | 外部使能、订阅更新且字段有限；held SP=消息，last_read=本次native hrt。无消息/无效消息不能更新时间。 |
| 超时 | `!last_read_set || use_internal_reference || native_now−last_read >200000 us`；**等于200000仍fresh**。 |
| 捕获 | stale且首次stale或stale下新激活；p0和v0从同一实际观测状态复制，yaw从当前姿态捕获。RTGT0置v=0，RTGT2保留水平v并减速。旧队列不清空。 |
| 捕获段 | 以gyro sample计算elapsed，积分`p0+dir(v0 t−a t²/2)`至停；新鲜SP/停用结束profile。 |
| 接回 | fresh且was_stale；外部SP恢复原轨迹；armed被消费。RREC>0才从实际机体p/v启动虚拟目标；RREC0不启动。 |
| 恢复积分/退出 | 首步dt0；随后gyro差值clamp到[0,.05]，限加速度，先v后p；误差均<.02退出。本轮映射这些分支，但未将RREC>0纳入证书。 |
| 新超时/停用 | 已在恢复时新stale结束恢复并可能重新armed；停用清armed并结束恢复。 |
| 首事件前额外START | 非计划stale→fresh或初始active虚拟目标必须计入。主类初始previous-stale/armed/recovery-active均false，RREC0，且预滚动read-age≤16 ms，故该分支被源码guard排除，而不是删除事件。初始已有恢复或RREC>0均拒证。 |

固定时钟类：publisher在 `−2 ms mod20 ms`被调用并发布；gap exit在下次调用立即发；有效消息在下一4 ms native tick读取。native hrt、gyro和剖面时钟在声明轨迹上1:1推进，sample dt=4 ms；消息从发布到读取有2 ms相差。这个调用/相位模式是明确的**条件类**，尚未声称当前runner每次实际都按此运行。改变guard/队列索引的时钟变化必须另算；不强求无关步长泛化。

文件/表中的`native_us`是**相对首个计划gap原生时钟锚点**的微秒，不是负的PX4无符号绝对时间；加任一足够大的共同epoch常数可使所有实际hrt/sample时戳为正，所有age和elapsed不变。发布/gyro各自的恒定原点偏移按声明的时钟绑定处理，不能拿消息UTC替换该锚点。

源码事件处理先于本次observe/control：读取→stale判断/捕获→capture profile→恢复transition→observe中的虚拟目标→executor。实际executor native action cadence可以与observe不同；本代理4 ms积分不是神经executor的精确离散模型。

还核到sample-clock重复/回退拒绝发生在capture/recovery transition之后；因此这类早退可能已经改变目标/模块状态，不能当作“无事件跳过一拍”。缺angular更新/失效传感器的较早返回又可能在外部读取之后。事件图分别保留这些顺序；主类严格要求每拍有效唯一gyro，其他顺序路径UNKNOWN。

## 固定全段与受约束初始/跳后集合

保留P9完整参考：−5…−2 s静止3 s，−2…−1 s加速1 s，−1…0巡航1 s；速度1.8 m/s，gap `[0,.5)`；单事件后继续原线至4.6 s再以2 m/s²减速.9 s、保持6 s、11.5 s停流。观察一直到16 s，**没有缩短参考、末保持或停流后过程**。这是独立单事件类，不把删除多事件后的结果冒称原多事件证明。

初始两个独立参数 `z_p,z_q∈[−1,1]`，位置offset `.01 z_p m`、q=`.1 z_q m/s²`、当前v=0；不是一条名义轨迹，也不只是对误差不敏感的平移。前88 ms令 `u=t/.088∈[−1,0]`，构造同参数历史：

```
p_pre(t) = p_base + .01 z_p + .1 z_q (.088)² (.5u⁴+u³+.5u²)
v_pre(t) = .1 z_q (.088) (2u³+3u²+u)
q_pre(t) = .1 z_q (6u²+6u+1)
```

满足p'=v、v'=q，端点回到同一p及v=0；此前可属classic，未声称满足此前神经代理的控制方程。历史误差来自这段机体历史和恒定外部参考，当前外部消息已fresh，模块状态按上述源码初始化。观测/native float32的初始包络由独立算术不等式纳入初始P余项半径.0005；用 `P>.5I` 和每坐标余项<2R另核整个初始历史均在clip盒内。实际集合是这些源关系的像，不要求整个无约束47维球可达。

主捕获的实际v在约 `1.79320659904 ± .00014261048 m/s`，严格非零。每个初始参数/扰动轨迹都执行 `pcap=fl32(p_observed),vcap=fl32(v_observed)`，保留同一参数和余项依赖。接回及末捕获用同一保存变量，不引入自由独立跳后球。末捕获v的集合跨零；对停止位移`f(v)=v|v|/4`用全局C¹、导数1/2-Lipschitz的Taylor余项≤width²/4，覆盖两种符号，而非只走名义正号。

## 新V、集合传播与可计算决定

每轴物理坐标状态为 `Y=[p,v,q,clip(e)_(k−1),clip(d)_(k−1),...,clip(e)_(k−22),clip(d)_(k−22)]`，共47维。主类横向恒0。h=.004、rho=exp(−.05)，kp/kv为原模型前向轴。q一阶、p/v梯形端点，旧22槽正常移位。完整辅助capture/时钟/模块状态另保留。

这22槽是**辨识代理的延迟历史**，不声称PX4原生存在一个相同的e/d FIFO，也不把实际latest-value电机链或GRU等同于它。源码联系在参考选择、捕获/恢复映射和时钟guard；代理动力学与真实控制链之间仍只有明确的条件误差接口。

令实际Y位于 `Yhat_k + Gp_k z_p + Gq_k z_q + E_k`，`||E_k||_P≤R_k`。新P是该4 ms、满斜率误差矩阵的离散Lyapunov候选，独立精确核验：

```
.5 I < P < 30000 I
P − A' P A >= .5 I
|E_p|² <= .00015 V(E), |E_v|² <= .0008 V(E), |E_q|² <= .4 V(E)
sqrt(P_33) < 5.4, sqrt(P_44) < 5.0
```

V只度量当前物理/队列误差；**不宣称它对自由变化的capture辅助状态正定或全局渐近稳定**。capture变量的G和余项由源码copy关联携带，作为参考误差输入单独入管。选择保守有理上界LP=.013、LV=.029、LQ=.633，则每步：

```
R_next = outward_ceil_1e-12(R + 5.4 E_target_position + 5 E_target_velocity
                         + 1e-8 discrete_rounding_budget + 1e-7 conditional_w_budget)
```

这里使用 `||A E||_P≤||E||_P`，未靠缩放P。捕获减速期间目标位置误差≤cap_p_err+t cap_v_err，速度误差≤cap_v_err；停止时加上述二次余项。浮点目标/观测的保守条件包络为 `EP=2^-21+1e-12 m, EV=2^-23+1e-12 m/s`。核验每步|p|/目标<16 m、|v|/目标速度<4 m/s，使binary32最近偶数舍入界适用；另加1e−12为声明的基本运算/时钟数值包络，**不是实测残差或对整个C++二进制的形式化等价证明**。实际machine conformance是外推条件。

每前缀检查：`|e_hat|+sum|G_e|+LP R+target_position_error<.5`，速度类似<1；因此全集合永不进入clip模式，差分矩阵每步适用。初始盒、当前输出界及历史移位通过归纳闭合，不先假设不饱和。若跨阈值，返回UNKNOWN，不放宽或缩域。

**具体完整决定**：输入证书规定的源参数、两时钟模式、初始关联集合及w条件，输出 `ADMIT_DECLARED_COMPLETE_EVENT_SEQUENCE_FOR_PROXY_TILT`。验证器拒绝其他配置/未知字段；没有把证书外判必败。该决定覆盖完整5251前缀，而非瞬时跳步约束。

实际交付的 [decision input](../data/p10-20261024-a2/complete-decision-input.json) 和 [decision output](../data/p10-20261024-a2/complete-decision.json)绑定独立审计哈希，列明源参数、时钟、关联初集、完整窗口、条件及拒判；不是建议未来再实现的排序接口。输入不匹配或不能证明其假设时拒证，不能因为事后轨迹看似安全而改变类定义。

| 核验项 | 有理数审计结果 |
|---|---:|
| 首超时 | .200 s年龄恰200 ms仍fresh；.204 s年龄204 ms捕获 |
| 接回 | .518 s发布，.520 s实际读取并接回，旧历史不清空 |
| 末停流再捕获 | 11.704 s，观察继续至16 s |
| 最大位置误差集合上界 | .32530096024 m |
| 最大速度误差集合上界 | .49233816470 m/s |
| 最大q集合上界 | 5.08676804786 m/s² |
| 简明充分输出阈值 | q<6，倾角<31.459535°（名义峰值不是该保证） |
| 最终余项P半径 | 8.035968408394；仍同时满足域和输出界 |
| 中心/两生成元离散舍入余项上界 | <2.974e−9 P范数/步，小于预算1e−8 |

此集合决定比单条回放增加对全部z_p/z_q、结构化初始余项及每步声明w的全称覆盖，以及状态依赖捕获/停止分支的关联检查。没有测到或声称真实节省飞行数；整个类外仍需测试/另证。

## 输出、采样间与任务范围

q采用指定常指令指数输出插值；它不是全状态连续流。p/v只在4 ms端点按梯形更新，舍入余项1e−8不含相对连续DDE的积分截断误差。无端点扰动时区间q是相邻端点的凸组合；若w在采样端加到q，额外给 `sqrt(.4)*1e−7`，仍严格低于45°对应的g。未证明连续V(X(t))耗散。

几何lift是纯俯仰、yaw0、Rzz>0，`theta=atan(|q|/g)`；实际四元数/估计器误差若要外推须另入包络。高度、最大落后/超前、追回、累计偏差、后续任务代价均未获证；原C/CR权衡保持不变，整体安全ABSTAIN。本轮没有“完整修复参数族”主张，正结果是一类完整原事件序列的倾角充分条件。

## 独立复核、反例和拒证

生成器 `construct.py`使用numpy/scipy生成候选；独立 `verify.py`只用标准库Fraction/整数，不导入生成器、原P10或P9预测器。P正定/秩一界用精确Bareiss/Sylvester，耗散用有理数Gershgorin；rho由交错Taylor级数包围，A对rho仿射与矩阵凸性涵盖整个rho区间。误差管和源码copy关联按归纳证明；区间q峰值用解析凸组合。**5251步不是拿有限扫描证明区域。** 有限18候选仅用于反例/选类，并明确披露选类发生在已见开发资料之后。

拒绝测试覆盖≥代替>、8 ms替换4 ms、以发布时间替代read、初始额外active恢复、RREC>0、清空历史后的错误q响应、漏捕获事件、错误capture生成元关联、饱和/阈值跨越、未知字段、缩到2 s观察、去掉gap及零初始位置不确定性。停止位移测试覆盖速度集合跨正负号；原A测试也继续运行。已知反例只否定对应的缺队列/漏事件描述，不断言所有无显式历史方法均不可能。

第一份中间审计 `audit-01`及之后 `construction-final/audit-final`均保留；早期部分模块/研究开关条件是验证器隐含初值。父线程请求进展后将条件显式写入证书并拒绝未知初始恢复、队列清空、RSH0、停用或错误浮点模式，正式结果另存 [construction-reviewed](../data/p10-20261024-a2/construction-reviewed/certificate.json)/[audit-source-reviewed](../data/p10-20261024-a2/audit-source-reviewed/audit.json)；P和trace字节未改，门限不放宽。这是离线证明输入的显式化，不是异常后放宽飞行接纳。没有协议/基础设施异常或飞行续跑。

本地“独立”指生成器与验证器程序分离，不代表外部审阅者亲自执行本机程序。结论供父线程独立复核；本轮没有调用子代理或读取其他代理会话。

## 复现、门槛与下一步

```bash
uav_lab/.local/venv/bin/python tools/p10r2/construct.py /tmp/p10-a2-build-NEW
python3 tools/p10r2/verify.py /tmp/p10-a2-build-NEW --output /tmp/p10-a2-check-NEW
python3 tools/p10r2/verify.py data/p10-20261024-a2/construction-reviewed --output /tmp/p10-a2-delivered-check-NEW
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uav_lab/.local/venv/bin/python -m pytest -q tests/test_p10_a2.py tests/test_p10_a.py
```

输出目录必须全新，不启动任何运行器。输入/输出哈希、源码窄摘录、复现比较、测试/成本和发布实测随本轮目录交付。构造/审计墙钟单列，不将历史辨识成本算作免费，不编造人工工时。

[最终测试](../data/p10-20261024-a2/tests-complete.log)共33项通过（包含原A测试）；最终两次标准库集合审计约1.43 s/1.42 s。独立重构的certificate、trace、nominal和18候选表均逐字节相同，cost文件单列不要求时间相同。原A的34个文件及28个P9历史输入逐项未变，见 [reproduction-and-preservation](../data/p10-20261024-a2/reproduction-and-preservation.json)。

本轮门槛逐项：**非零研究速度、真实>200 ms源码guard、完整接回及末段事件、非零初始关联集合、完整段集合准入/拒判**在声明代理/时钟/误差条件内得到正证据，提交父审；原raw证书覆盖失败和第一轮NOT_PASSED仍保留。真实模型w和machine/clock conformance并未由经验数据证明，不能把条件结论写成真实SITL保证。

下一步首要是父线程复核初始/捕获集合及精确时钟子类是否构成有价值、可被实测链完整核查的机制类；若认可，才有资格讨论机制验证冻结。还需覆盖一般yaw、RREC>0和改变guard的真实时序模式时，必须另推而非静默泛化。**是否适合讨论B设计：仅在父审认可本条件类后；本轮无论结论如何均不启动B/C/D。**

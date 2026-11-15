# PX4 RAPTOR 交接问题：实测结果与执行过程

对应[四类分类](HANDOVER_PROBLEM_TAXONOMY_20261115.md)。下文先讲实测行为，再沿代码、参考、内部状态和电机应用解释其发生过程。历史飞行、主动注入和组件验证直接标在各案例中。

## 已测到的交接问题

|类别|实测行为|最直接的对照|
|---|---|---|
|T1 接管后安全余量消耗|首推理参考准备配对：经典25.539°，神经44.126°；35°测试预算仅神经越过|继续经典、运动中进入神经、提前进入神经|
|T2 历史接续|进入时历史处理改变电机阶跃和短时失高；未执行的影子动作会积累内部偏离|默认初始化、真实动作准备、自由影子及退出快照|
|T3 参考接续|初始参考空窗156/168ms时两次约55°，缩到16ms后约30–31°|保持经典、原等待、及时恢复参考；活动超时捕获另行对比|
|T4 实际交付|完整SITL受控注入：首N应用4→8ms，通常首应用步四路仍为C、首N sample被后续N覆盖|同固定悬停任务、正常relay/有界延迟relay|

## T1：首轮参考、历史和交付正常，接管后仍消耗更多余量

同一紧弯任务继续经典控制的峰值为**25.5394°**，运动中交给RAPTOR为**44.1263°**；相对入口失高为**0.07199m / 0.28412m**。只有神经轨迹越过飞行前声明的35°测试预算，两臂均在原45°保护线内正常落地、disarm和退出。35°是本次测试预算，不是外部应用规范。

x500从4m起飞，seed20261110；tight_turn_1p8时间尺度×1.15，profile2.875s触发。两臂共用持续完整参考，最大发送间隔8.498/8.965ms；入口位置差0.04981m、速度差0.03776m/s、姿态差0.4381°。RINI4按真实经典动作准备历史，RTGT/RREC/NCO均0。

为排除之前首轮零速捕获，两臂使用同一**私有参考准备实验构建**：仅当外部参考已通过原有限性检查且接收年龄≤12ms时，跨activation reset保留原有效标志和原接收时间，不改变目标payload。之后原订阅读取、超时与保护继续执行。实际首周期又收到更新目标，因此本例直接核对的是首推理输入，而非单独衡量carry改动的收益。[实验patch](tests/handover_t1_entryready_20261115/reference-readiness.patch)与[源码/binary身份](tests/handover_t1_entryready_20261115/provenance.json)固定了这项干预，未修改共享Lab的源码或binary。

接管执行链已逐项匹配：

1. 请求52.452s，activation及首native推理52.488s，stale=0。
2. 首推理参考来自唯一发送器id902，源timestamp52.484297s，年龄3.703ms；位置、速度、yaw、yawspeed八个float32字段全部匹配。
3. 前1s共125次teacher-forced更新；进入前后GRU逐项相同，previous_action等于实际经典动作 `[0.4906628,0.4788692,0.4609033,0.4815540]`。
4. 首神经发布52.500s，四电机在52.504s应用相同sample，延迟4ms。
5. 首次越35°在55.216s。之前完整2s有251次native推理，stale=0、参考接收年龄最大4ms，四路应用年龄与物理步间隔最大4ms，sample逐一匹配神经owner。

首active后前1/2s的峰值都只有29.4775°；44.1263°出现在后续紧弯，不能只看第一秒。当前参考、历史和交付正常时，两种闭环控制对同一运动的响应仍不同：神经轨迹的45°剩余姿态余量降为0.8737°，经典为19.4606°。

[配置、配对状态及完整审计](tests/handover_t1_entryready_20261115/REPRODUCTION.md)保存3次启动：首次C因私有目录缺alias，3.225s退出未arm；补齐runtime后C2/N实际飞行均完成。流程总173.263s，失败启动成本完整保留。编译时附带重建同目标app symlink的记录亦保留，清洁复现命令已移除该附带步骤。

原两个>50°紧弯及此前两对校准全部保存在固定历史核验中。本例提供更直接的“正常接续后的余量消耗”配对观察，不把新两臂说成越过45°。

## T2：历史接续改变首个实际电机动作

P4-01a在相同10s经典悬停停用段后比较三种历史处理。下表三条代表例已从Thor原始ULog和四路motor记录逐路复核：

|处理|入口水平速度m/s|首次神经发布阶跃|失高m|四电机首应用|
|---|---:|---:|---:|---|
|reset，D2-N0-1|0.00556|0.213936|0.035299|67.776s，发布后4ms|
|自由影子，D2-N2s-1|0.01061|0.364445|0.059031|67.792s，发布后4ms|
|真实动作teacher forcing，D2-N2-1|0.00246|0.026634|0.016761|68.000s，发布后4ms|

默认初始化丢失悬停历史；自由影子继续把自己未执行的动作反馈给内部状态，使历史偏离真实经历。用真实经典动作准备历史，首个实际施加的神经输出扰动明显减小。批内各5轮阶跃均值分别为0.218258/0.377009/0.017158。三例均处于低速悬停，四路实际交付均为正常4ms，这把比较重点落在历史进入与动作生成，而不是用发布记录替代应用证据。

固定入口：[N0](https://github.com/JacksonW1025/uav_handover/blob/c186c96d6ffbaf4b04c01b234cb3f9621d616e30/data/p4-20261016-a-D2-N0-1/p3-metrics.json)、[N2s](https://github.com/JacksonW1025/uav_handover/blob/c186c96d6ffbaf4b04c01b234cb3f9621d616e30/data/p4-20261016-a-D2-N2s-1/p3-metrics.json)、[N2](https://github.com/JacksonW1025/uav_handover/blob/c186c96d6ffbaf4b04c01b234cb3f9621d616e30/data/p4-20261016-a-D2-N2-1/p3-metrics.json)，各同目录output-chain.json保存原应用审计。代码链从[退出副本保存](https://github.com/JacksonW1025/uav_handover/blob/abe54c9cedc9484c42276a53922f9ed0f5cacdba/tools/apply_research.py#L607-L635)、[进入历史选择](https://github.com/JacksonW1025/uav_handover/blob/abe54c9cedc9484c42276a53922f9ed0f5cacdba/research/state/MemoryInit.hpp#L26-L49)到[非活动仍更新上一动作、active才发布](https://github.com/JacksonW1025/uav_handover/blob/f596cf9839b496b108b405e795313901aaeb37ca/patches/raptor-final.patch#L1052-L1087)，解释了自由影子为何可能记录未执行经历。本次新增的是原始ULog与逐路应用回查，不增加飞行次数。

## T3：setpoint 信号接续异常

### T3-a：接管时参考空窗，采用默认停车目标（旧 F1，P+X）

经典 OFFBOARD → RAPTOR，x500、三维转弯、seed 20261110。E1 保持经典两次峰 25.229°/25.113°；E2 原等待两次，四电机首次应用到第一条有效外部读取为 156/168 ms，峰 55.276°/55.560°、两次保护中止；E3 缩短等待后为 16/16 ms、峰 31.184°/30.292°、两次正常落地。入口原生位置、速度、姿态、角速度及可比程度见 [F/f1-summary.json](https://github.com/JacksonW1025/uav_handover/blob/cbaf3a53914efe26b2e00444f56f16935b760a27/data/handover-f1-sync-20261112-analysis-v1/f1-summary.json) 的 request_state、entry_state 和 pairwise_states；E2-1 实际入口 NED 约 (2.666,1.790,−4.153) m 和 (0.705,1.642,0.280) m/s。E2-1 发布距请求下界 48 ms，参考有效读 208 ms，桥后实际应用距首读156 ms。不是旧目标滞留：RAPTOR 已经接管但没有有效新参考，按当前位置和零速度生成内部目标。E3 也有首帧零速度，变化是持续周期缩短；同一轨迹时钟在不同时间取样，所以首发 payload 相位不同，不把姿态峰称持续振荡。

实际数据流：[F/f1_runner.py:12–46](https://github.com/JacksonW1025/uav_handover/blob/cbaf3a53914efe26b2e00444f56f16935b760a27/data/handover-f1-sync-20261112-analysis-v1/f1_runner.py#L12-L46)，E2等mode/ACK/nav后恢复，E3监督新active、owner=1、发布后8 ms才恢复，逐电机独立核验，不把8 ms当物理证据；[F/source/project/tools/handover_100/runner.py:90–111](https://github.com/JacksonW1025/uav_handover/blob/cbaf3a53914efe26b2e00444f56f16935b760a27/data/handover-f1-sync-20261112-analysis-v1/source/project/tools/handover_100/runner.py#L90-L111) 在绝对相位生成 ROS TrajectorySetpoint（含位置、速度、偏航）与发送账本，经 XRCE-DDS 到 PX4 同名 uORB。[mc_raptor.cpp:687–719](https://github.com/JacksonW1025/uav_handover/blob/cbaf3a53914efe26b2e00444f56f16935b760a27/data/handover-f1-sync-20261112-analysis-v1/source/px4/resolved/src/modules/mc_raptor/mc_raptor.cpp#L687-L719) 按nav进入、[:145–159](https://github.com/JacksonW1025/uav_handover/blob/cbaf3a53914efe26b2e00444f56f16935b760a27/data/handover-f1-sync-20261112-analysis-v1/source/px4/resolved/src/modules/mc_raptor/mc_raptor.cpp#L145-L159)清有效性/历史，[:829–857](https://github.com/JacksonW1025/uav_handover/blob/cbaf3a53914efe26b2e00444f56f16935b760a27/data/handover-f1-sync-20261112-analysis-v1/source/px4/resolved/src/modules/mc_raptor/mc_raptor.cpp#L829-L857)读取八个必要有限字段并记当前读取时间，[:1051–1089](https://github.com/JacksonW1025/uav_handover/blob/cbaf3a53914efe26b2e00444f56f16935b760a27/data/handover-f1-sync-20261112-analysis-v1/source/px4/resolved/src/modules/mc_raptor/mc_raptor.cpp#L1051-L1089)无有效参考则捕获当前位置/偏航，v=0；[:452–546](https://github.com/JacksonW1025/uav_handover/blob/cbaf3a53914efe26b2e00444f56f16935b760a27/data/handover-f1-sync-20261112-analysis-v1/source/px4/resolved/src/modules/mc_raptor/mc_raptor.cpp#L452-L546)按目标偏航变换并裁剪位置和速度误差，[:1130–1140](https://github.com/JacksonW1025/uav_handover/blob/cbaf3a53914efe26b2e00444f56f16935b760a27/data/handover-f1-sync-20261112-analysis-v1/source/px4/resolved/src/modules/mc_raptor/mc_raptor.cpp#L1130-L1140) RL Tools 推理，[:1239–1290](https://github.com/JacksonW1025/uav_handover/blob/cbaf3a53914efe26b2e00444f56f16935b760a27/data/handover-f1-sync-20261112-analysis-v1/source/px4/resolved/src/modules/mc_raptor/mc_raptor.cpp#L1239-L1290)缩放/重排、发布门、actuator_motors与owner记录。ESC桥[GZMixingInterfaceESC.cpp:66–131](https://github.com/JacksonW1025/uav_handover/blob/cbaf3a53914efe26b2e00444f56f16935b760a27/data/handover-f1-sync-20261112-analysis-v1/source/px4/resolved/src/modules/simulation/gz_bridge/GZMixingInterfaceESC.cpp#L66-L131)传输电机输入，[ResearchMulticopterMotorModel.cc:640–669](https://github.com/JacksonW1025/uav_handover/blob/cbaf3a53914efe26b2e00444f56f16935b760a27/data/handover-f1-sync-20261112-analysis-v1/source/px4/untracked/src/modules/simulation/gz_plugins/research_motor_model/ResearchMulticopterMotorModel.cc#L640-L669)每路物理步记录refMotorInput、appliedSampleUs和stepWallNs。随后用原生ULog姿态/高度和 [F/f1-motor-curves.json](https://github.com/JacksonW1025/uav_handover/blob/cbaf3a53914efe26b2e00444f56f16935b760a27/data/handover-f1-sync-20261112-analysis-v1/f1-motor-curves.json) 复核物理输入与姿态；[F/REPORT.zh.md](https://github.com/JacksonW1025/uav_handover/blob/cbaf3a53914efe26b2e00444f56f16935b760a27/data/handover-f1-sync-20261112-analysis-v1/REPORT.zh.md)有原解释。RINI/RTGT/NCO/RREC/P12一致为0，分组没有额外H干预，不重复算T2。[F/source-identity.json](https://github.com/JacksonW1025/uav_handover/blob/cbaf3a53914efe26b2e00444f56f16935b760a27/data/handover-f1-sync-20261112-analysis-v1/source-identity.json)固定实际版本。

### T3-b：活动参考终止后，超时选择零速度（旧022/023，P+X）

[M/runs/022_active_timeout_rtgt1-a1/mechanism-audit.json](https://github.com/JacksonW1025/uav_handover/blob/46d339713cb3982ef17eace3f6ee30f45b246c48/data/handover-mutation-20261111-analysis-v1/runs/022_active_timeout_rtgt1-a1/mechanism-audit.json) 与[相应023_active_timeout_rtgt2-a1](https://github.com/JacksonW1025/uav_handover/blob/46d339713cb3982ef17eace3f6ee30f45b246c48/data/handover-mutation-20261111-analysis-v1/runs/023_active_timeout_rtgt2-a1/mechanism-audit.json)。M同提交 [tools/handover_mutation/runner.py:9–25](https://github.com/JacksonW1025/uav_handover/blob/46d339713cb3982ef17eace3f6ee30f45b246c48/tools/handover_mutation/runner.py#L9-L25) 先正常交接，看到 active 且目标不 stale 才关闭自己的发布；[tools/handover_100/runner.py:90–111](https://github.com/JacksonW1025/uav_handover/blob/46d339713cb3982ef17eace3f6ee30f45b246c48/tools/handover_100/runner.py#L90-L111) 由 reference_enabled 截断。两例首发布四路都在+4 ms应用，超时捕获均在最后有效读后204 ms。022发布52.044s、应用52.048s，33次有效外部读取，最后52.728s，52.932s出现 activation=0 的 stale 捕获：实际水平(1.9890,0.0473)m/s而目标(0,0)，超时后340ms主体峰49.168°、失高0.121m。023发布51.936s、应用51.940s，52.828s active超时以实际(2.0388,0.0445)m/s捕获，主体峰14.313°、失高0.047m并落地。它们的初始捕获及物理状态不同，是机制对照，不冒充严格同态。实际二进制、补丁、插件和策略身份已同 F1 对齐：用 F 版 [mc_raptor.cpp:829–857](https://github.com/JacksonW1025/uav_handover/blob/cbaf3a53914efe26b2e00444f56f16935b760a27/data/handover-f1-sync-20261112-analysis-v1/source/px4/resolved/src/modules/mc_raptor/mc_raptor.cpp#L829-L857)、[1051–1089](https://github.com/JacksonW1025/uav_handover/blob/cbaf3a53914efe26b2e00444f56f16935b760a27/data/handover-f1-sync-20261112-analysis-v1/source/px4/resolved/src/modules/mc_raptor/mc_raptor.cpp#L1051-L1089)、[1402–1442](https://github.com/JacksonW1025/uav_handover/blob/cbaf3a53914efe26b2e00444f56f16935b760a27/data/handover-f1-sync-20261112-analysis-v1/source/px4/resolved/src/modules/mc_raptor/mc_raptor.cpp#L1402-L1442)（RTGT=1限激活，RTGT=2也覆盖active超时）及上节相同的观察→输出→四电机链。[M/raw-source-index.json](https://github.com/JacksonW1025/uav_handover/blob/46d339713cb3982ef17eace3f6ee30f45b246c48/data/handover-mutation-20261111-analysis-v1/raw-source-index.json) 保存原始入口，[M/FINAL_REPORT.zh.md](https://github.com/JacksonW1025/uav_handover/blob/46d339713cb3982ef17eace3f6ee30f45b246c48/data/handover-mutation-20261111-analysis-v1/FINAL_REPORT.zh.md) 报告主体和清理，未确认落地不单列为T4。

### T3-c：相同中断长度，回退目标不同，恢复冲击不同

飞机已由RAPTOR沿直线约2m/s跟踪，H固定为N2。两例都主动中断参考1s，在最后有效读取后204ms进入速度匹配减速捕获，只改变超时后的目标减速度：

|减速度|恢复位置/速度跳变|原生最大倾角|失高|
|---|---|---:|---:|
|1m/s²|0.454727m / 0.814480m/s|35.136325°|0.179713m|
|2m/s²|0.767929m / 1.587384m/s|49.337401°|0.177660m|

两例捕获实际速度2.001615/2.020644m/s。相同间隙下，更快的回退目标减速把飞机与仍推进的原轨迹拉得更远，恢复时需要更大的追赶动作；2m/s²例越过45°实验安全线。这里改善突出在倾角，失高近似相同。目标恢复不是简单“重新收到数据”，还包括目标语义与时间进度的接续。

原始vehicle_attitude已独立重算，峰值与固定JSON一致；恢复附近发布命令四路均在+4ms应用。P5 first_reception_px4_us混合消息/状态记录，因此不用它硬标“第一条采用新目标的动作”。这是主动发送间隙，不是DDS自然丢包统计。P5处理名T1不等于分类T1。

固定数据：[1m/s²](https://github.com/JacksonW1025/uav_handover/blob/2deb79e2451e191623e86711c5fafed67c428513/data/p5-20261018-e2-D1.0-A0-T1a1-1/p5-metrics.json)、[2m/s²](https://github.com/JacksonW1025/uav_handover/blob/2deb79e2451e191623e86711c5fafed67c428513/data/p5-20261018-e2-D1.0-A0-T1-1/p5-metrics.json)。代码：[active超时门控](https://github.com/JacksonW1025/uav_handover/blob/2deb79e2451e191623e86711c5fafed67c428513/tools/apply_research.py#L649-L657)、[减速目标及外部参考接回](https://github.com/JacksonW1025/uav_handover/blob/2deb79e2451e191623e86711c5fafed67c428513/tools/apply_research.py#L704-L740)。原先0.3s/1.0s间隙比较及A45结果保存在固定历史核验，不从档案删除。

## T4：实际模式已切换，四电机仍消费旧经典命令

**完整PX4/RAPTOR悬停交接的受控注入对照**直接记录了命令来源滞留。正常relay与有界暂存relay各飞一次，使用同一原PX4二进制、策略、固定3.5m悬停参考和原保护。两臂都实际起飞、C→N、悬停、切回经典并正常降落。

|事件（原生μs）|正常|受控注入|
|---|---:|---:|
|模式请求下界|51148000|51348000|
|ACK accepted / nav23|51164000 / 51176000|51364000 / 51376000|
|首神经发布及桥Publish|51188000|51388000|
|发布后4ms实际四路来源/sample|N / 51188000|C / 51352000|
|四路首次N来源应用|51192000|51396000|
|该步应用的N sample|51188000|51392000|

正常首N发布后4ms应用；注入组+4ms仍用旧C，+8ms才用后续N，首N sample四路从未应用。预设40ms是整个relay暂存窗口，大部分位于首N发布之前；**实际新增首次N交付延迟是4ms，不是40ms**。

独立relay只在私有SDF中接入四个motor插件的command topic，模型和原插件不变。[runner第6–25行](tests/handover_t4_fullstack_20261115/runner.py#L6-L25)建立私有topic并在正常模式请求前触发一次窗口；[relay第14–19行](tests/handover_t4_fullstack_20261115/relay.cpp#L14-L19)暂存最新命令，到模拟窗口或100ms宿主上限先到者释放，此后一直透传。ACK、准入和安全检查未绕过。

注入窗口51.352–51.392s。51.392物理步已经执行后，relay才释放首N sample51.388，随后又收到sample51.392；51.396物理步每电机收到两条，latest-value槽采用后者。因此上游已产生并成功发布的首N命令没有成为实际电机输入。motor0在正常预期应用步仍执行C输入769.483521，而首N桥值为588.869873；下一步采用后续N输入587.058411。四路sample来源、bridge motor_speed与refMotorInput逐值一致，误差0，原ULog无dropout，bin尾完整。

这项主动注入展示了T4的实际传播：模式进入→神经发布→下游暂存→旧C仍被应用→后续N覆盖首N。两臂倾角1.893°/1.614°、失高0.0462/0.0360m，均正常落地disarm，没有观察到飞行性能恶化。它证明交付契约被注入改变，而非把这次悬停称为自然缺陷或危险越界。

[计划、源代码、窗口CSV和逐四路审计](tests/handover_t4_fullstack_20261115/REPRODUCTION.md)保存两次启动，总wall145.916s、CPU69.429s，无重试。此前旧发布者回跳、P8活动期间旧sample保持及真实单转子8ms注入结果仍保留在固定历史审计与原小材料中；这些不同证据不混成同一个故障或新增飞行。

## 代码与历史审计

请求、Commander准入/nav、控制标志、参考读取、神经/经典计算、发布仲裁、输出桥和电机物理步是不同事件。代码行号依各次真实源码版本，不跨版本套用；“命令已发布”与“物理步已应用”分别核对。

[固定历史核验文档](https://github.com/JacksonW1025/uav_handover/blob/3720a9e8438453be0b57e4a85c475a78d9e09bb6/HANDOVER_TAXONOMY_EVIDENCE_20261115.md)保留共用链精确源码位置、完整版本哈希、原始负结果、校准过程、成本和逐项审计。此次改写不删除这些记录，也不把历史案例重复计成新增飞行。本轮新增为T1三次启动（一次未arm失败、两次完成飞行）与T4两次完成飞行；总启动5次、实际飞行4次，原材料和失败成本保留。


## 本次材料整理

原分类和README未改，旧证据目录未覆盖。新增T1首推理准备配对与T4完整SITL注入的小型配置、源码、审计和图表；不提交private-build、编译程序或大原始日志。as-run-sha256和published-sha256分别记录原始/发布副本，路径参数化及换行规范化均有说明。整理后脚本只做语法检查，未重跑飞行；历史固定引用与材料链接已核对。

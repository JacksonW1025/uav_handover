# F1：发现来源与代码链

## 发现历史不是本轮结果

2026-10-13 P1已报告reset hold、零速度返回交接点；10-15 P2分离历史与零速目标；10-16 P4对比捕获语义；10-18 P5研究活动期间参考超时。11月Mission单例不是首次发现参考语义，而是暴露runner等待与首次参考抵达的具体窗口。

`docs/THOR_CN_SINGLE_20261109_REPORT.md`及`data/cn-single-20261109-final-v1`记录四电机66.464s至首有效参考66.724s（260ms）。`tools/cn_single/runner.py:179–206`请求前锚定参考，185行阻塞等待mode返回，然后才发布。这个窗口内的零速目标来自reset后的内部捕获，不是已证明的旧外部命令滞留。

旧quickcheck C虽提前发送，但首参考可能在经典电机持权时抵达，且B/C初态速度相差3.231m/s。不能用它充当干净同步消融。022/023的49.168°与14.313°比较则是活动期间超时后的目标语义变更，不等同初始同步修复。

## 本轮唯一干预

`f1_runner.py:34–43`同一绝对轨迹时间处请求；E1在37行保持经典及连续流。E2在15行阻止等待期间发送，在44–46行mode正常完成才恢复。E3在16–28行要求新active消息、owner=1神经发布记录、原生时钟至少比该发布晚8ms，再恢复；44行正常命令/ACK/nav核验仍进行。29行调用原有publish，不重置轨迹相位，不改轨迹速度或位置。不提前写共享目标通道的结论需四电机stepWallNs独立验证，8ms条件本身不是四电机物理证据。

E3的两次listener是有成本的读操作，因此只能把实际测量空窗当作结果，不能假设它是理想无延迟同步。首条参考取同一绝对时钟的当时轨迹点，首发较早所以数值与E2稍不同，这是同步改变的自然结果，不是额外目标补偿。

## PX4实际控制链

源码路径前缀为 `uav_lab/.local/checkouts/px4-raptor/`。

- `src/modules/mc_raptor/mc_raptor.cpp:145–159` reset清零参考有效时间、previous_action及网络状态；687–719由实际nav确定active并在进入时reset及选择历史模式。本轮RINI=0。
- 同文件829–857只接收position/velocity/yaw/yawspeed全部有限的新参考，更新last-valid-read。接受时间是控制器读取时间，不是发送者时间。
- 同文件1051–1089在无有效参考、内部参考或200ms过期条件下捕获当前位置与yaw、将目标速度置零。本轮RTGT=0，未增加速度匹配或补偿。
- 同文件1130观察构造，1140推理，1239–1290动作至电机映射和owner1发布。P11记录network_target_velocity/position、policy_input、executor_action、last_valid_read_us、external_valid、stale、activation，可以区分目标捕获与真正旧参考保留。
- `src/modules/simulation/gz_bridge/GZMixingInterfaceESC.cpp:90–130`桥接样本发布不等于执行；`src/modules/simulation/gz_plugins/research_motor_model/ResearchMulticopterMotorModel.cc:651–669`四路分别记录实际appliedSampleUs、simUs、stepWallNs。必须从四路实际记录确定首次应用。
- mc_raptor.cpp1407–1414的P12可能覆盖RTGT，因此需同时核查P12关闭和research_target实际mode=0。

应记录整个链：请求→ACK/nav/active→激活零速捕获→神经推理/发布→四电机应用→外部首发→有效读取→目标与动作变化→姿态/高度。时间基准不得混用；发送与实际电机墙钟比较用同宿主monotonic时钟，控制器/仿真事件用原生microseconds。

## 结论边界

若E2更危险且E3空窗缩短，只能在初态可比和输出链证实后支持本案例的参考接续机制。必须按签名姿态/位置曲线识别往复变化；单一倾角峰不能叫持续振荡。零速度捕获不能写成旧参考命令滞留。经典控制本轮是Offboard，不是原Mission原样回放；失败截断后不得填满两秒或全窗。

源码身份：本轮结束复核 mc_raptor.cpp SHA-256 `f6081a683ea77e327aca64608501c342970b8d173a60b8571a8fc2f9bfcfe7e5`。仓库HEAD为`003cd249a`，原有工作未覆盖；实验程序与计划在每次启动前保存哈希，六次candidate_unchanged均为true。六例初始RINI/RTGT/NCO/RREC/P12均为0且相关参数无中途变更，见parameter-audit.json。

# fresh→timeout计划与实际activation捕获：分开判定

015–017没有实现计划中的在N已active后外部目标超时捕获。原始证据限定汇总保持不变；这里另列已实现物理轨迹的冻结/任务判据，禁止把实际activation通过解释为active-timeout通过。

## 015_fresh_then_timeout_rtgt0-a1
声明接管前静默=0.0s；实际active-timeout捕获=0；场景=NOT_REALIZED_ACTIVE_TIMEOUT。
已实现物理冻结=FAILURE；已实现物理任务=FAILURE；原始证据限定冻结/任务=FAILURE/FAILURE；落地=False。
主体峰=53.244°@0.372s。
捕获native=52004000µs，activation=1，模式=0，机体水平速度=[1.9745270013809204, 0.12537792325019836]，目标水平速度=[0.0, 0.0]。
最后inactive：timestamp=52000000，last_valid_read_us=51964000，stale=0。首个active：timestamp=52004000，last_valid_read_us=0，stale=1。

## 016_fresh_then_timeout_rtgt1-a1
声明接管前静默=0.0s；实际active-timeout捕获=0；场景=NOT_REALIZED_ACTIVE_TIMEOUT。
已实现物理冻结=SUCCESS；已实现物理任务=SUCCESS；原始证据限定冻结/任务=UNKNOWN/UNKNOWN；落地=True。
主体峰=13.327°@0.504s。
捕获native=52112000µs，activation=1，模式=1，机体水平速度=[1.9830914735794067, 0.08990426361560822]，目标水平速度=[1.9830914735794067, 0.08990426361560822]。
最后inactive：timestamp=52108000，last_valid_read_us=52084000，stale=0。首个active：timestamp=52112000，last_valid_read_us=0，stale=1。

## 017_fresh_then_timeout_rtgt2-a1
声明接管前静默=0.0s；实际active-timeout捕获=0；场景=NOT_REALIZED_ACTIVE_TIMEOUT。
已实现物理冻结=SUCCESS；已实现物理任务=SUCCESS；原始证据限定冻结/任务=UNKNOWN/UNKNOWN；落地=True。
主体峰=12.991°@0.504s。
捕获native=51704000µs，activation=1，模式=2，机体水平速度=[1.9635111093521118, 0.12712353467941284]，目标水平速度=[1.9635111093521118, 0.12712353467941284]。
最后inactive：timestamp=51700000，last_valid_read_us=51668000，stale=0。首个active：timestamp=51704000，last_valid_read_us=0，stale=1。

## 022_active_timeout_rtgt1-a1
声明接管前静默=未使用接管前静默；实际active-timeout捕获=1；场景=VERIFIED_ACTIVE_TIMEOUT。
已实现物理冻结=FAILURE；已实现物理任务=FAILURE；原始证据限定冻结/任务=FAILURE/FAILURE；落地=False。
主体峰=49.168°@1.228s。
捕获native=52932000µs，activation=0，模式=1，机体水平速度=[1.9889945983886719, 0.047332148998975754]，目标水平速度=[0.0, 0.0]。
最后inactive：timestamp=52028000，last_valid_read_us=52008000，stale=0。首个active：timestamp=52032000，last_valid_read_us=52032000，stale=0。

## 023_active_timeout_rtgt2-a1
声明接管前静默=未使用接管前静默；实际active-timeout捕获=1；场景=VERIFIED_ACTIVE_TIMEOUT。
已实现物理冻结=SUCCESS；已实现物理任务=SUCCESS；原始证据限定冻结/任务=SUCCESS/SUCCESS；落地=True。
主体峰=14.313°@1.664s。
捕获native=51924000µs，activation=1，模式=2，机体水平速度=[1.9888911247253418, 0.11626049876213074]，目标水平速度=[1.9888911247253418, 0.11626049876213074]。
捕获native=52828000µs，activation=0，模式=2，机体水平速度=[2.0388405323028564, 0.04445121809840202]，目标水平速度=[2.0388405323028564, 0.04445121809840202]。
最后inactive：timestamp=51920000，last_valid_read_us=51916000，stale=0。首个active：timestamp=51924000，last_valid_read_us=0，stale=1。

## 第2轮设计偏差与第3轮修正
当前tools/handover_100/runner.py:114–138在handover_reference=native时先关流，再请求N；quiet=0仅去掉等待，不让外部流跨越activation继续有效。015–017的原生日志直接证明该流程走activation。单调增加进入前quiet到0.10或0.18秒不能构成可靠active-timeout对照。因此第3轮没有继续该名义静默补点。第3轮另以active_timeout_after_s扩展编排，使用新的候选记录；必须检查N持权后fresh读取再activation=0捕获，不能与第1/2轮冒充完全同候选因果配对。

# 目标、记忆和电机证据审计

原生捕获事件不等于神经最终消费目标，必须与P11实际网络目标并看。发布到trajectory_setpoint且C持权，不自动证明经典控制器具体哪次循环读取，但足以禁止“仅N受到目标突变”因果表述。

## 002_control_matched_2p0-a1
原始ULog哈希一致=True；原始数据保留={'flight.ulg': {'exists': True, 'bytes': 55581518}, 'events.jsonl': {'exists': True, 'bytes': 20110}, 'telemetry.jsonl': {'exists': True, 'bytes': 272502}, 'explore-setpoints.jsonl': {'exists': True, 'bytes': 55567}, 'gz-motor': {'exists': True, 'bytes': None}}。
- 四电机应用=True；RINI=0，记忆机制=VERIFIED。
- 主体active采样=4176，external_valid=0，stale=4176。native设计=True。
- activation，owner后-0.016000s，模式1，预期水平目标=vehicle velocity，残差=0.00000000m/s，VERIFIED。

## 003_speed_zero_1p6-a1
原始ULog哈希一致=True；原始数据保留={'flight.ulg': {'exists': True, 'bytes': 54939450}, 'events.jsonl': {'exists': True, 'bytes': 20156}, 'telemetry.jsonl': {'exists': True, 'bytes': 273252}, 'explore-setpoints.jsonl': {'exists': True, 'bytes': 56774}, 'gz-motor': {'exists': True, 'bytes': None}}。
- 四电机应用=True；RINI=0，记忆机制=VERIFIED。
- 主体active采样=4180，external_valid=0，stale=4180。native设计=True。
- activation，owner后-0.008000s，模式0，预期水平目标=zero，残差=0.00000000m/s，VERIFIED。

## 004_speed_zero_1p8-a1
原始ULog哈希一致=True；原始数据保留={'flight.ulg': {'exists': True, 'bytes': 34097473}, 'events.jsonl': {'exists': True, 'bytes': 18785}, 'telemetry.jsonl': {'exists': True, 'bytes': 163294}, 'explore-setpoints.jsonl': {'exists': True, 'bytes': 57180}, 'gz-motor': {'exists': True, 'bytes': None}}。
- 四电机应用=True；RINI=0，记忆机制=VERIFIED。
- 主体active采样=79，external_valid=0，stale=79。native设计=True。
- activation，owner后-0.012000s，模式0，预期水平目标=zero，残差=0.00000000m/s，VERIFIED。

## 005_speed_zero_2p2-a1
原始ULog哈希一致=True；原始数据保留={'flight.ulg': {'exists': True, 'bytes': 34314365}, 'events.jsonl': {'exists': True, 'bytes': 18776}, 'telemetry.jsonl': {'exists': True, 'bytes': 165009}, 'explore-setpoints.jsonl': {'exists': True, 'bytes': 55322}, 'gz-motor': {'exists': True, 'bytes': None}}。
- 四电机应用=True；RINI=0，记忆机制=VERIFIED。
- 主体active采样=82，external_valid=0，stale=82。native设计=True。
- activation，owner后-0.012000s，模式0，预期水平目标=zero，残差=0.00000000m/s，VERIFIED。

## 006_control_matched_2p2-a1
原始ULog哈希一致=True；原始数据保留={'flight.ulg': {'exists': True, 'bytes': 55740414}, 'events.jsonl': {'exists': True, 'bytes': 20135}, 'telemetry.jsonl': {'exists': True, 'bytes': 274842}, 'explore-setpoints.jsonl': {'exists': True, 'bytes': 55246}, 'gz-motor': {'exists': True, 'bytes': None}}。
- 四电机应用=True；RINI=0，记忆机制=VERIFIED。
- 主体active采样=4176，external_valid=0，stale=4176。native设计=True。
- activation，owner后-0.012000s，模式1，预期水平目标=vehicle velocity，残差=0.00000000m/s，VERIFIED。

## 007_external_freeze_2p0-a1
原始ULog哈希一致=True；原始数据保留={'flight.ulg': {'exists': True, 'bytes': 33993180}, 'events.jsonl': {'exists': True, 'bytes': 18590}, 'telemetry.jsonl': {'exists': True, 'bytes': 162371}, 'explore-setpoints.jsonl': {'exists': True, 'bytes': 61000}, 'gz-motor': {'exists': True, 'bytes': None}}。
- 四电机应用=True；RINI=0，记忆机制=VERIFIED。
- 主体active采样=92，external_valid=18，stale=0。native设计=False。
- activation，owner后-0.012000s，模式0，预期水平目标=zero，残差=0.00000000m/s，VERIFIED。
- 外部freeze：首个匹配发布相对N owner提前23.753ms，发布时owner=2（2=C），后续C电机发布5条。不能称N独有目标突变。

## 008_external_brake_2p0-a1
原始ULog哈希一致=True；原始数据保留={'flight.ulg': {'exists': True, 'bytes': 55215381}, 'events.jsonl': {'exists': True, 'bytes': 19914}, 'telemetry.jsonl': {'exists': True, 'bytes': 274294}, 'explore-setpoints.jsonl': {'exists': True, 'bytes': 296614}, 'gz-motor': {'exists': True, 'bytes': None}}。
- 四电机应用=True；RINI=0，记忆机制=VERIFIED。
- 主体active采样=4244，external_valid=838，stale=0。native设计=False。
- 外部brake：首个匹配发布相对N owner提前15.950ms，发布时owner=2（2=C），后续C电机发布3条。不能称N独有目标突变。

## 009_direction_ypos-a1
原始ULog哈希一致=True；原始数据保留={'flight.ulg': {'exists': True, 'bytes': 35877894}, 'events.jsonl': {'exists': True, 'bytes': 19419}, 'telemetry.jsonl': {'exists': True, 'bytes': 173076}, 'explore-setpoints.jsonl': {'exists': True, 'bytes': 62684}, 'gz-motor': {'exists': True, 'bytes': None}}。
- 四电机应用=True；RINI=0，记忆机制=VERIFIED。
- 主体active采样=82，external_valid=0，stale=82。native设计=True。
- activation，owner后-0.012000s，模式0，预期水平目标=zero，残差=0.00000000m/s，VERIFIED。

## 010_direction_xneg-a1
原始ULog哈希一致=True；原始数据保留={'flight.ulg': {'exists': True, 'bytes': 36070772}, 'events.jsonl': {'exists': True, 'bytes': 19401}, 'telemetry.jsonl': {'exists': True, 'bytes': 173189}, 'explore-setpoints.jsonl': {'exists': True, 'bytes': 62707}, 'gz-motor': {'exists': True, 'bytes': None}}。
- 四电机应用=True；RINI=0，记忆机制=VERIFIED。
- 主体active采样=104，external_valid=0，stale=104。native设计=True。
- activation，owner后-0.012000s，模式0，预期水平目标=zero，残差=0.00000000m/s，VERIFIED。

## 011_direction_yneg-a1
原始ULog哈希一致=True；原始数据保留={'flight.ulg': {'exists': True, 'bytes': 55023699}, 'events.jsonl': {'exists': True, 'bytes': 20667}, 'telemetry.jsonl': {'exists': True, 'bytes': 272830}, 'explore-setpoints.jsonl': {'exists': True, 'bytes': 63365}, 'gz-motor': {'exists': True, 'bytes': None}}。
- 四电机应用=True；RINI=0，记忆机制=VERIFIED。
- 主体active采样=4177，external_valid=0，stale=4177。native设计=True。
- inactive_capture，owner后-0.096000s，模式0，预期水平目标=zero，残差=0.00000000m/s，VERIFIED。
- activation，owner后-0.012000s，模式0，预期水平目标=zero，残差=0.00000000m/s，VERIFIED。

## 012_direction_diagonal-a1
原始ULog哈希一致=True；原始数据保留={'flight.ulg': {'exists': True, 'bytes': 34082024}, 'events.jsonl': {'exists': True, 'bytes': 19349}, 'telemetry.jsonl': {'exists': True, 'bytes': 163791}, 'explore-setpoints.jsonl': {'exists': True, 'bytes': 62406}, 'gz-motor': {'exists': True, 'bytes': None}}。
- 四电机应用=True；RINI=0，记忆机制=VERIFIED。
- 主体active采样=81，external_valid=0，stale=81。native设计=True。
- activation，owner后-0.012000s，模式0，预期水平目标=zero，残差=0.00000000m/s，VERIFIED。

## 013_history_shadow-a1
原始ULog哈希一致=True；原始数据保留={'flight.ulg': {'exists': True, 'bytes': 34147570}, 'events.jsonl': {'exists': True, 'bytes': 18970}, 'telemetry.jsonl': {'exists': True, 'bytes': 163821}, 'explore-setpoints.jsonl': {'exists': True, 'bytes': 55394}, 'gz-motor': {'exists': True, 'bytes': None}}。
- 四电机应用=True；RINI=1，记忆机制=VERIFIED。
- 主体active采样=80，external_valid=0，stale=80。native设计=True。
- inactive_capture，owner后-0.096000s，模式0，预期水平目标=zero，残差=0.00000000m/s，VERIFIED。
- activation，owner后-0.012000s，模式0，预期水平目标=zero，残差=0.00000000m/s，VERIFIED。

## 014_history_teacher-a1
原始ULog哈希一致=True；原始数据保留={'flight.ulg': {'exists': True, 'bytes': 33991772}, 'events.jsonl': {'exists': True, 'bytes': 18935}, 'telemetry.jsonl': {'exists': True, 'bytes': 163531}, 'explore-setpoints.jsonl': {'exists': True, 'bytes': 55348}, 'gz-motor': {'exists': True, 'bytes': None}}。
- 四电机应用=True；RINI=4，记忆机制=VERIFIED。
- 主体active采样=83，external_valid=0，stale=83。native设计=True。
- activation，owner后-0.016000s，模式0，预期水平目标=zero，残差=0.00000000m/s，VERIFIED。

## 015_fresh_then_timeout_rtgt0-a1
原始ULog哈希一致=True；原始数据保留={'flight.ulg': {'exists': True, 'bytes': 33892405}, 'events.jsonl': {'exists': True, 'bytes': 19226}, 'telemetry.jsonl': {'exists': True, 'bytes': 161996}, 'explore-setpoints.jsonl': {'exists': True, 'bytes': 55432}, 'gz-motor': {'exists': True, 'bytes': None}}。
- 四电机应用=True；RINI=0，记忆机制=VERIFIED。
- 主体active采样=94，external_valid=0，stale=94。native设计=True。
- activation，owner后-0.012000s，模式0，预期水平目标=zero，残差=0.00000000m/s，VERIFIED。

## 016_fresh_then_timeout_rtgt1-a1
原始ULog哈希一致=True；原始数据保留={'flight.ulg': {'exists': True, 'bytes': 55553090}, 'events.jsonl': {'exists': True, 'bytes': 20598}, 'telemetry.jsonl': {'exists': True, 'bytes': 272901}, 'explore-setpoints.jsonl': {'exists': True, 'bytes': 55078}, 'gz-motor': {'exists': True, 'bytes': None}}。
- 四电机应用=True；RINI=0，记忆机制=VERIFIED。
- 主体active采样=4246，external_valid=0，stale=4246。native设计=True。
- activation，owner后-0.012000s，模式1，预期水平目标=vehicle velocity，残差=0.00000000m/s，VERIFIED。

## 017_fresh_then_timeout_rtgt2-a1
原始ULog哈希一致=True；原始数据保留={'flight.ulg': {'exists': True, 'bytes': 55263176}, 'events.jsonl': {'exists': True, 'bytes': 20600}, 'telemetry.jsonl': {'exists': True, 'bytes': 272285}, 'explore-setpoints.jsonl': {'exists': True, 'bytes': 55343}, 'gz-motor': {'exists': True, 'bytes': None}}。
- 四电机应用=True；RINI=0，记忆机制=VERIFIED。
- 主体active采样=4241，external_valid=0，stale=4241。native设计=True。
- activation，owner后-0.012000s，模式2，预期水平目标=vehicle velocity，残差=0.00000000m/s，VERIFIED。

## 018_speed_zero_1p7-a1
原始ULog哈希一致=True；原始数据保留={'flight.ulg': {'exists': True, 'bytes': 55082976}, 'events.jsonl': {'exists': True, 'bytes': 20234}, 'telemetry.jsonl': {'exists': True, 'bytes': 273196}, 'explore-setpoints.jsonl': {'exists': True, 'bytes': 56726}, 'gz-motor': {'exists': True, 'bytes': None}}。
- 四电机应用=True；RINI=0，记忆机制=VERIFIED。
- 主体active采样=4180，external_valid=0，stale=4180。native设计=True。
- activation，owner后-0.016000s，模式0，预期水平目标=zero，残差=0.00000000m/s，VERIFIED。

## 019_seed2_zero_1p6-a1
原始ULog哈希一致=True；原始数据保留={'flight.ulg': {'exists': True, 'bytes': 54826271}, 'events.jsonl': {'exists': True, 'bytes': 20326}, 'telemetry.jsonl': {'exists': True, 'bytes': 271950}, 'explore-setpoints.jsonl': {'exists': True, 'bytes': 56979}, 'gz-motor': {'exists': True, 'bytes': None}}。
- 四电机应用=True；RINI=0，记忆机制=VERIFIED。
- 主体active采样=4178，external_valid=0，stale=4178。native设计=True。
- activation，owner后-0.008000s，模式0，预期水平目标=zero，残差=0.00000000m/s，VERIFIED。

## 020_seed2_zero_1p8-a1
原始ULog哈希一致=True；原始数据保留={'flight.ulg': {'exists': True, 'bytes': 35959535}, 'events.jsonl': {'exists': True, 'bytes': 19064}, 'telemetry.jsonl': {'exists': True, 'bytes': 172993}, 'explore-setpoints.jsonl': {'exists': True, 'bytes': 57153}, 'gz-motor': {'exists': True, 'bytes': None}}。
- 四电机应用=True；RINI=0，记忆机制=VERIFIED。
- 主体active采样=103，external_valid=0，stale=103。native设计=True。
- activation，owner后-0.012000s，模式0，预期水平目标=zero，残差=0.00000000m/s，VERIFIED。

## 021_seed2_direction_yneg-a1
原始ULog哈希一致=True；原始数据保留={'flight.ulg': {'exists': True, 'bytes': 36326897}, 'events.jsonl': {'exists': True, 'bytes': 19193}, 'telemetry.jsonl': {'exists': True, 'bytes': 174415}, 'explore-setpoints.jsonl': {'exists': True, 'bytes': 63142}, 'gz-motor': {'exists': True, 'bytes': None}}。
- 四电机应用=True；RINI=0，记忆机制=VERIFIED。
- 主体active采样=105，external_valid=0，stale=105。native设计=True。
- activation，owner后-0.012000s，模式0，预期水平目标=zero，残差=0.00000000m/s，VERIFIED。

## 022_active_timeout_rtgt1-a1
原始ULog哈希一致=True；原始数据保留={'flight.ulg': {'exists': True, 'bytes': 36300684}, 'events.jsonl': {'exists': True, 'bytes': 19063}, 'telemetry.jsonl': {'exists': True, 'bytes': 174573}, 'explore-setpoints.jsonl': {'exists': True, 'bytes': 64354}, 'gz-motor': {'exists': True, 'bytes': None}}。
- 四电机应用=True；RINI=0，记忆机制=VERIFIED。
- 主体active采样=320，external_valid=33，stale=98。native设计=False。
- active_timeout，owner后0.888000s，模式1，预期水平目标=zero，残差=0.00000000m/s，VERIFIED。

## 023_active_timeout_rtgt2-a1
原始ULog哈希一致=True；原始数据保留={'flight.ulg': {'exists': True, 'bytes': 55388478}, 'events.jsonl': {'exists': True, 'bytes': 20300}, 'telemetry.jsonl': {'exists': True, 'bytes': 273253}, 'explore-setpoints.jsonl': {'exists': True, 'bytes': 64550}, 'gz-motor': {'exists': True, 'bytes': None}}。
- 四电机应用=True；RINI=0，记忆机制=VERIFIED。
- 主体active采样=4243，external_valid=34，stale=4020。native设计=False。
- activation，owner后-0.012000s，模式2，预期水平目标=vehicle velocity，残差=0.00000000m/s，VERIFIED。
- active_timeout，owner后0.892000s，模式2，预期水平目标=vehicle velocity，残差=0.00000000m/s，VERIFIED。


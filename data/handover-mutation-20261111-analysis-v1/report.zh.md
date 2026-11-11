# 069种子变异实验：离线独立分析

仅纳入PHYSICAL_END后的最终证据。基础设施中断不算安全样本；保护退出后未观测到落地不写成已落地。冻结主判据与任务判据保留并列，不调阈值。所有峰值是保护干预前的已观察峰值，不能推断无保护峰值。

同seed与同名义参考不保证同入口状态；RTGT、外部freeze/brake的比较不是严格因果配对。一个或少量seed、适应性选例不能推导总体事故率或安全界限。先比较实际速度、姿态、角速度、目标生效和物理电机接管。

## 001_reproduce_zero_2p0-a1
证据=INCOMPLETE；冻结=UNKNOWN；任务=UNKNOWN；主体实际交接=0；正常落地disarm=未在原实验确认。
场景实现=NO_SUBJECT_HANDOVER；已实现物理冻结/任务=UNKNOWN/UNKNOWN。原始证据限定判据保持不变。
原实验在主体交接前中断；独立恢复确认落地和disarm，但不把恢复拼成原实验成功。
证据缺口：Original runner interrupted before subject; no subject handover. Recovery is independent.

## 002_control_matched_2p0-a1
证据=MEASURED；冻结=SUCCESS；任务=SUCCESS；主体实际交接=1；正常落地disarm=True。
场景实现=OBSERVED_REQUESTED_HANDOVER；已实现物理冻结/任务=SUCCESS/SUCCESS。原始证据限定判据保持不变。
- C→N owner=52372000µs；四电机物理应用=True。入口位置=[4.4345, -0.0206, -2.9626]m，速度=[1.9488, 0.1038, 0.0087]m/s，角速度=[0.1849, -0.0071, -0.0286]rad/s。
- 首0.25/0.5/1/2秒峰倾角：8.5405/12.6543/12.6726/12.6726°；对应实际观察时长：0.2500/0.5000/1.0000/2.0000s。
- 已观测主体峰值=12.6726°，发生在owner后0.5200s。入口相对失高=0.0492m；低于实际活动目标最大=0.0496m。最大单轴角速率=0.8633rad/s；电机连续饱和=0.0000s。
- activation=VERIFIED；捕获机体速度=[1.9521, 0.1053, 0.0091]；原生目标速度=[1.9521, 0.1053, 0.0000]m/s。外部参考是否真正消费另见JSON的reference_evidence与first_neural_consumed_state。
- 冻结=SUCCESS []；任务=SUCCESS；主体结束原因=explore_subject_finished。
证据缺口：无已识别缺口

## 003_speed_zero_1p6-a1
证据=MEASURED；冻结=SUCCESS；任务=SUCCESS；主体实际交接=1；正常落地disarm=True。
场景实现=OBSERVED_REQUESTED_HANDOVER；已实现物理冻结/任务=SUCCESS/SUCCESS。原始证据限定判据保持不变。
- C→N owner=52212000µs；四电机物理应用=True。入口位置=[3.5542, -0.0155, -3.0342]m，速度=[1.5650, 0.0813, 0.0094]m/s，角速度=[0.1536, -0.0071, -0.0078]rad/s。
- 首0.25/0.5/1/2秒峰倾角：36.8824/44.1848/44.1848/44.1848°；对应实际观察时长：0.2500/0.5000/1.0000/2.0000s。
- 已观测主体峰值=44.1848°，发生在owner后0.3480s。入口相对失高=0.3519m；低于实际活动目标最大=0.3519m。最大单轴角速率=3.9083rad/s；电机连续饱和=0.0000s。
- activation=VERIFIED；捕获机体速度=[1.5663, 0.0815, 0.0095]；原生目标速度=[0.0000, 0.0000, 0.0000]m/s。外部参考是否真正消费另见JSON的reference_evidence与first_neural_consumed_state。
- 冻结=SUCCESS []；任务=SUCCESS；主体结束原因=explore_subject_finished。
证据缺口：无已识别缺口

## 004_speed_zero_1p8-a1
证据=MEASURED；冻结=FAILURE；任务=FAILURE；主体实际交接=1；正常落地disarm=False。
场景实现=OBSERVED_REQUESTED_HANDOVER；已实现物理冻结/任务=FAILURE/FAILURE。原始证据限定判据保持不变。
- C→N owner=52304000µs；四电机物理应用=True。入口位置=[4.0292, -0.0444, -2.9969]m，速度=[1.7249, 0.0765, 0.0047]m/s，角速度=[0.1537, -0.0051, -0.0180]rad/s。
- 首0.25/0.5/1/2秒峰倾角：38.1272/45.9760/45.9760/45.9760°；对应实际观察时长：0.2500/0.3120/0.3120/0.3120s。
- 已观测主体峰值=45.9760°，发生在owner后0.3120s。入口相对失高=0.0811m；低于实际活动目标最大=0.0812m。最大单轴角速率=3.8747rad/s；电机连续饱和=0.0000s。
- activation=VERIFIED；捕获机体速度=[1.7278, 0.0768, 0.0048]；原生目标速度=[0.0000, 0.0000, 0.0000]m/s。外部参考是否真正消费另见JSON的reference_evidence与first_neural_consumed_state。
- 冻结=FAILURE ['max_tilt_deg', 'runner safety abort']；任务=FAILURE；主体结束原因=failure。
证据缺口：无已识别缺口

## 005_speed_zero_2p2-a1
证据=MEASURED；冻结=FAILURE；任务=FAILURE；主体实际交接=1；正常落地disarm=False。
场景实现=OBSERVED_REQUESTED_HANDOVER；已实现物理冻结/任务=FAILURE/FAILURE。原始证据限定判据保持不变。
- C→N owner=52580000µs；四电机物理应用=True。入口位置=[4.9112, 0.0078, -2.9549]m，速度=[2.1272, 0.0980, 0.0147]m/s，角速度=[0.1977, -0.0079, -0.0210]rad/s。
- 首0.25/0.5/1/2秒峰倾角：39.8978/50.8387/50.8387/50.8387°；对应实际观察时长：0.2500/0.3240/0.3240/0.3240s。
- 已观测主体峰值=50.8387°，发生在owner后0.3240s。入口相对失高=0.0934m；低于实际活动目标最大=0.0935m。最大单轴角速率=3.9455rad/s；电机连续饱和=0.0000s。
- activation=VERIFIED；捕获机体速度=[2.1294, 0.0986, 0.0147]；原生目标速度=[0.0000, 0.0000, 0.0000]m/s。外部参考是否真正消费另见JSON的reference_evidence与first_neural_consumed_state。
- 冻结=FAILURE ['max_tilt_deg', 'runner safety abort']；任务=FAILURE；主体结束原因=failure。
证据缺口：无已识别缺口

## 006_control_matched_2p2-a1
证据=MEASURED；冻结=SUCCESS；任务=SUCCESS；主体实际交接=1；正常落地disarm=True。
场景实现=OBSERVED_REQUESTED_HANDOVER；已实现物理冻结/任务=SUCCESS/SUCCESS。原始证据限定判据保持不变。
- C→N owner=52396000µs；四电机物理应用=True。入口位置=[4.9164, -0.0650, -3.0133]m，速度=[2.1638, 0.0813, 0.0175]m/s，角速度=[0.2068, -0.0153, -0.0006]rad/s。
- 首0.25/0.5/1/2秒峰倾角：7.7312/12.6033/12.7384/12.7384°；对应实际观察时长：0.2500/0.5000/1.0000/2.0000s。
- 已观测主体峰值=12.7384°，发生在owner后0.5480s。入口相对失高=0.0405m；低于实际活动目标最大=0.0405m。最大单轴角速率=0.8658rad/s；电机连续饱和=0.0000s。
- activation=VERIFIED；捕获机体速度=[2.1659, 0.0816, 0.0175]；原生目标速度=[2.1659, 0.0816, 0.0000]m/s。外部参考是否真正消费另见JSON的reference_evidence与first_neural_consumed_state。
- 冻结=SUCCESS []；任务=SUCCESS；主体结束原因=explore_subject_finished。
证据缺口：无已识别缺口

## 007_external_freeze_2p0-a1
证据=MEASURED；冻结=FAILURE；任务=FAILURE；主体实际交接=1；正常落地disarm=False。
场景实现=OBSERVED_REQUESTED_HANDOVER；已实现物理冻结/任务=FAILURE/FAILURE。原始证据限定判据保持不变。
- C→N owner=52160000µs；四电机物理应用=True。入口位置=[4.0054, -0.0833, -2.9786]m，速度=[1.9596, 0.0997, 0.0103]m/s，角速度=[-0.0504, 0.0232, -0.0449]rad/s。
- 首0.25/0.5/1/2秒峰倾角：42.3366/56.0527/56.0527/56.0527°；对应实际观察时长：0.2500/0.3640/0.3640/0.3640s。
- 已观测主体峰值=56.0527°，发生在owner后0.3640s。入口相对失高=0.1214m；低于实际活动目标最大=0.1204m。最大单轴角速率=4.4529rad/s；电机连续饱和=0.0000s。
- activation=VERIFIED；捕获机体速度=[1.9602, 0.1001, 0.0107]；原生目标速度=[0.0000, 0.0000, 0.0000]m/s。外部参考是否真正消费另见JSON的reference_evidence与first_neural_consumed_state。
- 冻结=FAILURE ['max_tilt_deg', 'runner safety abort']；任务=FAILURE；主体结束原因=failure。
证据缺口：无已识别缺口

## 008_external_brake_2p0-a1
证据=MEASURED；冻结=SUCCESS；任务=SUCCESS；主体实际交接=1；正常落地disarm=True。
场景实现=OBSERVED_REQUESTED_HANDOVER；已实现物理冻结/任务=SUCCESS/SUCCESS。原始证据限定判据保持不变。
- C→N owner=52136000µs；四电机物理应用=True。入口位置=[3.9888, -0.0349, -2.9735]m，速度=[1.9748, 0.1214, 0.0056]m/s，角速度=[-0.0552, 0.0316, -0.0329]rad/s。
- 首0.25/0.5/1/2秒峰倾角：3.2775/3.2775/8.8667/9.1905°；对应实际观察时长：0.2500/0.5000/1.0000/2.0000s。
- 已观测主体峰值=9.1905°，发生在owner后1.0880s。入口相对失高=0.0442m；低于实际活动目标最大=0.0425m。最大单轴角速率=0.6189rad/s；电机连续饱和=0.0000s。
- activation=UNKNOWN；捕获机体速度=缺失；原生目标速度=缺失m/s。外部参考是否真正消费另见JSON的reference_evidence与first_neural_consumed_state。
- 冻结=SUCCESS []；任务=SUCCESS；主体结束原因=explore_subject_finished。
证据缺口：无已识别缺口

## 009_direction_ypos-a1
证据=MEASURED；冻结=FAILURE；任务=FAILURE；主体实际交接=1；正常落地disarm=False。
场景实现=OBSERVED_REQUESTED_HANDOVER；已实现物理冻结/任务=FAILURE/FAILURE。原始证据限定判据保持不变。
- C→N owner=52132000µs；四电机物理应用=True。入口位置=[0.0365, 4.4567, -3.0240]m，速度=[-0.0972, 1.9208, 0.0032]m/s，角速度=[0.0114, 0.1772, -0.0190]rad/s。
- 首0.25/0.5/1/2秒峰倾角：38.5652/47.0434/47.0434/47.0434°；对应实际观察时长：0.2500/0.3240/0.3240/0.3240s。
- 已观测主体峰值=47.0434°，发生在owner后0.3240s。入口相对失高=0.0815m；低于实际活动目标最大=0.0815m。最大单轴角速率=3.8395rad/s；电机连续饱和=0.0000s。
- activation=VERIFIED；捕获机体速度=[-0.0975, 1.9229, 0.0032]；原生目标速度=[0.0000, 0.0000, 0.0000]m/s。外部参考是否真正消费另见JSON的reference_evidence与first_neural_consumed_state。
- 冻结=FAILURE ['max_tilt_deg', 'runner safety abort']；任务=FAILURE；主体结束原因=failure。
证据缺口：无已识别缺口

## 010_direction_xneg-a1
证据=MEASURED；冻结=FAILURE；任务=FAILURE；主体实际交接=1；正常落地disarm=False。
场景实现=OBSERVED_REQUESTED_HANDOVER；已实现物理冻结/任务=FAILURE/FAILURE。原始证据限定判据保持不变。
- C→N owner=52272000µs；四电机物理应用=True。入口位置=[-4.3927, 0.0451, -2.9751]m，速度=[-1.9513, -0.0930, 0.0016]m/s，角速度=[-0.1932, 0.0068, -0.0196]rad/s。
- 首0.25/0.5/1/2秒峰倾角：36.0658/48.1627/48.1627/48.1627°；对应实际观察时长：0.2500/0.4120/0.4120/0.4120s。
- 已观测主体峰值=48.1627°，发生在owner后0.3840s。入口相对失高=0.1273m；低于实际活动目标最大=0.1273m。最大单轴角速率=3.4115rad/s；电机连续饱和=0.0000s。
- activation=VERIFIED；捕获机体速度=[-1.9526, -0.0936, 0.0017]；原生目标速度=[0.0000, 0.0000, 0.0000]m/s。外部参考是否真正消费另见JSON的reference_evidence与first_neural_consumed_state。
- 冻结=FAILURE ['max_tilt_deg', 'runner safety abort']；任务=FAILURE；主体结束原因=failure。
证据缺口：无已识别缺口

## 011_direction_yneg-a1
证据=MEASURED；冻结=FAILURE；任务=FAILURE；主体实际交接=1；正常落地disarm=True。
场景实现=OBSERVED_REQUESTED_HANDOVER；已实现物理冻结/任务=FAILURE/FAILURE。原始证据限定判据保持不变。
- C→N owner=52388000µs；四电机物理应用=True。入口位置=[0.0038, -4.5201, -2.9781]m，速度=[0.1009, -1.9253, 0.0050]m/s，角速度=[-0.0143, -0.1777, -0.0285]rad/s。
- 首0.25/0.5/1/2秒峰倾角：38.0592/47.0000/47.0000/47.0000°；对应实际观察时长：0.2500/0.5000/1.0000/2.0000s。
- 已观测主体峰值=47.0000°，发生在owner后0.3600s。入口相对失高=0.3804m；低于实际活动目标最大=0.3806m。最大单轴角速率=3.9920rad/s；电机连续饱和=0.0000s。
- activation=VERIFIED；捕获机体速度=[0.1019, -1.9271, 0.0052]；原生目标速度=[0.0000, 0.0000, 0.0000]m/s。外部参考是否真正消费另见JSON的reference_evidence与first_neural_consumed_state。
- 冻结=FAILURE ['max_tilt_deg']；任务=FAILURE；主体结束原因=explore_subject_finished。
证据缺口：无已识别缺口

## 012_direction_diagonal-a1
证据=MEASURED；冻结=FAILURE；任务=FAILURE；主体实际交接=1；正常落地disarm=False。
场景实现=OBSERVED_REQUESTED_HANDOVER；已实现物理冻结/任务=FAILURE/FAILURE。原始证据限定判据保持不变。
- C→N owner=52208000µs；四电机物理应用=True。入口位置=[3.1770, 3.1499, -2.9792]m，速度=[1.3282, 1.4451, -0.0011]m/s，角速度=[0.1419, 0.1277, -0.0251]rad/s。
- 首0.25/0.5/1/2秒峰倾角：48.8149/59.0539/59.0539/59.0539°；对应实际观察时长：0.2500/0.3200/0.3200/0.3200s。
- 已观测主体峰值=59.0539°，发生在owner后0.3200s。入口相对失高=0.1045m；低于实际活动目标最大=0.1045m。最大单轴角速率=3.7605rad/s；电机连续饱和=0.0000s。
- activation=VERIFIED；捕获机体速度=[1.3295, 1.4470, -0.0009]；原生目标速度=[0.0000, 0.0000, 0.0000]m/s。外部参考是否真正消费另见JSON的reference_evidence与first_neural_consumed_state。
- 冻结=FAILURE ['max_tilt_deg', 'runner safety abort']；任务=FAILURE；主体结束原因=failure。
证据缺口：无已识别缺口

## 013_history_shadow-a1
证据=MEASURED；冻结=FAILURE；任务=FAILURE；主体实际交接=1；正常落地disarm=False。
场景实现=OBSERVED_REQUESTED_HANDOVER；已实现物理冻结/任务=FAILURE/FAILURE。原始证据限定判据保持不变。
- C→N owner=52388000µs；四电机物理应用=True。入口位置=[4.4902, -0.0770, -2.9700]m，速度=[1.9405, 0.0820, 0.0024]m/s，角速度=[0.1780, -0.0093, 0.0013]rad/s。
- 首0.25/0.5/1/2秒峰倾角：39.2953/48.4274/48.4274/48.4274°；对应实际观察时长：0.2500/0.3160/0.3160/0.3160s。
- 已观测主体峰值=48.4274°，发生在owner后0.3160s。入口相对失高=0.0905m；低于实际活动目标最大=0.0905m。最大单轴角速率=3.9091rad/s；电机连续饱和=0.0000s。
- activation=VERIFIED；捕获机体速度=[1.9422, 0.0821, 0.0025]；原生目标速度=[0.0000, 0.0000, 0.0000]m/s。外部参考是否真正消费另见JSON的reference_evidence与first_neural_consumed_state。
- 冻结=FAILURE ['max_tilt_deg', 'runner safety abort']；任务=FAILURE；主体结束原因=failure。
证据缺口：无已识别缺口

## 014_history_teacher-a1
证据=MEASURED；冻结=FAILURE；任务=FAILURE；主体实际交接=1；正常落地disarm=False。
场景实现=OBSERVED_REQUESTED_HANDOVER；已实现物理冻结/任务=FAILURE/FAILURE。原始证据限定判据保持不变。
- C→N owner=52220000µs；四电机物理应用=True。入口位置=[4.4424, -0.0071, -3.0066]m，速度=[1.9504, 0.0850, 0.0002]m/s，角速度=[0.1891, -0.0060, -0.0339]rad/s。
- 首0.25/0.5/1/2秒峰倾角：39.0795/50.1469/50.1469/50.1469°；对应实际观察时长：0.2500/0.3280/0.3280/0.3280s。
- 已观测主体峰值=50.1469°，发生在owner后0.3280s。入口相对失高=0.0773m；低于实际活动目标最大=0.0776m。最大单轴角速率=3.7496rad/s；电机连续饱和=0.0000s。
- activation=VERIFIED；捕获机体速度=[1.9535, 0.0859, 0.0006]；原生目标速度=[0.0000, 0.0000, 0.0000]m/s。外部参考是否真正消费另见JSON的reference_evidence与first_neural_consumed_state。
- 冻结=FAILURE ['max_tilt_deg', 'runner safety abort']；任务=FAILURE；主体结束原因=failure。
证据缺口：无已识别缺口

## 015_fresh_then_timeout_rtgt0-a1
证据=INCOMPLETE；冻结=FAILURE；任务=FAILURE；主体实际交接=1；正常落地disarm=False。
场景实现=NOT_REALIZED_ACTIVE_TIMEOUT；已实现物理冻结/任务=FAILURE/FAILURE。原始证据限定判据保持不变。
- C→N owner=52016000µs；四电机物理应用=True。入口位置=[4.0262, -0.0035, -3.0009]m，速度=[1.9733, 0.1246, 0.0066]m/s，角速度=[-0.0523, 0.0302, -0.0643]rad/s。
- 首0.25/0.5/1/2秒峰倾角：38.4270/53.2438/53.2438/53.2438°；对应实际观察时长：0.2500/0.3720/0.3720/0.3720s。
- 已观测主体峰值=53.2438°，发生在owner后0.3720s。入口相对失高=0.1186m；低于实际活动目标最大=0.1186m。最大单轴角速率=4.0566rad/s；电机连续饱和=0.0000s。
- activation=VERIFIED；捕获机体速度=[1.9745, 0.1254, 0.0066]；原生目标速度=[0.0000, 0.0000, 0.0000]m/s。外部参考是否真正消费另见JSON的reference_evidence与first_neural_consumed_state。
- 冻结=FAILURE ['max_tilt_deg', 'runner safety abort']；任务=FAILURE；主体结束原因=failure。
证据缺口：boundary 1: sender-matched active reference read

## 016_fresh_then_timeout_rtgt1-a1
证据=INCOMPLETE；冻结=UNKNOWN；任务=UNKNOWN；主体实际交接=1；正常落地disarm=True。
场景实现=NOT_REALIZED_ACTIVE_TIMEOUT；已实现物理冻结/任务=SUCCESS/SUCCESS。原始证据限定判据保持不变。
- C→N owner=52124000µs；四电机物理应用=True。入口位置=[4.0070, -0.0040, -2.9744]m，速度=[1.9822, 0.0895, -0.0016]m/s，角速度=[-0.0578, 0.0232, -0.0231]rad/s。
- 首0.25/0.5/1/2秒峰倾角：8.1204/13.3257/13.3274/13.3274°；对应实际观察时长：0.2500/0.5000/1.0000/2.0000s。
- 已观测主体峰值=13.3274°，发生在owner后0.5040s。入口相对失高=0.0469m；低于实际活动目标最大=0.0468m。最大单轴角速率=1.0094rad/s；电机连续饱和=0.0000s。
- activation=VERIFIED；捕获机体速度=[1.9831, 0.0899, -0.0016]；原生目标速度=[1.9831, 0.0899, 0.0000]m/s。外部参考是否真正消费另见JSON的reference_evidence与first_neural_consumed_state。
- 冻结=UNKNOWN []；任务=UNKNOWN；主体结束原因=explore_subject_finished。
证据缺口：boundary 1: sender-matched active reference read

## 017_fresh_then_timeout_rtgt2-a1
证据=INCOMPLETE；冻结=UNKNOWN；任务=UNKNOWN；主体实际交接=1；正常落地disarm=True。
场景实现=NOT_REALIZED_ACTIVE_TIMEOUT；已实现物理冻结/任务=SUCCESS/SUCCESS。原始证据限定判据保持不变。
- C→N owner=51716000µs；四电机物理应用=True。入口位置=[3.9736, -0.0467, -3.0474]m，速度=[1.9626, 0.1268, 0.0027]m/s，角速度=[-0.0563, 0.0284, -0.0334]rad/s。
- 首0.25/0.5/1/2秒峰倾角：8.0283/12.9892/12.9906/12.9906°；对应实际观察时长：0.2500/0.5000/1.0000/2.0000s。
- 已观测主体峰值=12.9906°，发生在owner后0.5040s。入口相对失高=0.0463m；低于实际活动目标最大=0.0463m。最大单轴角速率=0.9935rad/s；电机连续饱和=0.0000s。
- activation=VERIFIED；捕获机体速度=[1.9635, 0.1271, 0.0028]；原生目标速度=[1.9635, 0.1271, 0.0000]m/s。外部参考是否真正消费另见JSON的reference_evidence与first_neural_consumed_state。
- 冻结=UNKNOWN []；任务=UNKNOWN；主体结束原因=explore_subject_finished。
证据缺口：boundary 1: sender-matched active reference read

## 018_speed_zero_1p7-a1
证据=MEASURED；冻结=FAILURE；任务=FAILURE；主体实际交接=1；正常落地disarm=True。
场景实现=OBSERVED_REQUESTED_HANDOVER；已实现物理冻结/任务=FAILURE/FAILURE。原始证据限定判据保持不变。
- C→N owner=52208000µs；四电机物理应用=True。入口位置=[3.8185, -0.0457, -3.0107]m，速度=[1.6443, 0.1073, 0.0126]m/s，角速度=[0.1637, -0.0049, -0.0157]rad/s。
- 首0.25/0.5/1/2秒峰倾角：37.6732/47.0425/47.0425/47.0425°；对应实际观察时长：0.2500/0.5000/1.0000/2.0000s。
- 已观测主体峰值=47.0425°，发生在owner后0.3520s。入口相对失高=0.4207m；低于实际活动目标最大=0.4209m。最大单轴角速率=3.8646rad/s；电机连续饱和=0.0000s。
- activation=VERIFIED；捕获机体速度=[1.6470, 0.1077, 0.0129]；原生目标速度=[0.0000, 0.0000, 0.0000]m/s。外部参考是否真正消费另见JSON的reference_evidence与first_neural_consumed_state。
- 冻结=FAILURE ['max_tilt_deg']；任务=FAILURE；主体结束原因=explore_subject_finished。
证据缺口：无已识别缺口

## 019_seed2_zero_1p6-a1
证据=MEASURED；冻结=FAILURE；任务=FAILURE；主体实际交接=1；正常落地disarm=True。
场景实现=OBSERVED_REQUESTED_HANDOVER；已实现物理冻结/任务=FAILURE/FAILURE。原始证据限定判据保持不变。
- C→N owner=51968000µs；四电机物理应用=True。入口位置=[3.5848, 0.0058, -3.0420]m，速度=[1.5721, 0.0647, 0.0028]m/s，角速度=[0.1492, -0.0101, -0.0154]rad/s。
- 首0.25/0.5/1/2秒峰倾角：36.8625/45.1001/45.1001/45.1001°；对应实际观察时长：0.2500/0.5000/1.0000/2.0000s。
- 已观测主体峰值=45.1001°，发生在owner后0.3480s。入口相对失高=0.3819m；低于实际活动目标最大=0.3819m。最大单轴角速率=3.8841rad/s；电机连续饱和=0.0000s。
- activation=VERIFIED；捕获机体速度=[1.5737, 0.0652, 0.0029]；原生目标速度=[0.0000, 0.0000, 0.0000]m/s。外部参考是否真正消费另见JSON的reference_evidence与first_neural_consumed_state。
- 冻结=FAILURE ['max_tilt_deg']；任务=FAILURE；主体结束原因=explore_subject_finished。
证据缺口：无已识别缺口

## 020_seed2_zero_1p8-a1
证据=MEASURED；冻结=FAILURE；任务=FAILURE；主体实际交接=1；正常落地disarm=False。
场景实现=OBSERVED_REQUESTED_HANDOVER；已实现物理冻结/任务=FAILURE/FAILURE。原始证据限定判据保持不变。
- C→N owner=52164000µs；四电机物理应用=True。入口位置=[4.0845, -0.0803, -3.0374]m，速度=[1.7391, 0.0901, 0.0007]m/s，角速度=[0.1655, 0.0003, -0.0038]rad/s。
- 首0.25/0.5/1/2秒峰倾角：37.9233/47.6785/47.6785/47.6785°；对应实际观察时长：0.2500/0.4080/0.4080/0.4080s。
- 已观测主体峰值=47.6785°，发生在owner后0.3560s。入口相对失高=0.1334m；低于实际活动目标最大=0.1333m。最大单轴角速率=3.8144rad/s；电机连续饱和=0.0000s。
- activation=VERIFIED；捕获机体速度=[1.7409, 0.0903, 0.0007]；原生目标速度=[0.0000, 0.0000, 0.0000]m/s。外部参考是否真正消费另见JSON的reference_evidence与first_neural_consumed_state。
- 冻结=FAILURE ['max_tilt_deg', 'runner safety abort']；任务=FAILURE；主体结束原因=failure。
证据缺口：无已识别缺口

## 021_seed2_direction_yneg-a1
证据=MEASURED；冻结=FAILURE；任务=FAILURE；主体实际交接=1；正常落地disarm=False。
场景实现=OBSERVED_REQUESTED_HANDOVER；已实现物理冻结/任务=FAILURE/FAILURE。原始证据限定判据保持不变。
- C→N owner=52264000µs；四电机物理应用=True。入口位置=[-0.0165, -4.5268, -2.9768]m，速度=[0.0916, -1.9239, 0.0086]m/s，角速度=[-0.0227, -0.1839, -0.0227]rad/s。
- 首0.25/0.5/1/2秒峰倾角：38.4546/47.9260/47.9260/47.9260°；对应实际观察时长：0.2500/0.4160/0.4160/0.4160s。
- 已观测主体峰值=47.9260°，发生在owner后0.3640s。入口相对失高=0.1762m；低于实际活动目标最大=0.1767m。最大单轴角速率=4.0371rad/s；电机连续饱和=0.0000s。
- activation=VERIFIED；捕获机体速度=[0.0936, -1.9283, 0.0092]；原生目标速度=[0.0000, 0.0000, 0.0000]m/s。外部参考是否真正消费另见JSON的reference_evidence与first_neural_consumed_state。
- 冻结=FAILURE ['max_tilt_deg', 'runner safety abort']；任务=FAILURE；主体结束原因=failure。
证据缺口：无已识别缺口

## 022_active_timeout_rtgt1-a1
证据=MEASURED；冻结=FAILURE；任务=FAILURE；主体实际交接=1；正常落地disarm=False。
场景实现=VERIFIED_ACTIVE_TIMEOUT；已实现物理冻结/任务=FAILURE/FAILURE。原始证据限定判据保持不变。
- C→N owner=52044000µs；四电机物理应用=True。入口位置=[3.9962, -0.0813, -2.9809]m，速度=[1.9785, 0.1168, -0.0033]m/s，角速度=[-0.0487, 0.0310, -0.0437]rad/s。
- 首0.25/0.5/1/2秒峰倾角：3.7513/4.1664/23.2537/49.1685°；对应实际观察时长：0.2500/0.5000/1.0000/1.2760s。
- 已观测主体峰值=49.1685°，发生在owner后1.2280s。入口相对失高=0.1208m；低于实际活动目标最大=0.1083m。最大单轴角速率=2.9798rad/s；电机连续饱和=0.0000s。
- activation=UNKNOWN；捕获机体速度=缺失；原生目标速度=缺失m/s。外部参考是否真正消费另见JSON的reference_evidence与first_neural_consumed_state。
- 冻结=FAILURE ['max_tilt_deg', 'runner safety abort']；任务=FAILURE；主体结束原因=failure。
证据缺口：无已识别缺口

## 023_active_timeout_rtgt2-a1
证据=MEASURED；冻结=SUCCESS；任务=SUCCESS；主体实际交接=1；正常落地disarm=True。
场景实现=VERIFIED_ACTIVE_TIMEOUT；已实现物理冻结/任务=SUCCESS/SUCCESS。原始证据限定判据保持不变。
- C→N owner=51936000µs；四电机物理应用=True。入口位置=[3.9589, -0.1231, -3.0113]m，速度=[1.9880, 0.1166, -0.0005]m/s，角速度=[-0.0537, 0.0334, -0.0178]rad/s。
- 首0.25/0.5/1/2秒峰倾角：5.2912/5.6442/9.7130/14.3132°；对应实际观察时长：0.2500/0.5000/1.0000/2.0000s。
- 已观测主体峰值=14.3132°，发生在owner后1.6640s。入口相对失高=0.0471m；低于实际活动目标最大=0.0451m。最大单轴角速率=1.2237rad/s；电机连续饱和=0.0000s。
- activation=VERIFIED；捕获机体速度=[1.9889, 0.1163, -0.0004]；原生目标速度=[1.9889, 0.1163, 0.0000]m/s。外部参考是否真正消费另见JSON的reference_evidence与first_neural_consumed_state。
- 冻结=SUCCESS []；任务=SUCCESS；主体结束原因=explore_subject_finished。
证据缺口：无已识别缺口


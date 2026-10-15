批次 p2-20261015-batch-explore-02

|运行|处理|交接时速度 m/s|电机阶跃|0.5 s RMS 偏离|最大高度损失 m|最大倾角 °|恢复(变化) s|写入/协调核对|捕获|最大年龄 ms|飞行结果|
|---|---|---:|---:|---:|---:|---:|---:|---|---|---:|---|
|X1.5-c_to_n-N0-1|N0|1.48|0.519|0.093|0.371|44.1|3.35|VERIFIED|activation_reset_hold|4|SUCCESS|
|X1.5-baseline_raptor-B-1|B|1.54|0.236|0.029|0.235|41.4|2.90|—|setpoint_timeout_hold|4|SUCCESS|
|X1.5-c_to_n-N0-2|N0|1.49|0.556|0.090|0.345|43.6|3.38|VERIFIED|activation_reset_hold|4|SUCCESS|
|X1.5-baseline_raptor-B-2|B|1.52|0.404|0.029|0.248|40.3|3.26|—|setpoint_timeout_hold|8|SUCCESS|
|X1.5-c_to_n-N0-3|N0|1.50|0.526|0.090|0.341|43.5|3.37|VERIFIED|activation_reset_hold|4|SUCCESS|
|X2.0-c_to_n-N0-1|N0|1.98|0.574|0.106|0.190|54.6|—|VERIFIED|activation_reset_hold|8|FAILURE safety_envelope:tilt_safety_deg,runner_safety_abort,no_joint_recovery|
|X2.0-baseline_raptor-B-1|B|2.02|0.381|0.027|0.073|48.7|—|—|setpoint_timeout_hold|4|FAILURE safety_envelope:tilt_safety_deg,runner_safety_abort,no_joint_recovery|
|X2.0-c_to_n-N0-2|N0|1.98|0.572|0.102|0.194|53.4|—|VERIFIED|activation_reset_hold|8|FAILURE safety_envelope:tilt_safety_deg,runner_safety_abort,no_joint_recovery|
|X2.0-baseline_raptor-B-2|B|2.04|0.356|0.027|0.090|49.8|—|—|setpoint_timeout_hold|8|FAILURE safety_envelope:tilt_safety_deg,runner_safety_abort,no_joint_recovery|
|X2.0-c_to_n-N0-3|N0|2.00|0.571|0.103|0.200|54.2|—|VERIFIED|activation_reset_hold|4|FAILURE safety_envelope:tilt_safety_deg,runner_safety_abort,no_joint_recovery|
|X2.0-n_to_c-C0-1|C0|2.09|0.014|—|0.015|13.4|3.54|VERIFIED|auto_loiter|4|SUCCESS|
|X2.0-n_to_c-C0-2|C0|2.10|0.011|—|0.010|13.2|3.43|VERIFIED|auto_loiter|4|SUCCESS|
|X2.0-n_to_c-C0-3|C0|2.06|0.015|—|0.005|13.3|5.17|VERIFIED|auto_loiter|4|SUCCESS|
|X2.0-c_to_n-N2-1|N2|1.98|0.490|0.084|0.201|54.9|—|VERIFIED|activation_reset_hold|4|FAILURE safety_envelope:tilt_safety_deg,runner_safety_abort,no_joint_recovery|
|X2.0-c_to_n-N2-2|N2|1.98|0.500|0.081|0.178|53.8|—|VERIFIED|activation_reset_hold|4|FAILURE safety_envelope:tilt_safety_deg,runner_safety_abort,no_joint_recovery|
|X2.0-c_to_n-N2-3|N2|1.98|0.487|0.083|0.169|54.4|—|VERIFIED|activation_reset_hold|8|FAILURE safety_envelope:tilt_safety_deg,runner_safety_abort,no_joint_recovery|

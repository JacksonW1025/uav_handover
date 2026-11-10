# 同一单例的主体前基础设施修复

用户要求一个经典→神经切换单例，不增加其他随机种子，并未限制主体前工程故障只能物理启动一次。仍只研究原来的 seed20261109/同一 Mission/同一参考轨迹；首次失败完整保留，不算独立切换样本。

首次物理启动已真实完成解锁、3m起飞和10.048s经典悬停；悬停最大倾角0.317°，固定参考最大位置误差0.443m。原生ULog无dropout，33,885,663bytes，SHA256 a092efe86c8a612a0d0b347e674cb4a533df4825387c813bbe3871e07f73453e。RAPTOR注册成功，mode23，但未请求主体切换，实际神经入口0。

失败发生于 Mission 协议前的第二次 MAVLink handshake。通用 preflight 使用一个 UDPout socket 验证PX4后关闭，场景后来创建新的临时源端口。PX4 `mavlink_receiver.cpp:3797–3810` 仅首次绑定UDP回复peer，`mavlink_main.cpp:924–926`继续回原端口。第二条heartbeat可到达PX4，所以出现GCS regained，但回复没有到达新socket。原运行没有记录两个源端口，故这是源代码与日志支持的高置信度诊断，不冒称有数据包级证据。

修复只改Python试验接线：新config `repair.json` opt-in保留最初验证过的socket，记录其local endpoint，Mission阶段复用同一个socket，非阻塞接收且持续执行安全pump/heartbeat。其他旧实验仍沿用原close语义。未修改PX4、策略、物理步长、安全阈值、seed、Mission或神经目标。

一项真实loopback socket/MAVLink编码测试模拟“只回首次peer”的对端，验证复用端口可以完成第二次核验；无需PX4/Gazebo。连同所有离线回归，119项通过。

`--repair-mavlink`不是通用放行开关：仅在账本恰有一个已终止START、原始失败为指定handshake错误、原始subject_requests为空且actual_neural_entries=0时允许一次修复启动。使用新输出 `data/cn-single-20261109-repair-flight` 和新证据目录；旧运行不会覆盖。第二次START之后再次调用必拒绝。

首次运行关闭流程仅请求land后立即shutdown，没有完整降落或disarm证据。末尾仍在3.018m、armed/AUTO_LOITER；不能说“安全落地”。PX4和Gazebo退出0，无残留仿真进程。首次物理流程wall56.139s、CPU22.516s，分析wall2.070s、CPU2.030s。失败原始飞行数据仍只留Thor，提交小证据。

修复启动命令：

```bash
./tools/cn_single/experiment --execute --repair-mavlink
```

本文件是修复候选记录，不是重飞成功声明。实际后续结果另写最终报告。

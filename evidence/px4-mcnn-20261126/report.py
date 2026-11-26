"""Write the MCNN results readme from the checked numeric bundle."""
import json
import sys
from pathlib import Path
r=Path(sys.argv[1]); p=r/'evidence/px4-mcnn-20261126'
m=json.loads((p/'metrics.json').read_text())
def f(x,n=2):return format(x,f'.{n}f')
def v(k,stat,win=1000):return m[k][f'first_{win}ms'][stat]
def peak(k,win=1000): return f(v(k,'peak_tilt_deg',win))
def drift(k): return f(v(k,'horiz_excursion_m'),3)
def down(k):return f(100*v(k,'loss_m'))
def err(k):return f(v(k,'xyz_tracking_rmse_m'),3)
def vel(k):return f(v(k,'peak_horiz_speed_m_s'),3)
def step(k):return f(m[k]['max_first_motor_step'],4)
def gap(k):return f(m[k]['first_publish_to_all_four_us']/1000,0)
def v0(k):return f(m[k]['entry_v_m_s'][0],3)
def yaw(k):return f(m[k]['entry_yaw_deg'],1)
def act(k):return str(m[k]['activation_us'])
def delayrow(k):
    d=m[k];return ' | '.join(str(d[name]) for name in ['request_us','activation_us','first_publish_us','first_common_motor_sample_us','first_four_application_us','covered_source_samples_in_no_motor'])
src='https://github.com/PX4/PX4-Autopilot/blob/5de8e5c1372fa3b21e3c42701a14ee9ec1b27248'
text=f"""# PX4 / MCNN Control：x500 原生闭环交接

同一台 Gazebo x500、同一组冻结的官方 MCNN 参数。八条物理闭环仿真分别做四组配对，见[原生切片与验算](../../evidence/px4-mcnn-20261126/README.md)和[对比图](../../evidence/px4-mcnn-20261126/paired-windows.pdf)。

## 四组结果

| 类别与对照 | 接管入口 | 首秒实测：对照 → 处理 |
| --- | --- | --- |
| T1 同一条 3 m 直线减速：经典持续 → MCNN 接管 | 北向速度 {v0('t1_c')} → {v0('t1_n')} m/s；偏航 {yaw('t1_c')}° → {yaw('t1_n')}° | 峰值倾角 {peak('t1_c')}° → {peak('t1_n')}°；对外部轨迹位置 RMSE {err('t1_c')} → {err('t1_n')} m；失高 {down('t1_c')} → {down('t1_n')} cm |
| T2 原地保持：经典持续 → 无内部历史的 MCNN 接管 | 两臂保持各自入口当前位置，北向速度 {v0('t2_c')} → {v0('t2_n')} m/s；偏航 {yaw('t2_c')}° → {yaw('t2_n')}° | MCNN 首拍最大单电机归一化阶跃 **{step('t2_n')}**；水平峰速 {vel('t2_c')} → {vel('t2_n')} m/s；水平位移 {drift('t2_c')} → {drift('t2_n')} m；失高 {down('t2_c')} → {down('t2_n')} cm |
| T3 B 点二次接管：B 点新目标 → 保留 A 点旧目标 | 北向速度 {v0('t3_fresh')} → {v0('t3_stale')} m/s；首次推理目标年龄 {f(m['t3_fresh']['initial_reference_age_us']/1000,1)} ms → {f(m['t3_stale']['initial_reference_age_us']/1e6,3)} s | 峰值倾角 {peak('t3_fresh')}° → **{peak('t3_stale')}°**；水平偏移 {drift('t3_fresh')} → **{drift('t3_stale')} m**；水平峰速 {vel('t3_fresh')} → {vel('t3_stale')} m/s |
| T4 运动接管：直接交付 → 下游短时保留旧命令 | 北向速度 {v0('t4_release')} → {v0('t4_hold')} m/s；入口倾角 {f(m['t4_release']['entry_tilt_deg'])}° → {f(m['t4_hold']['entry_tilt_deg'])}° | 首条 MCNN 发布至四电机收到同一样本 {gap('t4_release')} → **{gap('t4_hold')} ms**；前 250 ms 峰值倾角 {peak('t4_release',250)}° → {peak('t4_hold',250)}°；前 250 ms 北向位移 {f(v('t4_release','max_forward_displacement_m',250),3)} → {f(v('t4_hold','max_forward_displacement_m',250),3)} m；首秒北向位移 {f(v('t4_release','max_forward_displacement_m'),3)} → {f(v('t4_hold','max_forward_displacement_m'),3)} m |

## 干预与证据口径

- **T1**：经典 OFFBOARD 采用同一连续的位置、速度和加速度目标；MCNN 已在首拍采用对齐的新鲜位置参考，并在自然输出链应用。收到的目标速度和加速度不进入 MCNN 张量。相比经典，切换臂在运动中出现不同的制动和跟踪响应。证据是完整控制律的闭环对照，没有单独剥离速度前馈的贡献。见[输入构造]({src}/src/modules/mc_nn_control/mc_nn_control.cpp#L465-L507)。
- **T2**：官方模型是 15→64→32→4 的前馈 MLP，不接收上一拍动作或经典速度积分，也没有可清零的 GRU。测量比较最后一条已记录的经典归一化命令与第一条 MCNN 命令，并记录后续位移和姿态。该实验呈现的是前馈接管的命令不连续，未测量或单独改变经典积分项。固件包装层仍有目标缓存及上次有效输出的异常回退，与正常推理是否带历史是不同的事。这组明显变化是电机命令和水平响应，首秒掉高没有放大。
- **T3**：A 进入 MCNN 时接受有限 XYZ；返回经典后仅靠速度参考飞到 B，避免用有限 XYZ 的共享话题更新覆盖 A。再切换时，旧目标臂首拍使用的参考时间戳在前一次 MCNN 的接受记录里，同时未在重入后首拍采纳新的有限 XYZ。对照在 B 刷新有限位置，MCNN 首拍采用 B。旧目标臂首拍的北向位置误差为 {f(m['t3_stale']['initial_ref_error_xyz_m'][0],3)} m。见[模式入口]({src}/src/modules/mc_nn_control/mc_nn_control.cpp#L625-L678)和[轨迹分支]({src}/src/modules/mc_nn_control/mc_nn_control.cpp#L714-L754)。
- **T4**：同一 Gazebo relay，透明臂不暂存；处理臂在请求前紧邻时刻开启限定时窗，暂存期间继续使用最后交付的旧命令。日志保留真实命令重复应用和被覆盖条数。延迟臂前 250 ms 倾角更小，但向前走得更远；首秒北向位移进一步拉开。仍然保留请求时的 0.03 m/s 入口速度差，见表。每个电机实际采纳的时间来自其物理步的记录，电机索引、原生消息时间戳与四通道命令数值三者相符。记录的是物理步消费的电机转速**参考**，不是物理转子转速或瞬时力。

| T4 组别 | 请求 µs | 激活 µs | 首条 N 发布 µs | 四电机首个共同样本的发布戳 µs | 四电机均采纳 µs | 前序 N 从未被电机采纳 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 直接交付 | {delayrow('t4_release')} |
| 限时暂存 | {delayrow('t4_hold')} |

## 构建与复核

PX4 固定为 [{src.split('/')[-1][:8]}]({src})，Gazebo Harmonic 8.11.0，x500 模型及物理常量固定。启用 TFLM 和 MCNN 后，先在官方未加仪表的二进制上做短闭环经典→MCNN 悬停校准。各组冻结为 `MC_NN_THRST_COEF=1.05`、`MC_NN_MIN_RPM=1000`、`MC_NN_MAX_RPM=22000`、`MC_NN_MANL_CTRL=0` 和 `THR_MDL_FAC=0`。保持模拟器原生 ESC 量程 150–1000 rad/s，不拿它改写 MCNN 归一化参数。仪表补丁只记录 MCNN 有效参考与输出，向输出桥帧加入原生样本标识；官方权重、动作映射、准入和失效保护不变。两个 ELF 中嵌入的 15,088 字节策略逐字节一致。

八条主对照均落地、自动解除武装并结束仿真。探索运行和启动失败另列在[运行台账](../../evidence/px4-mcnn-20261126/attempts.json)。姿态以机身竖轴偏离竖直的夹角定义。首秒和前 250 ms 均按原生模式请求计时。模式请求、Commander 激活、MCNN 模块激活、实际发布及物理采纳保存在独立字段。原始 ULog 和 Gazebo 原生记录留在 Thor，路径和哈希见[溯源文件](../../evidence/px4-mcnn-20261126/provenance.json)。每个对照臂是一次测量，具体数值指这组入口与路线。
"""
(r/'docs/handover/PX4_MCNN_CASES.md').write_text(text)

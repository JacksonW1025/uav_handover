import csv,pathlib,json,math,bisect,hashlib
root=pathlib.Path(__file__).parent
arms={}
order=['C_slow','N_slow','H_clear','R_stale','D_hold','C_fast','N_fast']
for arm in order:
 p=root/('pilot-v1' if arm=='C_slow' else 'results-v1')/arm
 s=json.loads((p/'summary.json').read_text()); assert s['status']=='landed' and not s['errors']
 with (p/'host.csv').open() as f: host=list(csv.DictReader(f))
 with (p/'native.csv').open() as f: native=list(csv.DictReader(f))
 first=next(x for x in host if float(x['t'])>=2.2)
 t0=float(first['wall'])
 group={g:[x for x in native if x['group']==g] for g in ('position','attitude','target','motors')}
 def win(g,span): return [x for x in group[g] if t0<=float(x['wall'])<=t0+span]
 def x_at(t):
  a=group['position']; ts=[float(r['wall']) for r in a]
  i=bisect.bisect_right(ts,t); assert 0<i<len(a)
  xa,xb=(float(a[j]['stateEstimate.x']) for j in (i-1,i))
  return xa+(xb-xa)*(t-ts[i-1])/(ts[i]-ts[i-1])
 def first_when(g,pred):
  hit=next((x for x in win(g,1.5) if pred(x)),None)
  return float(hit['wall'])-t0 if hit else None
 def tilt(x):
  return math.degrees(math.acos(math.cos(math.radians(float(x['stabilizer.roll'])))*math.cos(math.radians(float(x['stabilizer.pitch'])))))
 target_at_first=next(x for x in group['target'] if float(x['wall'])>=t0)
 arms[arm]=dict(entry_vx=s['entry']['stateEstimate.vx'], entry_z=s['entry']['stateEstimate.z'], entry_tilt=s['entry']['tilt'],
  n_ref=float(first['nref']), plan=float(first['ref']), n_output=float(first['neural']), source=first['source'], sent=float(first['sent_vx']),
  h_before=float(first['h_before']),h_after=float(first['h_after']),first_native_vx=float(target_at_first['ctrltarget.vx']),
  fw_brake_s=first_when('target',lambda x:float(x['ctrltarget.vx'])<-.005),
  measured_brake_s=first_when('position',lambda x:float(x['stateEstimate.vx'])<=.05),
  drift_cm=(x_at(t0+1)-x_at(t0))*100, tilt_peak_deg=max(map(tilt,win('attitude',1))),
  vx_min=min(float(x['stateEstimate.vx']) for x in win('position',1)),
  loss_cm=100*s['loss_z'], final_z=float(group['position'][-1]['stateEstimate.z']),
  final_motor_requests=[int(group['motors'][-1][f'motor.m{k}req']) for k in range(1,5)], native_rows=s['native_rows'])
for k,r in arms.items(): assert r['final_z']<0.075, (k,r)
j={'seed':20261123,'runner_sha256':hashlib.sha256((root/'runner.py').read_bytes()).hexdigest(),'cases':arms}
(root/'metrics.json').write_text(json.dumps(j,indent=2)+'\n')
f=lambda x,n=3:f'{x:.{n}f}'
tab=['| 组 | 入口实测 vx (m/s) | 新外环实际读到目标 (m/s) | 新外环首条输出 (m/s) | 首条选中来源 / 值 (m/s) | 固件日志首次观测到负速目标 (ms) | 机体 vx 首降到 0.05 (ms) | 前 1s 前移 (cm) | 峰值倾角 (°) |','|---|---:|---:|---:|---|---:|---:|---:|---:|']
for a,r in arms.items():
 tab.append(f"| {a} | {f(r['entry_vx'])} | {f(r['n_ref'])} | {f(r['n_output'])} | {r['source']} / {f(r['sent'])} | {f(1000*r['fw_brake_s'],0)} | {f(1000*r['measured_brake_s'],0)} | {f(r['drift_cm'],1)} | {f(r['tilt_peak_deg'],2)} |")
d=arms
report=f"""# Crazyflie 交接验证：T1–T4 单种子

CrazySim/MuJoCo Crazyflie 2.x 标准模型 cf2x_L250，CrazySim 所用 Crazyflie SITL 固件的 PID 内环，外部经典速度修正器交给学习型外环。无 PX4 参与。固定种子 20261123；学习器为固定随机 tanh 隐层＋拟合输出，带一维目标历史状态，训练目标速度点在 ±0.24 m/s 内；同一个策略用于所有案例。不是 RAPTOR 或 Crazyflie 原厂神经模式。独立启动 7 次，统一起飞至约 0.43 m，以 25 Hz 发世界系速度，2.2 s 轨迹进入刹停目标 −0.05 m/s。每臂一条。全程保留固件保护。

## 结果

{chr(10).join(tab)}

时间从宿主首次发出切换拍命令算起；固件观察时刻取 20 ms 日志的本机回调，包含回传延迟。实测速率和姿态来自 Crazyflie 固件估计，不是 MuJoCo 真值。前移是切换时起前 1 秒的净 x 变化，按记录到达时间插值，不把切换之前的样本间隔算进去。所有臂正常降到地面估计高度约 0.02 m，发停止和解除解锁请求，无中途安全停止。落地由宿主完成标记和末端位置核对。

## 四种机制

- **T1，入口运动超出接手外环的训练范围。** 快速经典续飞和快速交接的实测入口速度为 {f(d['C_fast']['entry_vx'])} / {f(d['N_fast']['entry_vx'])} m/s。快速交接保留历史、及时读到 −0.05 m/s 的刹停目标、首条学习型输出立即选中，但首条输出仅 {f(d['N_fast']['n_output'])} m/s，经典是 {f(d['C_fast']['sent'])} m/s。1 秒前移 {f(d['C_fast']['drift_cm'],1)} → {f(d['N_fast']['drift_cm'],1)} cm；慢速对照见表。这里的风险表现是刹停余量变小。
- **T2，历史不连续。** 温和入口，从同一刹停参考、同样及时的交付路径继续，唯一显式改动是在切换那一拍把学习器历史清零。首条命令由 {f(d['N_slow']['sent'])} 变为 {f(d['H_clear']['sent'])} m/s，峰值倾角由 {f(d['N_slow']['tilt_peak_deg'],2)}° 到 {f(d['H_clear']['tilt_peak_deg'],2)}°，实测速度最低 {f(d['N_slow']['vx_min'])} → {f(d['H_clear']['vx_min'])} m/s。清零使制动更猛，向后超调加重；前移反而较小。
- **T3，读取了旧目标。** 外环及时取得控制输出权，但开始约 0.3 秒继续读 +0.22 m/s 而不是 −0.05 m/s；于是它自己计算出继续向前的命令。固件日志首次观测到负速目标的时间由 {f(d['N_slow']['fw_brake_s']*1000,0)} 到 {f(d['R_stale']['fw_brake_s']*1000,0)} ms，前 1 秒前移 {f(d['N_slow']['drift_cm'],1)} → {f(d['R_stale']['drift_cm'],1)} cm。
- **T4，正确命令已存在但没送达。** 学习型外环第一拍读到 −0.05 m/s 并生成 {f(d['D_hold']['n_output'])} m/s；宿主选择层继续送缓冲的经典命令 {f(d['D_hold']['sent'])} m/s。固件负速时间为 {f(d['D_hold']['fw_brake_s']*1000,0)} ms，前 1 秒前移 {f(d['D_hold']['drift_cm'],1)} cm。这是外环命令交付异常，未替换电机源。T3 和 T4 都表现成晚刹，但前者计算的是旧目标，后者算对了却发错输出。

## 信号链与复核

- `runner.py`：`Learned` / `target` 产生共享参考和候选控制器，循环中分别标记 reset、实际参考、所选输出和发送时间。每臂 `host.csv` 保留这些数据。
- Crazyflie 固件 `crtp_commander_generic.c:98` 解码速度包，`commander.c:74,100` 保存并提供当前目标，`stabilizer.c:326,341` 读目标并喂给上机 PID。其 `stabilizer.c:409` 日志给出 `ctrltarget`；`native.csv` 同时记录机体状态和兼容保留的电机请求字段（非实测电机转速）。复核时以 `native.csv` 的 `firmware_ms` 观察固件内顺序，以同一宿主的回调时间与发送对齐。
- 固定源码版本见同目录 `README.md`。运行 `python3 analyze.py` 可重算表；`metrics.json` 是机器可读摘要。完整日志留本地 Git 忽略目录。

**SITL 日志说明：** motor.m*req 读取的实机补偿缓冲在本 SITL 分支未更新，飞行中也可能一直为零；不能用于核实实际电机输出、停桨或解除解锁。数值摘要中的 final_motor_requests 仅保留原始字段供兼容。参见[补充记录](../crazyflie-full-state-20261125/README.md)中直接记录四路 PWM 的对照。
"""
(root/'REPORT.zh.md').write_text(report)
print('\n'.join(tab))

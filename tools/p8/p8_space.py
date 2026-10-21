"""P8 测试空间（PX4 SITL，RAPTOR），2026-10-21。Thor 和项目两边共用同一份定义。只依赖 numpy。
一个测试用例：速度 v（m/s）、运动方向 heading_deg（0–90°，运动轴 motion_axis_ned = [cos h, sin h, 0]，即从 +N 转向 +E；45° 就是 P6 的 A45）、
  中断序列 durs（每次无 setpoint 时长，s）和 restored（中断之间恢复 setpoint 的时长，s，len = len(durs) − 1）。
规格（“被测接入层应当扛住的事件”）：v ∈ [1.5, 2.5]，heading ∈ [0, 90]，2–4 次中断，每次 0.25 s 到 DMAX，恢复 0.1–0.8 s。
能不能飞由 Thor 的 gap_spec 安全预算决定，放不下的用例直接跳过、不计入预算。
DMAX：T0 0.35、T1 0.80。取法：在模型里单次中断都还安全（v = 2 时单次失败边界 T1 约 0.80–0.85 s），失败只能靠多次叠加产生。"""
import numpy as np
SUTS = {"T0": {"rtgt": 0, "rtdec": 2.0, "dmax": 0.35}, "T1": {"rtgt": 2, "rtdec": 2.0, "dmax": 0.80}}
V_RANGE, H_RANGE, N_RANGE, R_RANGE, D_MIN = (1.5, 2.5), (0.0, 90.0), (2, 4), (0.1, 0.8), 0.25

def _r(x, q): return float(np.round(x / q) * q)            # 量化：速度 0.05、方向 1°、时长 0.01 s，便于命名和复现

def norm(c):
    return {"v": _r(c["v"], 0.05), "heading_deg": _r(c["heading_deg"], 1.0), "durs": [_r(d, 0.01) for d in c["durs"]], "restored": [_r(g, 0.01) for g in c["restored"]]}

def sample(rng, sut):
    n = int(rng.integers(N_RANGE[0], N_RANGE[1] + 1)); dm = SUTS[sut]["dmax"]
    return norm({"v": rng.uniform(*V_RANGE), "heading_deg": rng.uniform(*H_RANGE), "durs": list(rng.uniform(D_MIN, dm, n)), "restored": list(rng.uniform(*R_RANGE, n - 1))})

def mutate(rng, c, sut):
    c = {"v": c["v"], "heading_deg": c["heading_deg"], "durs": list(c["durs"]), "restored": list(c["restored"])}; dm = SUTS[sut]["dmax"]
    for _ in range(int(rng.integers(1, 4))):
        op = int(rng.integers(6))
        if op == 0: c["v"] = float(np.clip(c["v"] + rng.normal(0, 0.2), *V_RANGE))
        elif op == 1: c["heading_deg"] = float(np.clip(c["heading_deg"] + rng.normal(0, 12), *H_RANGE))
        elif op == 2: i = int(rng.integers(len(c["durs"]))); c["durs"][i] = float(np.clip(c["durs"][i] + rng.normal(0, 0.06), D_MIN, dm))
        elif op == 3: i = int(rng.integers(len(c["restored"]))); c["restored"][i] = float(np.clip(c["restored"][i] + rng.normal(0, 0.12), *R_RANGE))
        elif op == 4 and len(c["durs"]) < N_RANGE[1]: c["durs"].append(float(rng.uniform(D_MIN, dm))); c["restored"].append(float(rng.uniform(*R_RANGE)))
        elif op == 5 and len(c["durs"]) > N_RANGE[0]: c["durs"].pop(); c["restored"].pop()
    return norm(c)

def encode(c, sut):
    dm = SUTS[sut]["dmax"]; d = list(c["durs"]) + [0.0] * (N_RANGE[1] - len(c["durs"])); g = list(c["restored"]) + [0.0] * (N_RANGE[1] - 1 - len(c["restored"]))
    return np.array([(c["v"] - 1.5), c["heading_deg"] / 90, (len(c["durs"]) - 2) / 2] + [x / dm for x in d] + [x / 0.8 for x in g])

def windows(c):
    """相对第一次中断开始的 [开始, 结束) 窗口列表（和 P6 c2_patterns 的 windows_s 同格式）。"""
    t, out = 0.0, []
    for i, d in enumerate(c["durs"]):
        out.append([round(t, 4), round(t + d, 4)]); t += d + (c["restored"][i] if i < len(c["restored"]) else 0.0)
    return out

def _num(x):
    s = f"{x:.4f}".rstrip("0"); return s + "0" if s.endswith(".") else s

def name(c, sut):
    """例：v2.0-H37.0-W0.0-0.3_0.5-0.84:T1（和 P6 的命名规则一样：最多 4 位小数，2.0 保留一位）。"""
    return f"v{_num(c['v'])}-H{_num(c['heading_deg'])}-W" + "_".join(f"{_num(a)}-{_num(b)}" for a, b in windows(c)) + f":{sut}"

# 安全预算：照抄 P6 condition_rule（tools/p6_conditions.gap_spec）。剖面 = 1 s 线性加速 + 巡航 (pre_gap + 窗口总长 + post_gap) + 2.0 m/s² 减速，
# 直线以悬停捕获点为中心；半径 = 路径/2 + 1.0 m 余量 + 0.1 m 悬停偏移 ≤ 8 m。放不下：post_gap 3.0 → 2.0（步长 0.05），再 pre_gap 1.0 → 0.75。
def _path(v, span, pre, post): return 0.5 * v * 1.0 + v * (pre + span + post) + v * v / (2 * 2.0)

def budget(c):
    """返回 (pre_gap_s, post_gap_s)；放不下返回 None。Thor 的 gap_spec 是准绳，两者不一致时以 gap_spec 为准并停下报告。"""
    v = c["v"]; span = windows(c)[-1][1]; ok = lambda pre, post: _path(v, span, pre, post) / 2 + 1.0 + 0.1 <= 8.0 + 1e-9
    for k in range(21):
        post = round(3.0 - 0.05 * k, 2)
        if ok(1.0, post): return 1.0, post
    for k in range(1, 6):
        pre = round(1.0 - 0.05 * k, 2)
        if ok(pre, 2.0): return pre, 2.0
    return None

def fits(c): return budget(c) is not None

def cell(c):
    """“不同的失败”：方向 15° × 速度 0.5 m/s × 中断次数。"""
    return (int(min(c["heading_deg"], 89.99) // 15), int((c["v"] - 1.5) // 0.5), len(c["durs"]))

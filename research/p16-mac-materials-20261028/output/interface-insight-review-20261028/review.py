"""Recompute descriptive evidence from existing exports and render the research review.
No simulation, parameter fitting, remote execution, or new experiment is performed.
"""
from pathlib import Path
import csv, gzip, hashlib, html, json
from collections import defaultdict

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent
DOC = OUT / 'model-search-20261028/upstream/docs'
EXPORT = OUT / 'research-gap-audit-20261028/upstream/export'
esc = html.escape

def read(path):
    return json.loads(path.read_text())

def write(name, value):
    (ROOT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2))

def link(path, label):
    return f'<a href="{esc(str(path), quote=True)}">{esc(label)}</a>'

# Recheck every reviewed report against the previously fetched pinned Git tree.
verification = read(ROOT / 'source-verification.json')
remote = {r['name']: r for r in read(ROOT / 'remote-docs-index.json')['files']}
paths = [Path(r['path']) for r in verification['reports']]
paths += list((ROOT / 'upstream/docs').glob('*.md'))
verified = []
for path in sorted(set(paths)):
    b = path.read_bytes()
    blob = hashlib.sha1(b'blob ' + str(len(b)).encode() + b'\0' + b).hexdigest()
    verified.append(dict(path=str(path), sha256=hashlib.sha256(b).hexdigest(),
                         git_blob=blob, matches_pinned_source=blob == remote[path.name]['sha']))
assert all(r['matches_pinned_source'] for r in verified)
write('verified-evidence.json', dict(revision=verification['source_revision'], reports=verified))

# P7: independently align capture events with raw exported trace samples.
p7 = []
for path in sorted(EXPORT.glob('p7-20261020-a-q4-*')):
    summary = read(path / 'summary.json')
    with gzip.open(path / 'trace.csv.gz', 'rt') as f:
        trace = list(csv.DictReader(f))
    events = [e for e in summary['events'] if e['event'] == 'capture' and 0 <= e['gap'] < 4]
    captures = []
    for event in events:
        r = next(r for r in trace if float(r['t_s']) >= event['t_s'] - 1e-7)
        captures.append(dict(t=float(r['t_s']), local_vertical_error=float(r['ep_z']),
                             task_height_loss=float(r['alt_loss_m'])))
    p7.append(dict(id=path.name, captures=captures, max_loss=summary['max_altitude_loss_m'],
                   max_tilt=summary['max_tilt_deg']))
caps = [c for r in p7 for c in r['captures']]
p7_summary = dict(complete_traces=len(p7), captures=len(caps),
    max_abs_local_vertical_error=max(abs(c['local_vertical_error']) for c in caps),
    captures_with_loss_over_half_m=sum(c['task_height_loss'] > .5 for c in caps),
    captures_with_loss_over_one_m=sum(c['task_height_loss'] > 1 for c in caps),
    height_failures=sum(r['max_loss'] > 1 for r in p7),
    height_only_failures=sum(r['max_loss'] > 1 and r['max_tilt'] < 45 for r in p7))
assert p7_summary == dict(complete_traces=27, captures=108, max_abs_local_vertical_error=0.0,
    captures_with_loss_over_half_m=27, captures_with_loss_over_one_m=5,
    height_failures=11, height_only_failures=10)

# P8: count actual outcomes, without treating descriptive yield as predictive validation.
with (EXPORT / 'p8_b_results.csv').open() as f:
    p8rows = list(csv.DictReader(f))
p8 = []
for sut in sorted({r['sut'] for r in p8rows}):
    for method in sorted({r['method'] for r in p8rows}):
        rows = [r for r in p8rows if (r['sut'], r['method']) == (sut, method)]
        p8.append(dict(sut=sut, method=method, n=len(rows),
            primary_failures=sum(int(r['fail_primary']) for r in rows),
            task_failures=sum(int(r['fail_task']) for r in rows),
            task_without_primary=sum(int(r['fail_task']) and not int(r['fail_primary']) for r in rows)))
assert len(p8rows) == 900
assert sum(r['primary_failures'] for r in p8) == 432
assert sum(r['task_failures'] for r in p8) == 511

# P13: preserve all arms and censoring flags; report observed ranges as observed.
p13path = OUT / 'offline-adjoint-20261028/upstream/data/p13-20261026-results-v3/cases.json'
p13rows = read(p13path)['rows']
groups = defaultdict(list)
for r in p13rows:
    groups[(r['family'], r['arm'])].append(r)
p13 = []
for (family, arm), rows in sorted(groups.items()):
    p13.append(dict(family=family, arm=arm, n=len(rows),
        task_failures=sum(r['task'] != 'SUCCESS' for r in rows),
        primary_failures=sum(r['primary'] != 'SUCCESS' for r in rows),
        censored=sum(r['censored'] for r in rows),
        observed_tilt_range=[min(r['LP_peak_tilt_deg'] for r in rows),max(r['LP_peak_tilt_deg'] for r in rows)],
        observed_loss_range=[min(r['LP_max_loss_m'] for r in rows),max(r['LP_max_loss_m'] for r in rows)]))
assert len(p13rows) == 66
write('descriptive-reanalysis.json', dict(p7_summary=p7_summary, p7_captures=p7,
    p8_outcomes=p8, p13_outcomes=p13,
    limitations=['回顾性描述分析；未构成独立验证或预注册假设检验。',
                 'P7仅27条完整导出；P8按原研究的30个campaign理解独立性；P13同块条件相关。',
                 '提前终止的极值为已观测值，不能据未超过阈值判安全。'],
    new_SITL=0, new_flights=0))
data_paths = [EXPORT / 'p8_b_results.csv', p13path]
for folder in sorted(EXPORT.glob('p7-20261020-a-q4-*')):
    data_paths += [folder / 'summary.json', folder / 'trace.csv.gz']
data_paths += [OUT / 'greybox-baseline-audit-20261028/conclusion.json',
               OUT / 'sequential-budget-audit-20261028/conclusion.json']
write('data-manifest.json', [dict(path=str(p), sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
                                 bytes=p.stat().st_size) for p in data_paths])

# This matrix is an explicit evidence synthesis, not algorithmically inferred results.
evidence = [
('P1','THOR_P1_REPORT.md','48条接受记录；切入神经控制与切回经典控制的扰动不对称。激活时捕获当前位置，经典制动使用前方停车位置。','接入操作改变有效任务，目标语义值得作为测试单元。','原生控制器制动本身解释大量扰动；不能全归因于切换。'),
('P2','THOR_P2_REPORT.md','悬停下同时准备隐状态和实际动作历史显著减小接管跳变；运动状态下目标捕获仍主导。','每种操作需要独立的状态读写/继承清单。','神经记忆在激活场景有效；未推出对断流边界的普遍优势。'),
('P3','THOR_P3_REPORT.md','39条接受记录。返回悬停并重捕获后，世界平移/偏航可产生相同相对观测；未执行的影子动作反馈可恶化结果。','来源不同的历史可能在特定操作后共享有效输入。','相同观测不足以证明完整状态或后续任务安全等价。'),
('P4','THOR_P4_REPORT.md','独立种子/方向复核；速度匹配的参考捕获降低运动接管扰动。','源代码目标生成规则可能决定一整类场景的边界。','任务等价条件需要单独成立；改变任务语义可以制造表面改善。'),
('P5','THOR_P5_REPORT.md','35条探索飞行。激活与超过200ms的断流超时复用目标捕获代码；断流超时保留神经记忆。','共享捕获操作提供跨触发情境复用的候选接缝。','完整状态重置不同；两种触发器不能直接合并。参考恢复和按轴限幅也影响边界。'),
('P6','THOR_P6_REPORT.md','127次运行。11个A0单断流家族呈现单调安全/失败转变；重复扰动及方向变化可打破简单推广。','分支和状态条件确定后，部分局部边界可能便于搜索。','不能对重复序列全局二分；边界附近种子差异可翻转结果。'),
('P7','THOR_P7_REPORT.md','独立重算27条完整轨迹、108次捕获：捕获后局部垂直误差均为0，27次累计损高已超过0.5m，5次超过1m。','参考重置消除局部误差，同时保留物理下沉及任务损失；边界必须携带剩余裕量。','只有3个闭合捕获间隔；简单重复上一增量已较强，漂移周期理论尚无优势证据。'),
('P8','THOR_P8_REPORT.md','900次运行，30个campaign；重算得432次主失效、511次任务失效，79次任务失效无主失效。','倾角与损高需要分别覆盖，失败密集区不足以评估边界压缩。','冻结预测文件无法匹配900条结果；ours的高失败数不能当作预测或安全跳测优势。'),
('P9','THOR_P9_FINAL_REPORT.md','水平模型峰值MAE约1.802°、排序相关约0.924，但7个实际倾角失败漏判6个；一个边界中点误差0.50s。','平均预测和排序质量必须转换为边界附近的误差与漏判约束。','无损高模型支撑安全跳测；局部边界不能代表全局。'),
('P10','THOR_P10_A4_REPORT.md','无新增SITL。独立逐步误差球需约3.2405，原审计域为0.001；状态独立扰动导致证书失效。','保持状态相关性和源代码约束是复用条件的重要部分。','现有保守界在实际域内无效；不能借局部重放精度宣称未来保证。'),
('P11','THOR_P11_REPORT.md','69条有效正式运行；样本保持和调用/提交时钟显著影响重放。神经源码重放可达约1e-6。','缓存、消息年龄、读取和提交相位属于事件后的有效状态。','已知输入重放精度与自主闭环预测不同；相同种子不保证相同前态。'),
('P12','THOR_P12_CONT_REPORT.md','含P12/P12B/P12C；匹配前态的准备多次失败。当前损高、历史最大损高、下沉速度具有不同作用。','必须把物理恢复状态与任务监视器状态一起带过接口事件。','少量状态量的必要性不意味着充分性；同状态受控因果比较尚不足。'),
('P13','THOR_P13_REPORT.md','66条正式运行。F2单A、单B均安全；短间隔AB为3/3失败，中/长间隔均安全。F4更复杂，部分单事件已失败。','后续边界依赖进入事件时的恢复状态；按A/B名称分组会丢失重要条件。','整体仅一个控制栈；残余速度、姿态、动作历史等相关，无法单独归因某一状态。'),
('P14','THOR_P14_REPORT.md','含motion/R/G/H。源代码读取分支、几何、时钟逐步修正；P14H三种选择各4/4任务失败。','先识别合法时序分支，再考虑分支内的相近状态和边界复用。','全失败候选池没有成功侧边界；现实域误差界很快变宽，局部导数跨分支失效。'),
('P15','THOR_P15_REPORT.md','32条搜索飞行：便宜方法和模型方法均4/8失败。完整模型后继状态保留原始时钟原点后，6/6续算一致；简化垂直修正4次未改选择。','时钟完整的事件后状态可作为复用接缝；局部恢复预测比长程极值稳定。','模型计算复用尚未节省真实SITL；低维状态压缩、选点优势及总成本优势均未建立。'),
]
write('evidence-matrix.json', [dict(round=r, source=str(DOC/f), observation=o, implication=i, limitation=l)
                             for r,f,o,i,l in evidence])

papers = [
('ARIsTEO','https://arxiv.org/abs/1910.02837','已有系统辨识代理模型与仿真验证/精化循环；仅增加灰箱预测器不足以构成方法新意。'),
('DryVR','https://arxiv.org/abs/1702.06902','已有白箱切换图、数据驱动轨迹敏感度以及长短序列组合推理。'),
('SceneChecker','https://arxiv.org/abs/2011.10713','已有利用对称抽象提升场景验证效率的机制，涵盖神经控制车辆。'),
('Approximate Partial Order Reduction','https://arxiv.org/abs/1610.06317','已有近似可交换动作和相近初始状态下的执行覆盖，不能把一般时序归约宣称为新发现。'),
('Time-Staging Enhancement of Hybrid System Falsification','https://arxiv.org/abs/1803.03866','已有利用输入时间因果结构逐段搜索的思路；单纯后继状态续算不构成新意。'),
('Active Learning for Level Set Estimation','https://people.csail.mit.edu/alkisg/files/gotovos13active.pdf','已有基于置信区间的阈值边界主动采样及条件样本复杂度结果。'),
]
write('literature.json', [dict(title=t,url=u,relevance=r) for t,u,r in papers])

grey = read(OUT / 'greybox-baseline-audit-20261028/conclusion.json')
seq = read(OUT / 'sequential-budget-audit-20261028/conclusion.json')
decision = dict(
    selected_hypothesis='选择性重置后的条件边界复用',
    statement='由源码识别接口操作覆盖和继承的状态，在保留任务裕量、未来输入生成状态与合法时序分支的条件下，研究不同历史能否共享事件后的恢复边界。',
    established=['参考捕获与物理/任务状态的选择性继承','A+B风险依赖进入B时的状态','完整模型续算依赖时钟原点'],
    unproven=['具有实际压缩率的充分状态或近似等价类','跨触发情境的可靠边界迁移','相对强普通灰箱的SITL与总成本节省','跨控制栈和接入层泛化','相对已有抽象/组合验证工作的原创性'],
    current_greybox_task_correct=grey['primary']['ordinary_EE']['task_correct'],
    n=grey['primary']['ordinary_EE']['n'],
    new_SITL=0, novel_theorem_proved=False, new_method_superiority_demonstrated=False)
write('conclusion.json', decision)

def table(headers, rows):
    return '<div class="scroll"><table><thead><tr>' + ''.join(f'<th>{esc(x)}</th>' for x in headers) + '</tr></thead><tbody>' + ''.join('<tr>'+''.join(f'<td>{x}</td>' for x in row)+'</tr>' for row in rows) + '</tbody></table></div>'

parts = ['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>P1–P15 接入层 insight 复核</title>',
'''<style>body{font:17px/1.75 system-ui,sans-serif;color:#192c38;background:#f4f6f7;margin:0}main{max-width:1140px;margin:auto;padding:44px 32px 90px}h1{font-size:32px;line-height:1.35}h2{font-size:23px;margin-top:38px}p{max-width:950px}a{color:#006c75}table{border-collapse:collapse;width:100%;font-size:14px;background:white}th,td{text-align:left;vertical-align:top;border:1px solid #d7e0e5;padding:12px}th{background:#e3edef}.scroll{overflow:auto}.lead{font-size:21px;background:#e2efed;padding:22px;border-left:5px solid #267f73}.note{color:#52636d;font-size:14px}.formula{padding:16px;background:#fff;font-family:ui-monospace,monospace}.badge{font-weight:700;color:#846022}@media(max-width:650px){main{padding:24px 16px}td{min-width:170px}}</style><main>''',
'<h1>P1–P15：最有希望的接入层 insight</h1>',
f'<p class="note">2026-10-28 · 已核对{len(verified)}份报告/补充文档 · 固定源码版本 {esc(verification["source_revision"]["sha"][:12])} · 新增SITL 0次</p>',
'<p class="lead"><b>首选研究假设：选择性重置后的条件边界复用。</b>接入操作会覆盖一部分控制状态，同时继承物理恢复状态、执行状态和任务损失。若能识别哪些历史差异已被操作消除、哪些差异仍影响安全，就可能让多个触发情境共享一组局部边界测试。</p>',
'<p><span class="badge">证据支持机制，尚未支持效率或原创性结论。</span>普通混合灰箱已经能实现目标捕获和状态继承。候选贡献需要进一步给出有用的状态归约或边界迁移条件，并在相同漏判约束与边界精度下减少总仿真成本。当前没有已证明的新理论，也没有经过独立验证的跨情境边界复用算法。</p>',
'<h2>当前方法与 insight 的关系</h2>',
'<p>现有模型具有预测价值。严格18条AB留出比较中，原方法、普通独立灰箱和常规输出误差拟合都判断正确17条；13条完整轨迹上的损高MAE分别约8.32、8.32、7.92cm。删除捕获语义仅8/18正确，删除物理/执行继承10/18，删除神经历史继承仍17/18。作用机制明确，新增方法贡献尚未建立。</p>',
'<p>胜过基线与理论解释需要围绕同一发现形成证据链：接入结构 → 可复用/可排除的测试区域 → 受控漏判下的SITL减少。理论可以先表现为明确的适用条件、边界迁移误差与可检验预测；完整的新定理属于更高一层贡献。只取得小幅经验胜利、或增加与节省无关的公式，都不足以完成这条链。</p>',
'<h2>最有辨识度的事实</h2>',
table(['观测','意义'],[
['P5：激活与断流超时调用共享目标捕获操作；超时保留神经记忆。','触发名称与真正执行的状态操作存在多对一关系；全状态差异必须逐项保留。'],
[f'P7：{len(caps)}次捕获的局部垂直误差全为0，累计损高却有27次超过0.5m、5次超过1m。','重捕获可以让控制器局部误差归零，安全监视器必须继续记账。'],
['P13：F2单A/单B安全，短间隔AB 3/3失败，中/长间隔AB安全。','后续事件的危险边界受进入事件时的恢复状态影响。'],
['P15：完整模型状态保留原始时钟原点后6/6续算一致；原时钟处理3/6不一致。','执行相位、未来消息与任务监视器必须进入复用条件。模型一致性尚不等于真实系统边界一致。']]),
'<h2>如何具体转化为省仿真</h2>',
'<p>以捕获或恢复为接缝，从源码做依赖分析：列出被覆盖的变量，以及仍可经缓存、待消费消息、参考生成器或神经历史影响未来的变量。再按合法读取/提交分支归类。只有在变换后未来输入与任务判据也兼容时，才能去掉世界平移、历史标签等无效差异。</p>',
'<p>在每个合法分支内，学习“进入事件时的有效状态 → 后续新增损失/最大倾角”的局部边界。使用一次已验证轨迹覆盖邻近情境时，必须把迁移误差和模型误差计算进去；区间跨过阈值、未来分支不确定或状态超出已验证范围时，保留SITL查询。安全侧、危险侧和未知区应共同输出。</p>',
'<p>例如，在固定任务高度基准下，令Lₜ表示接缝时当前损高，Dₜ表示此前最大损高，ΔD⁺表示从接缝位置开始的未来最大新增损高（包含起点）。高度判据可按以下恒等式组合：</p>',
'<div class="formula">D_total = max(Dₜ, Lₜ + ΔD⁺)</div>',
'<p>若经验证的未来增量区间为[a,b]，则Dₜ≤1且Lₜ+b≤1时可在该区间有效条件下判定高度通过；Dₜ&gt;1或Lₜ+a&gt;1时判定高度失败。倾角及其他任务判据需同时组合。该恒等式本身属于基本记账关系；研究难点是让[a,b]跨不同历史保持有效且足够窄。当前损高、历史极值和下沉速度也尚未构成充分状态。</p>',
'<p>省掉的候选是被同一边界证据可靠覆盖的重复情境。独立前缀仿真、建模和校准费用仍计入成本；P15节省的离线模型续算CPU时间不能计作SITL节省。现阶段没有依据给出节省比例。</p>',
'<h2>为什么优先考虑这条线索</h2>',
table(['候选','已有支持','目前限制'],[
['神经隐藏状态压缩','P2/P3接管记忆效应明确。','断流留出中去神经继承仍17/18；单靠h不足以解释/改善主要边界。'],
['全局单调边界','P6单次部分家族近似单调。','P7/P9/P13重复与多阶段事件存在反例。'],
['时序分支梯度','P14G/H分支内局部关系有源码支持。','跨分支外推与初态差异干扰，P14H候选全失败，无边界优势证据。'],
['重复捕获的损高漂移','P7累计损失被局部参考重置遮蔽。','周期闭合/不变域未建立，简单上一周期增量已经很强。'],
['选择性重置后的条件边界复用','串联P1–P5共享操作、P7任务记账、P13状态依赖及P15时钟完整接缝。','充分状态、实际压缩率和迁移误差仍待建立；目前只推荐作为首选假设。']]),
'<h2>15轮证据与反证</h2>',
table(['轮次','已见证结果','对主线的启示','限制/反证'],[
[link(DOC/f,r),esc(o),esc(i),esc(l)] for r,f,o,i,l in evidence]),
'<h2>重算表：P8失败分项</h2>',
'<p class="note">每行90次运行，属于3个campaign。统计是描述性的；任务失败与主失效定义按原数据保留。缺失冻结预测使这些统计无法证明预测优越性。</p>',
table(['系统','方法','次数','主失效','任务失效','任务失效但无主失效'],[[esc(str(r[k])) for k in ['sut','method','n','primary_failures','task_failures','task_without_primary']] for r in p8]),
'<h2>重算表：P13全部条件</h2>',
'<p class="note">各组3个种子块。截断条目中所列极值范围仅为观测范围；不外推未观测后缀。F4部分单事件已失败，不能全归因于组合。</p>',
table(['家族','条件','次数','任务失败','主失效','截断数'],[[esc(str(r[k])) for k in ['family','arm','n','task_failures','primary_failures','censored']] for r in p13]),
'<h2>与已有理论和方法的距离</h2>',
table(['原始研究','已覆盖的思路'],[[f'<a href="{esc(u)}">{esc(t)}</a>',esc(r)] for t,u,r in papers]),
'<p>相对这些工作，值得争取的具体贡献是：从真实接入实现提取选择性重置与异步消费条件，保留非重置任务监视器，给出具有实用误差范围的边界迁移关系。文献检索尚不构成完整的新颖性证明。若最终只得到完整状态Markov续算、普通对称归约或一般主动采样，应按已有方法的适配报告。</p>',
'<h2>能够证实或推翻假设的下一步标准</h2>',
'<p>先用已有轨迹寻找同一接口操作之后的候选配对，所有特征只取决策时可得信息。对每一对逐项核验被覆盖状态、继承状态、未来消息生成状态及合法时序路径；证明不了的差异保留在误差项。按完整历史家族留出，避免把同轨迹的相邻片段拆入训练与测试。</p>',
'<p>冻结表示与误差估计后，比较“现有完整灰箱+同一个边界采样器”和“相同灰箱+所提复用关系+相同采样器”，并加入简单风险规则、普通回归/GP边界方法。让基线获得同样源码和初始数据。目标是相同危险漏判约束与边界分辨率下，总SITL秒数、测试次数及总墙钟成本下降；同时记录安全侧覆盖与未知区域。跨触发情境复用优先于继续堆AB参数；跨栈泛化需要另行证据。</p>',
'<p>如果有效等价类几乎只含一条轨迹、现实初态误差使所有迁移区间跨阈值、便宜规则达到相同成本，或加入一个控制层就必须重建全部模型，这条假设将受到直接否定或严格限缩。已见证的机制仍有工程价值。</p>',
'<h2>可追溯材料</h2><p>' + ' · '.join([
link(ROOT/'verified-evidence.json','文档版本与哈希'),link(ROOT/'evidence-matrix.json','15轮证据矩阵'),
link(ROOT/'data-manifest.json','重算输入哈希'),
link(ROOT/'descriptive-reanalysis.json','P7/P8/P13重算数据'),link(ROOT/'conclusion.json','结论与未证明项目'),
link(OUT/'greybox-baseline-audit-20261028/report.html','普通灰箱基线审计'),
link(OUT/'sequential-budget-audit-20261028/report.html','顺序查询成本审计')]) + '</p>',
'</main></html>']
(ROOT / 'report.html').write_text('\n'.join(parts))
print(json.dumps(dict(verified_reports=len(verified), p7=p7_summary, p8_n=len(p8rows),
                     p13_n=len(p13rows), report=str(ROOT/'report.html'), new_SITL=0),ensure_ascii=False))

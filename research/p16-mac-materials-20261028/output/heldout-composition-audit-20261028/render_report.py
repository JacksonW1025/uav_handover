from pathlib import Path
import json,html,math
from audit import ROOT,sha,validate_metrics,dump

primary=json.loads((ROOT/'results.json').read_text())['results']
sens=json.loads((ROOT/'sensitivity_results.json').read_text())['results']
capacity=json.loads((ROOT/'capacity_results.json').read_text())['results']
labels={'state_split':'状态拆分（CV）','cheap_rank':'廉价模型（CV择型）','cheap_ridge':'廉价回归','cheap_tree':'廉价树','lookup':'历史查表＋近邻','pooled_suffix':'取消拆分'}
foldnames={'all_AB':'留出全部 AB','all_B_only':'留出全部 B-only','all_REPAIR':'留出全部 REPAIR','F2_AB':'留出 F2 × AB','F4_AB':'留出 F4 × AB','family_F2':'留出整个 F2','family_F4':'留出整个 F4','gap_short':'留出全部短间隔','gap_medium':'留出全部中间隔','gap_long':'留出全部长间隔','D1':'留出 D1（短停用）','D2':'留出 D2（长停用）','D3':'留出 D3（长停用＋位移/转向）','all_long':'留出全部长停用 D2+D3','checkerboard_0':'前缀×处理交错留出 0','checkerboard_1':'前缀×处理交错留出 1'}
esc=lambda x:html.escape(str(x))
def table(headers,rows):
    return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+esc(x)+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+str(x)+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table></div>'
def pc(x):return f'{100*x:.1f}%'
def num(x):return '—' if x is None else f'{x:.4f}'
def find(ds,f,rr=primary):return next(r for r in rr if r['dataset']==ds and r['fold']==f)
methods=['state_split','cheap_rank','cheap_ridge','cheap_tree','lookup','pooled_suffix']
parts=['''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>整类前缀与事件组合留出核验</title><style>
:root{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;color:#142e35;background:#f4f6f5}body{max-width:1240px;margin:auto;padding:40px 28px 80px;line-height:1.75}h1{font-size:34px;line-height:1.25;letter-spacing:-1px;margin-bottom:14px}h2{font-size:23px;margin-top:40px;border-top:1px solid #cbd8d6;padding-top:26px}h3{font-size:18px}p{max-width:1040px}.eyebrow{color:#52726c;font-size:13px;letter-spacing:2px}.lead{font-size:20px;font-weight:600;max-width:1030px}.note{background:#e9efec;border-left:4px solid #44796c;padding:16px 22px;margin:24px 0}.warning{background:#f7eee2;border-color:#a46c29}.scroll{overflow:auto}table{width:100%;border-collapse:collapse;margin:16px 0 26px;font-size:13px;white-space:nowrap;background:white}th,td{padding:10px 12px;border-bottom:1px solid #dce5e2;text-align:right}th:first-child,td:first-child{text-align:left}th{background:#e4eeea;color:#234e43}tbody tr:hover{background:#f0f7f3}a{color:#146c65}small,.muted{color:#5a706e}details{background:white;border:1px solid #d5e1db;padding:14px 18px;margin:12px 0;border-radius:8px}summary{font-weight:650;cursor:pointer}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#eef3f0;padding:16px;font-size:12px;line-height:1.5}code{font-size:13px}li{margin:7px 0}.cards{display:flex;gap:16px;flex-wrap:wrap}.card{flex:1;min-width:180px;background:white;padding:16px 22px;border-top:3px solid #557f70}.card b{font-size:25px;display:block}@media(max-width:600px){body{padding:24px 16px}h1{font-size:28px}}
</style><body><div class="eyebrow">OFFLINE AUDIT · 2026-10-28 · PROTOCOL V2</div><h1>整类前缀与事件组合留出核验</h1>
<p class="lead">当前状态拆分方案仍缺少独立选测收益。它能拟合某些前缀依赖，也能改善部分留出地图误差；在这些现有候选池中，廉价回归已覆盖其有利选测结果，部分组合外推明显更差。</p>
<div class="cards"><div class="card"><b>102</b>已有记录：P13 66＋P3 36</div><div class="card"><b>16</b>整组留出：断流 10＋切换 6</div><div class="card"><b>0</b>新飞行 / 新仿真 / Thor 作业</div></div>
<div class="note">主比较相对廉价回归：断流 18 个候选池改变首选分布，0 胜 / 6 负 / 12 平；切换 9 个候选池改变首选分布，0 胜 / 9 负。不同留出会重复使用记录，这些计数仅描述该组离线比较，不能充当独立样本量或显著性证据。</div>
<h2>比较规则与可声称的范围</h2>
<p>数据来自冻结的历史归档。每个配置的 3 次重复一起留出；训练与测试不共享配置。模型只读计划中的前缀、事件、间隔和接口语义。B 前实测状态、事件实际执行状态、隐状态实测值、种子、ID、时间戳均不作为预测输入。配置均值等权训练；超参数通过训练配置内的留一交叉验证选择。候选池按相同场景和重复编号构造，属于已有独立运行的离线回放，无法等同于同一初态的在线反事实测试。</p>
<ul><li><b>状态拆分：</b>以训练集共享后续事件的响应差异作为拆分见证，仅在前缀字段上分支；每个状态使用小型二次岭回归响应头。最多 1/2/3/4 个状态及正则强度由训练配置 CV 选择。这是响应等价思想的最小离线实现；没有运行主动查询、完整自动机学习或等价性证明。</li>
<li><b>廉价特征排序：</b>相同输入上的线性/二次岭回归和浅树，训练 CV 选型；回归和树也分别公开，避免把选型波动当作结构贡献。</li>
<li><b>历史查表：</b>已见配置取历史均值；未见配置按固定归一化元数据距离找最近配置，等距均值。整组留出中没有精确命中项。</li>
<li><b>取消拆分：</b>只保留共享后续事件响应头，直接检验拆分是否带来额外收益。</li></ul>
<p>排序保留原始回归分数；概率截断到 [0,1] 仅用于 P13 地图 Brier 误差。并列首选按均匀随机选择计算期望，完全消除文件顺序打破并列的影响。历史结果此前已被讨论，因此这是一项固定规则的回顾性外推核验。</p>
<h2>断流：整组留出的首选失败命中率</h2>
<p>越高越好。每个候选池仅包含该折未见且带 B 的配置。P13 使用完整任务的 FAILURE 标签；F4 部分前缀 A 单独已经失败，因此不能把整表收益全算作新组合机制发现。REPAIR 留出全部成功，是负对照。首次失败排名只在确实存在失败的候选池中计算。</p>''']
rows=[]
for r in primary:
 if r['dataset']=='P13':rows.append([foldnames[r['fold']],str(r['eval_count']),f"{r['pool_count']} / {r['mixed_pools']}"]+[pc(r['summary'][m]['top1']) for m in methods])
parts.append(table(['留出内容','测试记录','池数 / 含成败混合']+[labels[m] for m in methods],rows))
parts.append('''<h3>关键反例：完整留出 F2 × AB</h3><p>训练仍保留 F2 的 A、B、REPAIR，以及 F4 的组合记录。测试仅含 F2 的短、中、长 AB，各 3 次。实测只有短间隔失败，3/3；中、长均成功。状态方法给短、中、长的原始分数分别为 0.1739、0.1782、0.1870，按长→中→短排序，三个重复均把唯一失败放到最后。历史近邻将短、长并列，首选期望命中 50%，首次失败期望第 1.5 个；状态方法为 0% 和第 3 个。固定启用两状态后仍然先选长间隔。</p>
<h3>有利留出也需要归因：留出全部 AB</h3><p>状态方法首选命中 100%，历史近邻为 66.7%。此折训练 CV 实际选择了一个状态，取消拆分预测完全相同；廉价回归也达到 100%。这项收益支持轻量预测在某些候选池中有用，无法作为状态拆分的独立贡献。</p>
<h2>切换：谁先选中实测跳变最大的组合</h2><p>P3 的 36 次任务全部成功。此处评价 second_C_to_N 时的电机指令跳变，不能解释为发现任务失败。表内为首选命中候选池最大跳变的概率；括号是首选遗憾，即最大实测跳变减去所选实测跳变，越小越好。电机指令按原始归一化尺度报告。</p>''')
rows=[]
for r in primary:
 if r['dataset']=='P3':rows.append([foldnames[r['fold']],str(r['eval_count']),str(r['pool_count'])]+[pc(r['summary'][m]['worst_hit'])+' ('+num(r['summary'][m]['regret'])+')' for m in methods])
parts.append(table(['留出内容','测试记录','候选池']+[labels[m] for m in methods],rows))
parts.append('''<p><b>整个 D3 留出：</b>状态方法选 N0，三次平均实际跳变 0.2098；廉价回归和历史近邻选 N2s，平均 0.3856，三次都选中最大跳变。<b>整个长停用 D2+D3 留出：</b>只用短停用 D1 学习，所有方法均继续选 N0，六个候选池都错过成为最坏项的 N2s。现有短停用响应无法提供这种次序反转的约束。</p>
<h2>拆分是否被过度保守的选型掩盖</h2><p>主比较中 P13 的 7/10 折、P3 的 5/6 折选择一个状态。看到该结果后，补做固定最多两状态、固定最多四状态的诊断；正则强度仍只用训练数据选。两种上限最后都最多形成两状态，全部预测一致。下面公开固定两状态的完整结果，同时让廉价模型固定容量作对应控制。该部分属于事后敏感性分析。</p>''')
rows=[]
for r in capacity:
 ds=r['dataset'];metric='top1' if ds=='P13' else 'worst_hit';fixed=next(s for s in sens if s['dataset']==ds and s['fold']==r['fold'] and s['variant']=='fixed_max_2')
 rows.append([ds+' · '+foldnames[r['fold']],str(fixed['model']['states'])]+[pc(r['summary'][m][metric]) for m in ['state_split','cheap_ridge','cheap_rank','cheap_tree','lookup']])
parts.append(table(['留出内容','实际状态数','固定两状态','固定二次回归','固定深度 2 树','固定深度 4 树','历史查表＋近邻'],rows))
parts.append('''<p>固定拆分在短间隔留出达到 100%，固定二次回归同样达到 100%。D2、D3 中也能选中最大跳变，廉价回归达到相同选择。前缀×处理交错留出中的失败仍然保留。因此，把复杂度选型改得更积极，尚未得到跨越廉价回归的选测证据。</p>
<div class="note warning"><b>分数处理修正：</b>初版把负回归分截到 0 后排序，导致短间隔留出里廉价回归误呈 66.7%。复查发现 F2 的 B / AB / REPAIR 原始分分别为 −0.1301 / −0.0354 / −0.1538，已经能优先选择 AB。已将全部方法改为原始分排序并重算 16 折及全部敏感性控制。修正后的廉价回归为 100%；原输出保存在 superseded-clipped-ranking，未用于本报告结论。</div>
<h2>地图更新：局部数值收益存在，组合外推收益不稳定</h2><p>这里的地图收益指训练得到的状态分区在未见配置上的预测误差，相当于更新完成后的泛化检验；没有声称实测了在线查询节省。主比较真正选出多个状态的四折，地图误差全部高于取消拆分的对应模型：</p>''')
rows=[]
for r in primary:
 if r['models']['state_split']['states']>1:
  rows.append([r['dataset']+' · '+foldnames[r['fold']],num(r['summary']['state_split']['map_mse']),num(r['summary']['pooled_suffix']['map_mse'])])
parts.append(table(['留出内容','状态拆分 MSE / Brier','取消拆分 MSE / Brier'],rows))
parts.append('<p>固定启用拆分具有真实的局部数值收益，以下保留正、负两面（P3 RMSE，越小越好）：</p>')
rows=[]
for f in ['D2','D3','checkerboard_0','checkerboard_1']:
 r=next(s for s in sens if s['dataset']=='P3' and s['fold']==f and s['variant']=='fixed_max_2')
 rows.append([foldnames[f]]+[num(math.sqrt(r['summary'][m]['map_mse'])) for m in ['state_split','cheap_ridge','lookup','pooled_suffix']])
parts.append(table(['留出内容','固定两状态','廉价回归','历史查表＋近邻','取消拆分'],rows))
parts.append('''<p>这说明按前缀拆分可以成为局部响应建模手段；当前数据无法建立稳定的规则，判断一条已见续接上的差异应如何迁移到其他未见续接。拆分后样本分散，尚未观察到的输出分支缺少约束。经典理论要求的“相同状态具有相同未来响应”是建模目标，现有有限见证无法自动补全其余事件组合。</p>
<h2>判断</h2><p><b>当前证据不足以把状态拆分／主动自动机学习确定为论文的核心选测贡献，也不足以据此投入新的在线实验。</b>已有记录支持历史依赖、接口语义和局部条件响应建模；本次核验没有支持“理论结构在未测组合上独立优于廉价排序”。保留状态分区作为候选地图组件是合理的，对其独立选测价值应撤回此前较强的判断。这一结论限于本报告的最小可执行实现和记录池，并不穷尽全部自动机方法。</p>
<h2>每一折的可核查记录</h2><p>展开可查看训练／测试配置、实际状态数、拆分见证，以及每个候选池的实测输出与原始分数。分数用于排序，不应直接解释为校准概率。</p>''')
for r in primary:
 parts.append('<details><summary>'+esc(r['dataset']+' · '+foldnames[r['fold']])+f" · train {r['train_n']} / test {r['test_n']} · states {r['models']['state_split']['states']}</summary>")
 metadata=dict(train_groups=r['train_groups'],test_groups=r['test_groups'],state_model={k:v for k,v in r['models']['state_split'].items() if k!='candidates'},cheap_model={k:v for k,v in r['models']['cheap_rank'].items() if k!='candidates'},changed_choices=r['comparisons'])
 parts.append('<pre>'+esc(json.dumps(metadata,ensure_ascii=False,indent=2))+'</pre>')
 for pool in r['pools']:
  parts.append('<h3>'+esc(pool['pool'])+'</h3>')
  rows=[[esc(a),num(y)]+[num(pool['predictions'][m][i]) for m in methods] for i,(a,y) in enumerate(zip(pool['arms'],pool['y']))]
  parts.append(table(['候选','实测输出']+[labels[m] for m in methods],rows))
  metricrows=[]
  for m in methods:
   z=pool['metrics'][m];metricrows.append([labels[m],num(z['top1']),num(z.get('first_failure_rank')),num(z.get('failures_at_2')),num(z['pair_accuracy'])])
  parts.append(table(['方法','首选实测收益','首次失败位置','前 2 项失败数','成对排序准确率'],metricrows))
 parts.append('</details>')
parts.append('''<h2>复现与验证</h2><p>所有数据下载均为历史归档读取，计算仅在本机执行。数据清单保存每个源文件的 SHA-256；记录拆分、内层调参、预测、见证、候选池与统计均已保存。检查覆盖完整重复留出、配置无交集、标签修改不改变预测、确定性复算、并列期望公式、负分排序，以及全部 16 折完成。</p><p><a href="protocol.json">主规则 v2</a> · <a href="results.json">主结果</a> · <a href="sensitivity_protocol.json">固定拆分规则</a> · <a href="sensitivity_results.json">固定拆分结果</a> · <a href="capacity_protocol.json">容量控制规则</a> · <a href="capacity_results.json">容量控制结果</a> · <a href="inputs_manifest.json">数据指纹</a> · <a href="validation.json">验证记录</a> · <a href="records.json">紧凑原始记录</a></p><pre>python3 audit.py
python3 sensitivity.py
python3 capacity_control.py
python3 render_report.py</pre><p class="muted">本报告不包含新实验排期。各折互有重叠；P3 的跳变收益和 P13 的任务失败收益分别报告，不合并成统一发现率。</p></body></html>''')
(ROOT/'report.html').write_text(''.join(parts))
validate_metrics()
v=json.loads((ROOT/'validation.json').read_text());v['checks'].append('negative regression scores retain ordering; clipping only affects map error');v['audit_sha256']=sha(ROOT/'audit.py');v['report_sha256']=sha(ROOT/'report.html');v['sensitivity_folds']=len(sens);v['capacity_control_folds']=len(capacity);dump(ROOT/'validation.json',v)
assert len(primary)==16 and len(sens)==32 and len(capacity)==16
assert all(find(ds,f)['models']['state_split']['states']>=1 for ds,f in [('P13','gap_short'),('P3','D3')])
print('Report written:',ROOT/'report.html')

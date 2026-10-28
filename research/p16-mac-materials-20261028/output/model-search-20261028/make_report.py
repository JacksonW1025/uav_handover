from pathlib import Path
import json,html,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parent
strict=json.loads((ROOT/'h2_strict_comparison.json').read_text());strong=json.loads((ROOT/'h2_strong_baselines.json').read_text());query=json.loads((ROOT/'h4_query_results.json').read_text());geometry=json.loads((ROOT/'h6_geometry_results.json').read_text());source=json.loads((ROOT/'h2_strict_singles.json').read_text());normal=json.loads((ROOT/'h2_strict_normal_only.json').read_text());audit=json.loads((ROOT/'h2_input_audit.json').read_text())
height=next(r for r in strict['results'] if r['outcome']=='height');task=next(r for r in strict['results'] if r['outcome']=='task_probability');tilt=next(r for r in strict['results'] if r['outcome']=='tilt');sh=next(r for r in strong['results'] if r['outcome']=='height');st=next(r for r in strong['results'] if r['outcome']=='task');querymap={r['group']:r for r in query['results']};srcmap={r['id']:r for r in source['results']};nmap={r['id']:r for r in normal['results']};updated={r['id']:r for r in querymap['F1|A']['results']}
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'#f6f8fb','axes.facecolor':'white'})
fig,axes=plt.subplots(2,2,figsize=(13,9.5),layout='constrained')
models=['State partition','Historical suffix','Extra Trees','Affine dynamics','Grey-box dynamics'];vals=[sh['metrics']['state_partition']['MAE'],height['metrics']['suffix_lookup']['MAE'],sh['metrics']['ExtraTrees_plan']['MAE'],geometry['results'][1]['metrics']['height_MAE'],height['metrics']['source_singles']['MAE']]
a=axes[0,0];a.barh(models,np.array(vals)*100,color=['#b8c1d0']*4+['#176b87']);a.invert_yaxis();a.set_xlabel('Height-loss MAE (cm), 13 complete AB flights');a.set_title('Strict AB holdout',loc='left',fontweight='bold')
for i,v in enumerate(vals):a.text(v*100+.4,i,f'{v*100:.1f}',va='center')
a=axes[0,1];groups=['F2 short','F2 medium','F2 long','F4 short','F4 medium','F4 long'];actual=[];pred=[]
for f,arm in [('F2','AB-short'),('F2','AB-medium'),('F2','AB-long'),('F4','AB-short'),('F4','AB-medium'),('F4','AB-long')]:
 rr=[r for r in source['results'] if r['family']==f and r['arm']==arm];actual.append(sum(r['actual_tilt']>45 or r['actual']>1 for r in rr));pred.append(sum(r['predicted_tilt']>45 or r['prediction']>1 for r in rr))
a.imshow(np.array([actual,pred]),vmin=0,vmax=3,cmap='YlOrRd',aspect='auto');a.set_xticks(range(6),groups,rotation=30,ha='right');a.set_yticks([0,1],['Observed','Grey-box']);a.set_title('Failure map: 3 repeats per cell',loc='left',fontweight='bold')
for i,row in enumerate([actual,pred]):
 for j,value in enumerate(row):a.text(j,i,f'{value}/3',ha='center',va='center',color='white' if value>2 else '#182331',fontweight='bold')
a=axes[1,0];names=['6 normal flights','+ 2 F1-A flights','+ 2 maximum-risk flights','All 18 normal/single flights'];v=[height['metrics']['source_normal_only']['MAE'],querymap['F1|A']['metrics']['height_MAE'],querymap['F3|B']['metrics']['height_MAE'],height['metrics']['source_singles']['MAE']];a.barh(names,np.array(v)*100,color=['#bd674b','#176b87','#8793a8','#176b87']);a.invert_yaxis();a.set_xlabel('Held-out AB height-loss MAE (cm)');a.set_title('Single-event data updates the unmeasured map',loc='left',fontweight='bold')
for i,x in enumerate(v):a.text(x*100+.5,i,f'{x*100:.1f}',va='center')
a=axes[1,1];labels=['F1-A','F1-B','F2-A','F2-B','F3-A','F3-B'];v=[querymap[k.replace('-','|')]['metrics']['height_MAE']*100 for k in labels];a.bar(labels,v,color=['#176b87']+['#a4afc0']*4+['#bd674b']);a.set_ylabel('Held-out AB height-loss MAE (cm)');a.set_ylim(0,12);a.set_title('D-optimal ties cheap screening',loc='left',fontweight='bold')
for i,x in enumerate(v):a.text(i,x+.2,f'{x:.2f}',ha='center')
fig.savefig(ROOT/'evidence.png',dpi=180);fig.savefig(ROOT/'evidence.svg');plt.close(fig)

rows=[]
for label,hm,fn,fp in [
 ('源码耦合灰箱模型',height['metrics']['source_singles']['MAE'],task['metrics']['source_singles']['FN'],task['metrics']['source_singles']['FP']),
 ('历史后缀查表',height['metrics']['suffix_lookup']['MAE'],task['metrics']['suffix_lookup']['FN'],task['metrics']['suffix_lookup']['FP']),
 ('廉价特征学习：Extra Trees',sh['metrics']['ExtraTrees_plan']['MAE'],st['metrics']['ExtraTrees_plan']['FN'],st['metrics']['ExtraTrees_plan']['FP']),
 ('状态拆分',sh['metrics']['state_partition']['MAE'],st['metrics']['state_partition']['FN'],st['metrics']['state_partition']['FP'])]:
 rows.append(f'<tr><td>{label}</td><td>{hm*100:.2f} cm</td><td>{fn}</td><td>{fp}</td><td>{18-fn-fp}/18</td></tr>')
cell=[]
for rid in ['p13-F2-b3-AB-short','p13-F4-b2-AB-medium','p13-F4-b2-AB-short']:
 n=nmap[rid];u=updated[rid];mode='倾角' if 'F2' in rid else '损高';key='predicted_tilt' if mode=='倾角' else 'prediction';obs='actual_tilt' if mode=='倾角' else 'actual';unit='°' if mode=='倾角' else 'm';actualtxt=('≥' if u['actual_censored'] else '')+f'{u[obs]:.3f} {unit}'
 cell.append(f'<tr><td>{rid.replace("p13-","")}</td><td>{mode}</td><td>{n[key]:.3f} {unit}</td><td>{u[key]:.3f} {unit}</td><td>{actualtxt}</td></tr>')
report=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>整类组合留出：离线方法核验</title>
<style>body{{margin:0;background:#f5f7fa;color:#182331;font:16px/1.8 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}}main{{max-width:1120px;margin:auto;padding:48px 28px 80px}}h1{{font-size:34px;line-height:1.3;margin:8px 0 18px}}h2{{font-size:22px;margin-top:38px}}p{{max-width:1000px}}.eyebrow{{font-size:13px;color:#64748b;letter-spacing:.08em}}.lead{{font-size:20px;color:#164e63}}.box{{background:white;border:1px solid #dce4eb;border-radius:12px;padding:18px 24px;margin:22px 0}}.warning{{border-left:4px solid #bd674b}}table{{border-collapse:collapse;background:white;width:100%;margin:18px 0;font-variant-numeric:tabular-nums}}th,td{{padding:12px 14px;border-bottom:1px solid #e1e6ed;text-align:left}}th{{background:#eaf0f6}}img{{width:100%;height:auto}}a{{color:#126782}}code{{background:#e9eef4;padding:2px 5px}}.small{{font-size:14px;color:#58677b}}.math{{font:16px/1.7 ui-monospace,monospace;background:#edf3f7;padding:16px;overflow:auto}}li{{margin:8px 0}}</style><main>
<div class="eyebrow">2026-10-28 · 仅既有记录与本地计算 · 未启动 SITL、未使用 Thor</div>
<h1>单事件信息能否迁移到未测组合？</h1>
<p class="lead">可保留的核心是：用控制器源码和结构化动力学，把少量单事件轨迹转化为整个组合响应地图的更新。本轮已得到跨组合预测优势；“更快找到任意失败”仍与强廉价基线打平。</p>
<div class="box"><strong>核心证据：</strong>辨识数据完全移除多事件轨迹后，18 条 AB 留出记录中，灰箱模型任务分类正确 17 条；最强历史查表正确 14 条。完整 AB 的损高误差为 8.32 cm，廉价特征学习为 13.12 cm。加入两条单事件记录，能够把未测 AB 地图的损高误差从 54.20 cm 降到 7.56 cm。</div>
<h2>留出协议与信息边界</h2>
<ul><li>重新辨识 P11 动力学，只使用 6 条 NORMAL 与 12 条单事件 A/B，共 18 条记录。AB、REPAIR 和多事件锚点均移除；已知控制器权重和源码事件规则保持固定。</li><li>廉价基线获得相同 P11 单事件历史，并额外获得 P13 单事件记录。所有 P13 AB 均留出。超参数只在训练集内按整类条件交叉验证。</li><li>预测从飞行开始前的初值和已知计划出发。没有使用 A 后状态、B 前状态、未来目标、实际未来触发时间或 COM 真值。</li><li>测试集为 18 条 AB：任务失败 10 条、成功 8 条。连续损高误差只评价 13 条完整记录；另外 5 条为截断下界。所有 18 条始终保留在选测候选池中。</li><li>原任务阈值保持倾角 45°、损高 1 m。损高基准统一为原始共同首事件时刻 13.255 s。66 份归档初值、参考计划、事件窗口和相位均逐一核对；两个案例通过未来结果置换不变性核验。</li><li>这是在熟悉历史结果后开展的回顾性方法搜索。每次拟合没有使用留出标签，但多次方法迭代共享了这批评价数据。</li></ul>
<h2>主对照结果</h2>
<table><thead><tr><th>方法</th><th>完整 AB 损高 MAE</th><th>任务漏判</th><th>任务误报</th><th>任务分类正确</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<p>还比较了线性/二次岭回归、浅树、RBF 核回归、梯度提升、最近邻、单事件加和和最大值组合。源码模型的全组合任务分类仍最好。平均完整轨迹倾角误差则由一个 Extra Trees 对照略胜：0.756° 对 0.811°；该对照漏掉了 7 个已观测倾角失败中的 6 个，源码模型漏掉 1 个。完整轨迹的平均误差不能代替危险尾部识别。</p>
<img src="evidence.png" alt="组合留出误差、失败地图、单事件更新与选样对照">
<h2>它确实改变了哪些选择</h2>
<p>以第三个重复块、最大倾角为目标，源码模型选择 <strong>F2–AB–short</strong>；廉价计划特征排序选择 <strong>F4–AB–long</strong>。模型预测分别为 46.424° 与 46.014°；实际前者已达到 50.849° 后截断，后者完整峰值为 45.884°。这一次选择得到更高的已证实倾角风险。前两块同样改变选择，但两个候选都有截断，完整峰值的真实先后仍未知。</p>
<p class="box warning"><strong>选择收益的边界：</strong>按“是否找到任意任务失败”计分，源码模型和最强廉价计划排序都能达到 3/3。按最大损高选择，两者也都选中 F4 短间隔。因此本轮支持危险响应地图更准确、部分风险目标下选择更好；不能据此宣称一般找错效率已超过廉价基线。</p>
<h2>地图更新的可复用信息是什么</h2>
<p>起点使用 6 条正常飞行，随后只加入 P11 的两条 F1–A 单事件记录；所有下表 AB 仍未进入辨识。更新了共享动力学系数，控制器源码、事件计划、阈值和网络权重均未改动。</p>
<table><thead><tr><th>未测组合</th><th>量</th><th>正常数据模型</th><th>加两条单事件后</th><th>实测</th></tr></thead><tbody>{''.join(cell)}</tbody></table>
<p>这次更新同时修正了“F2 短间隔的倾角危险”与“F4 中间隔的虚假损高危险”，并保留 F4 短间隔的真实损高失败。它体现了跨方向、跨事件组合传播的模型更新。查表只获得新的单事件单元；共享动力学参数为未测组合提供了新的响应预测。</p>
<p>六种可选单事件条件分别用于一次更新时，AB 损高误差为 7.54–8.51 cm。D-optimal 选择约 7.56 cm，简单筛选完整轨迹后均匀选样的平均值约 7.57 cm。<strong>D-optimal 的独立选样贡献未建立，当前不保留为核心贡献。</strong></p>
<h2>模型与经典理论的具体分工</h2>
<p><strong>模型：</strong>复用实际 GRU16、动作历史、采样与提交时钟、超时捕获和恢复规则；机体保留位置、速度、姿态、角速度及四个执行滤波状态。只辨识 10 个有效动力学系数。神经控制器权重保持封存。每个事件在预测状态上执行，A 的恢复状态自然成为 B 的初始状态；世界高度账本持续累积。</p>
<div class="math">v̇ = g e₃ − kT · T(f) · R(q)e₃ − Dv<br>ω̇ = Kτ · ΔT(f) − Dω · ω<br>θ = (kT, Dx, Dy, Dz, Kτx, Kτy, Kτz, Dωx, Dωy, Dωz)</div>
<p><strong>经典理论：</strong>采用<a href="https://www.mathworks.com/help/ident/grey-box-model-estimation.html">结构化灰箱系统辨识</a>。动力学方程规定参数如何跨方向和事件共享，参数通过轨迹回归估计；完整源码闭环随后组合未测事件。这些系数是有效经验系数，当前没有把它们解释为精确真实质量或惯量。</p>
<p>独立结构对照保留相同 18 条数据、控制器、事件逻辑和角动态，只替换平移动力学：局部推力线性化的 AB 损高 MAE 为 17.73 cm，普通仿射动力学为 12.65 cm，非线性推力方向结构为 8.32 cm。三者分别出现 3、3、0 个高度误报。这是目前经典结构提供独立收益的具体证据。</p>
<p>正常数据上用积分方程辨识也已核验：窗口由正常数据内部交叉验证选择，AB 损高误差却达到 60.09 cm。正常轨迹拟合得好，仍可能缺少对事件响应有用的激励。</p>
<h2>研究判断与反驳条件</h2>
<p><strong>值得保留的核心问题：</strong>一次便宜、可完整观测的测试，能否辨识出可迁移的闭环响应，从而预测并更新大量尚未执行的事件组合。当前已验证“单事件轨迹 → 共享参数 → 未测 AB 地图”的能力。这比重复统计发现了多少个已知类型的失败更能体现模型价值。</p>
<ul><li>保留的核心构造：源码耦合的轻量灰箱模型、单事件辨识、组合响应外推、共享参数驱动地图更新。</li><li>尚未建立：一般选测效率优势、D-optimal 独立贡献、未来误差硬界、跨平台有效性。</li><li>切换核验仍为负面：P3 的短暂重入输出预测可被 previous-action 廉价特征接近，选择没有独立收益；不能把断流的组合外推结果推广为切换已经成立。</li><li>修复选择也缺少独立优势：既有固定 C/CR 修复已很强。当前可以把修复写入同一源码事件模型，修复优选能力仍待证据支持。</li><li>明确反驳方式：同等信息的廉价时序模型达到同等组合地图准确率；跨组合优势依赖先前组合辨识数据；参数更新改善一个区域却系统性破坏其他区域；不同平台或控制器源码下共享结构失效。</li></ul>
<p class="small">范围：PX4–RAPTOR，当前主要是同一平台上的断流组合。严格留出只验证现有可比数据；结构设计已参考全部历史。更早轮次用于方向审查，没有把不同版本、观测口径的全部记录混成训练样本。</p>
<h2>可复核文件</h2>
<p><a href="h2_strict_comparison.json">主比较与逐案例预测</a> · <a href="h2_strong_baselines.json">补强基线</a> · <a href="h4_query_results.json">单事件更新</a> · <a href="h6_geometry_results.json">动力学结构对照</a> · <a href="h2_input_audit.json">输入核验</a> · <a href="research_ledger.json">假设与失败记录</a></p>
<p class="small">较早的完整轨迹训练、原点计量和候选池处理版本均单独保留，文件名含 prestream_accounting、v1 或 superseded 的结果已被后续版本替代。本报告只采用修正后的统一口径。</p>
</main></html>'''
(ROOT/'report.html').write_text(report)
summary=dict(core='Source-coupled grey-box identification for unseen event-combination response maps',status='independent full-horizon map advantage established on retrospective strict holdout; generic failure-search advantage not established',height_MAE=height['metrics']['source_singles']['MAE'],best_endpoint_baseline_height_MAE=sh['metrics']['ExtraTrees_plan']['MAE'],task_correct=17,task_n=18,cheap_lookup_task_correct=14,query_update_before=height['metrics']['source_normal_only']['MAE'],query_update_after=querymap['F1|A']['metrics']['height_MAE'],D_optimal_independent_gain=False,input_audit=audit['archived_inputs_verified'])
(ROOT/'conclusion.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False))

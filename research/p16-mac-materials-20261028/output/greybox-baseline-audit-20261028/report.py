from pathlib import Path
import json,hashlib,html,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parent
results=json.loads((ROOT/'results.json').read_text());eq=json.loads((ROOT/'equivalence.json').read_text());verify=json.loads((ROOT/'verification.json').read_text());models=json.loads((ROOT/'models.json').read_text())
idx={(r['name'],r['scope']):r for r in results['results']}
names={'ordinary_EE':'普通非线性灰箱：方程误差拟合','ordinary_OE':'普通非线性灰箱：多步输出误差拟合','hold_target':'删除超时捕获语义，保持末次目标','no_carry':'删除跨事件状态继承','hold_target_no_carry':'同时删除两项','no_neural_carry':'只删除神经记忆继承','no_physical_carry':'只删除机体与执行器状态继承'}
def table(scope,kind='per_case'):
    rows=[]
    for name in names:
        m=idx[(name,scope)][kind]['metrics']
        rows.append(f'<tr><td>{names[name]}</td><td>{m["task_correct"]}/18</td><td>{100*m["height_MAE"]:.2f} cm</td><td>{m["tilt_MAE"]:.3f}°</td><td>{m["task_FN"]} / {m["task_FP"]}</td></tr>')
    return '<table><thead><tr><th>模型</th><th>成败判断正确</th><th>损高MAE</th><th>倾角MAE</th><th>漏判 / 误报</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table>'

plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'#f5f7fa'})
fig,axes=plt.subplots(1,2,figsize=(12.5,5.2),layout='constrained')
labels=['Proposed model','Ordinary grey-box (EE)','Ordinary grey-box (OE)','No timeout capture','No state carry','No neural-state carry','No physical-state carry']
variants=['ordinary_EE','ordinary_EE','ordinary_OE','hold_target','no_carry','no_neural_carry','no_physical_carry']
colors=['#136c86','#4f8495','#789ca6','#b76b47','#b76b47','#8b789f','#b76b47']
for ax,key,title,factor in [(axes[0],'height_MAE','Height-loss MAE on 13 complete AB records',100),(axes[1],'task_correct','Task classification on all 18 AB records',1)]:
    vals=[idx[(v,'case_initial')]['per_case']['metrics'][key]*factor for v in variants]
    ax.barh(labels,vals,color=colors);ax.invert_yaxis();ax.set_title(title,loc='left',fontweight='bold');ax.set_xlabel('cm' if factor==100 else 'Correct / 18')
    ax.set_xlim(0,max(vals)*1.15)
    for i,v in enumerate(vals):ax.text(v+max(vals)*.012,i,f'{v:.2f}' if factor==100 else f'{int(v)}/18',va='center')
fig.savefig(ROOT/'comparison.png',dpi=180);fig.savefig(ROOT/'comparison.svg');plt.close(fig)

up=[]
for r in verify['ordinary_shared_parameter_updates']:
    m=r['ordinary_metrics'];p=r['proposed_metrics'];up.append(f'<tr><td>{r["budget"]}</td><td>{", ".join(r["selected"]) or "仅6条正常轨迹"}</td><td>{100*m["height_MAE"]:.2f} cm</td><td>{100*p["height_MAE"]:.2f} cm</td><td>{m["task_correct"]}/18</td></tr>')
source=json.loads((ROOT.parent/'model-search-20261028/h2_strict_singles.json').read_text());src={r['id']:r for r in source['results']}
examples=[]
for rid in ['p13-F2-b3-AB-short','p13-F4-b2-AB-short','p13-F4-b2-AB-medium']:
    r=src[rid];vals=[]
    for name in ['ordinary_EE','ordinary_OE','hold_target','no_carry','no_neural_carry']:
        q=next(x for x in idx[(name,'case_initial')]['per_case']['rows'] if x['id']==rid);vals.append(f'{q["prediction"]:.3f} m / {q["predicted_tilt"]:.2f}°')
    actual=('≥' if r['actual_censored'] else '')+f'{r["actual"]:.3f} m / '+('≥' if r['actual_censored'] else '')+f'{r["actual_tilt"]:.2f}°'
    examples.append('<tr><td>'+rid.removeprefix('p13-')+'</td><td>'+actual+'</td>'+''.join('<td>'+v+'</td>' for v in vals)+'</tr>')
report=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>普通灰箱强基线与事件消融</title>
<style>body{{margin:0;background:#f5f7fa;color:#192635;font:16px/1.8 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}}main{{max-width:1150px;margin:auto;padding:42px 28px 80px}}h1{{font-size:32px;line-height:1.4}}h2{{font-size:22px;margin-top:34px}}.lead{{font-size:20px;color:#135c70}}.box{{background:white;border:1px solid #dce4ec;border-left:4px solid #b76b47;border-radius:8px;padding:18px 24px;margin:20px 0}}table{{width:100%;border-collapse:collapse;background:white;font-variant-numeric:tabular-nums}}th,td{{padding:11px 13px;text-align:left;border-bottom:1px solid #dfe6ed}}th{{background:#e9eff4}}.scroll{{overflow-x:auto}}img{{width:100%;height:auto}}a{{color:#126b83}}.small{{font-size:14px;color:#5c6b7c}}li{{margin:8px 0}}</style><main>
<div class="small">2026-10-28 · 本地既有数据 · 新飞行0 · SITL0 · Thor未使用</div>
<h1>补上普通非线性灰箱后，独立贡献还剩什么？</h1>
<p class="lead">当前实现与同信息的普通非线性灰箱等价。事件语义和跨事件状态对预测很重要，但这些能力由完整灰箱共同拥有。现有数据没有建立独立辨识、组合或地图更新算法的优势。</p>
<div class="box">普通灰箱独立重写后，复现原方法的17/18成败判断与8.32 cm损高误差。常规64 ms多步输出误差拟合同样为17/18，损高误差7.92 cm。共享参数更新的预算收益也被普通灰箱复现。当前最可支持的成果是源码语义接线、状态记录与完整响应验证的工程整合，以及接入层现象的经验研究。</div>
<h2>强基线的同等信息条件</h2>
<ul><li>辨识数据严格相同：18条P11正常／单事件完整轨迹，逐文件hash核对。AB、REPAIR和P13结果均未用于拟合。</li>
<li>模型结构相同：非线性推力方向、四个执行器滤波状态、10个有效动力学系数与相同参数边界。双方使用相同冻结GRU、目标事件源码、初始状态和时钟假设。</li>
<li>普通方程误差基线独立组装原始测量的回归矩阵，并独立实现机体积分器。其参数与原方法最大差为{eq['parameter_max_abs']:.2e}。源控制器有意共享，符合用户要求的同源码信息。</li>
<li>补充普通非线性输出误差基线：由相同数据形成{models['oe_fit']['total_windows']}个64 ms窗口，拟合速度和角速度端点，固定误差尺度与80次评估上限。已执行{models['oe_fit']['nfev']}次评估并正常收敛。窗口来自同18条记录，不增加独立样本。训练中使用实测动作，留出预测闭环运行控制器，未来动作不作为输入。</li>
<li>主评价保持原严格留出报告口径：18条P13 AB、各自事件前初值。敏感性评价使用已知NORMAL初值模板，并按最新预算报告的组合地图均值评分。</li></ul>
<p>原方法已经实现了普通灰箱的上述模型和有界最小二乘估计器。独立重写和新增的输出误差优化用于检查这个等价关系；不把相同模型改名视作新的算法。多步拟合约0.40 cm的差异不支持在小样本上宣称稳定优越，但足以排除原方法在本比较中的独占收益。</p>
<h2>完整强基线与固定参数消融</h2>
{table('case_initial')}
<p class="small">原方法：17/18，损高8.32 cm，倾角0.811°，漏判1、误报0。高度和倾角MAE均只使用固定13条完整记录；5条截断记录不作为精确峰值。所有变体在本评价中均没有数值失域。消融使用同一组完整数据辨识的参数，不按留出标签重新调整。</p>
<img src="comparison.png" alt="普通灰箱复现原模型，删除事件捕获和物理继承后误差变大">
<h2>消融到底删了什么</h2>
<ul><li><strong>删除超时捕获：</strong>仍知道消息断流的时段，保留控制器、动力学与时钟；接入层只保持最后收到的目标，删除超时后从当前预测状态捕获新目标的规则。这只检验该具体事件语义。</li>
<li><strong>删除跨事件继承：</strong>在B开始前，用同初值、同时间的“没有A”预测状态替换当前后继。前缀已经发生的损高和峰值仍保留；没有读取实测B前状态。</li>
<li><strong>只删除神经记忆继承：</strong>仅替换h、上一动作、历史均值和计数，保留物理与事件状态。</li>
<li><strong>只删除物理继承：</strong>仅替换机体、执行器、待执行指令和观测缓存，保留控制器及事件状态。</li></ul>
<div class="box">这些删除是模型组件消融，未实际对飞行器实施状态重置。结果衡量模型对被删信息的依赖，不能直接当作真实系统的因果干预效果，也不能将删除后的弱模型当作同信息强基线。</div>
<p>删除超时捕获后，模型漏掉全部10条任务失败；删除完整状态继承也漏掉全部10条。两项对完整预测都有作用。普通灰箱连续推进状态并执行相同源码规则，自然获得相同收益。</p>
<p>只删除神经记忆继承仍为17/18，损高7.95 cm、倾角0.729°，本批指标没有下降；只删除物理继承降为10/18、18.46 cm。这说明在本批恢复间隔0.55–2 s的断流组合中，物理与执行器后继更敏感。消融作用存在相互依赖，不能将误差差值相加当作各状态的独立贡献；也不能推广到瞬时控制权切换。</p>
<h2>具体案例：同一初值下的模型对照</h2>
<div class="scroll"><table><thead><tr><th>案例</th><th>实测损高／倾角</th><th>普通灰箱EE</th><th>普通灰箱OE</th><th>删捕获</th><th>删继承</th><th>仅删神经记忆</th></tr></thead><tbody>{''.join(examples)}</tbody></table></div>
<p class="small">截断案例只给出已见峰值下界。原方法与普通灰箱EE的预测在这里相同至数值精度。</p>
<h2>使用NORMAL初值模板，结论是否改变</h2>
{table('normal_template','group_map')}
<p>此表使用已知正常记录的初值模板，在同一组合内汇总预测，再评价18条固定历史结果，与顺序预算报告一致。它与主表的逐案例口径分别保留；本次没有通过更换口径选择有利结果。</p>
<h2>普通灰箱是否也复制地图更新收益</h2>
<p>额外独立重拟合上轮“短断流优先”路径：6条正常轨迹起步，依次加入F1-r1-A、F1-r1-B。每一步都不使用任何AB辨识数据，使用相同NORMAL初值模板预测全部AB。</p>
<table><thead><tr><th>新增轨迹数</th><th>已加入单事件</th><th>普通灰箱损高MAE</th><th>原方法损高MAE</th><th>普通灰箱任务正确</th></tr></thead><tbody>{''.join(up)}</tbody></table>
<p>普通灰箱同样在两条新增单事件轨迹后达到90%准确率和10 cm损高误差的联合指标。该路径已经在上轮被简单选择规则实现，本轮又确认共享参数更新也属于普通灰箱的能力。</p>
<h2>研究结论</h2>
<p><strong>辨识算法：</strong>未发现独立新意；现有估计器与标准灰箱一致。<strong>事件组合：</strong>准确的源码事件规则和连续状态继承有用，但普通混合灰箱同样具备。<strong>地图更新：</strong>共享参数带来的跨组合改善被强基线复现。<strong>选测：</strong>本轮没有新增省预算证据，沿用上轮的否定性结论。</p>
<p>当前可保留的贡献是工程整合与经验发现：把可用源码、控制器记忆、执行器状态、参考事件和任务历史接成可运行模型，建立可复核的组合留出评价。若论文定位要求一种超过普通系统辨识的新核心方法，现有实现尚未达到这一要求。切换与跨平台仍是有意义的问题，但本轮未验证其方法优势，不能用尚未实施的复用主张补足当前新意。</p>
<h2>完整性检查与复现</h2>
<p>独立机体单步实现与原代码在50组固定随机状态的最大差{verify['plant_step_max_difference']:.2e}；预测API只接收事件前输入，置换结果标签和未来B前记录不改变预测；所有状态继承消融在B前的整段轨迹保持一致；没有A时，删除继承操作与完整模型逐点相同。参数更新0、1、2步均独立重拟合并执行全部AB预测。</p>
<p class="small">局限：方法设计已经接触过历史结果；18条数据只有6种组合；当前控制器时序与观测近似由双方共同继承。数值一致证明实现等价，不能证明真实世界模型精确。没有进行新飞行、SITL、切换或跨平台试验。</p>
<p><a href="protocol.json">固定比较协议</a> · <a href="models.json">辨识结果</a> · <a href="results.json">全部预测与评分</a> · <a href="equivalence.json">等价核验</a> · <a href="verification.json">信息边界与更新核验</a> · <a href="manifest.json">文件校验清单</a></p>
</main></html>'''
(ROOT/'report.html').write_text(report)
conclusion=dict(independent_method_advantage=False,ordinary_greybox_reproduces_proposed=True,ordinary_output_error_also_matches_task=True,
    primary={n:idx[(n,'case_initial')]['per_case']['metrics'] for n in names},shared_parameter_update_reproduced=True,
    supported_contribution='Engineering integration and empirical event-interface findings. No incremental identification, composition, map-update or test-selection algorithm advantage demonstrated.',new_flights=0,new_SITL=0,Thor_used=False)
(ROOT/'conclusion.json').write_text(json.dumps(conclusion,ensure_ascii=False,indent=2))
files=[p for p in ROOT.iterdir() if p.suffix in ['.py','.json','.png','.svg','.html'] and p.name not in ['manifest.json','progress.json']]
(ROOT/'manifest.json').write_text(json.dumps(dict(files=[dict(path=p.name,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(files)]),indent=2))
print('report written:',ROOT/'report.html')

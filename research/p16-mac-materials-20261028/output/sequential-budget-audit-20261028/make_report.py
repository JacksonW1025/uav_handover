from pathlib import Path
import json,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parent;main=json.loads((ROOT/'sequential_results.json').read_text());rob=json.loads((ROOT/'robustness_results.json').read_text());summary=json.loads((ROOT/'summary.json').read_text());traj=json.loads((ROOT/'trajectory_results.json').read_text());verify=json.loads((ROOT/'verification.json').read_text())
M={(r['learner'],r['policy']):r['curve'] for r in main['results']+rob['results']}
def arr(learner,policy,key):return np.array([r[key] for r in M[(learner,policy)]])
x=np.arange(13);plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'#f5f7fa','axes.facecolor':'white'})
fig,axes=plt.subplots(2,2,figsize=(12.8,9.2),layout='constrained')
a=axes[0,0]
for name,label,color in [('greybox_gp','Grey-box + update','#146b82'),('cheap_ridge','Cheap ranker + refit','#b66848'),('lookup_shrunk','Shrunk lookup update','#7d6ca6')]:a.plot(x,arr(name,'map_variance','accuracy')*100,'o-',ms=3,label=label,color=color)
a.axhline(77.7778,color='#7d6ca6',ls='--',label='Frozen lookup');a.axhline(90,color='#777',ls=':',lw=1);a.set_ylim(45,100);a.set_xlabel('Additional revealed tests');a.set_ylabel('Fixed-target task accuracy (%)');a.set_title('Task accuracy comes from the initial map',loc='left',fontweight='bold');a.legend(fontsize=8,loc='lower left')
a=axes[0,1]
for p,label,color in [('map_variance','Map-oriented queries','#146b82'),('random','Random queries','#808b9b'),('risk','Risk-first queries','#b66848')]:a.plot(x,arr('greybox_gp',p,'height_MAE')*100,'o-',ms=3,label=label,color=color)
a.axhline(arr('greybox_gp','map_variance','height_MAE')[0]*100,color='#146b82',ls='--',label='Frozen grey-box prior');a.set_xlabel('Additional revealed tests');a.set_ylabel('Height-loss MAE (cm)');a.set_title('Updates help height; selection adds little',loc='left',fontweight='bold');a.legend(fontsize=8)
a=axes[1,0]
for name,label,color in [('greybox_gp','Grey-box prior','#146b82'),('cheap_gp','Cheap learned prior','#b66848'),('lookup_gp','Lookup prior','#7d6ca6')]:a.plot(x,arr(name,'map_variance','brier'),'o-',ms=3,label=label,color=color)
a.set_xlabel('Additional revealed tests');a.set_ylabel('Configuration-frequency Brier error');a.set_title('Same queries and same residual updater',loc='left',fontweight='bold');a.legend(fontsize=8)
a=axes[1,1]
for r,label,color in zip(traj['results'],['Predicted information','Cheap risk ranking','Short-dropout-first'],['#146b82','#b66848','#7d6ca6']):a.plot([z['budget'] for z in r['steps']],[z['greybox']['height_MAE']*100 for z in r['steps']],'o-',ms=4,label=label,color=color)
a.axhline(10,color='#777',ls=':',lw=1);a.set_yscale('log');a.set_yticks([5,10,20,50],[5,10,20,50]);a.set_xlabel('Additional single-event trajectories');a.set_ylabel('Unqueried AB height-loss MAE (cm)');a.set_title('Shared dynamics update: cheap selection matches',loc='left',fontweight='bold');a.legend(fontsize=8)
fig.savefig(ROOT/'budget-curves.png',dpi=180);fig.savefig(ROOT/'budget-curves.svg');plt.close(fig)
from sequential import threshold
rows=[]
for r,label in zip(traj['results'],['模型预测信息量','廉价风险排序','简单短断流优先']):
 ac=np.array([z['greybox']['accuracy'] for z in r['steps']]);hm=np.array([z['greybox']['height_MAE'] for z in r['steps']]);valid=(ac>=.9)&(hm<=.1);hit=np.flatnonzero(valid);stable=[i for i in hit if valid[i:].all()];joint=int(stable[0]) if stable else '未达到';firsth=threshold(hm,.1,False)['persistent'];rows.append(f'<tr><td>{label}</td><td>{joint}</td><td>{firsth}</td><td>{r["steps"][0]["next_query"]}</td></tr>')
curve_rows=[]
for b in [0,1,2,4,8,12]:
 a=M[('greybox_gp','map_variance')][b];r=M[('greybox_gp','random')][b];w=M[('greybox_gp','risk')][b];curve_rows.append(f'<tr><td>{b}</td><td>{a["accuracy"]*100:.1f}%</td><td>{a["height_MAE"]*100:.2f} cm</td><td>{r["height_MAE"]*100:.2f} cm</td><td>{w["height_MAE"]*100:.2f} cm</td></tr>')
html=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>固定预算顺序选测核验</title><style>body{{margin:0;background:#f5f7fa;color:#192635;font:16px/1.8 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}}main{{max-width:1100px;margin:auto;padding:44px 28px 80px}}h1{{font-size:34px;line-height:1.35}}h2{{font-size:22px;margin-top:36px}}.eyebrow{{color:#64748b;font-size:13px}}.lead{{font-size:20px;color:#135b70}}.box{{background:white;border:1px solid #dce4ec;border-radius:10px;padding:18px 24px;margin:22px 0}}.caution{{border-left:4px solid #b66848}}table{{width:100%;border-collapse:collapse;background:white;margin:18px 0}}th,td{{text-align:left;border-bottom:1px solid #e0e5ec;padding:11px 14px}}th{{background:#eaf0f5}}img{{width:100%;height:auto}}li{{margin:8px 0}}a{{color:#126c84}}.small{{font-size:14px;color:#596a7d}}code{{background:#e8eef4;padding:2px 4px}}</style><main>
<div class="eyebrow">2026-10-28 · 既有数据顺序回放 · 无新飞行、无 SITL、无 Thor</div><h1>地图更准，能否转化为更少测试？</h1>
<p class="lead">在已有历史条件下，灰箱以更少新增结果达到地图指标；优势主要来自初始预测。当前没有建立模型引导选样相对合理廉价选样的独立省预算优势。</p>
<div class="box"><strong>关键结论：</strong>灰箱任务地图准确率从预算0到12次均为94.4%；损高误差由7.44 cm降至5.97 cm。固定4次预算时，面向地图的选择为6.39 cm，随机选择为6.58 cm，风险优先为7.53 cm。完整轨迹重辨识有明显价值，但模型信息量选样与“短断流优先”均在2次测试后达到联合指标。</div>
<h2>预算与评价区如何固定</h2><ul>
<li>共同初始历史：18条 P11 正常/单事件记录＋30条 P13 正常/单事件记录，共48条。AB 结果起初均不可见。灰箱参数只用 P11 正常/单事件轨迹辨识。</li>
<li>对象是6类 AB 组合，每类3次已完成的历史飞行。遍历全部15种“留出2类、从其余4类选测”的划分。两类评价组合在全部预算中始终不揭示，保证同一政策间评价对象一致。</li>
<li>预算为0–12次，每次只揭示一条历史飞行；重复结果按独立打乱次序逐个揭示，不能一次获得三个重复的平均值。主比较使用120种次序；这些回放不增加原始样本量。</li>
<li>所有未测组合的模型预测使用已知 NORMAL 记录提供的初值模板。没有读取未执行候选自身的实际初值，也没有读取 B 前状态。</li>
<li>任务准确率评价固定目标的历史成败。Brier误差评价各组合相对三次历史重复所形成的失败频率。高度误差只在固定完整目标记录上计算；截断高度保留为未知下界。</li>
<li>候选选择和更新不接触目标标签。比较冻结初始预测、原生顺序更新、相同残差更新器、风险排序、面向地图的方差下降和随机次序，分别隔离初始预测、更新、选样的贡献。</li></ul>
<p class="small">真实未来失败概率未由三个重复精确确定。本核验属于回顾性算法比较，研究者此前已熟悉数据。15种留出划分相互重叠，不作为15个独立新实验计算显著性。</p>
<h2>达到同样地图指标需要多少新增测试</h2>
<table><thead><tr><th>方法</th><th>任务准确率≥90%</th><th>损高 MAE≤10 cm</th></tr></thead><tbody><tr><td>灰箱初始预测＋更新</td><td><strong>0</strong></td><td><strong>0</strong></td></tr><tr><td>廉价特征排序＋更新</td><td>12次内未达到</td><td>12次内未达到</td></tr><tr><td>历史查表＋更新</td><td>12次内未达到</td><td>12次内未达到</td></tr></tbody></table>
<p>这些门槛在顺序结果计算前固定。表中次数来自15种留出与回放次序的汇总曲线，不要求每一种留出分别达标。还保留80%准确率、多个Brier门槛、15 cm高度门槛，以及首次达标和此后持续达标两种计数。二次岭回归、加入真实事件持续时间与超时暴露特征的完整树模型、带先验收缩的查表、冻结不更新的对照，以及不同残差核尺度均已核验；没有一个廉价版本在12次内达到90%。</p>
<div class="box caution"><strong>0次的含义：</strong>已有48条历史信息和已辨识模型提供的初始地图已经达到指标。它不表示模型开发和辨识没有成本，也不表示选测器能够在没有评价真值时证明可以停止。达标次数是完整回放后的事后读数。廉价方法耗尽当前12条候选仍未达到门槛，不能把这个结果外推成“再测第13次就能达到”或“稳定节省12次实验”。</div>
<img src="budget-curves.png" alt="固定预算的任务地图准确率、损高校正、先验对照及完整轨迹重辨识曲线">
<h2>初始预测、更新和选择各贡献多少</h2>
<table><thead><tr><th>新增测试</th><th>灰箱任务准确率</th><th>面向地图的高度误差</th><th>随机选择</th><th>风险优先</th></tr></thead><tbody>{''.join(curve_rows)}</tbody></table>
<p><strong>初始预测：</strong>任务准确率94.4%在预算0时已经取得，增加12次结果后没有增加百分点。相对历史查表初始77.8%的任务地图优势，完全在揭示新 AB 结果前出现。原报告使用各案例自身初值；本次统一使用历史 NORMAL 初值模板并输出组合层面均值，所以高度起点为7.44 cm，不能把它与之前8.3 cm的差异算作顺序更新收益。</p>
<p><strong>后续更新：</strong>同一灰箱先验的损高误差从7.44降到5.97 cm，增益1.47 cm，约19.8%；冻结预测的对照一直停在7.44 cm。失败频率Brier误差由0.01852变为0.01866，略有变差。由此可确认连续输出有校正收益，任务分类没有新增收益。</p>
<p class="small">分类指标存在上限：F4中间隔的三次重复中有一次失败。同一组合统一给出成败判断时，本批18条记录最多命中17条，即94.4%。灰箱起点已经达到这个上限，因此平坦的分类曲线不能单独证明更新无用；连续损高和失败频率误差仍保留改善空间。</p>
<p><strong>选样顺序：</strong>固定4次预算，面向地图的选择比随机平均好0.18 cm；15种重叠留出中9种更好、6种更差。风险优先在前几步甚至使高度地图略变差。预算12时，各政策揭示相同候选全集，结果完全一致。这个效果不足以支持强的独立选样收益主张。</p>
<p>查表和直接学习模型的跨组合更新经常伤害未测区域。保留冻结查表和收缩查表后，仍无法达到90%，因此结论不依赖于故意采用一个容易变差的更新器。这里的标签变化具有非单调性：F2短间隔失败，中、长间隔成功；F4两端间隔失败，中间隔多数成功。相邻标签的平滑传播会把这些结构抹掉。</p>
<h2>完整轨迹重辨识：另一项预算核验</h2>
<p>P13未归档完整同步轨迹，因此上面的后续更新明确属于输出地图校正。为检查上轮“共享参数更新”的原方法，又从6条 P11 正常轨迹起步，逐次揭示单条 P11 A/B 完整轨迹；P13全部18条 AB 一直不进入辨识。每一步重拟合同一个灰箱模型。三个策略使用相同更新器，评价地图和阈值也相同。</p>
<table><thead><tr><th>选测策略</th><th>达到90%准确率且≤10 cm</th><th>仅达到≤10 cm</th><th>第一条被揭示记录</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<p>初始损高误差约53.26 cm。加入一条完整单事件轨迹后，信息量选择和简单短断流优先分别降至约5.73、5.71 cm。两者都在第二次揭示后达到联合指标，且一直保持到预算6；廉价风险排序在第五次后达到。更多数据没有使每一个指标单调改善。</p>
<p class="box caution">这一补充采用三条确定的顺序回放，证明完整响应中的辨识信息有价值，同时显示复杂选择的主要收益可被简单规则复制。它不建立随机初值、其他候选池或新平台上的“2次一定够”。初始标量历史与主比较不同，两个预算表不能相加或混为总实验成本。</p>
<h2>如何更新研究判断</h2>
<p>值得保留的能力是：从完整单事件响应辨识共享动力学，再把信息传播到尚未测试的组合。现有数据支持更强的初始组合地图，以及连续输出的有限校正。当前不支持把核心贡献写成普遍更省测试的模型引导选测算法；“简单选样＋灰箱更新”已经复制了主要可验证收益。</p>
<p>预算单位为一次测试结果揭示。不同历史运行的实际时长没有折算进来，因此没有将测试次数换算为 Thor 墙钟时间。整个核验仅使用本地既有数据和模型计算。</p>
<h2>核验与复现</h2>
<p>225条代表顺序均检查了12个唯一测试、评价组合从未被揭示；修改目标标签不改变查询序列或预测；在线灰箱残差更新与批量解一致，在线廉价岭回归与批量重拟合一致；全部预算耗尽后的次序差异最大约{verify['full_budget_order_invariance_max_delta']:.1e}。</p>
<p><a href="protocol.json">预先固定的主协议</a> · <a href="summary.json">门槛与分解汇总</a> · <a href="sequential_results.json">完整预算曲线</a> · <a href="sequential_examples.json">逐步查询记录</a> · <a href="robustness_results.json">补强与敏感性</a> · <a href="semantic_tree_results.json">完整树基线</a> · <a href="trajectory_results.json">共享参数顺序更新</a> · <a href="verification.json">一致性核验</a></p>
<p class="small">主协议冻结后补充的更强基线、核尺度敏感性和高度专用选样单独记录，未根据评价结果挑选一个参数设置替代主结果。原逐案例评分保存于 trajectory_results_realization_metrics.json；最终统一使用组合地图均值口径，预测和参数均未因重评分而改变。</p>
</main></html>'''
(ROOT/'report.html').write_text(html)
conclusion=dict(initial_map_advantage=True,independent_model_guided_query_saving_established=False,warm_start_thresholds='Grey-box:0 additional tests; tested cheap ranking/lookup variants:90% and10cm targets not attained within12 queries.',update_task_accuracy_gain_pp=0.,update_height_gain_cm=(arr('greybox_gp','map_variance','height_MAE')[0]-arr('greybox_gp','map_variance','height_MAE')[-1])*100,map_vs_random_gain_at4_cm=(arr('greybox_gp','random','height_MAE')[4]-arr('greybox_gp','map_variance','height_MAE')[4])*100,cold_start_joint_threshold_tests=dict(predicted_information=2,cheap_risk=5,short_duration_first=2),new_physical_experiments=0,thor_used=False)
(ROOT/'conclusion.json').write_text(json.dumps(conclusion,ensure_ascii=False,indent=2));print(conclusion)

from pathlib import Path
import json,html,hashlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parent
p=json.load(open(ROOT/'p8_audit.json'));c=json.load(open(ROOT/'cycle_audit.json'));a=json.load(open(ROOT/'anchor_response.json'))
fig,axs=plt.subplots(1,2,figsize=(11,4),layout='constrained')
for condition,color,label in [('q4-D0.38-g0.5-A0','#c94736','D=0.38s, gap=0.50s, A0'),('q4-D0.3-g0.5-A45','#177d75','D=0.30s, gap=0.50s, A45')]:
 r=next(x for x in c['rows'] if x['condition']==condition)
 axs[0].plot(range(1,5),[v['height_loss'] for v in r['captures']],'-o',c=color,label=label)
axs[0].axhline(1,c='#888888',ls='--',label='Task loss threshold')
axs[0].plot(range(1,5),[0]*4,':',c='#20242b',lw=2,label='Local vertical error after every capture')
axs[0].set(xlabel='Capture number',ylabel='Height loss / local error (m)',xticks=range(1,5));axs[0].legend(fontsize=8)
selected=[x for x in a['events'] if x['task_relative_down_error']>.1]
axs[1].scatter([x['task_relative_down_error'] for x in selected],[100*x['collective_command_change'] for x in selected],c='#3e61a1',s=40)
axs[1].set_xlabel('Task-relative downward error (m)');axs[1].set_ylabel('Mean motor command increase (percentage points)');axs[1].set_ylim(0,10);axs[1].set_title('One-call source intervention',fontsize=11)
for ax in axs:ax.grid(alpha=.18)
fig.savefig(ROOT/'evidence.png',dpi=180);fig.savefig(ROOT/'evidence.svg');plt.close(fig)
rows=''.join(f"<tr><td>{x['sut']}</td><td>{x['holdout']}</td>"+''.join(f"<td>{x['metrics'][k]['accuracy']:.1%}</td>" for k in ['summary','bag','ordered'])+'</tr>' for x in p['aggregates'])
doc=f'''<!doctype html><html lang="zh"><meta charset="utf-8"><title>研究问题再核验 · 2026-10-28</title><style>body{{font-family:system-ui,sans-serif;max-width:1100px;margin:48px auto;padding:0 24px;line-height:1.7;color:#202832}}h1{{font-size:30px}}h2{{font-size:22px;margin-top:32px}}.status{{background:#fff3d4;border-left:4px solid #b98718;padding:16px}}table{{border-collapse:collapse;width:100%}}td,th{{padding:9px;border-bottom:1px solid #dce1e5;text-align:left}}img{{width:100%}}small{{color:#596671}}a{{color:#235a8f}}</style>
<h1>研究问题再核验</h1><p>2026-10-28 · 既有 P5/P7/P8/P11 记录 · 本地计算 · 无新飞行、无 SITL、无 Thor</p>
<p class="status"><b>当前尚未证明新方法优势。</b>新证据支持进一步核验“目标重置造成累计误差被反复清零”的机制。循环漂移方法仍需与完整信息灰箱、周期模板搜索和廉价漂移外推比较。</p>
<h2>扩大到900条记录后，廉价基线仍须认真对待</h2><p>900次运行对应767个不同计划输入；125组重复输入共258次运行，其中7组出现任务成败翻转。以下是固定 ExtraTrees 模型的回顾性整类留出；测试集出现的重复输入从训练集删除。summary使用时长汇总，bag保留无序时长，ordered保留顺序。数值为准确率，未将此表解释为新方法收益。</p><table><tr><th>接入层</th><th>留出类别</th><th>汇总</th><th>无序</th><th>顺序</th></tr>{rows}</table>
<h2>目标重置与累计掉高</h2><p>P7的27条四次断流轨迹包含108次捕获，垂直位置误差在每次捕获后均精确归零。其中27次已经掉高超过0.5米，5次超过1米。11条轨迹超过高度损失门槛，其中10条全程最大倾角低于45°。</p><img src="evidence.png" alt="捕获时累计掉高与局部误差，以及冻结网络对高度目标的指令响应">
<p>左图红线末两段增加0.326、0.340米，提示持续漂移结构；绿线在误差饱和后开始恢复，反驳“饱和就会持续漂移”。仅有相似峰值或相同事件顺序，不能证明动态状态已形成可重复循环。</p>
<p>右图来自P11的精确单次网络调用干预：保留同一实测物理状态、GRU与动作历史，仅将高度目标恢复为最后有效外部高度。10个已掉高超过10厘米的捕获点全部增加平均电机指令，平均8.11个百分点；原调用最大复现误差5.77×10⁻⁷。该结果证明指令因果效应，飞行后果尚未实测。</p>
<h2>待核验的核心方法</h2><p>搜索能够重复出现、每轮都增加任务损失的事件循环。模型估计一轮后的动态状态与净损失；源码分析检查目标重置和观测截断何时使更多掉高不再改变控制器输入。只有循环状态闭合、截断分支持续有效、故障与路径预算允许时，才把一轮结果推广到重复次数这一整族地图。</p>
<p>理论候选是固定任务参考下，由重置和截断共同产生的单向平移不变性及其循环推广条件。Poincaré返回映射、相对周期轨道和局部收缩已有成熟研究，不能直接作为创新。精确条件命题及未解决条件见 <a href="candidate.json">候选方法与完成审计</a>。</p>
<h2>继续核验后的反证与理论重合</h2><p>仅使用第三次捕获以前的数据，27条轨迹中有3条的第二轮外部高度误差全程处于向下饱和分支。这3条中，下一轮继续掉高的有2条，平均增量0.156米；直接按上一轮掉高排序取前三，3条全部继续掉高，平均增量0.325米。该检查说明饱和条件单独使用没有改善选择。它假设所有前缀已经可用，属于回顾性的续接选择压力检查，不能当作总飞行预算比较，也没有评估尚未实现的完整循环闭合算法。<a href="source_regime_audit.json">逐条结果</a></p>
<p><a href="https://arxiv.org/abs/2006.09485">混合系统对称性抽象</a>已经研究守卫、重置与可达集的变换复用；<a href="https://orbi.uliege.be/handle/2268/173234">混合变换循环加速</a>已经研究重复控制循环的无界效应。当前候选与这些工作直接相关。移动轨迹还要求外部参考路径及全部时钟在相应变换下闭合，这些条件尚未得到现有导出数据支持。当前保留机制发现，尚未获得独立理论或算法优势。</p>
<h2>当前证据的限制</h2><p>四次捕获只提供三段完整循环；P7导出缺少完整姿态、角速度、GRU、执行器与时钟缓存，无法验证完整状态复现。用第二段增量线性推算第四次捕获的误差仍为11.23厘米，尚未胜过强灰箱。切换和第二平台的优势没有证据，固定捕获修复C在P9已有9/9成功也必须保留为基线。</p>
<p><a href="p8_audit.json">P8全部结果</a> · <a href="cycle_audit.json">27条循环核验</a> · <a href="anchor_response.json">P11指令干预</a></p></html>'''
(ROOT/'report.html').write_text(doc)
files={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ROOT.rglob('*')) if p.is_file() and p.name!='manifest.json' and '__pycache__' not in p.parts}
(ROOT/'manifest.json').write_text(json.dumps(dict(source_repository='JacksonW1025/uav_handover',source_ref='d0f3924c762e7fbaf5d799ae582a5b59ebb578f0',files=files),indent=2))
print('report',ROOT/'report.html','files',len(files))

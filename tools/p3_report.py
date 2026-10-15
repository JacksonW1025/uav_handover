#!/usr/bin/env python3
"""P3 report figures and tables from one finished, audited P3 batch (reads batch-audit.json, p3-metrics.json and
p3-memory.json; edits no run). All panels draw runs of that batch only.
"""
import argparse,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
# Categorical slots in fixed order N0, N3, N2, N2s (validated with the dataviz palette validator, light mode;
# N0/N2/N2s keep their P2 colors); baseline neutral gray.
TREAT=['N0','N3','N2','N2s'];CONDS=['D1','D2','D3']
COLOR={'N0':'#2a78d6','N3':'#eb6834','N2':'#1baf7a','N2s':'#008300','B':'#8a8984'}
NAME={'N0':'N0 reset','N3':'N3 old memory (held)','N2':'N2 teacher forcing','N2s':'N2s shadow memory','B':'RAPTOR continuous hover'}
COND={'D1':'D1 0.3 s hover','D2':'D2 10 s hover','D3':'D3 10 s, 3 m + 90° yaw'}
INK='#0b0b0b';MUTED='#52514e';GRID='#e4e3df'
plt.rcParams.update({'font.size':9,'axes.edgecolor':MUTED,'axes.labelcolor':INK,'xtick.color':MUTED,'ytick.color':MUTED,
    'axes.grid':True,'grid.color':GRID,'grid.linewidth':.6,'axes.spines.top':False,'axes.spines.right':False,'lines.linewidth':1.6,'font.family':'DejaVu Sans'})

def load(batch):
    batch=(ROOT/batch).resolve();audit=json.loads((batch/'batch-audit.json').read_text())
    res={r['id']:r for r in json.loads((batch/'results.json').read_text())['runs']};runs=[]
    for r in audit['runs']:
        d=ROOT/res[r['id']]['directory']
        runs.append({**r,'m':json.loads((d/'p3-metrics.json').read_text()),'mem':json.loads((d/'p3-memory.json').read_text())})
    return batch.name,audit,runs

def group(runs,cond,treat):return [r for r in runs if r['condition']==cond and r['treatment']==treat]

def fig_motors(label,audit,runs,out):
    base=group(runs,'R','B');fig,axes=plt.subplots(3,4,figsize=(13,8),sharex=True,sharey=True)
    for i,c in enumerate(CONDS):
        for j,t in enumerate(TREAT):
            ax=axes[i,j]
            for r in base:e=r['m']['events']['baseline_recapture']['curves'];ax.plot(e['motor_t_s'],np.mean(e['motor'],1),color=COLOR['B'],lw=1.1)
            for r in group(runs,c,t):e=r['m']['events']['second_C_to_N']['curves'];ax.plot(e['motor_t_s'],np.mean(e['motor'],1),color=COLOR[t],lw=1.4)
            g=audit['summary']['second_C_to_N'].get(f'{c}:{t}',{});st=g.get('motor_step_at_change')
            ax.text(.97,.93,f"step {st['mean']:.3f} (n={st['n']})" if st else '',transform=ax.transAxes,color=MUTED,fontsize=8,ha='right')
            ax.axvline(0,color=MUTED,lw=.8,ls=':');ax.set_xlim(-.1,.5)
            if i==0:ax.set_title(NAME[t],color=INK,fontsize=9)
            if j==0:ax.set_ylabel(f'{COND[c]}\nmean motor [0,1]')
    for ax in axes[-1]:ax.set_xlabel('time from second C→N owner change [s]')
    fig.suptitle(f'Second C→N: mean of four motor commands (colored: treatment runs; gray: RAPTOR continuous hover re-capture; {label})',color=INK)
    fig.tight_layout();fig.savefig(out/'p3-fig1-second-motors.png',dpi=130);plt.close(fig)

def fig_metrics(label,audit,runs,out):
    specs=[('motor_step_at_change','motor step at change'),('motor_rms_vs_baseline','motor RMS vs baseline, 0–0.5 s'),('max_altitude_loss_m','max altitude loss [m]')]
    fig,axes=plt.subplots(1,3,figsize=(14,4))
    b=audit['summary']['baseline_recapture'].get('R:B',{})
    for ax,(k,yl) in zip(axes,specs):
        x=0;ticks=[];names=[]
        for c in CONDS:
            for t in TREAT:
                vals=[r['events']['second_C_to_N'].get(k) for r in group(audit['runs'],c,t)];vals=[v for v in vals if v is not None]
                xs=x+np.linspace(-.15,.15,len(vals)) if len(vals)>1 else [x]*len(vals)
                ax.scatter(xs,vals,s=30,color=COLOR[t],edgecolor='white',linewidth=1,zorder=3)
                if vals:ax.plot([x-.25,x+.25],[np.mean(vals)]*2,color=INK,lw=1)
                ticks.append(x);names.append(t);x+=1
            x+=.6
        if b.get(k):ax.axhspan(b[k]['min'],b[k]['max'],color=COLOR['B'],alpha=.25,lw=0)
        ax.set_xticks(ticks);ax.set_xticklabels(names,fontsize=7);ax.set_ylabel(yl);ax.set_ylim(bottom=0)
        for i,c in enumerate(CONDS):ax.text(i*4.6+1.5,1.0,c,transform=ax.get_xaxis_transform(),ha='center',va='bottom',color=INK,fontsize=9)
    fig.suptitle(f'Second C→N by deactivation condition: each dot one run, bar = mean, gray band = baseline re-capture range ({label})',color=INK,y=1.04)
    fig.tight_layout();fig.savefig(out/'p3-fig2-second-metrics.png',dpi=130,bbox_inches='tight');plt.close(fig)

def fig_gru(label,audit,runs,out):
    offs=[float(o) for o in json.loads((ROOT/audit['config']).read_text())['p3']['gru_distance_offsets_s']]
    fig,axes=plt.subplots(1,3,figsize=(13,3.8),sharey=True)
    for ax,c in zip(axes,CONDS):
        for t in TREAT:
            rows=[r['events']['second_C_to_N'].get('gru_distance_to_baseline') for r in group(audit['runs'],c,t)];rows=[x for x in rows if x]
            if rows:ax.plot(offs,[np.mean([x[str(o)] for x in rows]) for o in offs],marker='o',ms=5,color=COLOR[t],label=NAME[t])
        base=[r['events']['baseline_recapture'].get('gru_distance_to_baseline') for r in group(audit['runs'],'R','B')];base=[x for x in base if x]
        if base:ax.plot(offs,[np.mean([x[str(o)] for x in base]) for o in offs],marker='o',ms=5,color=COLOR['B'],label='baseline (leave-one-out)')
        ax.set_xscale('symlog',linthresh=.1);ax.set_xticks(offs);ax.set_xticklabels([f'{o:g}' for o in offs]);ax.set_title(COND[c],color=INK);ax.set_xlabel('time after second C→N [s]')
    axes[0].set_ylabel('GRU distance to baseline mean');axes[0].legend(fontsize=7,frameon=False)
    fig.suptitle(f'GRU after the second C→N: distance to the RAPTOR baseline at the same time after its re-capture (group means; {label})',color=INK,y=1.03)
    fig.tight_layout();fig.savefig(out/'p3-fig3-gru-distance.png',dpi=130,bbox_inches='tight');plt.close(fig)

def fig_deactivation(label,runs,out):
    fig,axes=plt.subplots(1,3,figsize=(13,3.8),sharey=True)
    for ax,c in zip(axes,CONDS):
        for t in TREAT:
            for k,r in enumerate(group(runs,c,t)):
                d=r['m'].get('deactivation_memory')
                if d:ax.plot(d['t_s'],d['distance_curve'],color=COLOR[t],lw=1.1,label=NAME[t] if k==0 else None)
        ax.set_title(COND[c],color=INK);ax.set_xlabel('time after N→C [s]')
    axes[0].set_ylabel('shadow GRU distance to the stored exit memory');axes[0].legend(fontsize=7,frameon=False)
    fig.suptitle(f'Deactivation: how far the inactive shadow GRU moves from the memory N3 restores (one line per run; {label})',color=INK,y=1.03)
    fig.tight_layout();fig.savefig(out/'p3-fig4-deactivation-memory.png',dpi=130,bbox_inches='tight');plt.close(fig)

def fig_memory(label,runs,out,threshold):
    fig,axes=plt.subplots(1,3,figsize=(13,3.8),sharey=True)
    panels=[('raptor_hover','zero (reset)','RAPTOR hover inputs, replay from zero'),('teacher_forced_deactivation','zero (reset)','teacher-forced deactivation (N2), replay from zero'),
            ('second_entry_counterfactual',None,'second C→N inputs, replay from other memories')]
    for ax,(seg,init,title) in zip(axes,panels):
        for r in runs:
            for s in r['mem'].get('segments',[]):
                if s['segment']!=seg or (init and s['initial']!=init):continue
                if not len(s['distance_curve']) or s['distance_curve'][0]<1e-5:continue  # counterfactual equal to the logged memory
                color=COLOR['B'] if init else {'zero (N0)':COLOR['N0'],'exit memory (N3)':COLOR['N3']}.get(s['initial'],COLOR['N2s'])
                ax.plot(np.arange(1,len(s['distance_curve'])+1),s['distance_curve'],color=color,lw=.9,alpha=.7)
        ax.axhline(threshold,color=INK,lw=.8,ls='--');ax.set_yscale('log');ax.set_title(title,color=INK,fontsize=9);ax.set_xlabel('native steps after replay start (8 ms)')
    axes[0].set_ylabel('distance to logged full-history GRU')
    from matplotlib.lines import Line2D
    for ax in axes:ax.set_ylim(1e-3,3)
    axes[2].legend([Line2D([],[],color=COLOR[t]) for t in ['N0','N3','N2s']],['from zero (N0)','from exit memory (N3)','from shadow memory at entry'],fontsize=7,frameon=False)
    fig.suptitle(f'GRU memory length in SITL: exact policy replay on logged inputs (dashed: {threshold}; {label})',color=INK,y=1.03)
    fig.tight_layout();fig.savefig(out/'p3-fig5-memory-length.png',dpi=130,bbox_inches='tight');plt.close(fig)

def fmt(s,d=3):return f"{s['mean']:.{d}f} [{s['min']:.{d}f}, {s['max']:.{d}f}]" if s else '—'
def table(audit):
    S=audit['summary'];E=audit['elimination_ratios'];L=[]
    L.append('### 第二次 C→N（均值 [范围]）\n\n| 停用 | 处理 | n | 电机阶跃 | 消除 | 0.5 s RMS 偏离 | 消除 | 最大高度损失 m | 消除 | 恢复(变化) s | 最大倾角 ° | GRU 距离 @0 / 0.1 / 0.25 s | 实际停用 s |\n|---|---|---:|---|---:|---|---:|---|---:|---|---:|---|---|')
    for c in CONDS:
        for t in TREAT:
            g=S['second_C_to_N'].get(f'{c}:{t}')
            if not g:continue
            e=E.get(f'{c}:{t}',{});ratio=lambda k:f"{e[k]['ratio']*100:.0f}%" if k in e and e[k]['ratio'] is not None else '—'
            gd=g.get('gru_distance_to_baseline',{});gs=' / '.join(f"{gd[o]['mean']:.3f}" if o in gd else '—' for o in ['0.0','0.1','0.25'])
            L.append(f"| {c} | {t} | {g['runs']} | {fmt(g['motor_step_at_change'])} | {ratio('motor_step_at_change')} | {fmt(g['motor_rms_vs_baseline'],4)} | {ratio('motor_rms_vs_baseline')} | {fmt(g['max_altitude_loss_m'])} | {ratio('max_altitude_loss_m')} | {fmt(g['recovery_from_change_s'],2)} | {g['max_tilt_deg']['mean']:.1f} | {gs} | {fmt(g['deactivation_actual_s'],3)} |")
    b=S['baseline_recapture'].get('R:B')
    if b:
        gd=b.get('gru_distance_to_baseline',{});gs=' / '.join(f"{gd[o]['mean']:.3f}" if o in gd else '—' for o in ['0.0','0.1','0.25'])
        L.append(f"| R | 基线 | {b['runs']} | {fmt(b['motor_step_at_change'])} | | {fmt(b['motor_rms_vs_baseline'],4)} | | {fmt(b['max_altitude_loss_m'])} | | {fmt(b['recovery_from_change_s'],2)} | {b['max_tilt_deg']['mean']:.1f} | {gs} | — |")
    L.append('\n### N→C（C0，经典 OFFBOARD 原地接管）\n\n| 停用 | 处理 | n | 电机阶跃 | RMS 偏离（相对经典保持） | 最大高度损失 m | 恢复(变化) s | 最大倾角 ° |\n|---|---|---:|---|---|---|---|---:|')
    for c in CONDS:
        for t in TREAT:
            g=S['N_to_C'].get(f'{c}:{t}')
            if g:L.append(f"| {c} | {t} | {g['runs']} | {fmt(g['motor_step_at_change'])} | {fmt(g['motor_rms_vs_classic_hold'],4)} | {fmt(g['max_altitude_loss_m'])} | {fmt(g['recovery_from_change_s'],2) if g['recovery_from_change_s'] else '不判（0.3 s）'} | {g['max_tilt_deg']['mean']:.1f} |")
    f=S['first_C_to_N_pooled']
    L.append(f"\n### 第一次 C→N（全部 N0，含基线）\n\nn={f['runs']}：电机阶跃 {fmt(f['motor_step_at_change'])}，RMS 偏离 {fmt(f['motor_rms_vs_baseline'],4)}，高度损失 {fmt(f['max_altitude_loss_m'])} m，恢复 {fmt(f['recovery_from_change_s'],2)} s，GRU 距离 @0 {fmt(f['gru_distance_to_baseline']['0.0'])}、@0.25 s {fmt(f['gru_distance_to_baseline']['0.25'])}。")
    L.append('\n### 记忆长度（精确回放；保持在阈值内所需原生步数）\n\n| 片段 | 初始记忆 | 案例 | 未达到 | 步数 均值 [范围] | 秒 均值 |\n|---|---|---:|---:|---|---|')
    for k,v in audit['memory_length'].items():
        seg,init,*rest=k.split('|');name=seg+((' '+rest[0]) if rest else '')
        L.append(f"| {name} | {init} | {v['cases']} | {v['not_reached']} | {fmt(v['steps'],1)} | {v['seconds']['mean']:.3f} |" if v['steps'] else f"| {name} | {init} | {v['cases']} | {v['not_reached']} | — | — |")
    return '\n'.join(L)+'\n'

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('batch');p.add_argument('--out',default='docs/figures/p3');a=p.parse_args()
    out=ROOT/a.out;out.mkdir(parents=True,exist_ok=True);label,audit,runs=load(a.batch)
    cfg=json.loads((ROOT/audit['config']).read_text())
    fig_motors(label,audit,runs,out);fig_metrics(label,audit,runs,out);fig_gru(label,audit,runs,out);fig_deactivation(label,runs,out)
    fig_memory(label,runs,out,cfg['p3']['memory_length']['threshold'])
    (ROOT/a.batch/'p3-table.md').write_text(table(audit));print('figures',out,'table',ROOT/a.batch/'p3-table.md')
if __name__=='__main__':main()

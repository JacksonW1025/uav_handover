#!/usr/bin/env python3
"""P2 report figures and tables from finished, audited P2 batches (reads p2-metrics.json and batch-audit.json; edits no run).

Every panel draws runs of one batch only (no splicing across batches); the batch is named in the panel title.
"""
import argparse,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
# Categorical slots 1-7 (validated with the dataviz palette validator, light mode), fixed per treatment; baseline neutral gray.
COLOR={'N0':'#2a78d6','N1':'#eb6834','N2':'#1baf7a','Nstar':'#eda100','N2g':'#e87ba4','N2s':'#008300','C0':'#2a78d6','C2':'#6250d6','B':'#8a8984'}
NAME={'N0':'N0 original reset','N1':'N1 classic prev. action','N2':'N2 teacher GRU + classic prev.','Nstar':'N★ baseline memory',
      'N2g':'N2g teacher GRU','N2s':'N2s shadow memory','C0':'C0 original','C2':'C2 integrator coordinated','B':'same-controller baseline'}
INK='#0b0b0b';MUTED='#52514e';GRID='#e4e3df'
plt.rcParams.update({'font.size':9,'axes.edgecolor':MUTED,'axes.labelcolor':INK,'xtick.color':MUTED,'ytick.color':MUTED,
    'axes.grid':True,'grid.color':GRID,'grid.linewidth':.6,'axes.spines.top':False,'axes.spines.right':False,'lines.linewidth':1.6,
    'font.family':'DejaVu Sans'})

def load(batch):
    batch=(ROOT/batch).resolve();audit=json.loads((batch/'batch-audit.json').read_text())
    res={r['id']:r for r in json.loads((batch/'results.json').read_text())['runs']};runs=[]
    for r in audit['runs']:
        f=ROOT/res[r['id']]['directory']/'p2-metrics.json'
        if f.exists():runs.append({**r,'m':json.loads(f.read_text())})
    return batch.name,audit,runs

def group(runs,kind,cond,treat):return [r for r in runs if r['kind']==kind and r['condition']==cond and r['treatment']==treat]

def fig_motor_traces(batches,out,cond='S1',name='p2-fig1-s1-motors.png'):
    """Mean of the four motor commands around the change, per run (colored) and baseline runs (gray), one panel per treatment."""
    panels=[(b,t) for b,(label,audit,runs) in batches.items() for t in ['N0','N1','N2g','N2','N2s','Nstar'] if group(runs,'p2_c_to_n',cond,t)]
    cols=3;rows=(len(panels)+cols-1)//cols
    fig,axes=plt.subplots(rows,cols,figsize=(12,3.1*rows),sharex=True,sharey=True,squeeze=False)
    for ax,(b,t) in zip(axes.flat,panels):
        label,audit,runs=batches[b]
        for r in group(runs,'p2_baseline_raptor',cond,'B'):
            c=r['m']['curves'];ax.plot(c['motor_t_s'],np.mean(c['motor'],1),color=COLOR['B'],lw=1.2,alpha=.9)
        for r in group(runs,'p2_c_to_n',cond,t):
            c=r['m']['curves'];ax.plot(c['motor_t_s'],np.mean(c['motor'],1),color=COLOR[t],lw=1.4)
        g=audit['summary'].get(f'p2_c_to_n:{cond}:{t}',{})
        ax.set_title(f"{NAME[t]}  ({label})",color=INK,fontsize=9)
        st=g.get('motor_step_at_change');ax.text(.02,.04,f"step at change {st['mean']:.3f} (n={st['n']})" if st else '',transform=ax.transAxes,color=MUTED,fontsize=8)
        ax.axvline(0,color=MUTED,lw=.8,ls=':');ax.set_xlim(-.1,.5)
    for ax in axes.flat[len(panels):]:ax.set_visible(False)
    for ax in axes[:,0]:ax.set_ylabel('mean motor command [0,1]')
    for ax in axes[-1]:ax.set_xlabel('time from owner change [s]')
    fig.suptitle(f'{cond}: mean of four motor commands around C→N (colored: treatment runs; gray: RAPTOR baseline runs, same batch)',color=INK)
    fig.tight_layout();fig.savefig(out/name,dpi=130);plt.close(fig)

def dots(ax,items,metric,ylabel):
    for x,(label,runs,t) in enumerate(items):
        vals=[metric(r) for r in runs];vals=[v for v in vals if v is not None]
        xs=x+np.linspace(-.15,.15,len(vals)) if len(vals)>1 else [x]*len(vals)
        ax.scatter(xs,vals,s=30,color=COLOR[t],edgecolor='white',linewidth=1,zorder=3)
        if vals:ax.plot([x-.25,x+.25],[np.mean(vals)]*2,color=INK,lw=1)
    ax.set_xticks(range(len(items)));ax.set_xticklabels([l for l,_,_ in items],fontsize=8);ax.set_ylabel(ylabel);ax.set_ylim(bottom=0)

def fig_metrics(batches,out,cond,kind,treatments,name,baseline_kind):
    items=[]
    for b,(label,audit,runs) in batches.items():
        for t in treatments:
            g=group(runs,kind,cond,t)
            if g:items.append((f'{t}\n{label[-3:]}',g,t))
        base=group(runs,baseline_kind,cond,'B')
        if base:items.append((f'B\n{label[-3:]}',base,'B'))
    fig,axes=plt.subplots(1,3,figsize=(13,3.8))
    dots(axes[0],items,lambda r:r['m']['auxiliary']['motor']['step_at_change'],'motor step at change')
    dots(axes[1],items,lambda r:r['m']['primary']['max_altitude_loss_m'],'max altitude loss [m]')
    dots(axes[2],items,lambda r:(r.get('vs_baseline') or {}).get('motor_rms_vs_baseline_0_0p5s'),'motor RMS vs baseline, 0–0.5 s')
    fig.suptitle(f'{cond} {"C→N" if kind=="p2_c_to_n" else "N→C"}: each dot one run, bar = mean; label suffix = batch',color=INK,y=1.02)
    fig.tight_layout();fig.savefig(out/name,dpi=130,bbox_inches='tight');plt.close(fig)

def fig_gru(batches,out,cond,name):
    fig,ax=plt.subplots(figsize=(8,4))
    for b,(label,audit,runs) in batches.items():
        base=group(runs,'p2_baseline_raptor',cond,'B')
        if not base:continue
        # Baseline mean GRU over [0, 0.5) s after its change is the reference (stationary for S1).
        ref=np.mean([np.mean(np.asarray(r['m']['gru_curves']['gru'])[(np.asarray(r['m']['gru_curves']['t_s'])>=0)&(np.asarray(r['m']['gru_curves']['t_s'])<.5)],0) for r in base],0)
        for t in ['N0','N1','N2g','N2','N2s','Nstar']:
            for i,r in enumerate(group(runs,'p2_c_to_n',cond,t)):
                c=r['m']['gru_curves'];ts=np.asarray(c['t_s']);g=np.asarray(c['gru']);w=ts>=0
                ax.plot(ts[w],np.linalg.norm(g[w]-ref,axis=1),color=COLOR[t],lw=1,alpha=.8,label=f'{NAME[t]} ({label[-3:]})' if i==0 else None)
    ax.set_xlim(0,2);ax.set_ylim(bottom=0);ax.set_xlabel('time from owner change [s]');ax.set_ylabel('‖GRU − baseline mean‖')
    ax.legend(frameon=False,fontsize=7);ax.set_title(f'{cond}: GRU distance to the in-batch RAPTOR baseline after C→N',color=INK,fontsize=9)
    fig.tight_layout();fig.savefig(out/name,dpi=130);plt.close(fig)

def fig_curves(batches,out,cond,kind,treatments,baseline_kind,name):
    fig,axes=plt.subplots(1,3,figsize=(13,3.8),sharex=True)
    for b,(label,audit,runs) in batches.items():
        for t in treatments+['B']:
            rs=group(runs,kind if t!='B' else baseline_kind,cond,t)
            if not rs:continue
            c=rs[0]['m']['curves'];ts=np.asarray(c['t_s']);p=np.asarray(c['position_ned_m']);v=np.asarray(c['velocity_ned_m_s'])
            ls='--' if t=='B' else '-'
            axes[0].plot(ts,v[:,0],color=COLOR[t],ls=ls,label=f'{NAME[t]} (rep 1)');axes[1].plot(ts,-p[:,2],color=COLOR[t],ls=ls)
            axes[2].plot(np.asarray(c['motor_t_s']),np.mean(c['motor'],1),color=COLOR[t],ls=ls,lw=1.1)
    axes[0].set_ylabel('north velocity [m/s]');axes[1].set_ylabel('altitude [m]');axes[2].set_ylabel('mean motor command')
    for a in axes:a.axvline(0,color=MUTED,lw=.8,ls=':');a.set_xlabel('time from change [s]')
    axes[0].set_xlim(-1,3);axes[0].legend(frameon=False,fontsize=7)
    fig.suptitle(f'{cond}: typical runs (repetition 1); dashed = same-controller baseline',color=INK,y=1.02)
    fig.tight_layout();fig.savefig(out/name,dpi=130,bbox_inches='tight');plt.close(fig)

def ecolor(kind,t):
    # N->C shares no colour with C->N N0 in the exploration figure (C2 is absent there).
    return COLOR['C2'] if kind=='p2_n_to_c' else COLOR[t]

def fig_exploration(label,audit,runs,out,name='p2-fig6-exploration.png'):
    levels=sorted({r['condition'] for r in runs},key=lambda c:float(c[1:]))
    specs=[('p2_c_to_n','N0'),('p2_baseline_raptor','B'),('p2_n_to_c','C0')]+sorted({('p2_c_to_n',r['treatment']) for r in runs if r['kind']=='p2_c_to_n' and r['treatment']!='N0'})
    metrics=[(lambda r:r['m']['primary']['window_constraints']['tilt_safety_deg']['max'],'max tilt [°]',45),
             (lambda r:r['m']['primary']['max_altitude_loss_m'],'max altitude loss [m]',None),
             (lambda r:r['m']['auxiliary']['motor']['step_at_change'],'motor step at change',None),
             (lambda r:r['m']['primary']['window_constraints']['angular_rate_component_rad_s']['max'],'max angular rate [rad/s]',8)]
    fig,axes=plt.subplots(1,4,figsize=(15,3.8))
    for ax,(f,yl,limit) in zip(axes,metrics):
        for k,(kind,t) in enumerate(specs):
            for r in runs:
                if r['kind']==kind and r['treatment']==t:
                    x=levels.index(r['condition'])+(k-1.5)*.12;fail=r['m']['flight_outcome']['outcome']=='FAILURE'
                    ax.scatter([x],[f(r)],s=36,color=ecolor(kind,t),marker='X' if fail else 'o',edgecolor='white',linewidth=.8,zorder=3)
        if limit:ax.axhline(limit,color=MUTED,lw=.8,ls='--');ax.text(len(levels)-.6,limit,'safety limit',color=MUTED,fontsize=7,va='bottom',ha='right')
        ax.set_xticks(range(len(levels)));ax.set_xticklabels([l[1:]+' m/s' for l in levels]);ax.set_ylabel(yl);ax.set_ylim(bottom=0);ax.set_xlim(-.5,len(levels)-.5)
    for kind,t in specs:axes[0].scatter([],[],color=ecolor(kind,t),label=('N→C ' if kind=='p2_n_to_c' else ('RAPTOR own brake' if t=='B' else 'C→N '))+(t if t!='B' else ''))
    axes[0].scatter([],[],marker='X',color=MUTED,label='flight failure');axes[0].legend(frameon=False,fontsize=7,loc='lower right')
    fig.suptitle(f'Exploration ({label}): each mark one run; X = pre-registered flight failure (aborted runs measured up to the abort)',color=INK,y=1.02)
    fig.tight_layout();fig.savefig(out/name,dpi=130,bbox_inches='tight');plt.close(fig)

def table(label,audit,runs):
    f=lambda v,d=3:'—' if v is None else f'{v:.{d}f}'
    lines=['|运行|处理|交接时速度 m/s|电机阶跃|0.5 s RMS 偏离|最大高度损失 m|最大倾角 °|恢复(变化) s|写入/协调核对|捕获|最大年龄 ms|飞行结果|',
           '|---|---|---:|---:|---:|---:|---:|---:|---|---|---:|---|']
    for r in runs:
        m=r['m'];p=r.get('p1') or {};fo=m.get('flight_outcome') or {}
        check=(m.get('entry') or {}).get('status') or (m.get('coordination') or {}).get('status') or '—'
        lines.append(f"|{r['id']}|{r['treatment']}|{f(p.get('speed_at_change_m_s'),2)}|{f(p.get('motor_step_at_change'))}|{f((r.get('vs_baseline') or {}).get('motor_rms_vs_baseline_0_0p5s'))}|"
            f"{f(p.get('max_altitude_loss_m'))}|{f(m['primary']['window_constraints']['tilt_safety_deg']['max'],1)}|{f(p.get('recovery_from_change_s'),2)}|{check}|"
            f"{p.get('reference_classification')}|{f((r.get('output_chain_counts') or {}).get('max_applied_age_us',0)/1e3,0)}|{fo.get('outcome')}{' '+','.join(fo['reasons']) if fo.get('reasons') else ''}|")
    return f'批次 {label}\n\n'+'\n'.join(lines)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--s1',nargs='+',default=[]);p.add_argument('--s3',nargs='+',default=[])
    p.add_argument('--nc',nargs='+',default=[]);p.add_argument('--explore');p.add_argument('--figures',type=Path,default=ROOT/'docs/figures/p2');a=p.parse_args()
    a.figures.mkdir(parents=True,exist_ok=True)
    s1={b:load(b) for b in a.s1};s3={b:load(b) for b in a.s3};nc={b:load(b) for b in a.nc}
    if s1:
        fig_motor_traces(s1,a.figures);fig_metrics(s1,a.figures,'S1','p2_c_to_n',['N0','N1','N2g','N2','N2s','Nstar'],'p2-fig2-s1-metrics.png','p2_baseline_raptor')
        fig_gru(s1,a.figures,'S1','p2-fig3-s1-gru.png')
    if s3:
        fig_metrics(s3,a.figures,'S3','p2_c_to_n',['N0','N1','N2','N2g'],'p2-fig4-s3-metrics.png','p2_baseline_raptor')
        fig_curves(s3,a.figures,'S3','p2_c_to_n',['N0','N1','N2','N2g'],'p2_baseline_raptor','p2-fig4b-s3-curves.png')
        fig_motor_traces(s3,a.figures,'S3','p2-fig4c-s3-motors.png')
    if nc:fig_metrics(nc,a.figures,'S3','p2_n_to_c',['C0','C2'],'p2-fig5-nc-metrics.png','p2_baseline_classic')
    allb={**s1,**s3,**nc}
    if a.explore:
        ex=load(a.explore);fig_exploration(*ex,a.figures);allb[a.explore]=ex
    for b,(label,audit,runs) in allb.items():(ROOT/b/'p2-table.md').write_text(table(label,audit,runs)+'\n')
    print('figures',sorted(x.name for x in a.figures.iterdir()))

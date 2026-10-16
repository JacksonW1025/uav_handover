#!/usr/bin/env python3
"""P4-01c report figures and table from a finished, audited batch (reads batch-audit.json and the stored per-run
p4c-metrics.json; edits no run). Every panel draws runs of this one batch; the 01b M1 RAPTOR baseline is drawn as a
labelled reference line (capture part of the 1.0 m/s cost), not mixed into a group.

  p4c_report.py data/<01c batch>    # figures -> docs/figures/p4, table -> <batch>/p4c-table.md
"""
import argparse,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
COLOR={'T0':'#2a78d6','T1':'#eb6834'};NAME={'T0':'T0 zero-velocity capture','T1':'T1 speed-matched, 2 m/s²'}
REF='#8a8984';INK='#0b0b0b';MUTED='#52514e';GRID='#e4e3df'
plt.rcParams.update({'font.size':9,'axes.edgecolor':MUTED,'axes.labelcolor':INK,'xtick.color':MUTED,'ytick.color':MUTED,
    'axes.grid':True,'grid.color':GRID,'grid.linewidth':.6,'axes.spines.top':False,'axes.spines.right':False,'lines.linewidth':1.6,'font.family':'DejaVu Sans'})
LEVELS=['V1.0','V1.5','V2.0','V3.0']

def load(batch):
    batch=(ROOT/batch).resolve();audit=json.loads((batch/'batch-audit.json').read_text())
    res={r['id']:r for r in json.loads((batch/'results.json').read_text())['runs']}
    runs=[{**r,'c':json.loads((ROOT/res[r['id']]['directory']/'p4c-metrics.json').read_text())} for r in audit['runs']]
    return batch,audit,runs

def fig_groups(audit,runs,out):
    specs=[('max_tilt_deg','max tilt [°]'),('max_altitude_loss_m','max altitude loss [m]'),('motor_step_at_change','motor step at change'),
           ('max_travel_along_axis_m','max travel past takeover point [m]'),('settle_time_s','settle time (speed < 0.1 m/s) [s]'),('settle_distance_m','takeover → settle point [m]')]
    fig,axes=plt.subplots(1,6,figsize=(18,3.9))
    for ax,(k,title) in zip(axes,specs):
        for x,lvl in enumerate(LEVELS):
            for dx,t in [(-.17,'T0'),(.17,'T1')]:
                g=[r for r in runs if r['condition']==lvl and r['treatment']==t]
                if not g:continue
                v=np.array([r['metrics'].get(k) if r['metrics'].get(k) is not None else np.nan for r in g],float);fail=np.array([r['flight_failure'] for r in g])
                xs=x+dx+(np.linspace(-.06,.06,len(v)) if len(v)>1 else np.zeros(1))
                ax.scatter(xs[~fail],v[~fail],s=30,color=COLOR[t],edgecolor='white',linewidth=1,zorder=3)
                if fail.any():ax.scatter(xs[fail],v[fail],s=40,color=COLOR[t],marker='x',linewidth=1.6,zorder=3)
                ok=v[~fail&np.isfinite(v)]
                if len(ok):ax.plot([x+dx-.1,x+dx+.1],[ok.mean()]*2,color=INK,lw=1.2)
        if k=='max_tilt_deg':ax.axhline(45,color=MUTED,lw=1,ls='--');ax.text(3.45,45.6,'45° envelope',color=MUTED,ha='right',fontsize=8)
        ax.set_xticks(range(len(LEVELS)));ax.set_xticklabels([l[1:]+' m/s' for l in LEVELS]);ax.set_title(title,color=INK,fontsize=9);ax.set_ylim(bottom=0)
    from matplotlib.lines import Line2D
    fig.legend([Line2D([],[],marker='o',ls='',color=COLOR[t]) for t in COLOR]+[Line2D([],[],marker='x',ls='',color=MUTED),Line2D([],[],color=INK)],
               [NAME[t] for t in COLOR]+['flight failure (pre-registered criteria; 2.0 m/s: runner safety abort, measured up to it)','mean of runs without failure'],loc='lower center',ncol=4,frameon=False)
    fig.suptitle(f'P4-01c: C→N during the classic cruise, N2 memory, per run (bar = mean of runs without failure; × = flight failure) — {audit["batch"]}',color=INK)
    fig.tight_layout(rect=(0,.08,1,1));fig.savefig(out/'p4-fig8-01c-groups.png',dpi=130);plt.close(fig)

def fig_curves(audit,runs,out):
    fig,axes=plt.subplots(2,4,figsize=(15,6.2),sharex=True)
    for j,lvl in enumerate(LEVELS):
        for t in ['T0','T1']:
            for r in [r for r in runs if r['condition']==lvl and r['treatment']==t]:
                c=r['c']['curves'];ls='-' if not r['flight_failure'] else ':'
                axes[0,j].plot(c['tilt_t_s'],c['tilt_deg'],color=COLOR[t],lw=1.1,ls=ls,alpha=.9)
                axes[1,j].plot(c['t_s'],c['speed_along_axis_m_s'],color=COLOR[t],lw=1.1,ls=ls,alpha=.9)
                if t=='T1' and c.get('target_t_s'):axes[1,j].plot(c['target_t_s'],c['target_speed_along_axis_m_s'],color=COLOR[t],lw=.9,ls='--',alpha=.7)
        axes[0,j].axhline(45,color=MUTED,lw=.9,ls='--');axes[0,j].set_title(f'{lvl[1:]} m/s',color=INK,fontsize=9)
        axes[1,j].axhline(0.1,color=MUTED,lw=.8,ls=':');axes[1,j].set_xlabel('time from C→N [s]');axes[0,j].set_xlim(-.5,3.5)
    axes[0,0].set_ylabel('tilt [°]');axes[1,0].set_ylabel('speed along +N [m/s]')
    from matplotlib.lines import Line2D
    fig.legend([Line2D([],[],color=COLOR['T0']),Line2D([],[],color=COLOR['T1']),Line2D([],[],color=COLOR['T1'],ls='--'),Line2D([],[],color=MUTED,ls=':')],
               [NAME['T0'],NAME['T1'],'T1 target speed (research_target)','dotted run: flight failure / 0.1 m/s settle threshold'],loc='lower center',ncol=4,frameon=False)
    fig.suptitle(f'P4-01c: tilt and speed after the C→N, every run — {audit["batch"]}',color=INK)
    fig.tight_layout(rect=(0,.06,1,1));fig.savefig(out/'p4-fig9-01c-curves.png',dpi=130);plt.close(fig)

def fig_capture(audit,out):
    c=audit.get('capture_cost_1p0') or {}
    if not c:return
    specs=[('motor_step_at_change','motor step at change'),('max_altitude_loss_m','max altitude loss [m]'),('max_tilt_deg','max tilt [°]')]
    fig,axes=plt.subplots(1,3,figsize=(12,4))
    for ax,(k,title) in zip(axes,specs):
        d=c[k];cols=[('01b\nbaseline',d['baseline_01b'],REF),('01b\nN2',d['n2_01b'],REF),('01c\nT0',d['T0'],COLOR['T0']),('01c\nT1',d['T1'],COLOR['T1'])]
        for x,(lab,g,col) in enumerate(cols):
            v=np.asarray(g['values']);ax.bar(x,g['mean'],width=.6,color=col,alpha=.35 if col==REF else .85,edgecolor='none')
            ax.scatter(x+np.linspace(-.12,.12,len(v)),v,s=18,color=INK if col!=REF else MUTED,zorder=3)
        ax.set_xticks(range(len(cols)));ax.set_xticklabels([x[0] for x in cols],fontsize=8)
        ax.set_title(f"{title}\nT1 removes {100*d['removed_fraction']:.0f}% [{100*d['ci95'][0]:.0f}, {100*d['ci95'][1]:.0f}] of the capture part",color=INK,fontsize=8.5)
    fig.suptitle('P4-01c at 1.0 m/s: capture part of the C→N cost and what T1 removes',color=INK)
    fig.text(.5,.01,'01b baseline: acceleration-matched RAPTOR zero-velocity capture, intact memory (capture part; cross-batch reference)\n01b N2 / 01c T0: N2 memory, zero-velocity capture;  01c T1: N2 memory, speed-matched target',ha='center',fontsize=7.5,color=MUTED)
    fig.tight_layout(rect=(0,.08,1,1));fig.savefig(out/'p4-fig10-01c-capture.png',dpi=130);plt.close(fig)

def fmt(g,d=3):
    if not g:return '—'
    s=f"{g['mean']:.{d}f}"
    return s+(f" [{g['ci95'][0]:.{d}f}, {g['ci95'][1]:.{d}f}]" if 'ci95' in g else '')

def table(audit,runs,batch):
    L=['# P4-01c per-run table','',f'Batch `{audit["batch"]}`; audit passed: {audit["passed"]}.','',
       '| run | level | target | speed at C→N m/s | flight | max tilt ° | alt loss m | motor step | saturation s | max travel m | settle s | settle dist m | pos clip s | vel clip s |','|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    f=lambda v,d=3:'—' if v is None else f'{v:.{d}f}'
    for r in runs:
        m=r['metrics'];L.append(f"| {r['id']} | {r['condition']} | {r['treatment']} | {f(r['speed_at_change_m_s'])} | {'FAILURE' if r['flight_failure'] else 'ok'} | {f(m.get('max_tilt_deg'),1)} | {f(m.get('max_altitude_loss_m'))} | {f(m.get('motor_step_at_change'))} | {f(m.get('motor_saturation_any_s'))} | {f(m.get('max_travel_along_axis_m'),2)} | {f(m.get('settle_time_s'),2)} | {f(m.get('settle_distance_m'),2)} | {f(r['clipping']['position']['duration_s'])} | {f(r['clipping']['velocity']['duration_s'])} |")
    L+=['','## Groups (mean [95% t interval])','','| group | n | failures | max tilt ° | alt loss m | motor step | settle s | settle dist m | pos clip s (runs) | vel clip s (runs) |','|---|---:|---:|---|---|---|---|---|---|---|']
    for k,g in audit['summary'].items():
        a=g['all_runs'];s=g['settle'] or {}
        L.append(f"| {k} | {g['runs']} | {g['flight_failures']} | {fmt(a['max_tilt_deg'],1)} | {fmt(a['max_altitude_loss_m'])} | {fmt(a['motor_step_at_change'])} | {fmt(s.get('settle_time_s'),2)} | {fmt(s.get('settle_distance_m'),2)} | {fmt(g['clipping']['position']['duration_s'])} ({g['clipping']['position']['runs_triggered']}) | {fmt(g['clipping']['velocity']['duration_s'])} ({g['clipping']['velocity']['runs_triggered']}) |")
    (batch/'p4c-table.md').write_text('\n'.join(L)+'\n')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('batch');a=p.parse_args()
    batch,audit,runs=load(a.batch);out=ROOT/'docs/figures/p4';out.mkdir(parents=True,exist_ok=True)
    fig_groups(audit,runs,out);fig_curves(audit,runs,out);fig_capture(audit,out);table(audit,runs,batch);print('figures ->',out)
if __name__=='__main__':main()

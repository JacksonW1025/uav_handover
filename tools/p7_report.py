#!/usr/bin/env python3
"""P7 figures (docs/figures/p7) and tables (<batch>/p7-table.md) from the batch audits and the exports.

  p7_report.py --a data/<A> --b data/<B> --c data/<C>

Tables list measured values only (outcome, max tilt, catch-up, lag); no model, prediction or classification.
"""
import argparse,gzip,io,json
from pathlib import Path
import numpy as np
import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
import p7_conditions as pc
ROOT=Path(__file__).resolve().parents[1];FIG=ROOT/'docs/figures/p7';EXPORT=ROOT/'export'
f2=lambda x,n=2:'—' if x is None else f'{x:.{n}f}'
SERIES=['#2a78d6','#eb6834','#1baf7a','#eda100','#e87ba4','#008300','#6250d6','#e34948']  # categorical slots, fixed order
GOOD,CRIT,INK,MUTED='#0ca30c','#d03b3b','#0b0b0b','#52514e'
plt.rcParams.update({'axes.edgecolor':MUTED,'axes.labelcolor':INK,'xtick.color':MUTED,'ytick.color':MUTED,'axes.grid':True,'grid.color':'#e6e5e1','grid.linewidth':.6,
                     'axes.spines.top':False,'axes.spines.right':False,'font.size':8,'figure.facecolor':'#fcfcfb','axes.facecolor':'#fcfcfb'})

def audit(b):return json.loads((Path(b)/'batch-audit.json').read_text())
def trace(run):
    p=EXPORT/Path(run).name/'trace.csv.gz'
    if not p.exists():return None
    return np.genfromtxt(io.BytesIO(gzip.decompress(p.read_bytes())),delimiter=',',names=True,dtype=None,encoding=None)
def cell(o,t,op=False,task=None):return f"{'S' if o=='SUCCESS' else 'F'} {f2(t,1)}{'*' if op else ''}{'†' if task is not None and task!=o else ''}"
def run_dir(a,rid):return next(x['directory'] for x in json.loads((ROOT/a['batch']/'results.json').read_text())['runs'] if x['id']==rid)

def table_a(A):
    gs=None;rows=[]
    for key,v in A['tables']['A'].items():
        gs=[r['g_s'] for r in v['by_interval']];ref=v['single_reference']
        cells=[('取消' if r.get('cancelled') else '未飞') if not r['flown'] else cell(r['outcome'],r['max_tilt_deg'],r['max_tilt_from_open_gap'],r.get('task_outcome'))+('' if r['gaps_completed']==4 else f" ({r['gaps_completed']}/4)") for r in v['by_interval']]
        rows.append(f"| {key} | {cell(ref['outcome'],ref['max_tilt_deg']) if ref else '—'} | "+' | '.join(cells)+' |')
    head='| 组（捕获 方向 D） | 单次参照 | '+' | '.join(f'g = {pc.fmt(g)} s' for g in gs)+' |'
    return '\n'.join(['S 成功，F 失败（冻结判据），数字为最大倾角 °（从第一次中断起）；* 中断中被中止，倾角取到 RAPTOR 结束；† 按任务判据（倾角 ≥ 45° 或高度损失 > 1 m）结果不同；(k/4) 被中止前完成的中断次数。','',head,'|'+'---|'*(len(gs)+2)]+rows)

def table_b(B):
    rows=['| 序列 | 次数 | 中断 D s | 间隔 g s | 总中断 s | 跨度 s | 结果 | 最大倾角 ° | 每段最大倾角 ° | 每次恢复跳变 m |','|---|---|---|---|---|---|---|---|---|---|']
    for n,r in sorted(B['tables']['B'].items()):
        rows.append(f"| {n} | {r['count']} | {'/'.join(pc.fmt(x) for x in r['durations_s'])} | {'/'.join(pc.fmt(x) for x in r['intervals_s'])} | {pc.fmt(r['total_interruption_s'])} | {pc.fmt(r['span_s'])} | "
                    f"{'S' if r['outcome']=='SUCCESS' else 'F'}{'†' if r.get('task_outcome') not in [None,r['outcome']] else ''} | {f2(r['max_tilt_deg'],1)}{'*' if r['max_tilt_from_open_gap'] else ''} | {', '.join(f2(x,1) for x in r['per_interruption_max_tilt_deg'])} | {', '.join(f2(x) for x in r['setpoint_jumps_m'])} |")
    return '\n'.join(rows)

def table_c(C):
    rows=['追回用时 = 虚拟目标从恢复到位置差、速度差都 < 0.02 的时间（STALE = 追回中再次断链）；落后 = 原轨迹点减机体位置沿运动轴（正 = 落后），窗口为恢复后 6 s；网络看到的跳变 = 虚拟目标起点（机体）减恢复前目标。','',
          '| 运行 | 结果 | 最大倾角 ° | 高度损失 m | 每次恢复：追回用时 s | 限速时长 s | setpoint 跳变 m | 网络看到的跳变 m | 6 s 内最大落后 m | 6 s 时落后 m |','|---|---|---|---|---|---|---|---|---|---|']
    for r in sorted(C['tables']['C'],key=lambda r:r['condition']):
        pr=r['per_resume'];j=lambda k,n=2:', '.join(f2(x.get(k),n) if x.get(k) is not None else ('STALE' if k=='catch_up_s' and x.get('recovery_end')=='STALE' else '—') for x in pr)
        rows.append(f"| {r['condition']} | {'S' if r['outcome']=='SUCCESS' else 'F'}{'†' if r.get('task_outcome') not in [None,r['outcome']] else ''} | {f2(r['max_tilt_deg'],1)}{'*' if r['max_tilt_from_open_gap'] else ''} | {f2(r['max_altitude_loss_m'],3)} | {j('catch_up_s')} | {j('acceleration_limited_s')} | "
                    f"{j('setpoint_jump_along_axis_m')} | {j('observed_jump_along_axis_m')} | {j('max_along_track_lag_m')} | {j('along_track_lag_at_6s_m')} |")
    return '\n'.join(rows)

def fig_a(A):
    fig,ax=plt.subplots(figsize=(8,4.2))
    for i,(key,v) in enumerate(A['tables']['A'].items()):
        pts=[(r['g_s'],r['max_tilt_deg'],r['outcome']) for r in v['by_interval'] if r['flown']];c=SERIES[i]
        if pts:ax.plot([p[0] for p in pts],[p[1] for p in pts],color=c,lw=1.5,label=key)
        for g,t,o in pts:ax.scatter(g,t,marker='o' if o=='SUCCESS' else 'X',s=36,color=c,edgecolors='#fcfcfb',linewidths=1.5,zorder=3)
        ref=v['single_reference']
        if ref:ax.scatter(0.62,ref['max_tilt_deg'],marker='o' if ref['outcome']=='SUCCESS' else 'X',s=36,color=c,edgecolors='#fcfcfb',linewidths=1.5,zorder=3)
    ax.axhline(45,color=MUTED,ls='--',lw=1);ax.text(0.005,45.4,'45° failure limit',color=MUTED,fontsize=7)
    ax.set_xticks([0.05,0.1,0.15,0.25,0.5,0.62]);ax.set_xticklabels(['0.05','0.10','0.15','0.25','0.50','single'])
    ax.set_xlabel('stream interval g between the 4 interruptions [s]   (o success, X failure)');ax.set_ylabel('max tilt [deg]');ax.legend(fontsize=7,frameon=False,ncol=2)
    fig.tight_layout();fig.savefig(FIG/'p7-fig1-a-interval-scan.png',dpi=140);plt.close(fig)

def fig_b(B):
    items=sorted(B['tables']['B'].items());fig,ax=plt.subplots(figsize=(8,0.32*len(items)+1.2))
    for i,(n,r) in enumerate(items):
        y=len(items)-1-i;st=GOOD if r['outcome']=='SUCCESS' else CRIT
        for a,b in r['windows_s']:ax.barh(y,b-a,left=a,height=.55,color=SERIES[0],edgecolor='#fcfcfb',linewidth=2)
        ax.text(r['span_s']+0.08,y,f"{'S' if r['outcome']=='SUCCESS' else 'F'} {r['max_tilt_deg']:.1f}°",va='center',fontsize=7,color=st)
    ax.set_yticks(range(len(items)));ax.set_yticklabels([n for n,_ in items][::-1]);ax.set_xlim(0,4);ax.grid(axis='y',visible=False)
    ax.set_xlabel('time from the first interruption start [s]  (bars = setpoint interruptions; S/F and max tilt at the right)')
    fig.tight_layout();fig.savefig(FIG/'p7-fig2-b-sequences.png',dpi=140);plt.close(fig)

def fig_c(C):
    runs=sorted(C['tables']['C'],key=lambda r:r['condition'])
    panels=[('C1 2.0 m/s A0',[r for r in runs if r['condition'].startswith('h-v2.0') and r['condition'].endswith('A0')]),
            ('C1 2.5 m/s A0',[r for r in runs if r['condition'].startswith('h-v2.5')]),
            ('C2 A45 / C3 / C4',[r for r in runs if not r['condition'].startswith('h-v2.5') and not (r['condition'].startswith('h-v2.0') and r['condition'].endswith('A0'))])]
    fig,ax=plt.subplots(2,3,figsize=(12,6),sharex=True)
    for j,(title,rs) in enumerate(panels):
        for i,r in enumerate(rs):
            tr=trace(run_dir(C,r['id']))
            if tr is None or not r['per_resume']:continue
            res=json.loads((EXPORT/Path(run_dir(C,r['id'])).name/'summary.json').read_text())['recovery']
            t0=res[-1]['resume_t_s'];t=tr['t_s']-t0;c=SERIES[i%8];lab=f"{r['condition'][2:]} {'S' if r['outcome']=='SUCCESS' else 'F'}"
            ax[0,j].plot(t,tr['traj_p_u']-tr['p_u'],color=c,lw=1.2,label=lab);ax[1,j].plot(t,tr['tilt_deg'],color=c,lw=1.2,label=lab)
        ax[0,j].set_title(title,fontsize=9,color=INK);ax[0,j].legend(fontsize=6,frameon=False);ax[1,j].axhline(45,color=MUTED,ls='--',lw=1)
        ax[1,j].set_xlabel('time from the last resume [s]');ax[0,j].set_xlim(-3,8)
    ax[0,0].set_ylabel('lag behind the trajectory [m]');ax[1,0].set_ylabel('tilt [deg]')
    fig.tight_layout();fig.savefig(FIG/'p7-fig3-c-recovery.png',dpi=140);plt.close(fig)

def main():
    global EXPORT,FIG
    p=argparse.ArgumentParser(description=__doc__)
    for k in ['a','b','c']:p.add_argument('--'+k,type=Path)
    p.add_argument('--export',type=Path,default=ROOT/'export');p.add_argument('--figures',type=Path,default=FIG)
    a=p.parse_args();EXPORT,FIG=a.export.resolve(),a.figures.resolve();FIG.mkdir(parents=True,exist_ok=True)
    if a.a:A=audit(a.a);(a.a/'p7-table.md').write_text(table_a(A)+'\n');fig_a(A)
    if a.b:B=audit(a.b);(a.b/'p7-table.md').write_text(table_b(B)+'\n');fig_b(B)
    if a.c:C=audit(a.c);(a.c/'p7-table.md').write_text(table_c(C)+'\n');fig_c(C)
    return 0
if __name__=='__main__':raise SystemExit(main())

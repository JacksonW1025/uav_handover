#!/usr/bin/env python3
"""P8 figures (docs/figures/p8) and tables (<batch>/p8-table.md) from the batch audits and the exports.

  p8_report.py --a data/<A batch>

Tables list measured values only (outcome, max tilt, altitude loss, jump timing, catch-up); no model, no prediction.
"""
import argparse,gzip,io,json
from pathlib import Path
import numpy as np
import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1];FIG=ROOT/'docs/figures/p8'
SERIES=['#2a78d6','#eb6834','#1baf7a','#eda100','#e87ba4','#008300','#6250d6','#52514e']  # dataviz reference categorical order
f2=lambda x,n=2:'—' if x is None else f'{x:.{n}f}'

def audit(b):return json.loads((Path(b)/'batch-audit.json').read_text())
def trace(run):
    p=ROOT/'export'/Path(run).name/'trace.csv.gz'
    return np.genfromtxt(io.BytesIO(gzip.decompress(p.read_bytes())),delimiter=',',names=True,dtype=None,encoding=None) if p.exists() else None

def table_a(a,cfg):
    conds=cfg['p6']['ident']['conditions']
    rows=['| # | 运行 | 剖面 | 巡航（跳变后 / 最长追赶）s 计划·实际 | 结果 | 最大倾角 °（时刻 s） | 首次 ≥45° s | 高度损失 m（时刻 s） | 最大下降速度 m/s | 电机指令均值 最小–最大 | 跳变 m / 时刻 s | 跳变后初始落后 m | 追上 s（≤0.2 m） | 最大沿轴速度 m/s | 任务判据 |',
          '|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|']
    for k,r in enumerate(a['runs'],1):
        m=r['metrics'];p8=r.get('p8') or {};j=p8.get('jump') or {};lg=p8.get('lag') or {};vt=p8.get('vertical') or {};ch=p8.get('chase') or {};tc=p8.get('task_criterion') or {}
        s=conds[r['condition']]
        if s['family']=='jump':prof=f"jump v{s['speed_m_s']} L{s['jump_m']} {s['axis']}";cr=f"{f2(s['post_jump_s'],1)} · {f2(j.get('realized_post_jump_cruise_s'))}";jm=f"{f2(j.get('jump_m'),3)} / {f2(j.get('family_time_s'),3)}"
        else:prof=f"chase x0 {s['x0_m']} V {s['speed_m_s']} {s['axis']}";cr=f"{f2(s['max_chase_s'],1)} · {f2(ch.get('switch_family_time_s'))} ({ch.get('reason')})";jm='—'
        rows.append(f"| {k} | {r['id']} | {prof} | {cr} | {m['outcome']} | {f2(m['max_tilt_deg'],1)} ({f2(m['max_tilt_at_s'])}) | {f2(m['first_at_or_above_45_s'])} | {f2(vt.get('max_altitude_loss_m'),3)} ({f2(vt.get('max_altitude_loss_at_s'))}) | "
                    f"{f2(vt.get('max_descent_speed_m_s'))} | {f2(vt.get('motor_command_mean_min'))}–{f2(vt.get('motor_command_mean_max'))} | {jm} | {f2(lg.get('initial_lag_m'))} | {f2(lg.get('catch_up_s'))} | {f2(lg.get('max_speed_along_axis_m_s'))} | "
                    f"{'超过（'+'、'.join(tc.get('reasons') or [])+'）' if tc.get('exceeded') else '未超过'} |")
    return '\n'.join(rows)

def fig_a(a):
    fig,ax=plt.subplots(1,3,figsize=(15,4.4),sharex=True)
    dirs={x['id']:x['directory'] for x in json.loads((ROOT/a['batch']/'results.json').read_text())['runs']}
    for k,r in enumerate(a['runs']):
        name=Path(dirs[r['id']]).name;t=trace(name)
        if t is None:continue
        ev=json.loads((ROOT/'export'/name/'summary.json').read_text())['events']
        ref=next((e['t_s'] for e in ev if e['event']=='jump'),0.)
        x=t['t_s']-ref;w=(x>=-1)&(x<=10);c=SERIES[k%len(SERIES)]
        ax[0].plot(x[w],t['ep_u'][w],color=c,lw=1.6,label=r['id'])
        ax[1].plot(x[w],t['tilt_deg'][w],color=c,lw=1.6);ax[2].plot(x[w],t['alt_loss_m'][w],color=c,lw=1.6)
    ax[1].axhline(45,color='#8a8984',lw=1,ls='--');ax[1].text(9.9,45.5,'45°',ha='right',va='bottom',color='#52514e',fontsize=8)
    ax[2].axhline(1.0,color='#8a8984',lw=1,ls='--');ax[2].text(9.9,1.02,'1 m',ha='right',va='bottom',color='#52514e',fontsize=8)
    for a_,y in zip(ax,['未截断位置误差 ep_u m（负 = 落后）','倾角 °','高度损失 m（正 = 下降）']):
        a_.set_ylabel(y);a_.set_xlabel('自跳变 / 目标出现起 s');a_.grid(alpha=.25,lw=.6)
        for s in ['top','right']:a_.spines[s].set_visible(False)
    ax[0].legend(fontsize=7,frameon=False,loc='lower right')
    fig.suptitle('P8-A 辨识飞行：跳变 / 追赶后的落后、倾角与高度',fontsize=11);fig.tight_layout()
    FIG.mkdir(parents=True,exist_ok=True);fig.savefig(FIG/'p8-fig1-a-ident.png',dpi=130);plt.close(fig)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--a',type=Path);a=p.parse_args()
    plt.rcParams['font.sans-serif']=['Noto Sans CJK SC','WenQuanYi Zen Hei','DejaVu Sans'];plt.rcParams['axes.unicode_minus']=False
    if a.a:
        au=audit(a.a);cfg=json.loads((ROOT/au['config']).read_text())
        (a.a/'p8-table.md').write_text('# P8-A 辨识飞行\n\n'+table_a(au,cfg)+'\n');fig_a(au);print('A table and figure written')
    return 0
if __name__=='__main__':raise SystemExit(main())

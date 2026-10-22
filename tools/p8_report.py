#!/usr/bin/env python3
"""P8 figures (docs/figures/p8) and tables (<batch>/p8-table.md) from the batch audits and the exports.

  p8_report.py --a data/<A batch>
  p8_report.py --b data/<B1 batch> [data/<B2 batch>] --state data/<B state>

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
    for a_,y in zip(ax,['unclipped position error ep_u (m, negative = behind)','tilt (deg)','altitude loss (m, positive = lower)']):
        a_.set_ylabel(y);a_.set_xlabel('time since the jump / target appearance (s)');a_.grid(alpha=.25,lw=.6)
        for s in ['top','right']:a_.spines[s].set_visible(False)
    ax[0].legend(fontsize=7,frameon=False,loc='lower right')
    fig.suptitle('P8-A identification: lag, tilt and altitude after the setpoint jump / target appearance',fontsize=11);fig.tight_layout()
    FIG.mkdir(parents=True,exist_ok=True);fig.savefig(FIG/'p8-fig1-a-ident.png',dpi=130);plt.close(fig)

METHODS=['random','contest','ours','fuzz','bo']

def camp_states(state):
    return {f.stem.replace('_','/'):json.loads(f.read_text()) for f in sorted((Path(state)/'campaigns').glob('*.json'))}

def b_rows(states,lo,hi):
    """Per system x method over rounds lo..hi: failures (primary, task) per seed, distinct failure cells, first failure round."""
    out={}
    for sut in ['T0','T1']:
        for m in METHODS:
            seeds={}
            for k in range(3):
                st=states.get(f'{m}/{sut}/{k}')
                runs=[x for x in (st or {}).get('runs',[]) if x.get('status')!='DEVELOPMENT_FAILED' and lo<=x['k']<=hi]
                fp=[x for x in runs if x['fail_primary']];ft=[x for x in runs if x['fail_task']]
                seeds[k]={'n':len(runs),'fp':len(fp),'ft':len(ft),'first_fp':fp[0]['k'] if fp else None,'first_ft':ft[0]['k'] if ft else None,
                          'cells_fp':{tuple(x['cell']) for x in fp},'cells_ft':{tuple(x['cell']) for x in ft},'reruns':sum(len(x.get('infra_reruns') or []) for x in runs)}
            out[(sut,m)]=seeds
    return out

def table_b(states,lo,hi,title):
    R=b_rows(states,lo,hi)
    rows=[f'### {title}（第 {lo}–{hi} 轮）','','| 被测 | 方法 | 轮数 | 主判据失败（种子 0/1/2 = 合计） | 任务判据失败（0/1/2 = 合计） | 不同失败格（主 / 任务，3 种子合并） | 第一个主判据失败的轮次（0/1/2） | 第一个任务判据失败的轮次（0/1/2） | 基础设施补跑 |','|---|---|---|---|---|---|---|---|---|']
    f=lambda x:'—' if x is None else str(x)
    for (sut,m),s in R.items():
        n=sum(x['n'] for x in s.values())
        rows.append(f"| {sut} | {m} | {n} | {'/'.join(str(s[k]['fp']) for k in range(3))} = **{sum(s[k]['fp'] for k in range(3))}** | {'/'.join(str(s[k]['ft']) for k in range(3))} = {sum(s[k]['ft'] for k in range(3))} | "
                    f"{len(set().union(*[s[k]['cells_fp'] for k in range(3)]))} / {len(set().union(*[s[k]['cells_ft'] for k in range(3)]))} | {'/'.join(f(s[k]['first_fp']) for k in range(3))} | {'/'.join(f(s[k]['first_ft']) for k in range(3))} | {sum(s[k]['reruns'] for k in range(3))} |")
    return '\n'.join(rows)

def fig_b(states,hi):
    fig,ax=plt.subplots(2,2,figsize=(12,7.5),sharex=True)
    for j,sut in enumerate(['T0','T1']):
        for i,key in enumerate(['fail_primary','fail_task']):
            a=ax[i][j]
            for c,m in enumerate(METHODS):
                cum=np.zeros(hi)
                for k in range(3):
                    st=states.get(f'{m}/{sut}/{k}') or {}
                    for x in st.get('runs',[]):
                        if x.get('status')!='DEVELOPMENT_FAILED' and x['k']<=hi and x[key]:cum[x['k']-1:]+=1
                a.step(np.arange(1,hi+1),cum,where='post',color=SERIES[c],lw=2,label=m)
            a.set_title(f"{sut}: {'primary (frozen flight-failure) criterion' if key=='fail_primary' else 'task criterion (tilt >= 45 deg or altitude loss > 1 m)'}",fontsize=9)
            a.set_ylabel('cumulative failures, 3 seeds');a.grid(alpha=.25,lw=.6)
            for sp in ['top','right']:a.spines[sp].set_visible(False)
            if i==1:a.set_xlabel('round k')
    ax[0][0].legend(frameon=False,fontsize=8);fig.suptitle('P8-B: cumulative failures found per method (sum over seeds 0-2)',fontsize=11);fig.tight_layout()
    FIG.mkdir(parents=True,exist_ok=True);fig.savefig(FIG/'p8-fig2-b-failures.png',dpi=130);plt.close(fig)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--a',type=Path);p.add_argument('--b',type=Path,nargs='*');p.add_argument('--state',type=Path);a=p.parse_args()
    if a.b:
        states=camp_states(a.state);hi=max([x['k'] for st in states.values() for x in st['runs'] if 'k' in x] or [0])
        txt='# P8-B 测试生成基线对比\n\n'+table_b(states,1,min(15,hi),'B1')+'\n\n'
        if hi>15:txt+=table_b(states,16,hi,'B2')+'\n\n'+table_b(states,1,hi,'B1 + B2')+'\n'
        for b in a.b:(b/'p8-table.md').write_text(txt)
        fig_b(states,hi);print('B tables and figure written, rounds up to',hi)
    if a.a:
        au=audit(a.a);cfg=json.loads((ROOT/au['config']).read_text())
        (a.a/'p8-table.md').write_text('# P8-A 辨识飞行\n\n'+table_a(au,cfg)+'\n');fig_a(au);print('A table and figure written')
    return 0
if __name__=='__main__':raise SystemExit(main())

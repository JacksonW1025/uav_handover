#!/usr/bin/env python3
"""P6 figures (docs/figures/p6) and per-stage tables (<batch>/p6-table.md) from the batch audits and the exports.

  p6_report.py --a data/<A> --b1 data/<B1> --b2 data/<B2> --b3 data/<B3> --c data/<C>

Tables only list measured values (outcome, max tilt, first >= 45 deg, altitude loss, jumps); no model or kernel.
"""
import argparse,gzip,io,json
from pathlib import Path
import numpy as np
import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
import p6_conditions as pc
ROOT=Path(__file__).resolve().parents[1];FIG=ROOT/'docs/figures/p6'
f2=lambda x,n=2:'—' if x is None else f'{x:.{n}f}'

def audit(b):return json.loads((Path(b)/'batch-audit.json').read_text())
def trace(run):
    p=ROOT/'export'/Path(run).name/'trace.csv.gz'
    if not p.exists():return None
    t=np.genfromtxt(io.BytesIO(gzip.decompress(p.read_bytes())),delimiter=',',names=True,dtype=None,encoding=None);return t

def table_a(a):
    rows=['| 条件 | 结果 | 最大倾角 ° | 最大倾角时刻 s | 首次 ≥45° s | 高度损失 m | 最大沿轴速度 m/s | 位置/速度截断 s | 两轴同时截断 位置/速度 s | chase 减速开始 s |','|---|---|---|---|---|---|---|---|---|---|']
    for r in sorted(a['runs'],key=lambda r:r['id']):
        m=r['metrics'];cs=m.get('chase_switch') or {}
        rows.append(f"| {r['id']} | {m['outcome']} | {f2(m['max_tilt_deg'],1)} | {f2(m['max_tilt_at_s'])} | {f2(m['first_at_or_above_45_s'])} | {f2(m['max_altitude_loss_m'],3)} | {f2(m['max_speed_along_axis_m_s'])} | "
                    f"{f2(m['clipping_s']['position'])}/{f2(m['clipping_s']['velocity'])} | {f2(m['clipping_both_axes_s']['position'])}/{f2(m['clipping_both_axes_s']['velocity'])} | {f2(cs.get('family_time_s'))} {cs.get('reason') or ''} |")
    return '\n'.join(rows)

def family_rows(audits):
    fam={}
    for name,a in audits:
        for k,f in a['families'].items():
            for r in f['runs']:fam.setdefault(k,[]).append({**r,'stage':name})
    return fam

def table_b(fam,refine=None):
    rows=['S 成功，F 失败；* 中断中被中止，倾角取到 RAPTOR 结束（P5 open-gap 测量）；括号为 B1 以外的阶段。','','| 族（处理@速度@方向） | D s：结果 / 最大倾角 °（阶段） | 最后成功 D | 首个失败 D | 状态 |','|---|---|---|---|---|']
    for k in sorted(fam,key=lambda k:(k.split('@')[0],k)):
        rs=sorted(fam[k],key=lambda r:(r['D_s'] or 0,r['stage'],r['id']))
        cells=' · '.join(f"{pc.fmt(r['D_s'])}: {'S' if r['outcome']=='SUCCESS' else 'F'}/{f2(r['max_tilt_deg'],1)}{'*' if r.get('max_tilt_from_open_gap') else ''}{'' if r['stage']=='B1' else '('+r['stage']+')'}" for r in rs if r['D_s'] is not None)
        from p6_batch import bracket
        pts=sorted((r['D_s'],'S' if r['outcome']=='SUCCESS' else 'F') for r in rs if r['stage'] in ['B1','B2','C'] and r['D_s'] is not None)
        _,st,ls,ff=bracket(pts) if pts else (None,'—',None,None)
        rows.append(f"| {k} | {cells} | {pc.fmt(ls) if ls is not None else '—'} | {pc.fmt(ff) if ff is not None else '—'} | {st} |")
    return '\n'.join(rows)

def fig_a(a):
    fig,ax=plt.subplots(1,2,figsize=(13,4.5));runs=sorted(a['runs'],key=lambda r:r['id'])
    ax[0].barh([r['id'] for r in runs],[r['metrics']['max_tilt_deg'] for r in runs],color=['C3' if (r['metrics']['max_tilt_deg'] or 0)>=45 else 'C0' for r in runs])
    ax[0].axvline(45,color='k',ls='--');ax[0].axvline(65,color='r',ls=':');ax[0].set_xlabel('max tilt [deg]');ax[0].tick_params(axis='y',labelsize=7);ax[0].invert_yaxis()
    res=json.loads((ROOT/a['batch']/'results.json').read_text())['runs']
    for r in runs:
        tr=trace(next(x['directory'] for x in res if x['id']==r['id']))
        if tr is not None and r['metrics']['family'] in ['chase','step']:ax[1].plot(tr['t_s'],tr['tilt_deg'],lw=.7,label=r['id'])
    ax[1].set_xlim(-1,8);ax[1].axhline(45,color='k',ls='--');ax[1].set_xlabel('time from family start [s]');ax[1].set_ylabel('tilt [deg]');ax[1].legend(fontsize=6)
    fig.tight_layout();fig.savefig(FIG/'p6-fig1-a-ident.png',dpi=130);plt.close(fig)

def fig_b(fam):
    keys=sorted([k for k in fam if any(r['D_s'] is not None for r in fam[k])],key=lambda k:(k.split('@')[0],k));fig,ax=plt.subplots(figsize=(11,0.45*len(keys)+1.5))
    mk={'B1':'o','B2':'s','B3':'^','C':'D'}
    for i,k in enumerate(keys):
        for r in fam[k]:
            if r['D_s'] is None:continue
            ax.scatter(r['D_s'],i+{'B1':0,'B2':.12,'B3':-.15,'C':0}[r['stage']],marker=mk[r['stage']],c='C2' if r['outcome']=='SUCCESS' else 'C3',s=30,edgecolors='k',linewidths=.3)
            ax.annotate(f"{r['max_tilt_deg']:.0f}" if r['max_tilt_deg'] else '',(r['D_s'],i+.18),fontsize=5,ha='center')
    ax.set_yticks(range(len(keys)));ax.set_yticklabels(keys,fontsize=7);ax.set_xlabel('planned interruption D [s]  (green success, red failure; o B1, s B2, ^ B3, D C; number = max tilt)')
    fig.tight_layout();fig.savefig(FIG/'p6-fig2-bc-grid.png',dpi=130);plt.close(fig)

def fig_c2(c):
    fig,ax=plt.subplots(figsize=(9,4))
    res=json.loads((ROOT/c['batch']/'results.json').read_text())['runs']
    for r in c['runs']:
        if not r['condition'].startswith('M'):continue
        tr=trace(next(x['directory'] for x in res if x['id']==r['id']))
        if tr is not None:ax.plot(tr['t_s'],tr['tilt_deg'],lw=.7,label=f"{r['condition']} {r['outcome']}")
    ax.axhline(45,color='k',ls='--');ax.set_xlim(-1,6);ax.set_xlabel('time from the first interruption [s]');ax.set_ylabel('tilt [deg]');ax.legend(fontsize=7)
    fig.tight_layout();fig.savefig(FIG/'p6-fig3-c2-sequences.png',dpi=130);plt.close(fig)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ['a','b1','b2','b3','c']:p.add_argument('--'+k,type=Path)
    a=p.parse_args();FIG.mkdir(parents=True,exist_ok=True)
    if a.a:A=audit(a.a);(a.a/'p6-table.md').write_text(table_a(A)+'\n');fig_a(A)
    stages=[(n,audit(getattr(a,n.lower()))) for n in ['B1','B2','B3'] if getattr(a,n.lower())]
    if stages:
        fam=family_rows(stages);txt=table_b(fam)
        for _,s in stages:(ROOT/s['batch']/'p6-table.md').write_text(txt+'\n')
    if a.c:
        C=audit(a.c);fam_all=family_rows(stages+[('C',C)]);fig_b(fam_all)
        c2=['| 运行 | 结果 | 最大倾角 ° | 首次 ≥45° s | 高度损失 m | 每次恢复跳变 m | 速度跳变 m/s |','|---|---|---|---|---|---|---|']
        for r in sorted(C['runs'],key=lambda r:r['id']):
            if r['condition'].startswith('M'):
                m=r['metrics'];c2.append(f"| {r['id']} | {r['outcome']} | {f2(m['max_tilt_deg'],1)} | {f2(m['first_at_or_above_45_s'])} | {f2(m['max_altitude_loss_m'],3)} | {', '.join(f2(g['jump_along_axis_m']) for g in m['gaps'])} | {', '.join(f2(g['velocity_jump_along_axis_m_s']) for g in m['gaps'])} |")
        (a.c/'p6-table.md').write_text(table_b(family_rows([('C',C)]))+'\n\n'+'\n'.join(c2)+'\n');fig_c2(C)
    return 0
if __name__=='__main__':raise SystemExit(main())

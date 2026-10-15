#!/usr/bin/env python3
"""P4 report figures and tables from finished, audited P4 batches (reads batch-audit.json and the stored per-run
metrics; edits no run). Every panel draws runs of one batch only.

  p4_report.py --a data/<01a batch> --b data/<01b batch>    # figures -> docs/figures/p4, tables -> <batch>/p4-table.md
"""
import argparse,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
COLOR={'N0':'#2a78d6','N3':'#eb6834','N2':'#1baf7a','N2s':'#008300','B':'#8a8984'}
NAME={'N0':'N0 reset','N3':'N3 old memory','N2':'N2 teacher forcing','N2s':'N2s shadow memory','B':'RAPTOR baseline'}
UNIT={'D2':'01a D2: 10 s hover deactivation','M1':'M1: classic 1 m/s cruise','M2':'M2: classic mid-deceleration (~0.5 m/s)','M3':'M3: P3 sequence, 2nd C→N at 1 m/s'}
INK='#0b0b0b';MUTED='#52514e';GRID='#e4e3df'
plt.rcParams.update({'font.size':9,'axes.edgecolor':MUTED,'axes.labelcolor':INK,'xtick.color':MUTED,'ytick.color':MUTED,
    'axes.grid':True,'grid.color':GRID,'grid.linewidth':.6,'axes.spines.top':False,'axes.spines.right':False,'lines.linewidth':1.6,'font.family':'DejaVu Sans'})

def load(batch):
    batch=(ROOT/batch).resolve();audit=json.loads((batch/'batch-audit.json').read_text())
    res={r['id']:r for r in json.loads((batch/'results.json').read_text())['runs']};runs=[]
    for r in audit['runs']:
        d=ROOT/res[r['id']]['directory'];name='p3-metrics.json' if r['kind'].startswith('p3_') else 'p2-metrics.json'
        runs.append({**r,'m':json.loads((d/name).read_text())})
    return batch,audit,runs

def measured(r):
    return {'p3_sequence':'second_C_to_N','p2_c_to_n':'C_to_N'}.get(r['kind'],'baseline_recapture')

def motor_curve(r):
    m=r['m']
    if r['kind'].startswith('p3_'):c=m['events'][measured(r)]['curves']
    else:c=m['curves']
    return np.asarray(c['motor_t_s']),np.mean(np.asarray(c['motor']),1)

def treatments(audit,unit):return [t for t in ['N0','N3','N2s','N2'] if f'{unit}:{t}' in audit['summary']]

def fig_groups(audit,runs,unit,out,name):
    if unit not in audit['units']:return
    base=audit['units'][unit]['baseline_condition'];specs=[('motor_step_at_change','motor step at change'),('motor_rms_vs_baseline','motor RMS vs baseline, 0–0.5 s'),('max_altitude_loss_m','max altitude loss [m]'),('max_tilt_deg','max tilt [°]')]
    fig,axes=plt.subplots(1,4,figsize=(15,3.8))
    for ax,(k,yl) in zip(axes,specs):
        cols=[(f'{unit}:{t}',t) for t in treatments(audit,unit)]+[(f'{base}:B','B')]
        for x,(key,t) in enumerate(cols):
            g=audit['summary'].get(key,{}).get(k)
            if not g:continue
            v=np.asarray(g['values']);xs=x+np.linspace(-.15,.15,len(v)) if len(v)>1 else [x]
            ax.scatter(xs,v,s=26,color=COLOR[t],edgecolor='white',linewidth=1,zorder=3)
            ax.plot([x-.28,x+.28],[g['mean']]*2,color=INK,lw=1.2)
            if 'ci95' in g:ax.plot([x,x],g['ci95'],color=INK,lw=.9)
        ax.set_xticks(range(len(cols)));ax.set_xticklabels([t for _,t in cols]);ax.set_title(yl,color=INK,fontsize=9)
    fig.suptitle(f'{UNIT[unit]}: measured takeover per run, group mean and 95% t interval ({audit["batch"]})',color=INK)
    fig.tight_layout();fig.savefig(out/name,dpi=130);plt.close(fig)

def fig_curves(audit,runs,units,out,name):
    units=[u for u in units if u in audit['units']]
    if not units:return
    fig,axes=plt.subplots(1,len(units),figsize=(4.2*len(units),3.6),sharey=True)
    for ax,unit in zip(np.atleast_1d(axes),units):
        base=audit['units'][unit]['baseline_condition']
        for r in runs:
            if r['condition']==base and r['treatment']=='B':t,v=motor_curve(r);ax.plot(t,v,color=COLOR['B'],lw=1.0)
        for r in runs:
            if r['condition']==unit and r['treatment']!='B':t,v=motor_curve(r);ax.plot(t,v,color=COLOR[r['treatment']],lw=1.2)
        ax.axvline(0,color=MUTED,lw=.8,ls=':');ax.set_xlim(-.1,.6);ax.set_title(UNIT[unit],color=INK,fontsize=9);ax.set_xlabel('time from takeover [s]')
    np.atleast_1d(axes)[0].set_ylabel('mean of four motor commands')
    hs=[plt.Line2D([],[],color=COLOR[k],label=NAME[k]) for k in ['N0','N3','N2','N2s','B']]
    fig.legend(handles=hs,loc='lower center',ncol=5,frameon=False);fig.tight_layout(rect=(0,.08,1,1));fig.savefig(out/name,dpi=130);plt.close(fig)

def fig_ratios(audits,out,name):
    metrics=[('motor_step_at_change','motor step'),('motor_rms_vs_baseline','motor RMS 0–0.5 s'),('max_altitude_loss_m','altitude loss'),('max_tilt_deg','max tilt')]
    fig,axes=plt.subplots(1,4,figsize=(15,4),sharey=True)
    for ax,(k,title) in zip(axes,metrics):
        y=0;labels=[]
        for audit in audits:
            for key,e in sorted(audit['elimination'].items(),key=lambda kv:(list(UNIT).index(kv[0].split(':')[0]),['N3','N2s','N2'].index(kv[0].split(':')[1]))):
                if k not in e:continue
                r=e[k];t=key.split(':')[1]
                if r['ratio'] is not None:ax.scatter([r['ratio']],[y],color=COLOR[t],s=30,zorder=3)
                if r.get('ratio_ci95'):ax.plot(r['ratio_ci95'],[y,y],color=COLOR[t],lw=1.2)
                labels.append(key);y-=1
        ax.axvline(0,color=MUTED,lw=.8);ax.axvline(1,color=MUTED,lw=.8,ls=':');ax.set_title(title,color=INK,fontsize=9);ax.set_xlabel('(N0 − Nx)/(N0 − baseline)')
        ax.set_xlim(-2.2,1.6)
    axes[0].set_yticks(range(0,-len(labels),-1));axes[0].set_yticklabels(labels)
    fig.suptitle('Part of the C→N cost removed by the memory treatment, point estimate and 95% bootstrap interval',color=INK)
    fig.tight_layout();fig.savefig(out/name,dpi=130);plt.close(fig)

def fmt(g,p=3):
    if not g:return '—'
    return f"{g['mean']:.{p}f} [{g['ci95'][0]:.{p}f}, {g['ci95'][1]:.{p}f}]" if 'ci95' in g else f"{g['mean']:.{p}f}"

def table(audit,batch):
    L=[f"# P4 table: {audit['batch']}",'','Measured takeover (p3_sequence: second C→N; p2_c_to_n: C→N; baselines: re-capture). Mean [95% t interval].','',
       '| group | n | speed at takeover m/s | accel m/s² | motor step | motor RMS vs baseline | max alt. loss m | max tilt ° | recovery s | GRU dist @0 / 0.1 / 0.25 s |','|---|---:|---|---|---|---|---|---|---|---|']
    for key,g in audit['summary'].items():
        gd=g.get('gru_distance_to_baseline') or {};gs=' / '.join(f"{gd[o]['mean']:.3f}" for o in ['0.0','0.1','0.25'] if o in gd)
        L.append(f"| {key} | {g['runs']} | {fmt(g.get('speed_along_axis_m_s'))} | {fmt(g.get('acceleration_along_axis_m_s2'),2)} | {fmt(g.get('motor_step_at_change'))} | {fmt(g.get('motor_rms_vs_baseline'),4)} | {fmt(g.get('max_altitude_loss_m'))} | {fmt(g.get('max_tilt_deg'),1)} | {fmt(g.get('recovery_from_change_s'),2)} | {gs} |")
    L+=['','Elimination (N0 − Nx)/(N0 − baseline), 95% bootstrap interval; total cost N0 − baseline.','','| unit:treatment | metric | total cost | ratio | 95% interval | remainder (capture) |','|---|---|---:|---:|---|---:|']
    for key,e in audit['elimination'].items():
        for k,r in e.items():
            ci=r.get('ratio_ci95');L.append(f"| {key} | {k} | {r['total_cost']:.4f} | {r['ratio']:.2f} | [{ci[0]:.2f}, {ci[1]:.2f}] | {r['remainder_attributed_to_capture']:.2f} |" if r['ratio'] is not None and ci else f"| {key} | {k} | {r['total_cost']:.4f} | — | — | — |")
    if audit.get('first_C_to_N_pooled'):
        f=audit['first_C_to_N_pooled'];L+=['',f"First C→N (always N0), pooled n={f['runs']}: motor step {fmt(f['motor_step_at_change'])}, altitude loss {fmt(f['max_altitude_loss_m'])} m, recovery {fmt(f['recovery_from_change_s'],2)} s."]
    (batch/'p4-table.md').write_text('\n'.join(L)+'\n')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--a',required=True);p.add_argument('--b',required=True)
    p.add_argument('--figures',default='docs/figures/p4');a=p.parse_args()
    out=ROOT/a.figures;out.mkdir(parents=True,exist_ok=True)
    ba,aa,ra=load(a.a);bb,ab,rb=load(a.b)
    fig_groups(aa,ra,'D2',out,'p4-fig1-01a-second-cn.png');fig_curves(aa,ra,['D2'],out,'p4-fig2-01a-motors.png')
    for i,u in enumerate(['M1','M2','M3']):fig_groups(ab,rb,u,out,f'p4-fig{3+i}-01b-{u}.png')
    fig_curves(ab,rb,['M1','M2','M3'],out,'p4-fig6-01b-motors.png');fig_ratios([aa,ab],out,'p4-fig7-elimination.png')
    table(aa,ba);table(ab,bb);print('figures',out)
if __name__=='__main__':main()

#!/usr/bin/env python3
"""P5 report figures and per-run tables from finished, audited batches (reads batch-audit.json and the stored per-run
p5-metrics.json / p4c-metrics.json; edits no run). Every panel draws runs of one batch; no group statistics (1-2 runs
per cell).

  p5_report.py --e1 data/<e1> --e2 data/<e2> --e3 data/<e3> --e4 data/<e4>   # figures -> docs/figures/p5, tables -> <batch>/p5-table.md
"""
import argparse,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
ROOT=Path(__file__).resolve().parents[1]
INK='#0b0b0b';MUTED='#52514e';GRID='#e4e3df'
DIR={'A0':'#2a78d6','A45':'#eb6834','Y45':'#3b9e5b'};DIRNAME={'A0':'+N (0°)','A45':'north-east (45°)','Y45':'+N, yaw +45°'}
TRT={'T1':'#eb6834','T1a1':'#c9a100','T1a3':'#8a3ffc','T0':'#3d3d3d'};TRTNAME={'T0':'T0 zero-velocity capture','T1':'T1 2 m/s²','T1a1':'T1 1 m/s²','T1a3':'T1 3 m/s²'}
plt.rcParams.update({'font.size':9,'axes.edgecolor':MUTED,'axes.labelcolor':INK,'xtick.color':MUTED,'ytick.color':MUTED,
    'axes.grid':True,'grid.color':GRID,'grid.linewidth':.6,'axes.spines.top':False,'axes.spines.right':False,'lines.linewidth':1.5,'font.family':'DejaVu Sans'})
f=lambda v,d=3:'—' if v is None else (f'{v:.{d}f}' if isinstance(v,(int,float)) else str(v))

def load(batch):
    if not batch:return None,None,[]
    batch=(ROOT/batch).resolve();audit=json.loads((batch/'batch-audit.json').read_text())
    res={r['id']:r for r in json.loads((batch/'results.json').read_text())['runs']}
    runs=[]
    for r in audit['runs']:
        d=ROOT/res[r['id']]['directory'];x={**r,'p5':json.loads((d/'p5-metrics.json').read_text())}
        if (d/'p4c-metrics.json').exists():x['c']=json.loads((d/'p4c-metrics.json').read_text())
        runs.append(x)
    return batch,audit,runs

def mark(ax,x,y,color,fail,**k):
    ax.scatter([x],[y],s=40 if fail else 30,color=color,marker='x' if fail else 'o',edgecolor=None if fail else 'white',linewidth=1.6 if fail else 1,zorder=3,**k)

def fig_e1(audit,runs,out):
    cells=[('V1.0','T0'),('V2.0','T1'),('V3.0','T1')]
    specs=[('max_tilt_deg','max tilt [°]'),('max_altitude_loss_m','max altitude loss [m]'),('motor_step_at_change','motor step at C→N'),('vclip','velocity-error clipping [s]'),('pclip','position-error clipping [s]')]
    fig,axes=plt.subplots(1,5,figsize=(17,3.9))
    for ax,(k,title) in zip(axes,specs):
        for x,(lvl,t) in enumerate(cells):
            for dx,d in [(-.22,'A0'),(0.,'A45'),(.22,'Y45')]:
                g=[r for r in runs if r['condition']==f'{lvl}-{d}' and r['treatment']==t]
                for i,r in enumerate(g):
                    m=r['metrics'];c=m.get('clipping') or {}
                    v={'vclip':(c.get('velocity') or {}).get('duration_s'),'pclip':(c.get('position') or {}).get('duration_s')}.get(k,m.get(k))
                    if v is not None:mark(ax,x+dx+(i-.5*(len(g)-1))*.07,v,DIR[d],r['flight_failure'])
        if k=='max_tilt_deg':ax.axhline(45,color=MUTED,lw=1,ls='--')
        ax.set_xticks(range(len(cells)));ax.set_xticklabels([f'{l[1:]} m/s {t}' for l,t in cells]);ax.set_title(title,color=INK,fontsize=9);ax.set_ylim(bottom=0)
    fig.legend([Line2D([],[],marker='o',ls='',color=DIR[d]) for d in DIR]+[Line2D([],[],marker='x',ls='',color=MUTED)],[DIRNAME[d] for d in DIR]+['flight failure'],loc='lower center',ncol=4,frameon=False)
    fig.suptitle(f'P5 E1: C→N during the classic cruise by flight direction (N2 memory; heading 96° for A0/A45) — {audit["batch"]}',color=INK)
    fig.tight_layout(rect=(0,.08,1,1));fig.savefig(out/'p5-fig1-e1-direction.png',dpi=130);plt.close(fig)

def fig_e2(audit,runs,out,batch=None):
    sup=json.loads((batch/'open-gap-supplement.json').read_text())['runs'] if batch and (batch/'open-gap-supplement.json').exists() else {}
    fig,axes=plt.subplots(1,4,figsize=(17,4))
    Ds=np.linspace(0,1.6,100);axes[0].plot(Ds,.5*2*Ds**2,color=MUTED,ls='--',lw=1);axes[0].text(1.25,.5*2*1.25**2+.05,'½·a·D² (a = 2)',color=MUTED,fontsize=8,ha='right')
    for r in runs:
        cond,t=r['condition'],r['treatment'];D=float(cond.split('-')[0][1:]);d=cond.split('-')[1];g=(r['metrics'].get('gaps') or [None])[0] or {}
        col=TRT[t] if t!='T1' else DIR[d];fail=r['flight_failure'];mk='s' if d=='A45' else 'o'
        if g.get('jump_along_axis_m') is not None:
            axes[0].scatter([D],[g['jump_along_axis_m']],s=34,color=col,marker='x' if fail else mk,zorder=3)
            axes[0].scatter([D+.03],[g['prediction_m']],s=30,facecolor='none',edgecolor=col,marker=mk,zorder=3)
        w=g.get('window') or {}
        og=sup.get(r['id']) or {}
        if not g and og.get('open_gap'):w={'max_tilt_deg':og.get('max_tilt_deg_until_raptor_end'),'max_altitude_loss_m':og.get('max_altitude_loss_m_until_raptor_end')}
        for ax,v in [(axes[1],w.get('max_tilt_deg') if w else r['metrics'].get('max_tilt_deg')),(axes[2],w.get('max_altitude_loss_m') if w else r['metrics'].get('max_altitude_loss_m')),(axes[3],g.get('catch_up_s'))]:
            if v is not None:ax.scatter([D+(.03 if d=='A45' else 0)],[v],s=34,color=col,marker='x' if fail else mk,zorder=3)
    axes[1].axhline(45,color=MUTED,lw=1,ls='--')
    for ax,t in zip(axes,['RAPTOR target jump at resume [m]\n(filled: measured, open: exact prediction)','max tilt (gap → 3 s after resume) [°]','max altitude loss [m]','catch-up after resume [s]']):
        ax.set_title(t,color=INK,fontsize=9);ax.set_xlabel('interruption D [s]');ax.set_ylim(bottom=0)
    h=[Line2D([],[],marker='o',ls='',color=DIR['A0']),Line2D([],[],marker='s',ls='',color=DIR['A45'])]+[Line2D([],[],marker='o',ls='',color=TRT[t]) for t in ['T1a1','T1a3','T0']]+[Line2D([],[],marker='x',ls='',color=MUTED)]
    fig.legend(h,['T1 2 m/s², +N','T1 2 m/s², north-east','T1 1 m/s² (+N)','T1 3 m/s² (+N)','T0 (circle +N, square NE; open gap, to the abort)','flight failure'],loc='lower center',ncol=6,frameon=False)
    fig.suptitle(f'P5 E2: single external-setpoint interruption at 2.0 m/s — {audit["batch"]}',color=INK)
    fig.tight_layout(rect=(0,.08,1,1));fig.savefig(out/'p5-fig2-e2-gap.png',dpi=130);plt.close(fig)

def curve_panel(axes,r,col,ls='-'):
    c=r['p5'].get('curves')
    if not c:return
    axes[0].plot(c['t_s'],c['target_minus_trajectory_m'],color=col,lw=1.1,ls=ls);axes[1].plot(c['t_s'],c['vehicle_lag_m'],color=col,lw=1.1,ls=ls)
    axes[2].plot(c['tilt_t_s'],c['tilt_deg'],color=col,lw=1.1,ls=ls)
    for a,b in c['gap_intervals_s']:
        for ax in axes:ax.axvspan(a,b,color=GRID,alpha=.5,lw=0)

def fig_e2_curves(audit,runs,out):
    Ds=sorted({float(r['condition'].split('-')[0][1:]) for r in runs})
    fig,axes=plt.subplots(3,len(Ds),figsize=(4*len(Ds),7.5),sharex=True,squeeze=False)
    for j,D in enumerate(Ds):
        for r in [r for r in runs if float(r['condition'].split('-')[0][1:])==D]:
            t=r['treatment'];d=r['condition'].split('-')[1];col=TRT[t] if t!='T1' else DIR[d]
            curve_panel(axes[:,j],r,col,':' if r['flight_failure'] else '-')
        axes[0,j].set_title(f'D = {D} s',color=INK);axes[2,j].axhline(45,color=MUTED,lw=.9,ls='--');axes[2,j].set_xlabel('time from last setpoint before the gap [s]');axes[0,j].set_xlim(-.5,4.)
    axes[0,0].set_ylabel('RAPTOR target − trajectory\nalong the line [m]');axes[1,0].set_ylabel('vehicle lag behind\ntrajectory point [m]');axes[2,0].set_ylabel('tilt [°]')
    fig.legend([Line2D([],[],color=DIR['A0']),Line2D([],[],color=DIR['A45'])]+[Line2D([],[],color=TRT[t]) for t in ['T1a1','T1a3','T0']]+[Line2D([],[],color=MUTED,ls=':')],
               ['T1 2 m/s² +N','T1 2 m/s² NE','T1 1 m/s²','T1 3 m/s²','T0','dotted: flight failure (to the abort); grey band: setpoint gap'],loc='lower center',ncol=6,frameon=False)
    fig.suptitle(f'P5 E2: target, lag and tilt around the interruption — {audit["batch"]}',color=INK)
    fig.tight_layout(rect=(0,.05,1,1));fig.savefig(out/'p5-fig3-e2-curves.png',dpi=130);plt.close(fig)

def fig_e3(audit,runs,out):
    fig,axes=plt.subplots(1,3,figsize=(15,4))
    for r in runs:
        t=r['treatment'];d=r['condition'].split('-')[1];col=TRT['T0'] if t=='T0' else DIR[d];ls='-' if t!='T0' else '--'
        gs=r['metrics'].get('gaps') or [];k=np.arange(1,len(gs)+1)
        if not len(gs):continue
        axes[0].plot(k,[(g.get('cycle_end') or {}).get('altitude_change_since_first_gap_m') for g in gs],color=col,ls=ls,marker='x' if r['flight_failure'] else 'o',ms=4)
        axes[1].plot(k,[(g.get('cycle_end') or {}).get('along_track_lag_m') for g in gs],color=col,ls=ls,marker='x' if r['flight_failure'] else 'o',ms=4)
        axes[2].plot(k,[(g.get('window') or {}).get('max_tilt_deg') for g in gs],color=col,ls=ls,marker='x' if r['flight_failure'] else 'o',ms=4)
    for ax,t in zip(axes,['altitude change since the first gap at cycle end [m]','along-track lag behind the trajectory at cycle end [m]','max tilt in the cycle [°]']):
        ax.set_title(t,color=INK,fontsize=9);ax.set_xlabel('cycle (0.5 s gap + 0.3 s link)')
    axes[2].axhline(45,color=MUTED,lw=1,ls='--')
    fig.legend([Line2D([],[],color=DIR['A0']),Line2D([],[],color=DIR['A45']),Line2D([],[],color=TRT['T0'],ls='--')],['T1 2 m/s² +N','T1 2 m/s² north-east','T0 +N'],loc='lower center',ncol=3,frameon=False)
    fig.suptitle(f'P5 E3: six interruptions at 2.0 m/s, state at every cycle end — {audit["batch"]}',color=INK)
    fig.tight_layout(rect=(0,.07,1,1));fig.savefig(out/'p5-fig4-e3-cycles.png',dpi=130);plt.close(fig)
    fig,axes=plt.subplots(3,1,figsize=(11,7),sharex=True)
    for r in runs:
        t=r['treatment'];d=r['condition'].split('-')[1];curve_panel(axes,r,TRT['T0'] if t=='T0' else DIR[d],':' if r['flight_failure'] else '-')
    axes[0].set_ylabel('target − trajectory [m]');axes[1].set_ylabel('vehicle lag [m]');axes[2].set_ylabel('tilt [°]');axes[2].axhline(45,color=MUTED,lw=.9,ls='--');axes[2].set_xlabel('time from the first gap [s]')
    fig.suptitle(f'P5 E3: curves, every run (grey: setpoint gaps) — {audit["batch"]}',color=INK)
    fig.tight_layout();fig.savefig(out/'p5-fig5-e3-curves.png',dpi=130);plt.close(fig)

def table_e1(audit,runs,batch):
    L=['# P5 E1 per-run table','',f'Batch `{audit["batch"]}`; audit passed: {audit["passed"]}.','',
       '| run | target | speed m/s | dir ° | rel. target yaw ° | flight | tilt ° | alt loss m | motor step | sat s | pos clip s (x/y) | vel clip s (x/y) | vel err retained min | settle s |','|---|---|---|---|---|---|---|---|---|---|---|---|---|---|']
    for r in runs:
        m=r['metrics'];c=m.get('clipping') or {};dr=m.get('direction') or {};te=m.get('true_error') or {}
        pc=(c.get('position') or {});vc=(c.get('velocity') or {})
        L.append(f"| {r['id']} | {r['treatment']} | {f(dr.get('speed_m_s'),2)} | {f(dr.get('realized_deg'),1)} | {f(dr.get('relative_to_target_yaw_deg'),1)} | {'FAILURE' if r['flight_failure'] else 'ok'} | {f(m.get('max_tilt_deg'),1)} | {f(m.get('max_altitude_loss_m'))} | {f(m.get('motor_step_at_change'))} | {f(m.get('motor_saturation_any_s'))} | {f(pc.get('duration_s'),2)} ({'/'.join(f(x,2) for x in (pc.get('per_axis_duration_s') or [])[:2])}) | {f(vc.get('duration_s'),2)} ({'/'.join(f(x,2) for x in (vc.get('per_axis_duration_s') or [])[:2])}) | {f((te.get('velocity') or {}).get('min_retained_ratio'),2)} | {f(m.get('settle_time_s'),2)} |")
    (batch/'p5-table.md').write_text('\n'.join(L)+'\n')

def table_gap(audit,runs,batch,title):
    L=[f'# P5 {title} per-run table','',f'Batch `{audit["batch"]}`; audit passed: {audit["passed"]}.','',
       '| run | flight | gap | silence s | capture after s | captured speed m/s | jump m | ½aD² m | prediction m | Δv m/s | catch-up s | tilt ° | alt loss m | pos/vel clip after resume s | cycle-end lag m | cycle-end Δalt m |','|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|']
    for r in runs:
        for i,g in enumerate(r['metrics'].get('gaps') or []):
            w=g.get('window') or {};ce=g.get('cycle_end') or {};ca=g.get('clipping_after_resume') or {}
            L.append(f"| {r['id']} | {'FAILURE' if r['flight_failure'] else 'ok'} | {i+1} | {f(g.get('silence_s'))} | {f(g.get('capture_after_last_reception_s'))} | {f(g.get('captured_speed_m_s'),2)} | {f(g.get('jump_along_axis_m'))} | {f(g.get('estimate_half_a_D2_m'))} | {f(g.get('prediction_m'))} | {f(g.get('velocity_jump_along_axis_m_s'),2)} | {f(g.get('catch_up_s'),2)} | {f(w.get('max_tilt_deg'),1)} | {f(w.get('max_altitude_loss_m'))} | {f((ca.get('position') or {}).get('duration_s'),2)}/{f((ca.get('velocity') or {}).get('duration_s'),2)} | {f(ce.get('along_track_lag_m'))} | {f(ce.get('altitude_change_since_first_gap_m'))} |")
        m=r['metrics'];L.append(f"| {r['id']} whole | | | | | | | | | | | {f(m.get('max_tilt_deg'),1)} | {f(m.get('max_altitude_loss_m'))} | | settle after rest {f(m.get('settle_after_rest_s'),2)} s | sat {f(m.get('motor_saturation_any_s'))} s |")
    (batch/'p5-table.md').write_text('\n'.join(L)+'\n')

def table_e4(audit,runs,batch):
    L=['# P5 E4 per-run table','',f'Batch `{audit["batch"]}`; audit passed: {audit["passed"]}.','','| run | speed m/s | flight | tilt ° | alt loss m | motor step | recovery s |','|---|---|---|---|---|---|---|']
    for r in runs:
        m=r['metrics'];L.append(f"| {r['id']} | {f((m.get('direction') or {}).get('speed_m_s'),2)} | {'FAILURE' if r['flight_failure'] else 'ok'} | {f(m.get('max_tilt_deg'),1)} | {f(m.get('max_altitude_loss_m'))} | {f(m.get('motor_step_at_change'))} | {f(m.get('joint_recovery_from_change_s'),2)} |")
    (batch/'p5-table.md').write_text('\n'.join(L)+'\n')

def main():
    p=argparse.ArgumentParser(description=__doc__);[p.add_argument('--'+k) for k in ['e1','e2','e3','e4']];a=p.parse_args()
    out=ROOT/'docs/figures/p5';out.mkdir(parents=True,exist_ok=True)
    b,au,r=load(a.e1)
    if b:fig_e1(au,r,out);table_e1(au,r,b)
    b,au,r=load(a.e2)
    if b:fig_e2(au,r,out,b);fig_e2_curves(au,r,out);table_gap(au,r,b,'E2')
    b,au,r=load(a.e3)
    if b:fig_e3(au,r,out);table_gap(au,r,b,'E3')
    b,au,r=load(a.e4)
    if b:table_e4(au,r,b)
    print('figures ->',out)
if __name__=='__main__':main()

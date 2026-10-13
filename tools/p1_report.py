#!/usr/bin/env python3
"""P1 report figures and summary table from a finished, audited P1 batch (reads p1-metrics.json; edits no run)."""
import argparse,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
COND={'S1':'#2a78d6','S2':'#eb6834','S3':'#1baf7a'}  # categorical slots 1-3 (validated all-pairs)
INK='#0b0b0b';MUTED='#52514e';GRID='#e4e3df';BASE='#8a8984'
LABEL={'p1_c_to_n':'C→N (classic → RAPTOR)','p1_n_to_c':'N→C (RAPTOR → classic)',
       'p1_baseline_raptor':'RAPTOR-only brake (baseline for C→N)','p1_baseline_classic':'classic-only brake (baseline for N→C)'}
BASELINE={'p1_c_to_n':'p1_baseline_raptor','p1_n_to_c':'p1_baseline_classic'}
plt.rcParams.update({'font.size':9,'axes.edgecolor':MUTED,'axes.labelcolor':INK,'xtick.color':MUTED,'ytick.color':MUTED,
    'axes.grid':True,'grid.color':GRID,'grid.linewidth':.6,'axes.spines.top':False,'axes.spines.right':False,'lines.linewidth':1.6,
    'font.family':'DejaVu Sans'})

def load(batch):
    audit=json.loads((batch/'batch-audit.json').read_text());runs=[]
    for r in audit['runs']:
        run=ROOT/json.loads((batch/'results.json').read_text())['runs'][[x['id'] for x in json.loads((batch/'results.json').read_text())['runs']].index(r['id'])]['directory']
        runs.append({**r,'m':json.loads((run/'p1-metrics.json').read_text())})
    return audit,runs

def pick(runs,kind,cond,rep=1):
    return next((r for r in runs if r['kind']==kind and r['condition']==cond and r['id'].endswith(f'-{rep}')),None)

def curves(ax3,r,color,ls='-',label=None):
    c=r['m']['curves'];t=np.array(c['t_s']);p=np.array(c['position_ned_m']);v=np.array(c['velocity_ned_m_s'])
    p0=np.array(r['m']['state_at_change']['position_ned_m'])
    ax3[0].plot(t,p[:,0]-p0[0],color=color,ls=ls,label=label);ax3[1].plot(t,v[:,0],color=color,ls=ls);ax3[2].plot(t,-p[:,2],color=color,ls=ls)

def fig_curves(runs,out):
    fig,axes=plt.subplots(2,3,figsize=(12,6.2),sharex=True)
    for row,kind in enumerate(['p1_c_to_n','p1_n_to_c']):
        ax=axes[row]
        for cond,color in COND.items():
            r=pick(runs,kind,cond)
            if r:curves(ax,r,color,label=f'{cond} handover')
            b=pick(runs,BASELINE[kind],cond)
            if b and cond=='S3':curves(ax,b,BASE,'--',label='S3 same-controller baseline')
        ax[0].set_ylabel(LABEL[kind]+'\nN offset from change [m]');ax[1].set_ylabel('North velocity [m/s]');ax[2].set_ylabel('Altitude [m]')
        for a in ax:a.axvline(0,color=MUTED,lw=.8,ls=':')
    for a in axes[1]:a.set_xlabel('Time from actual change [s]')
    axes[0,0].legend(frameon=False,fontsize=8);fig.suptitle('Typical runs (repetition 1): position, velocity, altitude around the subject event',color=INK)
    fig.tight_layout();fig.savefig(out/'p1-fig1-curves.png',dpi=130);plt.close(fig)

def fig_motors(runs,out):
    fig,axes=plt.subplots(2,3,figsize=(12,5.6),sharex=True,sharey=True)
    for row,kind in enumerate(['p1_c_to_n','p1_n_to_c']):
        for col,cond in enumerate(COND):
            ax=axes[row,col];r=pick(runs,kind,cond)
            if not r:continue
            c=r['m']['curves'];t=np.array(c['motor_t_s']);m=np.array(c['motor'])
            for i,color in enumerate(['#2a78d6','#eb6834','#1baf7a','#6250d6']):ax.plot(t,m[:,i],color=color,lw=1.1,label=f'motor {i}')
            ax.axvline(0,color=MUTED,lw=.8,ls=':');ax.set_title(f'{LABEL[kind].split(" (")[0]}  {cond}',color=INK,fontsize=9)
            step=r['m']['auxiliary']['motor']['step_at_change'];ax.text(.02,.04,f'step at change {step:.3f}',transform=ax.transAxes,color=MUTED,fontsize=8)
    for a in axes[:,0]:a.set_ylabel('actuator_motors [0,1]')
    for a in axes[1]:a.set_xlabel('Time from actual owner change [s]')
    axes[0,0].legend(frameon=False,fontsize=7,ncol=2);fig.suptitle('Motor commands across the switch (repetition 1)',color=INK)
    fig.tight_layout();fig.savefig(out/'p1-fig2-motors.png',dpi=130);plt.close(fig)

def dots(ax,runs,kinds,key,ylabel):
    xt=[];xl=[]
    for k,kind in enumerate(kinds):
        for c,(cond,color) in enumerate(COND.items()):
            x=k*4+c;xt.append(x);xl.append(cond)
            vals=[key(r) for r in runs if r['kind']==kind and r['condition']==cond]
            vals=[v for v in vals if v is not None]
            ax.scatter(x+np.linspace(-.15,.15,len(vals)) if len(vals)>1 else [x]*len(vals),vals,s=26,color=color,edgecolor='white',linewidth=1,zorder=3)
        ax.text(k*4+1,1.02,LABEL[kind].split(' (')[0],transform=ax.get_xaxis_transform(),ha='center',color=INK,fontsize=8)
    ax.set_xticks(xt);ax.set_xticklabels(xl);ax.set_ylabel(ylabel);ax.set_ylim(bottom=0)

KINDS=['p1_c_to_n','p1_baseline_raptor','p1_n_to_c','p1_baseline_classic']
def fig_recovery(runs,out):
    fig,axes=plt.subplots(1,2,figsize=(12,4.2))
    dots(axes[0],runs,KINDS,lambda r:r['m']['primary']['joint_recovery']['from_change_s'],'Joint recovery from actual change [s]')
    dots(axes[1],runs,KINDS,lambda r:r['m']['primary']['joint_recovery']['from_trigger_s'],'Joint recovery from trigger [s]')
    fig.suptitle('Joint recovery time by condition (each dot one run; incoming controller next to its own baseline)',color=INK,y=1.02)
    fig.tight_layout();fig.savefig(out/'p1-fig3-recovery.png',dpi=130,bbox_inches='tight');plt.close(fig)

def fig_deviation(runs,out):
    fig,axes=plt.subplots(1,2,figsize=(12,4.2))
    dots(axes[0],runs,KINDS,lambda r:r['m']['auxiliary']['max_position_error_to_active_target_m'],'Max position error to active target [m]')
    dots(axes[1],runs,KINDS,lambda r:r['m']['primary']['max_altitude_loss_m'],'Max altitude loss [m]')
    fig.suptitle('Maximum position deviation and altitude loss by direction and condition',color=INK,y=1.02)
    fig.tight_layout();fig.savefig(out/'p1-fig4-deviation-altitude.png',dpi=130,bbox_inches='tight');plt.close(fig)

def table(runs):
    lines=['|运行|工况|交接时速度 m/s|最大高度损失 m|恢复(持权变化) s|恢复(触发) s|窗口约束|最大倾角 °|最大位置偏差 m|电机阶跃|饱和 s|请求→持权 ms|接管参考 (NED m)|',
           '|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---|']
    for r in runs:
        m=r['m'];pr=m['primary'];jr=pr['joint_recovery'];au=m['auxiliary'];ref=m['reference_at_takeover']
        viol=[k for k,v in pr['window_constraints'].items() if not v['satisfied']]
        f=lambda v,d=2:'—' if v is None else f'{v:.{d}f}'
        refp=ref.get('position_ned_m');refv=ref.get('velocity_ned_m_s')
        reftxt=(f"{ref['classification']}: [{', '.join(f'{x:.2f}' for x in refp)}]" if refp else ref.get('classification',''))+(f", v={refv[0]:.2f}" if refv else '')
        lines.append(f"|{r['id']}|{r['condition']}|{f(m['state_at_change']['horizontal_speed_m_s'])}|{f(pr['max_altitude_loss_m'],3)}|{f(jr['from_change_s'])}|{f(jr['from_trigger_s'])}|"
            f"{'满足' if not viol else '超出: '+', '.join(viol)}|{f(pr['window_constraints']['tilt_hover_deg']['max'],1)}|{f(au['max_position_error_to_active_target_m'],3)}|"
            f"{f(au['motor']['step_at_change'],3)}|{f(au['motor']['saturation_any_s'],3)}|{f(m['delays_ms']['trigger_to_change'],0)}|{reftxt}|")
    return '\n'.join(lines)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('batch',type=Path);p.add_argument('--figures',type=Path,default=ROOT/'docs/figures/p1');a=p.parse_args()
    a.figures.mkdir(parents=True,exist_ok=True);audit,runs=load(a.batch.resolve())
    fig_curves(runs,a.figures);fig_motors(runs,a.figures);fig_recovery(runs,a.figures);fig_deviation(runs,a.figures)
    (a.batch/'p1-table.md').write_text(table(runs)+'\n');print(table(runs))

#!/usr/bin/env python3
"""Publication figures from all assigned valid cases; no fitting or sample selection."""
import json,sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p12c.features import load
BASE=R/'data/p12-cont-20261026-delivery-v2';F=R/'data/p12-cont-20261026-formal';OUT=R/'docs/figures/p12-cont'
C={'NORMAL0':'#3973ac','NORMAL1':'#739fc9','A':'#e6a23b','B':'#8e65b1','AB':'#d44b41','REPAIR':'#32966a'}
def main():
 OUT.mkdir(parents=True,exist_ok=False);cases=json.load(open(BASE/'cases.json'));plan=json.load(open(R/'config/p12-cont.json'));plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False})
 fig,axes=plt.subplots(3,1,figsize=(12,8),sharex=True)
 for i,row in enumerate(plan['rows'],1):
  n=row['id'];c=cases.get(n)
  if not c:
   for ax in axes:ax.axvline(i,color='0.7',lw=.7,ls=':')
   continue
  values=[c['measurement']['whole']['max_tilt_deg'],c['measurement']['whole']['max_altitude_loss_m'],c['absolute_world_height']['max_loss_from_task_start_m']]
  for ax,y in zip(axes,values):ax.scatter(i,y,color=C[row['branch']],marker='^' if c['censored'] else 'o',s=28,zorder=3)
 for ax,label in zip(axes,['Observed tilt peak (deg)','Frozen LP height loss (m)','World loss from task start (m)']):
  ax.set_ylabel(label);ax.grid(alpha=.2)
  for x in [12.5,24.5,36.5]:ax.axvline(x,color='0.5',lw=.7)
 axes[0].axhline(45,color='0.3',ls='--',lw=.8);axes[1].axhline(1,color='0.3',ls='--',lw=.8)
 for b,c in C.items():axes[0].scatter([],[],color=c,label=b)
 axes[0].legend(ncol=6,loc='upper left',fontsize=8);axes[-1].set_xlabel('Frozen ordinal: invalid11 / rejected27; ordinals28-48 unstarted (dotted)')
 axes[0].set_title('P12 continuation: all assigned results; complete peaks vs censored lower bounds')
 fig.tight_layout();fig.savefig(OUT/'all-assigned-outcomes.png',dpi=160);plt.close(fig)
 # Fixed boundary block2, both assigned gates and every branch, full absolute profile axis.
 fig,axes=plt.subplots(2,2,figsize=(12,7),sharex=True)
 for col,ph in enumerate([1,2]):
  doc=None
  for branch in C:
   n=f'b2-ph{ph}-{branch}'
   if n not in cases:continue
   a=F/n/'analysis';d=load(F/n/'run',a);doc=json.load(open(a/'packed/prediction-input.json'));first=doc['plan']['common_first_gap_profile_s'];end=doc['plan']['nominal_horizon_profile_s'];m=(d['t']>=first-.5)&(d['t']<=end)
   tilt=np.degrees(np.arccos(np.clip(1-2*(d['attitude'][:,1]**2+d['attitude'][:,2]**2),-1,1)))
   axes[0,col].plot(d['t'][m],tilt[m],color=C[branch],lw=1,label=branch);axes[1,col].plot(d['t'][m],-d['truth_pv'][m,2],color=C[branch],lw=1)
  if doc:
   ws=doc['plan']['full_source_windows_profile_s']
   for ax in axes[:,col]:
    for k in [0,1]:ax.axvspan(*ws[k],color='0.5',alpha=.12)
    ax.grid(alpha=.2)
  axes[0,col].set_title(f'F4 boundary block: assigned gate{ph} (one start per event arm)');axes[0,col].axhline(45,color='0.3',ls='--',lw=.8)
 axes[0,0].set_ylabel('Tilt (deg)');axes[1,0].set_ylabel('Independent world height (m)');axes[1,0].set_xlabel('Common absolute task profile time (s)');axes[1,1].set_xlabel('Common absolute task profile time (s)');axes[0,0].legend(ncol=3,fontsize=8)
 fig.suptitle('Complete event/resume/recovery segment; actual initial states differ; shaded=A/B stop windows',fontsize=10);fig.tight_layout();fig.savefig(OUT/'boundary-full-segment.png',dpi=160);plt.close(fig)
 # Prediction errors and three-valued label denominators use all cases, separately.
 models=['M2','M3','M4','single_clock','no_history','no_filter','uncorrelated_capture'];err={m:[] for m in models};labels={m:{k:0 for k in ['AGREEMENT','FALSE_ALARM','DANGER_MISS','UNKNOWN']} for m in models}
 for n in cases:
  score=json.load(open(F/n/'analysis/score/score.json'))['models']
  for model in models:
   s=score[model]
   if s['peak_abs_error_deg'] is not None:err[model].append(s['peak_abs_error_deg'])
   label=s['task_risk_comparison'];key=label if label in labels[model] else 'UNKNOWN';labels[model][key]+=1
 fig,axes=plt.subplots(1,2,figsize=(12,4));x=np.arange(len(models))
 axes[0].bar(x,[np.mean(err[m]) if err[m] else np.nan for m in models],color='#3973ac');axes[0].set_ylabel('Complete peak MAE (deg)')
 for i,m in enumerate(models):axes[0].text(i,0,f'n={len(err[m])}',ha='center',va='bottom',fontsize=7)
 bottom=np.zeros(len(models))
 for key,color in [('AGREEMENT','#3973ac'),('FALSE_ALARM','#e6a23b'),('DANGER_MISS','#d44b41'),('UNKNOWN','#a0a0a0')]:
  v=np.array([labels[m][key] for m in models]);axes[1].bar(x,v,bottom=bottom,label=key,color=color);bottom+=v
 axes[1].set_ylabel('Frozen v2 task label comparisons');axes[1].legend(fontsize=7)
 for ax in axes:ax.set_xticks(x,models,rotation=40,ha='right');ax.grid(axis='y',alpha=.2)
 fig.suptitle('Same flights across models: not independent flight samples; classification and full-peak denominators differ',fontsize=10);fig.tight_layout();fig.savefig(OUT/'prediction-denominators.png',dpi=160);plt.close(fig)
 print('FIGURES',OUT)
if __name__=='__main__':main()

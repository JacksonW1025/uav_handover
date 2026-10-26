import sys,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
sys.path.insert(0,'tools')
from p11.models import tilt
from p11.analyze import at
root=Path('data/p11-20261025-formal');analysis=Path('data/p11-20261026-analysis');out=Path('docs/figures/p11');out.mkdir(parents=True,exist_ok=True)
plt.rcParams.update({'font.size':9,'axes.grid':True,'grid.alpha':.2,'savefig.dpi':150})
def save(fig,name):fig.tight_layout();fig.savefig(out/(name+'.png'));fig.savefig(out/(name+'.svg'));plt.close(fig)
def load(i):return dict(np.load(root/i/'packed/measurement.npz'))
def pred(i,k):
 p=root/i/'prediction'
 if not p.exists():p=analysis/i/'prediction'
 return np.load(p/(k+'.npz'))['trace']
# Detailed clock/target/network chain, all logged calls (no data decimation).
i='F1-r1-AB';d=load(i);doc=json.loads((root/i/'packed/prediction-input.json').read_text());t=d['profile_s'];a,b=doc['plan']['windows_profile_s'][0];sel=(t>a-.1)&(t<b+.5);fig,ax=plt.subplots(4,1,figsize=(9,8),sharex=True)
ax[0].plot(t[sel],d['velocity'][sel,0],label='read vx');ax[0].plot(t[sel],d['target_v'][sel,0],label='network target vx');ax[0].set_ylabel('NED vx (m/s)');ax[0].legend()
ax[1].step(t[sel],(d['sample_us'][sel]-d['lp_sample'][sel])/1000,where='post',label='LP sample age');ax[1].step(t[sel],d['stale'][sel]*12,where='post',label='stale x12');ax[1].set_ylabel('age (ms)');ax[1].legend()
ax[2].plot(t[sel],d['action'][sel]);ax[2].set_ylabel('executor action')
ax[3].plot(t[sel],np.linalg.norm(d['h_after'][sel],axis=1));ax[3].set_ylabel('GRU L2');ax[3].set_xlabel('absolute source profile time (s)')
for q in ax:q.axvspan(a,b,color='gray',alpha=.15)
fig.suptitle('Actual event / sample-hold / command / committed-memory chain');save(fig,'clock-and-event')
# Heldout own-state forecasts: height-only failure and hard censored failure.
fig,axs=plt.subplots(2,2,figsize=(12,7),sharex='col')
for col,i in enumerate(['F4-r1-AB','ANCHOR-D-09-r1-ORIGINAL']):
 d=load(i);t=d['profile_s'];m=json.loads((root/i/'measured/measurement.json').read_text());start=json.loads((root/i/'packed/prediction-input.json').read_text())['plan']['common_first_gap_profile_s'];sel=t>=start
 axs[0,col].plot(t[sel],[tilt(q) for q in d['attitude'][sel]],color='black',lw=1.4,label='observed');axs[1,col].plot(t[sel],d['position'][sel,2]-np.interp(start,t,d['position'][:,2]),color='black',label='observed z change')
 for k in ['M0','M1','M2']:
  tr=pred(i,k);s=tr[:,0]>=start;color={'M0':'C0','M1':'C1','M2':'C2'}[k];axs[0,col].plot(tr[s,0],tr[s,7],label=k,color=color)
  if k!='M0':axs[1,col].plot(tr[s,0],tr[s,3]-np.interp(start,tr[:,0],tr[:,3]),label=k,color=color)
 axs[0,col].axhline(45,color='red',ls='--');axs[1,col].axhline(1,color='red',ls='--');axs[0,col].set_title(i+(' (right censored)' if m['censored'] else ' (full)'))
 for ax in axs[:,col]:ax.axvline(t[-1],color='black',ls=':',label='observed end');ax.axvspan(t[-1],doc['plan']['horizon_profile_s'],color='gray',alpha=.12,label='unobserved continuation');ax.legend(fontsize=7);ax.set_xlim(start,None)
 axs[1,col].set_xlabel('absolute source profile time (s)')
axs[0,0].set_ylabel('tilt (deg)');axs[1,0].set_ylabel('downward z change (m)');save(fig,'heldout-causal-forecasts')
# Explicit nonadditivity on a fully prestate-matched cluster.
ds={b:load('F2-r1-'+b) for b in ['NORMAL','A','B','AB']};st=json.loads((root/'F2-r1-AB/packed/prediction-input.json').read_text())['plan']['common_first_gap_profile_s'];end=min(x['profile_s'][-1] for x in ds.values());grid=np.arange(st,end,.004);fig,ax=plt.subplots(2,1,figsize=(9,6),sharex=True)
for field,label,q in [('position','p (m)',ax[0]),('velocity','v (m/s)',ax[1])]:
 delta={b:at(ds[b],grid,field)-at(ds['NORMAL'],grid,field) for b in ['A','B','AB']}
 for b in delta:q.plot(grid,np.linalg.norm(delta[b],axis=1),label=b+' - normal')
 non=delta['AB']-delta['A']-delta['B'];q.plot(grid,np.linalg.norm(non,axis=1),color='black',ls='--',label='AB - A - B + normal');q.set_ylabel(label);q.legend()
ax[1].set_xlabel('absolute source profile time (s)');fig.suptitle('F2-r1: nonadditivity diagnostic; not isolated memory causality');save(fig,'nonadditivity')
# Frozen denominators and all outcome categories, no averaging censored peaks.
r=json.loads((analysis/'analysis.json').read_text());fig,ax=plt.subplots(1,2,figsize=(10,4))
models=['M0','M1','M2'];v=r['model_summary']['heldout'];x=np.arange(3);ax[0].bar(x-.16,[v[k]['danger_misses'] for k in models],.32,label='tilt danger miss');ax[0].bar(x+.16,[v[k]['false_alarms'] for k in models],.32,label='tilt false alarm');ax[0].set_xticks(x,models);ax[0].set_ylabel('cases /31 heldout');ax[0].legend()
ax[1].bar(x,[v[k]['complete_peak_error_mean_deg'] for k in models]);ax[1].set_xticks(x,[k+' n='+str(v[k]['complete_peak_error_n']) for k in models]);ax[1].set_ylabel('complete peak MAE (deg)');ax[1].set_title('Unequal complete-forecast denominators shown')
fig.suptitle('Grouped heldout comparison; M0 height UNKNOWN; no hard-bound certificate');save(fig,'heldout-summary')
print('figures',len(list(out.glob('*.png'))))

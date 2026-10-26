from pathlib import Path
import json,sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
sys.path.insert(0,'tools')
from p12.execution import DTYPE
A=Path('data/p12-20261026-analysis');D=Path('data/p12-20261026-development');out=Path('docs/figures/p12');out.mkdir(parents=True,exist_ok=True)
names=['dev03-native','dev04-intermediate','dev05-native-repair','dev06-intermediate-repair']
fig,ax=plt.subplots(figsize=(8,3.6))
for row,name in enumerate(names):
 r=json.loads((A/(name+'-native/native-audit.json')).read_text());caps=[c for c in r['captures'] if not c['activation']]
 ax.scatter([(c['sample_us']-c['last_gru_sample_before'])/1000 for c in caps],[row]*len(caps),s=65,label=name)
ax.set(yticks=range(4),yticklabels=names,xticks=[4,8],xlabel='Capture sample - prior GRU commit sample (ms)',title='Achieved native phase: all nonactivation captures retained')
ax.grid(alpha=.2);fig.tight_layout()
for ext in ['png','svg']:fig.savefig(out/('achieved-phases.'+ext),dpi=160)
plt.close(fig)
fig,axes=plt.subplots(4,2,figsize=(10,9),sharex=True)
for row,name in enumerate(names):
 d=dict(np.load(A/(name+'-packed/measurement.npz')));pred=np.load(A/(name+'-predictions/M3.npz'))['trace']
 q=d['attitude'];angle=np.degrees(np.arccos(np.clip(1-2*(q[:,1]**2+q[:,2]**2),-1,1)))
 t=d['profile_s'];sel=t>=0
 axes[row,0].plot(t[sel],angle[sel],lw=1,label='observed');axes[row,0].plot(pred[:,0],pred[:,7],'--',lw=1,label='M3 autonomous')
 axes[row,0].set_ylabel(name+'\ntilt (deg)',fontsize=8);axes[row,0].axhline(45,color='r',ls=':',lw=.7)
 axes[row,1].plot(t[sel],-d['position'][sel,2],lw=1);axes[row,1].plot(pred[:,0],-pred[:,3],'--',lw=1);axes[row,1].set_ylabel('NED-derived altitude (m)')
 for ax in axes[row]:
  ax.axvspan(12.895,13.255,color='orange',alpha=.12);ax.axvspan(15.135,15.495,color='orange',alpha=.12);ax.grid(alpha=.2)
axes[0,0].legend(fontsize=8);axes[-1,0].set_xlabel('Shared absolute task profile time (s)');axes[-1,1].set_xlabel('Task profile time (s)')
fig.suptitle('Development evidence only: unmatched arms, no causal repair claim',fontsize=11);fig.tight_layout()
for ext in ['png','svg']:fig.savefig(out/('development-predictions.'+ext),dpi=160)
plt.close(fig)
name='dev03-native';sends=[json.loads(x) for x in (D/name/'run/p11-sends.jsonl').read_text().splitlines()];t0=next(s['stream_t0_monotonic_s'] for s in sends if s['stream_t0_monotonic_s'] is not None)
e=np.fromfile(D/name/'run/gz-motor/execution-p12-0.bin',DTYPE);t=e['end_ns']/1e9-t0;sel=(t>12.8)&(t<13.6)
fig,ax=plt.subplots(figsize=(8,3.4));ax.plot(t[sel],e['command'][sel],label='consumed command',lw=1);ax.plot(t[sel],e['filter_before'][sel],label='direct filter state',lw=1.2);ax.plot(t[sel],np.abs(e['scaled_joint'][sel]),'--',label='scaled actual joint',lw=1)
ax.set(xlabel='Absolute task profile time (s)',ylabel='rad/s',title='Distinct command, filter and actual joint interfaces (motor 0)');ax.grid(alpha=.2);ax.legend(fontsize=8);fig.tight_layout()
for ext in ['png','svg']:fig.savefig(out/('execution-interface.'+ext),dpi=160)
plt.close(fig)
print('3 figures, PNG+SVG')

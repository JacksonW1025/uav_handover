from pathlib import Path
import json,numpy as np,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parent;R=json.loads((P/'results.json').read_text())
plt.rcParams.update({'font.family':'DejaVu Sans','pdf.fonttype':42,'svg.fonttype':'none','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
f,axs=plt.subplots(3,1,figsize=(7.6,6.7),sharex=True)
for arm,c,label in [('C2','#24689B','Continue classical'),('N','#BD4939','Switch during motion'),('PRE','#34846B','Enter RAPTOR before motion')]:
 d=np.genfromtxt(P/(arm+'-trajectory.csv'),delimiter=',',names=True)
 for ax,key in zip(axs,['tilt_deg','descent_from_marker_m','vz']):ax.plot(d['marker_s'],d[key],color=c,label=label,lw=1.35)
for ax in axs:ax.set_xlim(-1,5);ax.grid(alpha=.17);ax.axvline(0,c='#888888',ls=':',lw=.9)
axs[0].axhline(35,c='#777777',ls='--',lw=.8,label='35 deg experiment budget');axs[0].axhline(45,c='#aaaaaa',ls='--',lw=.8,label='45 deg protection')
axs[0].set_ylabel('Tilt (deg)');axs[1].set_ylabel('Descent from marker (m)');axs[2].set_ylabel('Vertical velocity (m/s, down)');axs[2].set_xlabel('Time from motion-phase marker (s)')
axs[0].legend(frameon=False,fontsize=8,ncol=2)
f.tight_layout()
for ext in ['pdf','svg','png']:f.savefig(P/('three-arm-marker.'+ext),dpi=200)
